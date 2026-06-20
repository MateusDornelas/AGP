"""Login simples: valida credenciais hardcoded.

Em produção: substituir por DB + JWT/sessão. Por ora basta um token
opaco devolvido ao front, que envia no header Authorization.
"""

import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from core.config import VALID_PASS, VALID_USER

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Tokens emitidos durante a sessão da app (memória, sem persistência).
_TOKENS: set[str] = set()


class LoginIn(BaseModel):
    usuario: str
    senha: str


class LoginOut(BaseModel):
    token: str
    usuario: str


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn) -> LoginOut:
    if payload.usuario != VALID_USER or payload.senha != VALID_PASS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
        )
    token = secrets.token_urlsafe(32)
    _TOKENS.add(token)
    return LoginOut(token=token, usuario=payload.usuario)


def require_token(authorization: str | None = Header(default=None)) -> str:
    """Dependency: extrai e valida o token Bearer."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Autenticação requerida")
    token = authorization.removeprefix("Bearer ").strip()
    if token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return token
