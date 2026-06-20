"""2-opt euclidiano pós-solver.

O TSP/CVRP do OR-Tools usa matriz de distância euclidiana × fator de
correção. Como a malha viária real (OSRM) não é euclidiana, a sequência
"ótima" pelo solver pode mostrar cruzamentos visuais óbvios quando
desenhada com geometria real.

2-opt é um operador de melhoria local clássico: para cada par (i, j)
testa se inverter o segmento da rota entre i e j reduz a soma das
distâncias das duas arestas envolvidas. Se sim, aplica. Repete até
nenhum par melhorar (ótimo local).

Aplicação aqui é EUCLIDIANA — barata, sem chamadas extras ao OSRM.
Remove cruzamentos geométricos sem garantir o ótimo na malha viária
real, mas o efeito visual e o custo real costumam melhorar bastante.

Para um 2-opt que opera direto na matriz OSRM, basta passar uma função
de distância que use osrm.pair_distance — mas o trade-off de tempo
(throttle 0.3s/par) raramente compensa.
"""

from math import sqrt


def _euclid(p1: list, p2: list) -> float:
    """Distância euclidiana em graus (proporcional a km via fator)."""
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def two_opt_indices(
    coords: list,
    depot_fixed_start: bool = True,
    open_route: bool = True,
) -> list[int]:
    """Aplica 2-opt euclidiano sobre uma sequência de coordenadas.

    Args:
        coords: lista de [lat, lon] na ordem atual (ex: [depot, c1, c2, ..., cN])
        depot_fixed_start: se True, o índice 0 (depot) fica fixo no início.
        open_route: se True, considera reversões que envolvem o último nó
            (rota aberta — motorista termina na última parada, sem retorno).
            Se False, mantém o último nó intocado (rota fechada — clássico).

    Returns:
        Permutação dos índices [0, 1, ..., N-1] na ordem refinada.
        Aplique ao seu vetor original com `[lista[i] for i in result]`.
    """
    n = len(coords)
    if n < 4:
        return list(range(n))

    rota = list(range(n))
    inicio = 1 if depot_fixed_start else 0

    # 2-opt clássico: troca arestas (a,b) e (c,d_pt) por (a,c) e (b,d_pt),
    # invertendo o segmento entre b e c. Em open-route, j pode ir até a
    # última posição — nesse caso só a aresta (a,b) é afetada (não existe
    # d_pt após o último nó).
    melhorou = True
    iteracoes = 0
    LIMITE_ITER = 50  # safety net pra caso de empate flutuante

    while melhorou and iteracoes < LIMITE_ITER:
        melhorou = False
        iteracoes += 1

        j_limite = n if open_route else n - 1
        for i in range(inicio, n - 1):
            for j in range(i + 1, j_limite):
                a = coords[rota[i - 1]] if i > 0 else None
                b = coords[rota[i]]
                c = coords[rota[j]]

                if a is None:
                    continue

                antes = _euclid(a, b)
                depois = _euclid(a, c)

                # Se j não é o último nó, há também a aresta (c, d_pt)
                # que vira (b, d_pt) após a reversão.
                if j + 1 < n:
                    d_pt = coords[rota[j + 1]]
                    antes += _euclid(c, d_pt)
                    depois += _euclid(b, d_pt)

                if depois + 1e-9 < antes:
                    rota[i:j + 1] = rota[i:j + 1][::-1]
                    melhorou = True

    return rota


def two_opt_reorder(
    nodes_seq: list[int],
    coords_by_node: list,
    open_route: bool = True,
) -> list[int]:
    """Wrapper conveniente para reordenar uma sequência de nós já decidida
    pelo solver, usando as coordenadas indexadas por nó.

    Args:
        nodes_seq: sequência de índices de nó (ex: [0, 3, 1, 5, 2]).
                   nodes_seq[0] tipicamente é o depot (idx 0).
        coords_by_node: lista global de coordenadas, indexada por nó.
        open_route: ver two_opt_indices. Default True (rota aberta).

    Returns:
        Nova sequência de nós, mantendo o depot inicial fixo.
    """
    coords_seq = [coords_by_node[n] for n in nodes_seq]
    nova_ordem = two_opt_indices(
        coords_seq, depot_fixed_start=True, open_route=open_route,
    )
    return [nodes_seq[i] for i in nova_ordem]
