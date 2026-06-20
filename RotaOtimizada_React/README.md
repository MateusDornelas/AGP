# Otimizador de Rotas AGP — versão React + FastAPI

Migração da app Streamlit (`RotaOtimizada.py`) para arquitetura
**front/back separados**:

- **Backend** — FastAPI + Pydantic + OR-Tools + OSRM + Nominatim
- **Frontend** — React 18 + Vite + TypeScript + Tailwind CSS

## Estrutura

```
RotaOtimizada_React/
├── backend/
│   ├── main.py                  FastAPI + CORS + routers
│   ├── core/
│   │   ├── config.py            Constantes (CAP_MAX_VUC, MAX_KM_VUC…)
│   │   ├── data.py              normalizar_planilha (multi-header, ffill)
│   │   ├── geocoding.py         Nominatim + bbox BR
│   │   ├── osrm.py              Cliente OSRM com cache + fallback
│   │   ├── solver.py            OR-Tools TSP + fast_km_estimate
│   │   ├── clustering.py        Modelo Padrão + Modo Criativo + rebalance
│   │   ├── racks.py             calcular_racks
│   │   └── pipeline.py          Orquestra tudo → JSON
│   ├── routers/
│   │   ├── auth.py              POST /api/auth/login (token Bearer)
│   │   └── optimize.py          POST /api/optimize (upload + modo)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── package.json             Vite + React + TS + Tailwind
    ├── vite.config.ts           proxy /api → :8000
    ├── tailwind.config.js       cor agp-yellow #F5C518
    ├── index.html
    ├── public/AGPpng.png        Logo institucional
    └── src/
        ├── main.tsx / App.tsx
        ├── index.css
        ├── api/
        │   ├── client.ts        fetch + token + setSession
        │   └── types.ts         Tipagens da resposta
        ├── pages/
        │   ├── Login.tsx
        │   └── Dashboard.tsx
        └── components/
            ├── Sidebar.tsx      Logo + upload + modo + botão
            ├── ResumeCards.tsx  Cards (KM, peças, tempo, clientes)
            ├── DataTable.tsx    Tabela detalhada
            └── Warnings.tsx     Avisos (janela, KM, endereços)
```

## Como rodar localmente

### Pré-requisitos
- Python 3.11+ (testado em 3.13)
- Node.js 18+ (para o frontend)

### Backend

```powershell
cd RotaOtimizada_React/backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Configurar .env (copiar .env.example e preencher ANTHROPIC_API_KEY)
copy .env.example .env

# Rodar
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend sobe em `http://localhost:8000`. Docs interativas em `/docs`.

### Frontend

```powershell
cd RotaOtimizada_React/frontend
npm install
npm run dev
```

Frontend sobe em `http://localhost:5173`. As chamadas para `/api/*` são
automaticamente proxied para o backend (configurado em `vite.config.ts`).

### Credenciais

- Usuário: `Logistica`
- Senha: `Agp123`

## O que está implementado (Fase 1)

- [x] Login → token Bearer salvo no localStorage
- [x] Upload de planilha (xlsx/csv) com multi-header e mesclagens
- [x] Otimização Modelo Padrão e Modo Criativo
- [x] Resumo da Frota com KM, peças, tempo e lista de clientes
- [x] Tabela operacional detalhada (POS, PB/TS, Grandes, Médias, Total)
- [x] Avisos: violação 18:00, violação 140km, endereços não localizados,
      OSRM indisponível

## O que falta para paridade total com Streamlit (próximas fases)

- [ ] Mapa interativo (Leaflet/MapLibre — substitui PyDeck)
- [ ] Chat IA Claude (POST /api/chat) com condições externas
- [ ] Exportação PDF (GET /api/export/pdf)
- [ ] Comparação A/B Padrão vs Criativo lado a lado

## Decisões de arquitetura

- **Cookie vs token**: optei por token Bearer no `localStorage` para
  simplificar — produção deve migrar para cookie HttpOnly + CSRF.
- **Geocoding síncrono no backend**: bloqueia o request por ~1s/endereço
  (limite Nominatim). Para volumes maiores, migrar para fila assíncrona
  ou um cache persistente de endereços já vistos.
- **Sem state manager (Redux/Zustand)**: a UI tem pouco estado global,
  então `useState` na página `Dashboard` resolve. Reavaliar se a app
  crescer.
- **Tailwind sem shadcn**: para evitar dependência extra na Fase 1. Se
  o time quiser componentes mais ricos (modais, toasts, popovers),
  vale instalar.

## Notas de migração do Streamlit

A lógica de otimização foi movida quase intacta:

- `normalizar_planilha` → `core/data.py` (sem mudança funcional)
- `solve_group_route` → `core/solver.py`
- `cluster_modelo_padrao` / `cluster_modo_criativo` → `core/clustering.py`
- `fast_km_estimate` / `rebalancear_km` → `core/clustering.py` + `solver.py`
- `geocode_addresses` → `core/geocoding.py`
- OSRM helpers → `core/osrm.py`
- `calcular_racks_necessarios` → `core/racks.py`

O que mudou:
- Não há mais `st.session_state` — o front guarda o resultado em React state
- PDF e Chat ainda não migrados (próxima fase)
- Mapa será reescrito com Leaflet/MapLibre (PyDeck era específico do Streamlit)
