"""Constantes e parâmetros de negócio do otimizador AGP."""

import os
from dotenv import load_dotenv, find_dotenv

# Procura .env subindo a árvore (backend/ → RotaOtimizada_React/ → StreamLit/).
# Permite manter UM .env compartilhado na raiz do mono-repo Streamlit
# em vez de duplicar credenciais.
load_dotenv(find_dotenv(usecwd=True), override=False)

# Credenciais (uso interno; migrar para banco em produção)
VALID_USER = "Logistica"
VALID_PASS = "Agp123"

# Anthropic / Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODELO_IA = "claude-sonnet-4-6"

# Depot (CD Central)
DEPOT_COORDS = [-23.4357, -46.9427]
DEPOT_ADDRESS = (
    "R. José Roberto de Camargo Toledo, 1247 - Suru, "
    "Santana de Parnaíba - SP, 06504-150"
)

# Parâmetros operacionais
AVG_SPEED_KMH = 25.0
SERVICE_TIME_MIN = 90
START_HOUR = 8
DIESEL_PRECO_L = 6.20
KM_POR_LITRO = 8.0
CUSTO_FIXO_VUC = 1100.00

# Custo por KM (combustível) — derivado dos preços acima.
# Função objetivo do VRP: minimizar (CUSTO_FIXO_VUC × N_VUCs + CUSTO_KM × Σ KM).
CUSTO_KM = DIESEL_PRECO_L / KM_POR_LITRO  # R$ 0,775 / km

# Janela operacional total em minutos (08:00 → 18:00 = 600 min).
MAX_TIME_VUC_MIN = (18 - START_HOUR) * 60

# ===== TUNING DO SOLVER CVRP =====
# Tempo de busca do solver. Mais tempo = solução melhor (até saturar).
# 60s costuma converger em planilhas de até ~50 clientes.
VRP_TIME_LIMIT_SEC = 60

# Penalidade de "span" no minmax KM (balanceamento). Quanto maior, mais
# o solver tenta equilibrar a KM entre VUCs (em vez de privilegiar o
# custo total). 1000 = forte preferência por equilíbrio sem dominar o
# custo financeiro.
VRP_SPAN_COEFFICIENT = 1000

# Tempo de busca do TSP per-VUC do Modelo Padrão. 25s + GUIDED_LOCAL_SEARCH
# elimina a maioria dos cruzamentos que a heurística PATH_CHEAPEST_ARC pura
# deixava passar (especialmente em VUCs com 7+ paradas).
TSP_TIME_LIMIT_SEC = 25

# Fator de correção da distância euclidiana → rota real. 1.3 era o default
# (urbano cerrado). 1.35 representa melhor a malha de SP metropolitana
# (mistura urbano + suburbano).
EUCLIDEAN_FUDGE = 1.35

# Capacidades
CAP_RACK_G = 13
CAP_RACK_P = 22
CAP_MAX_VUC = 57
MAX_KM_VUC = 140.0

# Cache SQLite de geocoding
GEOCACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "geocode_cache.db",
)

# Bounding box Brasil (sanity check de geocoding)
BR_LAT_MIN, BR_LAT_MAX = -34.0, 5.5
BR_LON_MIN, BR_LON_MAX = -74.0, -34.0

# OSRM
OSRM_BASE_URL = "https://router.project-osrm.org"
OSRM_CONNECT_TIMEOUT = 3
OSRM_READ_TIMEOUT = 4
OSRM_THROTTLE_SEC = 0.3

# CORS — adicionar URL do front em produção
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
