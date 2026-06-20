"""
Otimizador de Rota Logística — v2.0 (Claude API)
==================================================
Migração: Google Gemini → Anthropic Claude
Execução: python -m streamlit run RotaOtimizada.py
"""

import streamlit as st
import pandas as pd
import anthropic  # MIGRAÇÃO: google-genai → anthropic
import polyline
import requests
import pydeck as pdk
from geopy.geocoders import Nominatim
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from math import sqrt, ceil
from datetime import datetime, timedelta
from fpdf import FPDF
import time
import os
import sys
import sqlite3
import unicodedata
from dotenv import load_dotenv


def _ascii_upper(s) -> str:
    """Normaliza string: tira acentos, faz strip, vira UPPERCASE.

    Usado para chavear o rename map de colunas sem se preocupar com
    variações como 'PEÇAS MÉDIAS' vs 'PEÇAS MEDIAS', 'ENDEREÇO' vs
    'ENDERECO', etc.
    """
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()

# --- CARREGAR VARIÁVEIS DE AMBIENTE ---
load_dotenv()


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str) -> None:
    """
    Imprime no terminal com timestamp + flush imediato.
    Permite acompanhar onde o app está em tempo real sem depender
    apenas das mensagens da UI Streamlit (que podem buffer).
    """
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", "replace").decode("ascii")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)
    sys.stdout.flush()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Otimizador de Rota Logística",
    page_icon="🚛",
)

# Logo AGP — versão grande ocupando toda a largura da sidebar.
_AGP_LOGO = os.path.join(os.path.dirname(__file__), "AGPpng.png")

