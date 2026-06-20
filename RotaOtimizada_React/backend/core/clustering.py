"""Agrupamentos heurísticos.

- ``cluster_modelo_padrao``: agrupa por ROTA (1+2, 3+4, 5+) — usado
  pelo Modelo Padrão.
- ``cluster_modo_criativo_fallback``: greedy por proximidade — só
  é chamado quando o CVRP do ``vrp_solver.solve_vrp_global`` falha
  em encontrar solução (raro). Mantém o usuário com algum resultado
  utilizável em vez de zero VUCs.
"""

from math import sqrt
import pandas as pd
from .config import CAP_MAX_VUC, DEPOT_COORDS


def construir_grupos_padrao(df_geo: pd.DataFrame) -> list[tuple[str, list[str]]]:
    """Constrói grupos de rotas: 1+2 juntas, 3+4 juntas, 5+ isoladas."""
    rotas_presentes: set[str] = set()
    for valor in df_geo["ROTA"].dropna().tolist():
        txt = str(valor).strip()
        if not txt:
            continue
        digitos = "".join(ch for ch in txt.split(".")[0] if ch.isdigit())
        if not digitos:
            continue
        n = int(digitos)
        if n > 0:
            rotas_presentes.add(str(n))

    grupos: list[tuple[str, list[str]]] = []
    if {"1", "2"} & rotas_presentes:
        grupos.append(("Rota (1+2)", ["1", "2", "01", "02"]))
    if {"3", "4"} & rotas_presentes:
        grupos.append(("Rota (3+4)", ["3", "4", "03", "04"]))
    for n in sorted(int(r) for r in rotas_presentes if int(r) >= 5):
        grupos.append((f"Rota ({n})", [str(n), f"{n:02d}"]))
    return grupos


def cluster_modelo_padrao(df_geo: pd.DataFrame) -> list[tuple[str, list]]:
    """Agrupa por ROTA (1+2, 3+4, 5+) e packa ≤57 peças/VUC."""
    vucs = []
    for label, codes in construir_grupos_padrao(df_geo):
        sub = df_geo[df_geo["ROTA"].astype(str).isin(codes)]
        if sub.empty:
            continue
        vuc_atual, carga = [], 0
        for _, row in sub.iterrows():
            if carga + row["TOTAL"] > CAP_MAX_VUC and vuc_atual:
                vucs.append((label, vuc_atual))
                vuc_atual, carga = [], 0
            vuc_atual.append(row)
            carga += row["TOTAL"]
        if vuc_atual:
            vucs.append((label, vuc_atual))
    return vucs


def cluster_modo_criativo_fallback(df_geo: pd.DataFrame) -> list[tuple[str, list]]:
    """Greedy: ordena por distância ao depot, agrupa por proximidade,
    packa ≤57 peças/VUC. Sem restrição de KM ou tempo — usado quando
    o CVRP global do OR-Tools falha em encontrar solução."""
    df_c = df_geo.copy()
    df_c["dist_depot"] = df_c.apply(
        lambda r: sqrt(
            (r["lat"] - DEPOT_COORDS[0]) ** 2 +
            (r["lon"] - DEPOT_COORDS[1]) ** 2
        ),
        axis=1,
    )
    df_c = df_c.sort_values("dist_depot")

    vucs = []
    max_iter = max(len(df_c) + 5, 50)
    it = 0

    while not df_c.empty and it < max_iter:
        it += 1
        ref = df_c.iloc[0]
        df_c["dist_to_ref"] = df_c.apply(
            lambda r: sqrt(
                (r["lat"] - ref["lat"]) ** 2 + (r["lon"] - ref["lon"]) ** 2
            ),
            axis=1,
        )
        df_c = df_c.sort_values("dist_to_ref")

        vuc_temp, carga_temp, remover = [], 0, []
        for idx, row in df_c.iterrows():
            if carga_temp + row["TOTAL"] <= CAP_MAX_VUC:
                vuc_temp.append(row)
                carga_temp += row["TOTAL"]
                remover.append(idx)

        # Anti loop-infinito: cliente oversized sozinho na 1ª posição
        if not vuc_temp:
            primeiro_idx = df_c.index[0]
            primeira = df_c.iloc[0]
            vuc_temp = [primeira]
            remover = [primeiro_idx]

        vucs.append(("VUC Otimizado", vuc_temp))
        df_c = df_c.drop(remover)

    return vucs
