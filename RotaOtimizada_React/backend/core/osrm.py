"""Cliente OSRM com cache em memória e fallback euclidiano."""

import os
import time
from math import sqrt
import requests
import polyline
from .config import (
    AVG_SPEED_KMH, EUCLIDEAN_FUDGE, OSRM_BASE_URL, OSRM_CONNECT_TIMEOUT,
    OSRM_READ_TIMEOUT, OSRM_THROTTLE_SEC,
)


_CACHE: dict[tuple, dict] = {}
_DISABLED = {"flag": False, "fails": 0}
_PROXY = {
    "http": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
    "https": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
}
_PROXY = {k: v for k, v in _PROXY.items() if v}


def reset():
    """Limpa cache e flag entre execuções (chamar no início de cada otimização)."""
    _CACHE.clear()
    _DISABLED["flag"] = False
    _DISABLED["fails"] = 0


def is_disabled() -> bool:
    return _DISABLED["flag"]


def pair_distance(p1: list, p2: list) -> dict | None:
    """Distância e duração entre 2 pontos [lat, lon]. None em falha."""
    if _DISABLED["flag"]:
        return None

    key = (round(p1[0], 5), round(p1[1], 5), round(p2[0], 5), round(p2[1], 5))
    if key in _CACHE:
        return _CACHE[key]

    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{p1[1]},{p1[0]};{p2[1]},{p2[0]}?overview=false"
    )
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "RotaOtimizadaReact/1.0"},
            timeout=(OSRM_CONNECT_TIMEOUT, OSRM_READ_TIMEOUT),
            proxies=_PROXY or None,
        )
        r.raise_for_status()
        data = r.json()
        resultado = {
            "distance_km": data["routes"][0]["distance"] / 1000,
            "duration_min": data["routes"][0]["duration"] / 60,
        }
        _CACHE[key] = resultado
        _DISABLED["fails"] = 0
        time.sleep(OSRM_THROTTLE_SEC)
        return resultado
    except Exception:
        _DISABLED["fails"] += 1
        if _DISABLED["fails"] >= 2:
            _DISABLED["flag"] = True
        return None


def fallback_distance_km(p1: list, p2: list) -> float:
    """Euclidean × EUCLIDEAN_FUDGE — proxy quando OSRM indisponível."""
    return (
        sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
        * 111 * EUCLIDEAN_FUDGE
    )


def route_geometry(coords: list) -> list | None:
    """Calcula a polilinha da rota REAL (seguindo ruas) entre os pontos.

    coords: lista de [lat, lon] na ordem que o veículo vai passar
            (depot → cliente1 → cliente2 → ... → depot, idealmente).
    Retorna: lista de [lat, lon] da geometria decodificada, ou None
             em falha (caller deve cair pra reta).
    """
    if _DISABLED["flag"] or len(coords) < 2:
        return None

    # OSRM espera lon,lat (não lat,lon)
    locs_url = ";".join(f"{p[1]},{p[0]}" for p in coords)
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{locs_url}?overview=simplified&geometries=polyline"
    )
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "RotaOtimizadaReact/1.0"},
            timeout=(OSRM_CONNECT_TIMEOUT, OSRM_READ_TIMEOUT + 5),
            proxies=_PROXY or None,
        )
        r.raise_for_status()
        data = r.json()
        # polyline.decode retorna [(lat, lon), ...]
        pts = polyline.decode(data["routes"][0]["geometry"])
        _DISABLED["fails"] = 0
        time.sleep(OSRM_THROTTLE_SEC)
        return [[lat, lon] for (lat, lon) in pts]
    except Exception:
        _DISABLED["fails"] += 1
        if _DISABLED["fails"] >= 2:
            _DISABLED["flag"] = True
        return None
