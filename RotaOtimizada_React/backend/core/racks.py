"""Cálculo de racks necessários por VUC."""

from math import ceil
from .config import CAP_RACK_G, CAP_RACK_P, CAP_MAX_VUC


def calcular_racks(total_pecas: int) -> tuple[int, int, int]:
    """Retorna (n_vucs, racks_g, racks_p)."""
    n = ceil(total_pecas / CAP_MAX_VUC) if total_pecas > 0 else 1
    ref = total_pecas if total_pecas <= CAP_MAX_VUC else CAP_MAX_VUC
    g = 1 if ref > 0 else 0
    p = ceil(max(0, ref - CAP_RACK_G) / CAP_RACK_P)
    return n, g, p
