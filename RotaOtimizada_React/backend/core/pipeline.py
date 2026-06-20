"""Pipeline completo: planilha → VUCs → rotas resolvidas → resposta JSON.

Modelo Padrão  → agrupa por ROTA + TSP per-VUC (clustering.py + solver.py)
Modo Criativo  → CVRP global do OR-Tools (vrp_solver.py)
                 alocação + roteamento conjunto, minimizando custo R$.
"""

import pandas as pd
from .config import (
    CUSTO_FIXO_VUC, CUSTO_KM, DEPOT_COORDS, MAX_KM_VUC, MAX_TIME_VUC_MIN,
    SERVICE_TIME_MIN, START_HOUR,
)
from .data import normalizar_planilha, planilha_tem_rota_valida
from .geocoding import geocode_addresses
from .clustering import cluster_modelo_padrao, cluster_modo_criativo_fallback
from .solver import solve_group_route
from .vrp_solver import solve_vrp_global
from .racks import calcular_racks
from . import osrm


def _arrival_to_hhmm(arrival_min: float) -> str:
    total = int(arrival_min)
    hh = (total // 60) + START_HOUR
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"


def _label_vuc(label_base: str, idx: int) -> str:
    return f"{label_base} {chr(65 + (idx % 26))}"


def _vuc_data_to_outputs(
    vuc: dict, final_label: str, color_idx: int,
) -> tuple[dict, list[dict], dict] | None:
    """Converte um VUC já resolvido (paradas + km + time) nas estruturas
    de saída do pipeline: (stats_dict, table_rows, vuc_for_map).
    Retorna None se vier vazio.
    """
    paradas = vuc.get("paradas", [])
    if not paradas:
        return None
    total_p = int(sum(p["total"] for p in paradas))
    _, rg, rp = calcular_racks(total_p)
    km_real = round(vuc["total_km"], 2)

    stats_entry = {
        "km": km_real,
        "tempo_min": round(vuc["total_time_min"], 1),
        "tempo_label": (
            f"{int(vuc['total_time_min'] // 60)}h "
            f"{int(vuc['total_time_min'] % 60)}min"
        ),
        "pecas": total_p,
        "racks": f"{rg}G e {rp}P",
        "custo": round(CUSTO_FIXO_VUC + km_real * CUSTO_KM, 2),
        "clientes": [p["cliente"] for p in paradas],
    }

    table_rows = []
    for seq, parada in enumerate(paradas, 1):
        table_rows.append({
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

    # Geometria real (seguindo ruas) via OSRM /route — depot → paradas.
    # Open-route: motorista termina no último cliente, sem voltar ao CD.
    coords_completas = (
        [DEPOT_COORDS] + [[p["lat"], p["lon"]] for p in paradas]
    )
    geometry = osrm.route_geometry(coords_completas)

    vuc_map = {
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
        "route_geometry": geometry,  # null se OSRM falhar; front usa reta
    }
    return stats_entry, table_rows, vuc_map


def otimizar(file_bytes: bytes, filename: str, modo: str) -> dict:
    """Roda o pipeline e devolve estrutura serializável (dict)."""
    osrm.reset()

    df_raw = normalizar_planilha(file_bytes, filename)
    tem_rota = planilha_tem_rota_valida(df_raw)
    modo_efetivo = modo if tem_rota else "Modo Criativo"

    df_geo, erros = geocode_addresses(df_raw)

    if df_geo.empty:
        return {
            "modo_efetivo": modo_efetivo,
            "vucs": [],
            "stats": {},
            "table": [],
            "violacoes_janela": [],
            "violacoes_km": [],
            "enderecos_nao_localizados": erros,
            "osrm_indisponivel": False,
        }

    stats: dict = {}
    table: list[dict] = []
    vucs_out: list[dict] = []
    violacoes_janela: list[dict] = []
    violacoes_km: list[dict] = []
    color_idx = 0
    # Marca se o Modo Criativo caiu pra fallback (CVRP falhou).
    aviso_fallback: str | None = None

    if modo_efetivo == "Modelo Padrão":
        # Caminho clássico: agrupa por ROTA → TSP per-VUC
        for v_label, vuc_rows in cluster_modelo_padrao(df_geo):
            df_vuc = pd.DataFrame(vuc_rows)
            final_label = _label_vuc(v_label, color_idx)
            color_idx += 1
            res = solve_group_route(df_vuc)
            if not res:
                continue
            res["label"] = final_label
            out = _vuc_data_to_outputs(res, final_label, color_idx)
            if out is None:
                continue
            stats_entry, table_rows, vuc_map = out
            stats[final_label] = stats_entry
            table.extend(table_rows)
            vucs_out.append(vuc_map)
            _check_violacoes(
                final_label, res, violacoes_janela, violacoes_km,
            )
    else:
        # CVRP global do Modo Criativo (com safety net).
        # Se o solver falhar com TODAS as restrições + relaxamentos,
        # cai pra greedy clustering + per-VUC TSP — pior solução,
        # mas garante que ninguém fica fora.
        vrp_falhou = False
        vucs_resolvidos: list[dict] = []
        try:
            vucs_resolvidos = solve_vrp_global(df_geo)
        except Exception as e:
            print(
                f"[pipeline] ⚠ solve_vrp_global lançou exceção: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )
            vrp_falhou = True

        # Validação: VRP retornou todos os clientes?
        clientes_atendidos = sum(len(v.get("paradas", [])) for v in vucs_resolvidos)
        clientes_esperados = len(df_geo)
        if (
            not vrp_falhou
            and clientes_atendidos < clientes_esperados
        ):
            print(
                f"[pipeline] ⚠ VRP cobriu apenas {clientes_atendidos} de "
                f"{clientes_esperados} clientes — caindo pra fallback greedy",
                flush=True,
            )
            vrp_falhou = True

        if vrp_falhou:
            # Fallback: greedy por proximidade + TSP per-VUC
            aviso_fallback = (
                "O solver CVRP não encontrou solução viável dentro das "
                "restrições oficiais (140 km, janela 18:00). O sistema "
                "caiu pra um agrupamento greedy + TSP por VUC. As "
                "violações podem aparecer abaixo — avalie."
            )
            vucs_out.clear()
            stats.clear()
            table.clear()
            violacoes_janela.clear()
            violacoes_km.clear()
            color_idx = 0
            for v_label, vuc_rows in cluster_modo_criativo_fallback(df_geo):
                df_vuc = pd.DataFrame(vuc_rows)
                final_label = _label_vuc(v_label, color_idx)
                color_idx += 1
                res = solve_group_route(df_vuc)
                if not res:
                    continue
                res["label"] = final_label
                out = _vuc_data_to_outputs(res, final_label, color_idx)
                if out is None:
                    continue
                stats_entry, table_rows, vuc_map = out
                stats[final_label] = stats_entry
                table.extend(table_rows)
                vucs_out.append(vuc_map)
                _check_violacoes(
                    final_label, res, violacoes_janela, violacoes_km,
                )
        else:
            for vuc_resolvido in vucs_resolvidos:
                final_label = vuc_resolvido["label"]
                out = _vuc_data_to_outputs(vuc_resolvido, final_label, color_idx)
                color_idx += 1
                if out is None:
                    continue
                stats_entry, table_rows, vuc_map = out
                stats[final_label] = stats_entry
                table.extend(table_rows)
                vucs_out.append(vuc_map)
                _check_violacoes(
                    final_label, vuc_resolvido, violacoes_janela, violacoes_km,
                )

    return {
        "modo_efetivo": modo_efetivo,
        "vucs": vucs_out,
        "stats": stats,
        "table": table,
        "violacoes_janela": violacoes_janela,
        "violacoes_km": violacoes_km,
        "enderecos_nao_localizados": erros,
        "osrm_indisponivel": osrm.is_disabled(),
        "aviso_fallback": aviso_fallback,
    }


def _check_violacoes(
    label: str, res: dict,
    violacoes_janela: list[dict], violacoes_km: list[dict],
) -> None:
    """Anota violações de janela (>18:00) e KM (>140km)."""
    paradas = res.get("paradas", [])
    total_p = int(sum(p["total"] for p in paradas))

    fim_descarga = (
        paradas[-1]["arrival_min"] + SERVICE_TIME_MIN if paradas else 0
    )
    if fim_descarga > MAX_TIME_VUC_MIN:
        violacoes_janela.append({
            "vuc": label,
            "paradas": len(paradas),
            "pecas": total_p,
            "termino": _arrival_to_hhmm(fim_descarga),
        })

    km_real = round(res["total_km"], 2)
    if km_real > MAX_KM_VUC:
        violacoes_km.append({
            "vuc": label,
            "paradas": len(paradas),
            "pecas": total_p,
            "km_real": km_real,
            "limite": MAX_KM_VUC,
        })
