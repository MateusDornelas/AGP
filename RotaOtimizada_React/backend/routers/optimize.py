"""Endpoint principal: recebe planilha + modo e devolve VUCs otimizados.

NOTA: o `Depends(require_token)` foi removido — login está em stand by.
Para reativar a auth, importar `from .auth import require_token` e
voltar a colocar `_token: str = Depends(require_token)` no parametro.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from core.pipeline import otimizar

router = APIRouter(prefix="/api", tags=["optimize"])


@router.post("/optimize")
async def optimize(
    file: UploadFile = File(...),
    modo: str = Form("Modelo Padrão"),
):
    """Recebe planilha (xlsx/csv) + modo. Retorna VUCs + stats + tabela."""
    if not file.filename:
        raise HTTPException(400, "Nome de arquivo ausente.")
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Formato não suportado (use xlsx ou csv).")

    contents = await file.read()
    try:
        resultado = otimizar(contents, file.filename, modo)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro no processamento: {e}")

    return resultado
