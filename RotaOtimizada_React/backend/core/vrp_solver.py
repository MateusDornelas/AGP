"""CVRP global do Modo Criativo (OR-Tools, pesquisa operacional).

Substitui o greedy + rebalance + per-VUC TSP por uma única chamada ao
solver completo do OR-Tools. O solver decide alocação E roteamento
conjuntamente, minimizando a função objetivo financeira:

    custo = CUSTO_FIXO_VUC × N_VUCs + CUSTO_KM × Σ KM

Restrições rígidas:
  - capacidade ≤ CAP_MAX_VUC peças por VUC
  - distância  ≤ MAX_KM_VUC km por VUC
  - tempo      ≤ MAX_TIME_VUC_MIN min por VUC (janela 18:00)

Quando os limites rígidos tornam o problema infactível, o solver
não acha solução. Para evitar perder clientes, o solve_vrp_global
faz tentativas progressivas:
  1. Restrições oficiais (140km, 600min)
  2. Janela estendida (140km, 720min)
  3. Sem janela (140km, sem time)
  4. Sem janela e sem KM (só capacidade)

Se TODAS as tentativas falharem, levanta exceção (pipeline aplica
fallback greedy). Cada tentativa loga claramente no terminal.
"""

import time
from math import sqrt
import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .config import (
    AVG_SPEED_KMH, CAP_MAX_VUC, CUSTO_FIXO_VUC, CUSTO_KM,
    DEPOT_COORDS, EUCLIDEAN_FUDGE, MAX_KM_VUC, MAX_TIME_VUC_MIN,
    SERVICE_TIME_MIN, VRP_SPAN_COEFFICIENT, VRP_TIME_LIMIT_SEC,
)
from .osrm import fallback_distance_km, pair_distance
from .two_opt import two_opt_reorder


def _log(msg: str) -> None:
    print(f"[vrp] {msg}", flush=True)


def _proximo_label_factory():
    idx = [0]

    def _next() -> str:
        lbl = f"VUC Otimizado {chr(65 + (idx[0] % 26))}"
        idx[0] += 1
        return lbl

    return _next


def _resolver_e_montar_vuc(
    nodes_seq: list[int],
    df_consolidado: pd.DataFrame,
) -> dict | None:
    """Percorre nodes_seq calculando arrival + KM real via OSRM."""
    if len(nodes_seq) < 2:
        return None
    total_km = 0.0
    cur_time = 0.0
    arrival = 0.0
    paradas = []

    locs_local = [DEPOT_COORDS] + df_consolidado[["lat", "lon"]].values.tolist()
    # Open-route: motorista finaliza no último cliente, não retorna ao CD.
    # KM e tempo reais contam só depot → c1 → c2 → ... → cN (sem volta).
    full_seq = list(nodes_seq)

    for i in range(len(full_seq) - 1):
        p1, p2 = locs_local[full_seq[i]], locs_local[full_seq[i + 1]]
        osrm = pair_distance(p1, p2)
        if osrm is not None:
            step_km = osrm["distance_km"]
            step_time = osrm["duration_min"]
        else:
            step_km = fallback_distance_km(p1, p2)
            step_time = (step_km / AVG_SPEED_KMH) * 60

        arrival = cur_time + step_time
        node_idx = full_seq[i + 1]
        if node_idx > 0:
            cliente = df_consolidado.iloc[node_idx - 1]
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
            cur_time = arrival + SERVICE_TIME_MIN
        total_km += step_km

    arrival_last = paradas[-1]["arrival_min"] if paradas else 0.0
    return {
        "paradas": paradas,
        "total_km": total_km,
        "total_time_min": arrival_last,
    }


