"""TSP solver (OR-Tools) por VUC — usado pelo Modelo Padrão.

O Modo Criativo NÃO usa este módulo — ele vai direto pro CVRP global
em ``vrp_solver.solve_vrp_global`` (alocação + roteamento em um passo).
"""

from math import sqrt
import pandas as pd
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from .config import (
    AVG_SPEED_KMH, DEPOT_COORDS, EUCLIDEAN_FUDGE, SERVICE_TIME_MIN,
    TSP_TIME_LIMIT_SEC,
)
from .osrm import pair_distance, fallback_distance_km
from .two_opt import two_opt_reorder


def solve_group_route(df_subset: pd.DataFrame) -> dict | None:
    """Resolve TSP de um grupo de paradas. Retorna paradas em ordem ótima,
    com horários de chegada (min a partir das 08:00) e KM total real."""
    if df_subset.empty:
        return None

    for col in ("POS", "PB_TS"):
        if col not in df_subset.columns:
            df_subset = df_subset.copy()
            df_subset[col] = 0

    df_cons = (
        df_subset.groupby(["lat", "lon", "NOME", "ENDEREÇO"])
        .agg({
            "POS": "sum", "PB_TS": "sum",
            "PEÇAS GRANDES": "sum", "PEÇAS PEQUENAS": "sum", "TOTAL": "sum",
        })
        .reset_index()
    )

    coords = df_cons[["lat", "lon"]].values.tolist()
    locs = [DEPOT_COORDS] + coords

    manager = pywrapcp.RoutingIndexManager(len(locs), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_n = manager.IndexToNode(from_index)
        to_n = manager.IndexToNode(to_index)
        # Open-route: arco de retorno ao depot custa 0. O OR-Tools precisa
        # de um circuito fechado (depot → ... → depot) por design, mas
        # zerando o custo da última aresta o solver otimiza efetivamente
        # SÓ A IDA — sem viés pra escolher o cliente mais próximo do CD
        # como última parada. O motorista termina onde fizer sentido pra
        # rota de entrega, não pra "volta curta".
        if to_n == 0:
            return 0
        dist_km = (
            sqrt((locs[from_n][0] - locs[to_n][0]) ** 2 +
                 (locs[from_n][1] - locs[to_n][1]) ** 2) * 111 * EUCLIDEAN_FUDGE
        )
        return int((dist_km / AVG_SPEED_KMH) * 60)

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    # GUIDED_LOCAL_SEARCH refina a heurística inicial — reduz cruzamentos
    # e KM total. Antes só usávamos PATH_CHEAPEST_ARC (1ª solução).
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    sp.time_limit.seconds = TSP_TIME_LIMIT_SEC

    solution = routing.SolveWithParameters(sp)
    if not solution:
        return None

    index = routing.Start(0)
    nodes_seq = []
    while not routing.IsEnd(index):
        nodes_seq.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))

    # 2-opt euclidiano pós-solver: pega a sequência decidida pelo OR-Tools
    # e remove cruzamentos residuais. Operação barata (sem chamadas OSRM).
    nodes_seq = two_opt_reorder(nodes_seq, locs)

    total_km = 0.0
    current_time = 0.0
    arrival = 0.0
    paradas = []

    for i in range(len(nodes_seq) - 1):
        p1, p2 = locs[nodes_seq[i]], locs[nodes_seq[i + 1]]
        osrm = pair_distance(p1, p2)
        if osrm is not None:
            step_dist = osrm["distance_km"]
            step_time = osrm["duration_min"]
        else:
            step_dist = fallback_distance_km(p1, p2)
            step_time = (step_dist / AVG_SPEED_KMH) * 60

        arrival = current_time + step_time
        node_idx = nodes_seq[i + 1]

        if node_idx > 0:
            cliente = df_cons.iloc[node_idx - 1]
            paradas.append({
                "cliente": cliente["NOME"],
                "endereco": cliente["ENDEREÇO"],
                "lat": float(cliente["lat"]),
                "lon": float(cliente["lon"]),
                "pos": int(cliente["POS"]),
                "pb_ts": int(cliente["PB_TS"]),
                "pecas_g": int(cliente["PEÇAS GRANDES"]),
                "pecas_m": int(cliente["PEÇAS PEQUENAS"]),
                "total": int(cliente["TOTAL"]),
                "arrival_min": arrival,
            })

        current_time = arrival + SERVICE_TIME_MIN
        total_km += step_dist

    return {
        "paradas": paradas,
        "total_km": total_km,
        "total_time_min": arrival,
    }