# CSS global: reduz fontes em 1 unidade (≈1px) em relação aos defaults
# do Streamlit, mantendo proporções consistentes entre títulos/textos.
st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-size: 15px; }
    h1 { font-size: 1.875rem !important; }   /* default 2rem  → ~30px */
    h2 { font-size: 1.5rem !important; }     /* default 1.75rem → ~24px */
    h3 { font-size: 1.25rem !important; }    /* default 1.5rem  → ~20px */
    h4, h5, h6 { font-size: 1.0625rem !important; }
    .stMarkdown p, .stMarkdown li { font-size: 0.9375rem; }
    [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8125rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TELA DE LOGIN
# ============================================================
# Credenciais hardcoded (uso interno). Para produção, mover para
# st.secrets ou backend de autenticação dedicado.
_VALID_USER = "Logistica"
_VALID_PASS = "Agp123"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def _render_login_screen() -> None:
    """Tela de login centralizada com o logo AGP e formulário."""
    _, col_c, _ = st.columns([1, 1.2, 1])
    with col_c:
        if os.path.exists(_AGP_LOGO):
            st.image(_AGP_LOGO, use_container_width=True)
        st.markdown(
            "<h2 style='text-align:center;margin-top:0.5rem;'>"
            "Otimizador Logístico</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#666;margin-bottom:1.5rem;'>"
            "Acesso restrito — informe suas credenciais</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form", clear_on_submit=False):
            usuario = st.text_input("👤 Usuário", placeholder="Logistica")
            senha = st.text_input(
                "🔒 Senha", type="password", placeholder="••••••"
            )
            submit = st.form_submit_button(
                "Entrar", type="primary", use_container_width=True
            )
            if submit:
                if usuario == _VALID_USER and senha == _VALID_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Credenciais inválidas. Tente novamente.")


if not st.session_state.authenticated:
    _render_login_screen()
    st.stop()

# --- PARÂMETROS GLOBAIS ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODELO_IA = "claude-sonnet-4-6"

# 1. ENDEREÇO DE PARTIDA (CD Central)
DEPOT_COORDS = [-23.4357, -46.9427]
DEPOT_ADDRESS = (
    "R. José Roberto de Camargo Toledo, 1247 - Suru, "
    "Santana de Parnaíba - SP, 06504-150"
)

# PARÂMETROS OPERACIONAIS E FINANCEIROS
AVG_SPEED_KMH = 25.0
SERVICE_TIME_MIN = 90
START_HOUR = 8
DIESEL_PRECO_L = 6.20
KM_POR_LITRO = 8.0
CUSTO_FIXO_VUC = 1100.00

# CUSTO POR KM (combustível) — derivado dos preços acima.
# Função objetivo do VRP: minimizar (CUSTO_FIXO_VUC × N_VUCs + CUSTO_KM × Σ KM).
CUSTO_KM = DIESEL_PRECO_L / KM_POR_LITRO  # R$ 0,775 / km

# Janela operacional total em minutos (08:00 → 18:00 = 600 min).
MAX_TIME_VUC_MIN = (18 - START_HOUR) * 60

# Limite de tempo do solver VRP (segundos). Mais tempo = solução melhor.
VRP_TIME_LIMIT_SEC = 30

# Penalidade de "span" no minmax KM (balanceamento). Quanto maior, mais
# o solver tenta equilibrar a KM entre VUCs. 100 = peso médio.
VRP_SPAN_COEFFICIENT = 100

# CAPACIDADES RACKS
CAP_RACK_G = 13
CAP_RACK_P = 22
CAP_MAX_VUC = 57

# LIMITE DE QUILOMETRAGEM POR VUC (hard cap)
MAX_KM_VUC = 140.0

# BOUNDING BOX BRASIL (sanity check de geocoding)
# Qualquer coordenada fora desta caixa é descartada e listada como erro.
BR_LAT_MIN, BR_LAT_MAX = -34.0, 5.5
BR_LON_MIN, BR_LON_MAX = -74.0, -34.0


def coord_no_brasil(lat: float, lon: float) -> bool:
    """Retorna True se (lat, lon) cai dentro do bounding box do Brasil."""
    return (
        BR_LAT_MIN <= lat <= BR_LAT_MAX
        and BR_LON_MIN <= lon <= BR_LON_MAX
    )


# ============================================================
# CACHE PERSISTENTE DE GEOCODING (SQLite)
# ============================================================
# Endereços já consultados ficam salvos no DB local. Próximas
# execuções com o mesmo endereço (~95% dos casos no dia a dia)
# pulam o Nominatim e ganham ~1s por cliente.
_GEOCACHE_PATH = os.path.join(os.path.dirname(__file__), "geocode_cache.db")
_GEOCACHE_INITIALIZED = False


def _geocache_conn() -> sqlite3.Connection:
    """Conexão SQLite (cria DB+tabela na primeira chamada)."""
    global _GEOCACHE_INITIALIZED
    conn = sqlite3.connect(_GEOCACHE_PATH)
    if not _GEOCACHE_INITIALIZED:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS geocache (
                endereco TEXT PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                ts INTEGER NOT NULL
            )"""
        )
        conn.commit()
        _GEOCACHE_INITIALIZED = True
    return conn


def geocache_get(endereco: str) -> tuple[float, float] | None:
    """Busca (lat, lon) no cache. None se não houver hit."""
    try:
        with _geocache_conn() as conn:
            row = conn.execute(
                "SELECT lat, lon FROM geocache WHERE endereco = ?",
                (endereco.strip(),),
            ).fetchone()
        return (row[0], row[1]) if row else None
    except Exception as e:
        log(f"  ⚠ geocache_get falhou: {e}")
        return None


def geocache_set(endereco: str, lat: float, lon: float) -> None:
    """Salva (endereco, lat, lon) no cache (upsert)."""
    try:
        with _geocache_conn() as conn:
            conn.execute(
                """INSERT INTO geocache (endereco, lat, lon, ts)
                   VALUES (?, ?, ?, strftime('%s', 'now'))
                   ON CONFLICT(endereco) DO UPDATE SET
                     lat=excluded.lat, lon=excluded.lon, ts=excluded.ts""",
                (endereco.strip(), float(lat), float(lon)),
            )
            conn.commit()
    except Exception as e:
        log(f"  ⚠ geocache_set falhou: {e}")


# NOTA: fast_km_estimate e rebalancear_km foram REMOVIDAS no v3.
# Eram proxy euclidean para o greedy + swap-unilateral. O CVRP global
# do OR-Tools (solve_vrp_global) substitui essas funções com algoritmos
# muito superiores (GUIDED_LOCAL_SEARCH faz 2-opt, or-opt e
# cross-exchange entre rotas automaticamente).


def normalizar_planilha(uploaded_file) -> pd.DataFrame:
    """
    Lê e normaliza a planilha de entrada, suportando:

    FORMATO NOVO (detalhado, multi-header com células mescladas):
        Linha 1: BLINDADORAS | ROTA | PEÇAS GRANDES (mesclado 3 cols) |
                 PEÇAS MÉDIAS | PEÇAS TOTAIS | ENDEREÇO | RACK GRANDE |
                 RACK MEDIO | DATA | ...
        Linha 2:                | POS | PB/TS | TOTAL | (vazias)...

    FORMATO ANTIGO (header simples):
        NOME | ROTA | ENDEREÇO | PEÇAS GRANDES | PEÇAS PEQUENAS | TOTAL

    Características da nova leitura:
      - Lê com header=None para inspecionar a estrutura crua.
      - Forward-fill nos headers mesclados da linha 1 (resolve as células
        vazias que aparecem sob PEÇAS GRANDES).
      - Forward-fill em colunas de dados comumente mescladas (ROTA,
        RACK GRANDE, RACK MEDIO) — assim mesclagens de 2, 3 ou N linhas
        são propagadas para todos os blindadores da mesma rota.
      - Normaliza acentos (Ç, É) antes de bater chaves no rename map,
        então 'PEÇAS MÉDIAS' e 'PEÇAS MEDIAS' caem no mesmo destino.
      - Deduplica nomes finais defensivamente (evita Series → DataFrame
        em df["TOTAL"]).
      - Colunas extras (RACK GRANDE, RACK MEDIO, DATA, etc.) passam
        intactas para análise futura.

    Retorna DataFrame com colunas canônicas:
        NOME, ROTA, ENDEREÇO, POS, PB_TS, PEÇAS GRANDES, PECAS_MEDIAS,
        PEÇAS PEQUENAS (alias), TOTAL + quaisquer colunas extras.
    """
    nome = uploaded_file.name.lower()
    is_excel = nome.endswith(("xlsx", "xls"))

    uploaded_file.seek(0)
    if is_excel:
        df_raw = pd.read_excel(uploaded_file, header=None)
    else:
        df_raw = pd.read_csv(uploaded_file, header=None)

    if df_raw.empty:
        raise ValueError("Planilha vazia.")

    # Extrai as duas primeiras linhas como possíveis headers
    row0 = [
        str(v).strip() if pd.notna(v) else ""
        for v in df_raw.iloc[0].tolist()
    ]
    row1 = [
        str(v).strip() if pd.notna(v) else ""
        for v in (df_raw.iloc[1].tolist() if len(df_raw) > 1 else [""] * len(row0))
    ]

    # Forward-fill nos headers mesclados da linha 1
    row0_ffill, last = [], ""
    for v in row0:
        if v:
            last = v
        row0_ffill.append(last)

    row1_norm = [_ascii_upper(v) for v in row1]

    # Multi-header detectado se row1 traz POS ou PB/TS (gatilhos específicos
    # do formato detalhado; 'TOTAL' sozinho seria ambíguo com nome de cliente).
    is_multi = any(v in ("POS", "PB/TS", "PB-TS", "PB_TS") for v in row1_norm)

    if is_multi:
        headers, data_start = [], 2
        for top, sub in zip(row0_ffill, row1):
            top_n = _ascii_upper(top)
            sub_n = _ascii_upper(sub)
            if sub_n and top_n == "PECAS GRANDES":
                headers.append(f"PECAS GRANDES|{sub_n}")
            else:
                headers.append(top_n)
    else:
        headers = [_ascii_upper(v) for v in row0]
        data_start = 1

    # Deduplica nomes (defensivo: evita df["X"] virar DataFrame)
    seen, headers_final = {}, []
    for h in headers:
        if not h:
            h = "COL_VAZIA"
        if h in seen:
            seen[h] += 1
            headers_final.append(f"{h}__{seen[h]}")
        else:
            seen[h] = 0
            headers_final.append(h)

    df = df_raw.iloc[data_start:].reset_index(drop=True)
    df.columns = headers_final

    # Rename para nomes canônicos. Feito em DUAS PASSADAS para evitar
    # colisão quando a planilha tem tanto uma coluna "TOTAL" standalone
    # (que representa o total das grandes = POS + PB/TS) quanto uma
    # coluna "PEÇAS TOTAIS" (total geral = grandes + médias) — caso
    # contrário ambas viravam "TOTAL" e df["TOTAL"] retornava DataFrame.
    rename_pass1 = {
        "BLINDADORAS": "NOME",
        "BLINDADORA": "NOME",
        "ROTAS": "ROTA",
        "PECAS GRANDES|POS": "POS",
        "PECAS GRANDES|PB/TS": "PB_TS",
        "PECAS GRANDES|PB-TS": "PB_TS",
        "PECAS GRANDES|PB_TS": "PB_TS",
        "PECAS GRANDES|TOTAL": "PEÇAS GRANDES",
        "PECAS GRANDES": "PEÇAS GRANDES",
        "PECAS MEDIAS": "PECAS_MEDIAS",
        "PECAS PEQUENAS": "PECAS_MEDIAS",
        "ENDERECO": "ENDEREÇO",
    }
    df = df.rename(columns=rename_pass1)

    # Pass 2: resolve a ambiguidade do "TOTAL".
    # Caso 1: planilha tem "TOTAL" standalone + "PECAS TOTAIS"
    #   → standalone TOTAL é o total das grandes (vira PEÇAS GRANDES)
    #   → PECAS TOTAIS vira TOTAL canônico (grand total).
    # Caso 2: planilha só tem "PECAS TOTAIS" (formato antigo do print 1)
    #   → PECAS TOTAIS vira TOTAL direto.
    # Caso 3: planilha só tem "TOTAL" (formato muito antigo)
    #   → fica como está.
    if "TOTAL" in df.columns and "PECAS TOTAIS" in df.columns:
        if "PEÇAS GRANDES" not in df.columns:
            df = df.rename(columns={"TOTAL": "PEÇAS GRANDES"})
        else:
            # Já temos PEÇAS GRANDES de outra fonte; o TOTAL standalone
            # é redundante. Remove pra não colidir com PECAS TOTAIS.
            df = df.drop(columns=["TOTAL"])
    if "PECAS TOTAIS" in df.columns:
        df = df.rename(columns={"PECAS TOTAIS": "TOTAL"})

    # Garante colunas mínimas (cria zeradas se ausentes)
    for col in ("POS", "PB_TS", "PEÇAS GRANDES", "PECAS_MEDIAS"):
        if col not in df.columns:
            df[col] = 0

    # Forward-fill em colunas de dados que vêm mescladas no Excel
    # (ROTA, RACK GRANDE, RACK MEDIO). Mesclagem de 2, 3 ou N linhas
    # se torna o mesmo valor em todas as linhas dos blindadores.
    for col in ("ROTA", "RACK GRANDE", "RACK MEDIO", "RACK MÉDIO"):
        if col in df.columns:
            df[col] = df[col].ffill()

    # Conversão numérica robusta
    for col in ("POS", "PB_TS", "PEÇAS GRANDES", "PECAS_MEDIAS"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Reconcilia PEÇAS GRANDES: se a coluna veio zerada (só os subtipos
    # POS/PB_TS estão preenchidos), recalcula como POS + PB_TS.
    if df["PEÇAS GRANDES"].sum() == 0:
        df["PEÇAS GRANDES"] = df["POS"] + df["PB_TS"]

    # TOTAL: respeita o valor da planilha; recalcula apenas onde vier vazio.
    if "TOTAL" not in df.columns:
        df["TOTAL"] = df["PEÇAS GRANDES"] + df["PECAS_MEDIAS"]
    else:
        total_num = pd.to_numeric(df["TOTAL"], errors="coerce")
        df["TOTAL"] = total_num.fillna(df["PEÇAS GRANDES"] + df["PECAS_MEDIAS"])

    # Alias backward-compat para o resto do código que ainda referencia
    # 'PEÇAS PEQUENAS' (solver, contexto da IA, etc.).
    df["PEÇAS PEQUENAS"] = df["PECAS_MEDIAS"]

    # Remove linhas vazias (artefatos comuns ao final da planilha)
    if "NOME" in df.columns:
        df = df.dropna(subset=["NOME"])
        nome_str = df["NOME"].astype(str).str.strip()
        df = df[(nome_str != "") & (~nome_str.str.upper().isin(("NAN", "NONE")))]

    return df.reset_index(drop=True)



# 2. SYSTEM PROMPT PARA A IA
SYSTEM_PROMPT = """
Atue como um Especialista Sênior em Logística e Otimização de Transportes.
Sua missão é analisar os dados de rotas gerados pelo nosso motor de otimização
e responder de forma técnica, prática e resumida.
Seu objetivo principal é sempre buscar e sugerir otimizações financeiras e operacionais.

## RESTRIÇÃO DE ESCOPO (OBRIGATÓRIA):

Você SÓ pode responder perguntas relacionadas a:
- Rotas logísticas, otimização de entregas e roteirização
- Análise dos dados das rotas e VUCs apresentados nesta conversa
- Custos operacionais, racks, peças, janelas de atendimento, capacidades
- Sugestões de reotimização, reagrupamento ou rebalanceamento de rotas

Se a pergunta do usuário NÃO for relacionada a esses tópicos (ex.: programação,
política, receitas, esportes, conselhos pessoais, conhecimento geral, etc.),
responda EXATAMENTE com:

"Posso ajudar apenas com perguntas sobre rotas logísticas, otimização de
entregas e análise dos VUCs apresentados nesta conversa. Reformule sua
pergunta dentro desse escopo, por favor."

Não tente adivinhar, nem responder parcialmente. Recuse educadamente e siga.

Considere o endereço de saída (CD Central) sempre como:
R. José Roberto de Camargo Toledo, 1247 - Suru, Santana de Parnaíba - SP, 06504-150

Sempre que aplicável, apresente resumos, comparações e resultados em formato de tabela Markdown.

## COMO INTERPRETAR OS DADOS (CRÍTICO — LEIA COM ATENÇÃO):

Os dados que você recebe são uma tabela CSV com estas colunas:
- Rota/VUC: identificador do veículo/rota.
- Seq: ordem de entrega dentro da rota.
- Chegada: horário em que o veículo CHEGA ao cliente. Este valor já foi calculado
  pelo motor de otimização (OR-Tools + OSRM) e é a FONTE DE VERDADE.
  NÃO recalcule este horário (a menos que o usuário tenha pedido reotimização
  ou informado uma condição externa que altere a velocidade/serviço).
- Cliente: nome do cliente (vem da coluna BLINDADORAS da planilha).
- POS: quantidade de peças grandes do tipo posterior.
- PB/TS: quantidade de peças grandes do tipo parabrisa / teto solar.
- Grandes: total de peças grandes (POS + PB/TS).
- Médias: quantidade de peças médias entregues naquele ponto.
- Total: quantidade total de peças entregues (Grandes + Médias).
- Endereço: endereço completo do cliente.

Você também pode receber um RESUMO POR VEÍCULO com: km total, peças, racks, tempo e custo.

## MECÂNICA DE CRONOMETRAGEM (CRÍTICO):

Para cada parada na rota, a sequência temporal é:
1. DESLOCAMENTO: o veículo viaja do ponto anterior até o cliente a ~25 km/h.
   O horário de CHEGADA já está calculado na coluna "Chegada".
2. DESCARGA: ao CHEGAR no        cliente, o veículo fica parado 90 minutos (1h30).
3. SAÍDA: Horário de Saída = Chegada + 1h30.
4. O veículo só começa a se deslocar para o PRÓXIMO cliente APÓS a saída.

Exemplo prático de sequência correta:
- Parada 1: Chega 08:27 → Descarga 08:27~09:57 → Sai 09:57
- Deslocamento até parada 2 (ex: 17 min)
- Parada 2: Chega 10:14 → Descarga 10:14~11:44 → Sai 11:44
- Deslocamento até parada 3 (ex: 13 min)
- Parada 3: Chega 11:57 → Descarga 11:57~13:27 → Sai 13:27 → Retorno ao CD

ERRADO: somar 1h30 entre um cliente e outro como se fosse tempo de viagem.
CERTO: 1h30 é tempo PARADO no cliente, o deslocamento é adicional.

## VERIFICAÇÃO DE VIOLAÇÃO DE JANELA:

- Calcule: Horário de Saída = Chegada + 1h30.
- Se Horário de Saída > 18:00 → VIOLAÇÃO.
- Se Horário de Saída <= 18:00 → VIÁVEL.
- Exemplo: Chegada 12:17 → Saída 13:47 → VIÁVEL (13:47 < 18:00).
- Exemplo: Chegada 17:00 → Saída 18:30 → VIOLAÇÃO (18:30 > 18:00).
- SOMENTE marque como violação se Chegada + 90min > 18:00.

## FORMATO DE RESPOSTA PARA REOTIMIZAÇÕES:

Quando o usuário pedir para reotimizar, reagrupar ou reajustar rotas, você DEVE
apresentar o resultado EXATAMENTE neste formato de tabela Markdown:

| Rota/VUC | Seq | Chegada | Cliente | POS | PB/TS | Grandes | Médias | Total | Endereço |
|----------|-----|---------|---------|-----|-------|---------|--------|-------|----------|

Regras obrigatórias para preencher a tabela:
- Rota/VUC: nome do veículo/rota.
- Seq: sequência de entrega (1, 2, 3...), reiniciando para cada rota.
- Chegada: horário estimado de chegada (HH:MM). DEVE respeitar a mecânica:
  saída do ponto anterior (chegada anterior + tempo de descarga) + tempo de
  deslocamento. Para a primeira parada de cada rota, considere saída do CD às 08:00.
- Cliente: nome COMPLETO do cliente exatamente como aparece nos dados.
- POS, PB/TS, Grandes, Médias, Total: copie dos dados originais.
- Endereço: endereço COMPLETO do cliente (copie dos dados originais).

NUNCA omita colunas. NUNCA use "—" se o dado existe nos dados originais.
NUNCA apresente reotimizações em lista, bullet points ou texto corrido.

Após a tabela, inclua um RESUMO OPERACIONAL por veículo:
| Rota/VUC | Paradas | Peças Total | Término Estimado | Status |
|----------|---------|-------------|------------------|--------|
(Término = chegada da última parada + tempo de descarga.
 Status = VIÁVEL ou VIOLAÇÃO.)

## CONDIÇÕES EXTERNAS (AJUSTES DINÂMICOS):

O usuário pode informar condições que alteram os parâmetros padrão.
Quando isso acontecer, ajuste os cálculos PROPORCIONALMENTE e mostre o impacto.
Exemplos de gatilhos e ajustes:

- "Está chovendo" / "trânsito ruim" / "tempo ruim"
  → reduza a velocidade média de 25 km/h para 20 km/h
  (todos os tempos de deslocamento aumentam ~25%).
- "Descarga lenta hoje" / "descarregamento em 2h"
  → use SERVICE_TIME = 120 min (em vez de 90 min).
- "Cliente X demora 3h" → ajuste APENAS o tempo desse cliente.
- "Janela apertada, só até 17:00" → use 17:00 como fim da janela.
- "Caminhão menor, capacidade 40 peças" → use 40 como capacidade.
- "Limite de KM 100 hoje" → use 100 km como limite por VUC.

Quando aplicar um ajuste, mencione EXPLICITAMENTE na resposta:
1. Qual parâmetro mudou e o novo valor.
2. Como isso afetou o resultado (ex.: "com 20 km/h, o término da VUC A
   passa de 17:30 para 18:15 → VIOLAÇÃO").
3. Compare brevemente o cenário padrão vs ajustado.

Se o usuário aplicar múltiplas condições juntas, combine-as e mostre o efeito agregado.

## Restrições Operacionais (padrão):
- Capacidade Máxima: 57 peças por VUC.
- Quilometragem Máxima: 140 km por VUC.
- Janela de Atendimento: 08:00 às 18:00.
- Velocidade média de referência: 25 km/h (para estimativas de deslocamento,
  NÃO para recalcular horários que já existem na tabela).
- Tempo de descarga padrão: 90 min por cliente.

## PROIBIÇÕES:
- NUNCA recalcule os horários de chegada que já existem na tabela original,
  EXCETO se o usuário tiver pedido uma reotimização ou informado uma condição
  externa que altere velocidade/serviço.
- NUNCA confunda tempo de descarga (parado no cliente) com tempo de deslocamento.
- NUNCA omita POS, PB/TS, Grandes, Médias, Total ou Endereço da tabela de reotimização.
- NUNCA marque uma parada como violação se Chegada + tempo_descarga <= fim_da_janela.
"""


# ============================================================
# ESTADO DA SESSÃO
# ============================================================
_SESSION_DEFAULTS = {
    "messages": [],
    "map_layers": [],
    "table_data": None,
    "route_summary": "",
    "veiculos_stats": {},
    "enderecos_nao_encontrados": [],
}
for key, default in _SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def calcular_racks_necessarios(total_pecas: int) -> tuple[int, int, int]:
    """Retorna (n_vucs, racks_g, racks_p) com base na carga."""
    n_vucs = ceil(total_pecas / CAP_MAX_VUC) if total_pecas > 0 else 1
    pecas_ref = total_pecas if total_pecas <= CAP_MAX_VUC else CAP_MAX_VUC
    g = 1 if pecas_ref > 0 else 0
    p = ceil(max(0, pecas_ref - CAP_RACK_G) / CAP_RACK_P)
    return n_vucs, g, p


def construir_grupos_padrao(df_geo: pd.DataFrame) -> list[tuple[str, list[str]]]:
    """
    Monta dinamicamente os grupos do Modelo Padrão com base nas rotas
    presentes na planilha.

    Regra de negócio:
      - Rota 1 + Rota 2 → mesmo grupo
      - Rota 3 + Rota 4 → mesmo grupo
      - Rota 5 em diante → cada rota em seu próprio grupo (isolada)

    Para cada grupo, retorna o label e a lista de códigos aceitos
    (com e sem zero à esquerda) que serão comparados contra a coluna ROTA.
    Grupos sem nenhuma rota correspondente na planilha são omitidos.
    """
    # Extrai os números de rota presentes na planilha, normalizados como
    # strings de inteiros (ex.: "01" e 1.0 viram "1").
    rotas_presentes: set[str] = set()
    for valor in df_geo["ROTA"].dropna().tolist():
        txt = str(valor).strip()
        if not txt:
            continue
        # Pega o primeiro número inteiro contido no valor (lida com "5.0", "01", etc.)
        digitos = "".join(ch for ch in txt.split(".")[0] if ch.isdigit())
        if not digitos:
            continue
        n = int(digitos)
        if n > 0:
            rotas_presentes.add(str(n))

    grupos: list[tuple[str, list[str]]] = []

    # Bloco 1: rotas 1+2
    if {"1", "2"} & rotas_presentes:
        grupos.append(("Rota (1+2)", ["1", "2", "01", "02"]))

    # Bloco 2: rotas 3+4
    if {"3", "4"} & rotas_presentes:
        grupos.append(("Rota (3+4)", ["3", "4", "03", "04"]))

    # Bloco 3+: rotas 5 em diante, cada uma isolada
    rotas_isoladas = sorted(
        (int(r) for r in rotas_presentes if int(r) >= 5)
    )
    for n in rotas_isoladas:
        # Aceita tanto "5" quanto "05" na coluna ROTA da planilha
        codigos = [str(n), f"{n:02d}"]
        grupos.append((f"Rota ({n})", codigos))

    return grupos


def planilha_tem_rota_valida(df: pd.DataFrame) -> bool:
    """
    Verifica se a planilha possui a coluna ROTA preenchida de forma utilizável.
    Retorna True somente se a coluna existir E contiver pelo menos um valor
    não-nulo/não-vazio. Caso contrário (coluna ausente, totalmente vazia ou
    apenas com strings em branco), retorna False — sinalizando que o sistema
    deve fazer fallback automático para clustering geográfico.
    """
    if "ROTA" not in df.columns:
        return False
    # fillna() antes de astype(str) é essencial: sem isso, NaN vira a string
    # literal "nan" do float, que não é trivial de detectar por replace.
    serie = df["ROTA"].fillna("").astype(str).str.strip()
    serie = serie.replace(["nan", "NaN", "None", "<NA>"], "")
    return serie.ne("").any()


def export_as_pdf(df: pd.DataFrame, stats: dict) -> bytes:
    """Gera PDF do relatório operacional: resumo por VUC + tabela detalhada."""

    def _latin(txt) -> str:
        return str(txt).encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    # Título
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "Relatorio Operacional de Rotas", 0, 1, "C")
    pdf.ln(2)

    # Resumo por VUC (KM, peças, tempo) — espelha os cards da UI.
    if stats:
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 8, "Resumo por VUC", 0, 1, "L")

        pdf.set_font("Arial", "B", 9)
        col_widths = [(60, "VUC"), (28, "KM"), (28, "Pecas"),
                      (38, "Tempo"), (36, "Racks")]
        for w, label in col_widths:
            pdf.cell(w, 7, label, 1, 0, "C")
        pdf.ln()

        pdf.set_font("Arial", "", 9)
        for v_name, s in stats.items():
            pdf.cell(60, 7, _latin(v_name)[:35], 1)
            pdf.cell(28, 7, _latin(f"{s.get('km', 0)} km"), 1, 0, "R")
            pdf.cell(28, 7, _latin(f"{s.get('pecas', 0)} pcs"), 1, 0, "R")
            pdf.cell(38, 7, _latin(s.get("tempo", "")), 1, 0, "C")
            pdf.cell(36, 7, _latin(s.get("racks", "")), 1, 0, "C")
            pdf.ln()
        pdf.ln(4)

    # Tabela detalhada (paradas)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, "Tabela Operacional Detalhada", 0, 1, "L")

    pdf.set_font("Arial", "B", 10)
    headers = [("Rota/VUC", 40), ("Seq", 10), ("Cheg.", 15),
               ("Cliente", 50), ("Endereco", 75)]
    for label, w in headers:
        pdf.cell(w, 8, label, 1, 0, "C")
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    for _, row in df.iterrows():
        pdf.cell(40, 8, _latin(row["Rota/VUC"])[:20], 1)
        pdf.cell(10, 8, _latin(row["Seq"]), 1, 0, "C")
        pdf.cell(15, 8, _latin(row["Chegada"]), 1, 0, "C")
        pdf.cell(50, 8, _latin(row["Cliente"])[:25], 1)
        pdf.cell(75, 8, _latin(row["Endereço"])[:45], 1)
        pdf.ln()

    return pdf.output(dest="S").encode("latin-1")


# ============================================================
# OSRM — HELPERS COM CACHE E FALLBACK RÁPIDO
# ============================================================
# Cache em memória para evitar requisições repetidas ao OSRM público.
# Chave: tupla (lat1, lon1, lat2, lon2) arredondada -> dict com distance_km e duration_min.
_OSRM_CACHE: dict[tuple, dict] = {}

# Endpoint do OSRM público.
# IMPORTANTE: usamos HTTPS porque proxies corporativos costumam bloquear HTTP
# de saída (porta 80) para hosts desconhecidos. O servidor público OSRM aceita
# tanto http quanto https.
# Para subir um servidor próprio em Docker basta trocar para "http://localhost:5000".
OSRM_BASE_URL = "https://router.project-osrm.org"

# Timeout: (connect, read). connect curto evita travar em proxy bloqueando.
OSRM_CONNECT_TIMEOUT = 3
OSRM_READ_TIMEOUT = 4

# Pausa curta entre chamadas OSRM bem-sucedidas (respeita servidor público).
OSRM_THROTTLE_SEC = 0.3

# Flag global: se a primeira chamada OSRM falhar, assumimos que o servidor
# está fora do ar (ou bloqueado pela rede) e desabilitamos o resto da execução.
_OSRM_DISABLED = {"flag": False, "consecutive_failures": 0}

# Honra variáveis HTTP_PROXY / HTTPS_PROXY se estiverem definidas no .env
# (útil em redes corporativas que exigem proxy explícito).
_PROXY_CONFIG = {
    "http": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
    "https": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
}
# Remove None para o requests não reclamar
_PROXY_CONFIG = {k: v for k, v in _PROXY_CONFIG.items() if v}


def osrm_pair_distance(p1: list, p2: list) -> dict | None:
    """
    Consulta o OSRM para calcular distância (km) e duração (min) entre dois
    pontos [lat, lon]. Implementa cache em memória e fallback rápido.

    Retorna dict {distance_km, duration_min} em sucesso, ou None em falha
    (chamador deve aplicar fallback euclidiano).
    """
    # Se já desabilitamos OSRM nesta execução, retorna None imediatamente
    if _OSRM_DISABLED["flag"]:
        return None

    # Chave de cache com 5 casas decimais (~1m de precisão)
    cache_key = (
        round(p1[0], 5), round(p1[1], 5),
        round(p2[0], 5), round(p2[1], 5),
    )
    if cache_key in _OSRM_CACHE:
        return _OSRM_CACHE[cache_key]

    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=false"
    )

    log(f"  → OSRM call: {p1[0]:.4f},{p1[1]:.4f} → {p2[0]:.4f},{p2[1]:.4f}")
    t0 = time.time()
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "OtimizadorLogistico/2.0"},
            timeout=(OSRM_CONNECT_TIMEOUT, OSRM_READ_TIMEOUT),
            proxies=_PROXY_CONFIG or None,
        )
        r.raise_for_status()
        data = r.json()
        resultado = {
            "distance_km": data["routes"][0]["distance"] / 1000,
            "duration_min": data["routes"][0]["duration"] / 60,
        }
        _OSRM_CACHE[cache_key] = resultado
        _OSRM_DISABLED["consecutive_failures"] = 0
        log(f"  ← OSRM ok ({time.time()-t0:.1f}s, {resultado['distance_km']:.2f}km)")
        time.sleep(OSRM_THROTTLE_SEC)
        return resultado
    except Exception as e:
        log(f"  ✗ OSRM falhou ({time.time()-t0:.1f}s): {type(e).__name__}: {e}")
        _OSRM_DISABLED["consecutive_failures"] = (
            _OSRM_DISABLED.get("consecutive_failures", 0) + 1
        )
        if _OSRM_DISABLED["consecutive_failures"] >= 2:
            _OSRM_DISABLED["flag"] = True
            log("  ⚠ OSRM desabilitado pelo restante da execução")
        return None


# ============================================================
# MÓDULO DE IA — ANTHROPIC CLAUDE
# ============================================================
def get_claude_response(messages: list, route_context: str) -> str:
    """
    Envia histórico completo ao Claude via SDK oficial da Anthropic.
    O contexto da rota é injetado na primeira mensagem do usuário para
    que fique disponível em toda a conversa sem repetir a cada turno.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY não encontrada. "
            "Defina-a no arquivo .env na raiz do projeto."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    api_messages = []
    for i, msg in enumerate(messages):
        if i == 0 and msg["role"] == "user":
            content = f"DADOS DAS ROTAS:\n{route_context}\n\n{msg['content']}"
        else:
            content = msg["content"]
        api_messages.append({"role": msg["role"], "content": content})

    message = client.messages.create(
        model=MODELO_IA,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=api_messages,
    )

    return "".join(
        block.text for block in message.content if block.type == "text"
    )


# ============================================================
# GEOCODIFICAÇÃO
# ============================================================
@st.cache_data(show_spinner=False)
def geocode_addresses(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Geocodifica endereços via Nominatim (OpenStreetMap).

    Usa cache SQLite local: endereços já consultados saltam o Nominatim
    (~1s economizado por cliente). Endereço inédito é consultado online,
    validado contra o bounding box BR e gravado no cache.
    """
    geolocator = Nominatim(user_agent="log_opt_v2_claude")

    if "ENDEREÇO" not in df.columns:
        st.error("Coluna 'ENDEREÇO' não encontrada na planilha!")
        return pd.DataFrame(), []

    df["search_addr"] = df["ENDEREÇO"].astype(str) + ", Brasil"
    lats, lons = [], []
    nao_encontrados = []
    progress_bar = st.progress(0, text="Localizando endereços no mapa...")
    total_rows = len(df)
    hits_cache = 0

    for idx, (_, row) in enumerate(df.iterrows()):
        endereco = str(row["search_addr"])
        progress_bar.progress(
            (idx + 1) / total_rows,
            text=f"Geocodificando ({idx + 1}/{total_rows}): {row.get('NOME', 'Cliente')}",
        )

        # 1ª tentativa: cache local (SQLite)
        cached = geocache_get(endereco)
        if cached is not None:
            lats.append(cached[0])
            lons.append(cached[1])
            hits_cache += 1
            continue  # pula Nominatim e o sleep(1.0)

        # Cache miss → Nominatim
        try:
            loc = geolocator.geocode(endereco, timeout=10)
            if loc and coord_no_brasil(loc.latitude, loc.longitude):
                lats.append(loc.latitude)
                lons.append(loc.longitude)
                geocache_set(endereco, loc.latitude, loc.longitude)
            else:
                lats.append(None)
                lons.append(None)
                motivo = (
                    f"Geocodificado fora do Brasil ({loc.latitude:.3f}, {loc.longitude:.3f})"
                    if loc else "Endereço não encontrado"
                )
                nao_encontrados.append({
                    "Cliente": row.get("NOME", "N/A"),
                    "Rota": row.get("ROTA", "N/A"),
                    "Endereço": row["ENDEREÇO"],
                    "Motivo": motivo,
                })
        except Exception:
            lats.append(None)
            lons.append(None)
            nao_encontrados.append({
                "Cliente": row.get("NOME", "N/A"),
                "Rota": row.get("ROTA", "N/A"),
                "Endereço": row["ENDEREÇO"],
                "Motivo": "Erro de geocodificação (timeout/exceção)",
            })

        # Throttle Nominatim só em chamadas reais (cache hit pula).
        time.sleep(1.0)

    log(f"  Geocoding: {hits_cache}/{total_rows} hits no cache ({hits_cache/max(1,total_rows)*100:.0f}%)")

    progress_bar.empty()
    df["lat"], df["lon"] = lats, lons
    return df.dropna(subset=["lat", "lon"]), nao_encontrados


# ============================================================
# SOLVER OR-TOOLS
# ============================================================
def solve_group_route(df_subset: pd.DataFrame, vehicle_name: str) -> dict | None:
    """Resolve TSP para um grupo de entregas usando OR-Tools."""
    if df_subset.empty:
        return None

    # Garante colunas POS/PB_TS no df_subset (planilhas antigas não têm)
    for col in ("POS", "PB_TS"):
        if col not in df_subset.columns:
            df_subset = df_subset.copy()
            df_subset[col] = 0

    df_consolidado = (
        df_subset
        .groupby(["lat", "lon", "NOME", "ENDEREÇO"])
        .agg({
            "POS": "sum",
            "PB_TS": "sum",
            "PEÇAS GRANDES": "sum",
            "PEÇAS PEQUENAS": "sum",
            "TOTAL": "sum",
        })
        .reset_index()
    )

    coords = df_consolidado[["lat", "lon"]].values.tolist()
    locs = [DEPOT_COORDS] + coords

    manager = pywrapcp.RoutingIndexManager(len(locs), 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        dist_km = (
            sqrt(
                (locs[from_node][0] - locs[to_node][0]) ** 2
                + (locs[from_node][1] - locs[to_node][1]) ** 2
            )
            * 111
            * 1.3
        )
        return int((dist_km / AVG_SPEED_KMH) * 60)

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.time_limit.seconds = 10

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        return None

    # Reconstruir sequência
    index = routing.Start(0)
    nodes_sequence = []
    while not routing.IsEnd(index):
        nodes_sequence.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))

    total_dist_km = 0.0
    current_time_min = 0.0
    paradas_resultado = []
    arrival_at_stop = 0.0

    for i in range(len(nodes_sequence) - 1):
        p1, p2 = locs[nodes_sequence[i]], locs[nodes_sequence[i + 1]]

        # Usa helper com cache + retry + throttle. Se falhar, cai no fallback
        # euclidiano (linha reta * 1.3) sem travar a aplicação.
        osrm_result = osrm_pair_distance(p1, p2)
        if osrm_result is not None:
            step_dist = osrm_result["distance_km"]
            step_time = osrm_result["duration_min"]
        else:
            step_dist = (
                sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) * 111 * 1.3
            )
            step_time = (step_dist / AVG_SPEED_KMH) * 60

        arrival_at_stop = current_time_min + step_time
        node_idx = nodes_sequence[i + 1]

        if node_idx > 0:
            cliente = df_consolidado.iloc[node_idx - 1]
            paradas_resultado.append({
                "cliente": cliente["NOME"],
                "endereco": cliente["ENDEREÇO"],
                "lat": cliente["lat"],
                "lon": cliente["lon"],
                "pos": cliente["POS"],
                "pb_ts": cliente["PB_TS"],
                "pecas_g": cliente["PEÇAS GRANDES"],
                "pecas_p": cliente["PEÇAS PEQUENAS"],
                "total": cliente["TOTAL"],
                "arrival_min": arrival_at_stop,
            })

        current_time_min = arrival_at_stop + SERVICE_TIME_MIN
        total_dist_km += step_dist

    return {
        "paradas": paradas_resultado,
        "total_km": total_dist_km,
        "total_time_min": arrival_at_stop,
    }


# ============================================================
# CVRP GLOBAL — Modo Criativo "pesquisa operacional"
# ============================================================
def solve_vrp_global(df_geo: pd.DataFrame) -> list[dict]:
    """CVRP completo com múltiplas dimensões e função objetivo financeira.

    Substitui o greedy + rebalance + per-VUC TSP do Modo Criativo. O solver
    do OR-Tools decide alocação E roteamento conjuntamente, minimizando
    o custo total da AGP:
        custo = CUSTO_FIXO_VUC × N_VUCs + CUSTO_KM × Σ KM

    Restrições rígidas (o solver nunca produz solução que as viole):
        - capacidade: ≤ CAP_MAX_VUC (57) peças por VUC
        - distância:  ≤ MAX_KM_VUC (140) km por VUC
        - tempo:      ≤ MAX_TIME_VUC_MIN (600) min por VUC (janela 18:00)

    Penalização de span (SetGlobalSpanCostCoefficient) na dimensão KM
    força o equilíbrio entre veículos — sem precisar de pós-processamento.

    Metaheurística: GUIDED_LOCAL_SEARCH (≈LNS) com time_limit segundos
    de busca. Faz 2-opt, or-opt e cross-exchange entre rotas
    automaticamente.

    Clientes "oversized" (> 57 pç) são tratados antes do solver:
    cada um vira um VUC dedicado com aviso.

    Retorna lista de VUCs já resolvidos, cada um:
        {"label": str, "paradas": [...], "total_km": float, "total_time_min": float}
    """
    df_consolidado = (
        df_geo.groupby(["lat", "lon", "NOME", "ENDEREÇO"])
        .agg({
            "POS": "sum", "PB_TS": "sum",
            "PEÇAS GRANDES": "sum", "PEÇAS PEQUENAS": "sum", "TOTAL": "sum",
        })
        .reset_index()
    )
    df_consolidado["TOTAL"] = df_consolidado["TOTAL"].astype(int)

    # Separa oversized (TOTAL > CAP) — cada um vira VUC dedicado
    df_oversized = df_consolidado[df_consolidado["TOTAL"] > CAP_MAX_VUC]
    df_normal = df_consolidado[df_consolidado["TOTAL"] <= CAP_MAX_VUC].reset_index(drop=True)

    vucs_resolvidos: list[dict] = []
    label_idx = 0

    def _proximo_label() -> str:
        nonlocal label_idx
        lbl = f"VUC Otimizado {chr(65 + (label_idx % 26))}"
        label_idx += 1
        return lbl

    def _resolver_e_montar_vuc(nodes_seq: list[int], cons: pd.DataFrame) -> dict | None:
        """Percorre nodes_seq (já em ordem) calculando arrival + KM via OSRM."""
        if len(nodes_seq) < 2:
            return None
        total_km = 0.0
        cur_time = 0.0
        arrival = 0.0
        paradas = []

        locs_local = [DEPOT_COORDS] + cons[["lat", "lon"]].values.tolist()

        # nodes_seq não inclui o retorno ao depot — adicionamos manualmente
        full_seq = list(nodes_seq) + [0]

        for i in range(len(full_seq) - 1):
            p1, p2 = locs_local[full_seq[i]], locs_local[full_seq[i + 1]]
            osrm = osrm_pair_distance(p1, p2)
            if osrm is not None:
                step_km = osrm["distance_km"]
                step_time = osrm["duration_min"]
            else:
                step_km = (
                    sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) * 111 * 1.3
                )
                step_time = (step_km / AVG_SPEED_KMH) * 60

            arrival = cur_time + step_time
            node_idx = full_seq[i + 1]
            if node_idx > 0:
                cliente = cons.iloc[node_idx - 1]
                paradas.append({
                    "cliente": cliente["NOME"],
                    "endereco": cliente["ENDEREÇO"],
                    "lat": cliente["lat"],
                    "lon": cliente["lon"],
                    "pos": int(cliente["POS"]),
                    "pb_ts": int(cliente["PB_TS"]),
                    "pecas_g": int(cliente["PEÇAS GRANDES"]),
                    "pecas_p": int(cliente["PEÇAS PEQUENAS"]),
                    "total": int(cliente["TOTAL"]),
                    "arrival_min": arrival,
                })
                cur_time = arrival + SERVICE_TIME_MIN
            total_km += step_km

        # arrival_min do "último cliente" é o que importa pro check da janela.
        # Pegamos do penúltimo ponto da sequência (último cliente antes do
        # retorno ao depot).
        arrival_last = paradas[-1]["arrival_min"] if paradas else 0.0
        return {
            "paradas": paradas,
            "total_km": total_km,
            "total_time_min": arrival_last,
        }

    # --- VUCs dedicados para oversized ---
    for _, row_over in df_oversized.iterrows():
        cons_um = pd.DataFrame([row_over]).reset_index(drop=True)
        res = _resolver_e_montar_vuc([0, 1], cons_um)
        if res:
            res["label"] = _proximo_label()
            vucs_resolvidos.append(res)
            log(
                f"  ⚠ Cliente oversized '{row_over['NOME']}' "
                f"({int(row_over['TOTAL'])} pç) → VUC dedicado"
            )

    # --- Se sobrou cliente normal, monta o problema CVRP ---
    if df_normal.empty:
        return vucs_resolvidos

    n_clientes = len(df_normal)
    locs = [DEPOT_COORDS] + df_normal[["lat", "lon"]].values.tolist()
    n_nodes = len(locs)
    n_vehicles = n_clientes  # upper bound: pior caso 1 VUC por cliente

    # Matriz de distância em metros (Euclidean × 1.3, int). Esta é a
    # mesma heurística usada pelo solver TSP atual — manter consistente.
    def dist_m(i: int, j: int) -> int:
        return int(
            sqrt((locs[i][0] - locs[j][0]) ** 2 + (locs[i][1] - locs[j][1]) ** 2)
            * 111 * 1.3 * 1000
        )

    distance_matrix = [[dist_m(i, j) for j in range(n_nodes)] for i in range(n_nodes)]
    demands = [0] + df_normal["TOTAL"].astype(int).tolist()

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # --- Callback de trânsito (custo do arco = metros)
    def transit_cb(from_idx: int, to_idx: int) -> int:
        return distance_matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_cb_idx = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # --- Custo fixo por VUC (em "metros equivalentes")
    # 1 unidade de custo = 1 metro = R$ CUSTO_KM/1000.
    # Logo: CUSTO_FIXO_VUC R$ = CUSTO_FIXO_VUC / CUSTO_KM * 1000 metros.
    fixed_cost = int(CUSTO_FIXO_VUC / CUSTO_KM * 1000)
    routing.SetFixedCostOfAllVehicles(fixed_cost)

    # --- Dimensão CAPACIDADE (≤ 57 peças)
    def demand_cb(from_idx: int) -> int:
        return demands[manager.IndexToNode(from_idx)]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx, 0, [CAP_MAX_VUC] * n_vehicles, True, "Capacity",
    )

    # --- Dimensão DISTÂNCIA (≤ 140 km) + balanceamento via span
    routing.AddDimension(
        transit_cb_idx, 0, int(MAX_KM_VUC * 1000), True, "Distance",
    )
    routing.GetDimensionOrDie("Distance").SetGlobalSpanCostCoefficient(
        VRP_SPAN_COEFFICIENT
    )

    # --- Dimensão TEMPO (≤ 600 min, inclui descarga de 90min/parada)
    def time_cb(from_idx: int, to_idx: int) -> int:
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        dist_meters = distance_matrix[from_node][to_node]
        travel_min = (dist_meters / 1000.0) / AVG_SPEED_KMH * 60
        service = SERVICE_TIME_MIN if to_node != 0 else 0
        return int(travel_min + service)

    time_cb_idx = routing.RegisterTransitCallback(time_cb)
    routing.AddDimension(time_cb_idx, 0, MAX_TIME_VUC_MIN, True, "Time")

    # --- Parâmetros de busca (LNS via GUIDED_LOCAL_SEARCH)
    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    sp.time_limit.seconds = VRP_TIME_LIMIT_SEC

    log(
        f"VRP global: {n_clientes} clientes, até {n_vehicles} veículos, "
        f"{VRP_TIME_LIMIT_SEC}s de busca, fixed_cost={fixed_cost}"
    )
    t0 = time.time()
    solution = routing.SolveWithParameters(sp)
    log(f"  VRP resolveu em {time.time() - t0:.1f}s")

    if not solution:
        log("  ⚠ VRP não encontrou solução. Falhando para nenhum VUC.")
        return vucs_resolvidos

    # --- Extrai cada veículo usado
    custo_total_metros = solution.ObjectiveValue()
    log(f"  Objetivo do solver: {custo_total_metros} (metros equivalentes)")

    for v in range(n_vehicles):
        idx = routing.Start(v)
        proximo = solution.Value(routing.NextVar(idx))
        if routing.IsEnd(proximo):
            continue  # veículo não usado

        nodes_seq = []
        while not routing.IsEnd(idx):
            nodes_seq.append(manager.IndexToNode(idx))
            idx = solution.Value(routing.NextVar(idx))

        res = _resolver_e_montar_vuc(nodes_seq, df_normal)
        if res is None or not res["paradas"]:
            continue
        res["label"] = _proximo_label()
        vucs_resolvidos.append(res)

    log(f"VRP global: {len(vucs_resolvidos)} VUCs gerados")
    return vucs_resolvidos


# ============================================================
# BARRA LATERAL
# ============================================================
# Sidebar — PARTE 1: logo, upload, modo. Sempre renderizada ANTES do
# painel principal (precisa de uploaded_file e modo_otimizacao para o
# botão de otimização funcionar).
with st.sidebar:
    if os.path.exists(_AGP_LOGO):
        st.image(_AGP_LOGO, use_container_width=True)
        st.divider()

    st.header("📂 Operação")
    uploaded_file = st.file_uploader("Suba sua planilha", type=["xlsx", "csv"])

    st.divider()
    modo_otimizacao = st.radio(
        "🛠️ Modo de Otimização",
        ["Modelo Padrão", "Modo Criativo"],
    )


# ============================================================
# PAINEL PRINCIPAL
# ============================================================
st.title("🚛 Otimizador Logístico Inteligente")

if uploaded_file:
    if st.button("🚀 GERAR OTIMIZAÇÃO", type="primary"):
        log("=" * 60)
        log("INICIANDO OTIMIZAÇÃO")
        log(f"OSRM base URL: {OSRM_BASE_URL}")
        log(f"Proxy config: {_PROXY_CONFIG if _PROXY_CONFIG else 'nenhum'}")
        log("=" * 60)

        # Limpa cache OSRM e flag de disabled da execução anterior.
        _OSRM_CACHE.clear()
        _OSRM_DISABLED["flag"] = False
        _OSRM_DISABLED["consecutive_failures"] = 0

        status_box = st.status("Processando otimização...", expanded=True)
        status_box.write("📖 Lendo planilha...")
        log("Lendo planilha...")

        # Leitura da planilha — suporta formato novo (multi-header com
        # POS / PB-TS / PEÇAS MEDIAS / PEÇAS TOTAIS) e formato antigo
        # (PEÇAS GRANDES / PEÇAS PEQUENAS). Detecção automática.
        df_raw = normalizar_planilha(uploaded_file)

        # ----------------------------------------------------
        # DETECÇÃO AUTOMÁTICA: planilha sem coluna ROTA preenchida
        # cai automaticamente para clustering geográfico, ignorando
        # a seleção do usuário no rádio lateral.
        # ----------------------------------------------------
        tem_rota = planilha_tem_rota_valida(df_raw)
        if not tem_rota:
            modo_efetivo = "Modo Criativo"
            st.info(
                "ℹ️ Planilha enviada **sem coluna ROTA** preenchida. "
                "O sistema ativou automaticamente o **clustering geográfico** "
                "(equivalente ao Modo Criativo), ignorando a seleção lateral."
            )
        else:
            modo_efetivo = modo_otimizacao

        status_box.write(
            f"📍 Geocodificando {len(df_raw)} endereço(s) "
            f"(~1s por endereço, política Nominatim)..."
        )
        log(f"Iniciando geocodificação de {len(df_raw)} endereços...")
        df_geo, erros_geo = geocode_addresses(df_raw)
        st.session_state.enderecos_nao_encontrados = erros_geo
        log(f"Geocodificação concluída: {len(df_geo)} ok, {len(erros_geo)} erros")
        status_box.write(
            f"✅ {len(df_geo)} endereço(s) localizado(s) "
            f"({len(erros_geo)} não encontrado(s))"
        )

        vucs_vagas = []
        # Modo Criativo agora resolve VUCs no próprio solver VRP global
        # (alocação + roteamento conjuntamente). Estes já vêm com paradas,
        # KM e arrival_min calculados — o loop principal os usa direto,
        # sem rodar solve_group_route de novo.
        vucs_pre_resolvidos: list[dict] = []

        # --- MODO PADRÃO: Agrupamento por Rota ---
        if modo_efetivo == "Modelo Padrão":
            # Sanity check: avisa se há clientes que sozinhos excedem
            # a capacidade do VUC. No Modelo Padrão o cliente é alocado
            # mesmo assim (não trava), mas o VUC sai com excesso de carga.
            clientes_oversized = df_geo[df_geo["TOTAL"] > CAP_MAX_VUC]
            if not clientes_oversized.empty:
                nomes = clientes_oversized["NOME"].tolist()
                log(
                    f"⚠ AVISO: {len(clientes_oversized)} cliente(s) com carga "
                    f"acima de {CAP_MAX_VUC} peças (capacidade do VUC): {nomes}"
                )
                st.warning(
                    f"⚠️ {len(clientes_oversized)} cliente(s) excedem a "
                    f"capacidade de {CAP_MAX_VUC} peças por VUC: "
                    f"**{', '.join(nomes)}**. O sistema continuou o agrupamento "
                    f"normalmente, mas o(s) VUC(s) afetado(s) sairá(ão) com "
                    f"excesso de carga. Avalie dividir a entrega em múltiplos "
                    f"dias para esses clientes."
                )

            # Regra de negócio:
            #   1+2 juntas, 3+4 juntas, 5 em diante cada uma isolada.
            # Construído dinamicamente a partir das rotas presentes na planilha,
            # então funciona com qualquer quantidade de rotas (1..N).
            groups_config = construir_grupos_padrao(df_geo)
            for v_label, codes in groups_config:
                sub_total = df_geo[df_geo["ROTA"].astype(str).isin(codes)]
                if sub_total.empty:
                    continue
                vuc_atual, carga_atual = [], 0
                for _, row in sub_total.iterrows():
                    if carga_atual + row["TOTAL"] > CAP_MAX_VUC and vuc_atual:
                        vucs_vagas.append((v_label, vuc_atual))
                        vuc_atual, carga_atual = [], 0
                    vuc_atual.append(row)
                    carga_atual += row["TOTAL"]
                if vuc_atual:
                    vucs_vagas.append((v_label, vuc_atual))

        # --- MODO CRIATIVO: CVRP global do OR-Tools ---
        # Substitui o greedy + rebalance + per-VUC TSP por uma única
        # chamada ao solver completo, que minimiza a função objetivo:
        #     custo = CUSTO_FIXO_VUC × N_VUCs + CUSTO_KM × Σ KM
        # respeitando as restrições rígidas de 57 peças, 140 km e
        # janela 08:00–18:00 simultaneamente.
        else:
            clientes_oversized = df_geo[df_geo["TOTAL"] > CAP_MAX_VUC]
            if not clientes_oversized.empty:
                nomes = clientes_oversized["NOME"].tolist()
                st.warning(
                    f"⚠️ {len(clientes_oversized)} cliente(s) excedem a "
                    f"capacidade de {CAP_MAX_VUC} peças por VUC: "
                    f"**{', '.join(nomes)}**. Cada um recebeu um VUC dedicado."
                )

            status_box.write(
                f"🧠 Resolvendo CVRP (capacidade, KM, tempo) com "
                f"GUIDED_LOCAL_SEARCH por até {VRP_TIME_LIMIT_SEC}s..."
            )
            vucs_pre_resolvidos = solve_vrp_global(df_geo)

        log(f"Agrupamento concluído: {len(vucs_vagas) + len(vucs_pre_resolvidos)} VUCs")
        for i, (lbl, rows) in enumerate(vucs_vagas, 1):
            log(f"  [Padrão] VUC {i}: {lbl} - {len(rows)} paradas")
        for i, vuc in enumerate(vucs_pre_resolvidos, 1):
            log(
                f"  [VRP] VUC {i}: {vuc['label']} - "
                f"{len(vuc['paradas'])} paradas, {vuc['total_km']:.1f}km"
            )

        n_total_vucs = len(vucs_vagas) + len(vucs_pre_resolvidos)
        status_box.write(
            f"🚛 {n_total_vucs} veículo(s) definido(s). "
            f"Calculando rotas e desenhando no mapa..."
        )

        # --- MONTAR MAPA E TABELA ---
        new_layers, new_table_rows, new_stats = [], [], {}
        violacoes_janela: list[dict] = []  # VUCs que terminam após 18:00
        violacoes_km: list[dict] = []      # VUCs com KM real > MAX_KM_VUC
        colors = [
            [255, 0, 0], [0, 110, 255], [0, 160, 0],
            [255, 165, 0], [128, 0, 128], [255, 0, 255], [0, 255, 255],
        ]
        color_idx = 0

        # Marcador do CD Central
        new_layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=[{
                    "lat": DEPOT_COORDS[0],
                    "lon": DEPOT_COORDS[1],
                    "NOME": "CD CENTRAL",
                    "ENDEREÇO": DEPOT_ADDRESS,
                }],
                get_position="[lon, lat]",
                get_fill_color=[0, 0, 0],
                get_radius=250,
                pickable=True,
            )
        )

        # Unifica as duas fontes:
        #   - Modelo Padrão: roda solve_group_route por grupo agora
        #   - Modo Criativo (VRP): já vem pré-resolvido
        # Cada entrada em vucs_finais é dict com label + paradas + KMs.
        vucs_finais: list[dict] = []

        for v_label, vuc_rows in vucs_vagas:
            df_vuc = pd.DataFrame(vuc_rows)
            tmp_label = f"{v_label} {chr(65 + (color_idx % 26))}"
            log(f"--- [Padrão] {tmp_label} ({len(df_vuc)} paradas) ---")
            status_box.write(
                f"  ⚙️ Processando {tmp_label} ({len(df_vuc)} parada(s))..."
            )
            t_solver = time.time()
            res = solve_group_route(df_vuc, tmp_label)
            log(f"  solve_group_route: {time.time()-t_solver:.1f}s")
            if not res:
                log("  ✗ res vazio, pulando VUC")
                continue
            color_idx += 1
            vucs_finais.append({
                "label": tmp_label,
                "paradas": res["paradas"],
                "total_km": res["total_km"],
                "total_time_min": res["total_time_min"],
            })

        # VUCs pré-resolvidos do CVRP global já estão prontos.
        vucs_finais.extend(vucs_pre_resolvidos)

        for vuc_idx, vuc_data in enumerate(vucs_finais, 1):
            final_label = vuc_data["label"]
            paradas = vuc_data["paradas"]
            log(f"--- VUC {vuc_idx}/{len(vucs_finais)}: {final_label} ({len(paradas)} paradas) ---")
            status_box.write(
                f"  🗺️ Desenhando {final_label} ({len(paradas)} parada(s))..."
            )

            res = {
                "paradas": paradas,
                "total_km": vuc_data["total_km"],
                "total_time_min": vuc_data["total_time_min"],
            }

            color = colors[color_idx % len(colors)]
            color_idx += 1
            total_p = sum(p["total"] for p in paradas)
            _, rg, rp = calcular_racks_necessarios(total_p)

            # Checa violação da janela 18:00: chegada na última parada
            # + 90min de descarga deve fechar antes das 10h após 08:00.
            fim_descarga_min = paradas[-1]["arrival_min"] + SERVICE_TIME_MIN if paradas else 0
            if fim_descarga_min > 600:
                hh = int(fim_descarga_min // 60) + START_HOUR
                mm = int(fim_descarga_min % 60)
                violacoes_janela.append({
                    "VUC": final_label,
                    "Paradas": len(paradas),
                    "Peças": int(total_p),
                    "Término estimado": f"{hh:02d}:{mm:02d}",
                })
                log(f"  ⚠ {final_label} termina {hh:02d}:{mm:02d} (> 18:00)")

            # Checa violação do limite de 140km. O greedy + rebalance já
            # respeitam o limite com estimativa euclidiana ×1.3, mas a
            # quilometragem real (OSRM) pode ser ligeiramente maior pelas
            # ruas. Se passar do cap, registra para alerta visual.
            km_real = round(res["total_km"], 2)
            if km_real > MAX_KM_VUC:
                violacoes_km.append({
                    "VUC": final_label,
                    "Paradas": len(paradas),
                    "Peças": int(total_p),
                    "KM real": km_real,
                    "Limite": MAX_KM_VUC,
                })
                log(f"  ⚠ {final_label} fechou com {km_real}km (> {MAX_KM_VUC}km)")

            new_stats[final_label] = {
                "km": round(res["total_km"], 2),
                "tempo": (
                    f"{int(res['total_time_min'] // 60)}h "
                    f"{int(res['total_time_min'] % 60)}min"
                ),
                "contratacao": round(CUSTO_FIXO_VUC, 2),
                "custo": round(CUSTO_FIXO_VUC, 2),
                "pecas": int(total_p),
                "racks": f"{rg}G e {rp}P",
            }

            pts = [DEPOT_COORDS] + [[p["lat"], p["lon"]] for p in paradas]

            # Se OSRM já caiu nesta execução, pula direto pro fallback (linha
            # reta) sem fazer nova chamada. Evita esperar timeout em vão.
            if _OSRM_DISABLED["flag"]:
                log(f"  Mapa: OSRM desabilitado, usando linha reta")
                path = [[p[1], p[0]] for p in pts]
            else:
                locs_url = ";".join(f"{p[1]},{p[0]}" for p in pts)
                log(f"  Mapa: chamando OSRM com {len(pts)} pontos...")
                t_map = time.time()
                try:
                    osrm_route_url = (
                        f"{OSRM_BASE_URL}/route/v1/driving/"
                        f"{locs_url}?overview=simplified&geometries=polyline"
                    )
                    resp = requests.get(
                        osrm_route_url,
                        headers={"User-Agent": "OtimizadorLogistico/2.0"},
                        timeout=(OSRM_CONNECT_TIMEOUT, OSRM_READ_TIMEOUT + 2),
                        proxies=_PROXY_CONFIG or None,
                    )
                    resp.raise_for_status()
                    route_data = resp.json()
                    path = [
                        [p[1], p[0]]
                        for p in polyline.decode(route_data["routes"][0]["geometry"])
                    ]
                    log(f"  Mapa: ok ({time.time()-t_map:.1f}s, {len(path)} pontos)")
                    time.sleep(OSRM_THROTTLE_SEC)
                except Exception as e:
                    log(f"  Mapa: falhou ({time.time()-t_map:.1f}s) {type(e).__name__}: {e}")
                    path = [[p[1], p[0]] for p in pts]
                    _OSRM_DISABLED["flag"] = True

            new_layers.append(
                pdk.Layer(
                    "PathLayer",
                    data=[{"path": path}],
                    get_path="path",
                    get_width=5,
                    get_color=color,
                    width_min_pixels=3,
                )
            )

            for seq, parada in enumerate(paradas, 1):
                arrival_str = (
                    datetime.now().replace(hour=START_HOUR, minute=0)
                    + timedelta(minutes=parada["arrival_min"])
                ).strftime("%H:%M")

                new_table_rows.append({
                    "Rota/VUC": final_label,
                    "Seq": seq,
                    "Chegada": arrival_str,
                    "Cliente": parada["cliente"],
                    "POS": int(parada.get("pos", 0)),
                    "PB/TS": int(parada.get("pb_ts", 0)),
                    "Grandes": int(parada["pecas_g"]),
                    "Médias": int(parada["pecas_p"]),
                    "Total": int(parada["total"]),
                    "Endereço": parada["endereco"],
                })

                marker = {
                    "lat": parada["lat"],
                    "lon": parada["lon"],
                    "NOME": parada["cliente"],
                    "ENDEREÇO": parada["endereco"],
                    "seq_num": str(seq),
                }
                new_layers.append(
                    pdk.Layer(
                        "ScatterplotLayer",
                        data=[marker],
                        get_position="[lon, lat]",
                        get_fill_color=color,
                        get_radius=150,
                        radius_min_pixels=8,
                        pickable=True,
                    )
                )
                new_layers.append(
                    pdk.Layer(
                        "TextLayer",
                        data=[marker],
                        get_position="[lon, lat]",
                        get_text="seq_num",
                        get_size=20,
                        size_min_pixels=15,
                        get_color=[255, 255, 255],
                    )
                )

        st.session_state.map_layers = new_layers
        st.session_state.table_data = pd.DataFrame(new_table_rows)
        st.session_state.veiculos_stats = new_stats

        log("=" * 60)
        log(f"OTIMIZAÇÃO CONCLUÍDA - {len(new_stats)} VUCs")
        log("=" * 60)

        status_box.update(
            label="✅ Otimização concluída!",
            state="complete",
            expanded=False,
        )

        # Avisa se o servidor OSRM público estava fora do ar.
        # As distâncias e desenhos são aproximados (linha reta) nesse caso.
        if _OSRM_DISABLED["flag"]:
            st.warning(
                "⚠️ O servidor público de roteamento (OSRM) está instável "
                "no momento. As distâncias e o traçado das rotas no mapa "
                "foram calculados em **linha reta aproximada**. Os agrupamentos "
                "de clientes por VUC continuam corretos. Tente novamente mais "
                "tarde para obter rotas precisas, ou considere subir um servidor "
                "OSRM próprio em Docker."
            )

        # Avisa VUCs que terminam após 18:00 (clustering prioriza
        # minimizar veículos, então pode estourar janela em rotas
        # com clientes muito distantes).
        if violacoes_janela:
            st.warning(
                f"⚠️ **{len(violacoes_janela)} VUC(s) terminam após 18:00**. "
                "A otimização priorizou minimizar veículos (caminhões cheios). "
                "Avalie se vale dividir as paradas mais distantes em um VUC extra "
                "ou estender a janela operacional."
            )
            st.table(pd.DataFrame(violacoes_janela))

        # Avisa VUCs cuja quilometragem real (OSRM) ficou acima de
        # MAX_KM_VUC. Acontece em casos de borda quando a estimativa
        # euclidiana subestima a malha viária real.
        if violacoes_km:
            st.error(
                f"🚨 **{len(violacoes_km)} VUC(s) excedem o limite de "
                f"{MAX_KM_VUC:.0f} km/dia** na quilometragem real (OSRM). "
                "Reveja o agrupamento ou divida as paradas mais distantes "
                "em um VUC adicional."
            )
            st.table(pd.DataFrame(violacoes_km))


# Sidebar — PARTE 2: download do PDF + chat. Renderizada DEPOIS da
# otimização para que st.session_state já contenha os dados frescos
# do último modelo otimizado (caso contrário, o botão de download
# ficaria preso com os bytes da otimização anterior).
with st.sidebar:
    if st.session_state.table_data is not None:
        st.divider()
        pdf_data = export_as_pdf(
            st.session_state.table_data, st.session_state.veiculos_stats
        )
        st.download_button(
            "📥 Baixar Tabela em PDF",
            data=pdf_data,
            file_name="Relatorio_Logistico.pdf",
            mime="application/pdf",
        )

    st.divider()
    st.header("🤖 Chat Bot IA (Claude)")
    chat_container = st.container(height=350)

    for msg in st.session_state.messages:
        chat_container.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Dúvida sobre as rotas?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        chat_container.chat_message("user").write(prompt)

        try:
            if st.session_state.table_data is not None:
                contexto = st.session_state.table_data.to_csv(index=False)
                if st.session_state.veiculos_stats:
                    resumo_linhas = ["\nRESUMO POR VEÍCULO:"]
                    for v, s in st.session_state.veiculos_stats.items():
                        resumo_linhas.append(
                            f"- {v}: {s['km']}km | {s['pecas']} peças | "
                            f"Racks: {s['racks']} | Tempo: {s['tempo']} | "
                            f"Custo: R$ {s['custo']}"
                        )
                    contexto += "\n".join(resumo_linhas)
            else:
                contexto = "Nenhuma rota gerada ainda."

            with st.spinner("Claude analisando..."):
                resposta = get_claude_response(st.session_state.messages, contexto)

            st.session_state.messages.append(
                {"role": "assistant", "content": resposta}
            )
            chat_container.chat_message("assistant").write(resposta)

        except Exception as e:
            st.error(f"Erro na IA: {e}")


# ============================================================
# EXIBIÇÃO
# ============================================================
if st.session_state.enderecos_nao_encontrados:
    with st.expander("⚠️ Atenção: Endereços não localizados", expanded=True):
        st.table(pd.DataFrame(st.session_state.enderecos_nao_encontrados))

if st.session_state.map_layers:
    st.pydeck_chart(
        pdk.Deck(
            map_style=pdk.map_styles.ROAD,
            initial_view_state=pdk.ViewState(
                latitude=DEPOT_COORDS[0],
                longitude=DEPOT_COORDS[1],
                zoom=10.5,
            ),
            layers=st.session_state.map_layers,
            tooltip={
                "html": "<b>Parada:</b> {seq_num}<br/><b>Cliente:</b> {NOME}"
            },
        )
    )

if st.session_state.veiculos_stats:
    st.subheader("📊 Resumo da Frota")
    cols = st.columns(len(st.session_state.veiculos_stats))
    df_tabela = st.session_state.table_data
    for i, (v_name, stats) in enumerate(st.session_state.veiculos_stats.items()):
        # Lista de clientes desse VUC na ordem da rota (vem da tabela)
        clientes_vuc = []
        if df_tabela is not None:
            clientes_vuc = (
                df_tabela.loc[df_tabela["Rota/VUC"] == v_name, "Cliente"]
                .tolist()
            )
        clientes_md = "\n".join(f"- {c}" for c in clientes_vuc)

        with cols[i]:
            st.markdown(
                f"**🚚 {v_name}**  \n"
                f"{stats['km']} KM  \n"
                f"📦 {stats['pecas']} pçs  \n"
                f"⏱️ {stats['tempo']}"
                + (f"\n\n**Clientes:**\n{clientes_md}" if clientes_md else "")
            )

if st.session_state.table_data is not None:
    st.subheader("📋 Tabela Operacional Detalhada")
    st.dataframe(st.session_state.table_data, use_container_width=True, hide_index=True)