def _solve_attempt(
    df_normal: pd.DataFrame,
    locs: list,
    distance_matrix: list[list[int]],
    demands: list[int],
    max_km: float | None,
    max_time_min: int | None,
    rotulo: str,
):
    """Roda uma tentativa do solver com restrições configuráveis.

    max_km=None ou max_time_min=None → desabilita a dimensão.
    Retorna (solution, routing, manager) ou (None, None, None) em falha.
    """
    n_nodes = len(locs)
    n_vehicles = len(df_normal)

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def transit_cb(from_idx: int, to_idx: int) -> int:
        return distance_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_cb_idx = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    fixed_cost = int(CUSTO_FIXO_VUC / CUSTO_KM * 1000)
    routing.SetFixedCostOfAllVehicles(fixed_cost)

    # Capacidade (sempre ativa)
    def demand_cb(from_idx: int) -> int:
        return demands[manager.IndexToNode(from_idx)]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx, 0, [CAP_MAX_VUC] * n_vehicles, True, "Capacity",
    )

    if max_km is not None:
        routing.AddDimension(
            transit_cb_idx, 0, int(max_km * 1000), True, "Distance",
        )
        routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(
            VRP_SPAN_COEFFICIENT
        )

    if max_time_min is not None:
        def time_cb(from_idx: int, to_idx: int) -> int:
            from_n = manager.IndexToNode(from_idx)
            to_n = manager.IndexToNode(to_idx)
            meters = distance_matrix[from_n][to_n]
            travel_min = (meters / 1000.0) / AVG_SPEED_KMH * 60
            service = SERVICE_TIME_MIN if to_n != 0 else 0
            return int(travel_min + service)

        time_cb_idx = routing.RegisterTransitCallback(time_cb)
        routing.AddDimension(time_cb_idx, 0, max_time_min, True, "Time")

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    sp.time_limit.seconds = VRP_TIME_LIMIT_SEC

    _log(
        f"[{rotulo}] {n_vehicles} clientes, "
        f"KM_max={max_km if max_km else 'sem limite'}, "
        f"Tempo_max={max_time_min if max_time_min else 'sem limite'} min"
    )
    t0 = time.time()
    solution = routing.SolveWithParameters(sp)
    elapsed = time.time() - t0
    if solution:
        _log(f"[{rotulo}] ✓ solução em {elapsed:.1f}s")
        return solution, routing, manager
    _log(f"[{rotulo}] ✗ sem solução em {elapsed:.1f}s")
    return None, None, None


