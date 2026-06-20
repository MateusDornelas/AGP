"""Entry-point FastAPI do Otimizador de Rotas AGP (versão React).

Executar:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS
from routers import auth, chat, optimize, reoptimize

app = FastAPI(
    title="Otimizador de Rotas AGP",
    description="Backend FastAPI da versão React.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(optimize.router)
app.include_router(reoptimize.router)
app.include_router(chat.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
