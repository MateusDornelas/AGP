"""Endpoint de reotimização — recebe um arranjo manual de VUCs (vindo
do drag-and-drop do front) e re-resolve TSP por VUC, devolvendo a
mesma estrutura que /api/optimize."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd

from core.config import (
    CUSTO_FIXO_VUC, CUSTO_KM, DEPOT_COORDS, MAX_KM_VUC, MAX_TIME_VUC_MIN,
    SERVICE_TIME_MIN, START_HOUR,
)
from core.racks import calcular_racks
from core.solver import solve_group_route
from core import osrm

# NOTA: Depends(require_token) removido — login em stand by.
# Para reativar, voltar: `from .auth import require_token` e adicionar
# `_token: str = Depends(require_token)` no parametro do endpoint.

router = APIRouter(prefix="/api", tags=["reoptimize"])


class ClienteEntrada(BaseModel):
    nome: str
    endereco: str
    lat: float
    lon: float
    pos: int = 0
    pb_ts: int = 0
    pecas_g: int = 0
    pecas_m: int = 0
    total: int


class VucEntrada(BaseModel):
    label: str
    clientes: list[ClienteEntrada]


class ReoptimizePayload(BaseModel):
    vucs: list[VucEntrada]


def _arrival_to_hhmm(arrival_min: float) -> str:
    total = int(arrival_min)
    hh = (total // 60) + START_HOUR
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"


@router.post("/reoptimize")
def reoptimize(payload: ReoptimizePayload):
    """Recebe um arranjo {vucs: [{label, clientes: [...]}, ...]} e
    re-resolve apenas o TSP de cada VUC (alocação fixa pelo usuário).
    Retorna o mesmo shape de /api/optimize.
    """
    osrm.reset()

    stats: dict = {}
    table: list[dict] = []
    vucs_out: list[dict] = []
    violacoes_janela: list[dict] = []
    violacoes_km: list[dict] = []

    for vuc_in in payload.vucs:
        if not vuc_in.clientes:
            continue

        # Reconstruí um df_subset no mesmo formato que solve_group_route espera
        rows = []
        for c in vuc_in.clientes:
            rows.append({
                "lat": c.lat,
                "lon": c.lon,
                "NOME": c.nome,
                "ENDEREÇO": c.endereco,
                "POS": c.pos,
                "PB_TS": c.pb_ts,
                "PEÇAS GRANDES": c.pecas_g,
                "PEÇAS PEQUENAS": c.pecas_m,
                "TOTAL": c.total,
            })
        df_vuc = pd.DataFrame(rows)

        res = solve_group_route(df_vuc)
        if not res:
            continue

        paradas = res["paradas"]
        total_p = int(sum(p["total"] for p in paradas))
        _, rg, rp = calcular_racks(total_p)
        km_real = round(res["total_km"], 2)
        final_label = vuc_in.label

        # Violações
        fim_descarga = (
            paradas[-1]["arrival_min"] + SERVICE_TIME_MIN if paradas else 0
        )
        if fim_descarga > MAX_TIME_VUC_MIN:
            violacoes_janela.append({
                "vuc": final_label,
                "paradas": len(paradas),
                "pecas": total_p,
                "termino": _arrival_to_hhmm(fim_descarga),
            })
        if km_real > MAX_KM_VUC:
            violacoes_km.append({
                "vuc": final_label,
                "paradas": len(paradas),
                "pecas": total_p,
                "km_real": km_real,
                "limite": MAX_KM_VUC,
            })

        stats[final_label] = {
            "km": km_real,
            "tempo_min": round(res["total_time_min"], 1),
            "tempo_label": (
                f"{int(res['total_time_min'] // 60)}h "
                f"{int(res['total_time_min'] % 60)}min"
            ),
            "pecas": total_p,
            "racks": f"{rg}G e {rp}P",
            "custo": round(CUSTO_FIXO_VUC + km_real * CUSTO_KM, 2),
            "clientes": [p["cliente"] for p in paradas],
        }

        for seq, parada in enumerate(paradas, 1):
            table.append({
                "rota_vuc": final_label,
                "seq": seq,
                "chegada": _arrival_to_hhmm(parada["arrival_min"]),
                "cliente": parada["cliente"],
                "pos": parada["pos"],
                "pb_ts": parada["pb_ts"],
                "grandes": parada["pecas_g"],
                "medias": parada["pecas_m"],
                "total": parada["total"],
                "endereco": parada["endereco"],
                "lat": parada["lat"],
                "lon": parada["lon"],
            })

        # Geometria real (seguindo ruas) via OSRM — open-route
        # (motorista termina no último cliente, sem voltar ao CD).
        coords_completas = (
            [DEPOT_COORDS] + [[p["lat"], p["lon"]] for p in paradas]
        )
        geometry = osrm.route_geometry(coords_completas)

        vucs_out.append({
            "label": final_label,
            "paradas": [
                {
                    "seq": i + 1,
                    "cliente": p["cliente"],
                    "lat": p["lat"],
                    "lon": p["lon"],
                    "endereco": p["endereco"],
                    "chegada": _arrival_to_hhmm(p["arrival_min"]),
                }
                for i, p in enumerate(paradas)
            ],
            "route_geometry": geometry,
        })

    if not vucs_out:
        raise HTTPException(400, "Nenhum VUC válido no payload.")

    return {
        "modo_efetivo": "Modo Criativo (manual)",
        "vucs": vucs_out,
        "stats": stats,
        "table": table,
        "violacoes_janela": violacoes_janela,
        "violacoes_km": violacoes_km,
        "enderecos_nao_localizados": [],
        "osrm_indisponivel": osrm.is_disabled(),
        "aviso_fallback": None,
    }