def solve_vrp_global(df_geo: pd.DataFrame) -> list[dict]:
    """Resolve o CVRP do Modo Criativo. Lista de VUCs já com paradas e KM.

    Raises:
        RuntimeError: se nenhuma das tentativas progressivas encontrar
        solução (o pipeline deve aplicar fallback greedy).
    """
    n_clientes_in = len(df_geo)
    _log(f"=== entrada: {n_clientes_in} clientes geocodificados ===")

    df = df_geo.copy()
    for col in ("POS", "PB_TS"):
        if col not in df.columns:
            df[col] = 0

    df_cons = (
        df.groupby(["lat", "lon", "NOME", "ENDEREÇO"])
        .agg({
            "POS": "sum", "PB_TS": "sum",
            "PEÇAS GRANDES": "sum", "PEÇAS PEQUENAS": "sum", "TOTAL": "sum",
        })
        .reset_index()
    )
    df_cons["TOTAL"] = df_cons["TOTAL"].astype(int)
    _log(
        f"após dedup por (lat, lon, nome): {len(df_cons)} clientes únicos "
        f"({n_clientes_in - len(df_cons)} duplicatas mescladas)"
    )

    df_oversized = df_cons[df_cons["TOTAL"] > CAP_MAX_VUC]
    df_normal = df_cons[df_cons["TOTAL"] <= CAP_MAX_VUC].reset_index(drop=True)
    _log(
        f"oversized (>57 pç): {len(df_oversized)} cliente(s) → VUC dedicado"
    )
    _log(f"normal (≤57 pç): {len(df_normal)} cliente(s) → vai pro solver")

    vucs: list[dict] = []
    proximo_label = _proximo_label_factory()

    for _, row_over in df_oversized.iterrows():
        cons_um = pd.DataFrame([row_over]).reset_index(drop=True)
        res = _resolver_e_montar_vuc([0, 1], cons_um)
        if res:
            res["label"] = proximo_label()
            vucs.append(res)
            _log(
                f"oversized '{row_over['NOME']}' "
                f"({int(row_over['TOTAL'])} pç) → {res['label']}"
            )

    if df_normal.empty:
        _log("nenhum cliente normal — só oversized")
        return vucs

    # ===== MONTA O CVRP =====
    locs = [DEPOT_COORDS] + df_normal[["lat", "lon"]].values.tolist()
    n_nodes = len(locs)

    def dist_m(i: int, j: int) -> int:
        return int(
            sqrt((locs[i][0] - locs[j][0]) ** 2 + (locs[i][1] - locs[j][1]) ** 2)
            * 111 * EUCLIDEAN_FUDGE * 1000
        )

    distance_matrix = [[dist_m(i, j) for j in range(n_nodes)] for i in range(n_nodes)]
    # Open-route: zera o custo de retorno ao depot. O OR-Tools traça
    # um circuito fechado por design (cada veículo começa e termina em 0),
    # mas com a aresta de fechamento custando 0 o solver otimiza só a IDA.
    # Sem este zero, o solver tende a colocar o cliente mais perto do CD
    # como ÚLTIMA parada (pra minimizar a volta imaginária) — efeito que
    # o usuário viu nos VUCs voltando em direção a Santana de Parnaíba.
    for i in range(1, n_nodes):
        distance_matrix[i][0] = 0
    demands = [0] + df_normal["TOTAL"].astype(int).tolist()

    # ===== TENTATIVAS PROGRESSIVAS =====
    tentativas = [
        ("oficial", MAX_KM_VUC, MAX_TIME_VUC_MIN),
        ("janela_estendida_12h", MAX_KM_VUC, 720),
        ("sem_janela", MAX_KM_VUC, None),
        ("so_capacidade", None, None),
    ]

    solution = None
    routing = None
    manager = None
    rotulo_usado = None

    for rotulo, max_km, max_time in tentativas:
        solution, routing, manager = _solve_attempt(
            df_normal, locs, distance_matrix, demands, max_km, max_time, rotulo,
        )
        if solution is not None:
            rotulo_usado = rotulo
            break

    if solution is None:
        msg = (
            f"VRP falhou em todas as {len(tentativas)} tentativas para "
            f"{len(df_normal)} clientes normais."
        )
        _log(f"✗✗✗ {msg}")
        raise RuntimeError(msg)

    if rotulo_usado != "oficial":
        _log(
            f"⚠ ATENÇÃO: solução obtida com restrições relaxadas "
            f"({rotulo_usado}). Verifique violações na UI."
        )

    # ===== EXTRAI VUCs =====
    n_vehicles = len(df_normal)
    clientes_extraidos = 0
    for v in range(n_vehicles):
        idx = routing.Start(v)
        proximo = solution.Value(routing.NextVar(idx))
        if routing.IsEnd(proximo):
            continue
        nodes_seq = []
        while not routing.IsEnd(idx):
            nodes_seq.append(manager.IndexToNode(idx))
            idx = solution.Value(routing.NextVar(idx))

        # 2-opt euclidiano pós-solver: remove cruzamentos residuais
        # dentro de cada VUC sem custo extra de OSRM.
        nodes_seq = two_opt_reorder(nodes_seq, locs)

        res = _resolver_e_montar_vuc(nodes_seq, df_normal)
        if res is None or not res["paradas"]:
            continue
        res["label"] = proximo_label()
        vucs.append(res)
        clientes_extraidos += len(res["paradas"])

    _log(
        f"=== saída: {len(vucs)} VUCs com {clientes_extraidos} clientes "
        f"normais + {len(df_oversized)} oversized ==="
    )

    return vucs
