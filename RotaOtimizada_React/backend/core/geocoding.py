"""Geocodificação via Nominatim + validação BR + cache SQLite persistente.

Endereços já consultados ficam salvos no DB local. Próximas execuções
com o mesmo endereço (~95% dos casos no dia a dia) pulam o Nominatim
e o sleep(1s) de throttle.
"""

import sqlite3
import time
import pandas as pd
from geopy.geocoders import Nominatim
from .config import (
    BR_LAT_MAX, BR_LAT_MIN, BR_LON_MAX, BR_LON_MIN, GEOCACHE_PATH,
)


def coord_no_brasil(lat: float, lon: float) -> bool:
    return BR_LAT_MIN <= lat <= BR_LAT_MAX and BR_LON_MIN <= lon <= BR_LON_MAX


# ============================================================
# CACHE PERSISTENTE (SQLite)
# ============================================================
_INIT_OK = False


def _conn() -> sqlite3.Connection:
    global _INIT_OK
    conn = sqlite3.connect(GEOCACHE_PATH)
    if not _INIT_OK:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS geocache (
                endereco TEXT PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                ts INTEGER NOT NULL
            )"""
        )
        conn.commit()
        _INIT_OK = True
    return conn


def geocache_get(endereco: str) -> tuple[float, float] | None:
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT lat, lon FROM geocache WHERE endereco = ?",
                (endereco.strip(),),
            ).fetchone()
        return (row[0], row[1]) if row else None
    except Exception:
        return None


def geocache_set(endereco: str, lat: float, lon: float) -> None:
    try:
        with _conn() as c:
            c.execute(
                """INSERT INTO geocache (endereco, lat, lon, ts)
                   VALUES (?, ?, ?, strftime('%s', 'now'))
                   ON CONFLICT(endereco) DO UPDATE SET
                     lat=excluded.lat, lon=excluded.lon, ts=excluded.ts""",
                (endereco.strip(), float(lat), float(lon)),
            )
            c.commit()
    except Exception:
        pass


# ============================================================
# GEOCODIFICAÇÃO
# ============================================================
def geocode_addresses(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Geocodifica a coluna ENDEREÇO. Retorna (df_ok, erros).

    Estratégia:
      1. Tenta o cache local (SQLite) — instantâneo, sem rate limit
      2. Em cache miss, consulta Nominatim (≤1 req/s, política do servidor)
      3. Valida bounding box BR
      4. Salva no cache para próximas execuções
    """
    if "ENDEREÇO" not in df.columns:
        return pd.DataFrame(), [{"erro": "Coluna ENDEREÇO ausente"}]

    geolocator = Nominatim(user_agent="rota_otimizada_react")
    df = df.copy()
    df["search_addr"] = df["ENDEREÇO"].astype(str) + ", Brasil"

    lats, lons, erros = [], [], []
    hits_cache = 0
    total = len(df)

    for _, row in df.iterrows():
        endereco = str(row["search_addr"])

        # 1. Cache hit?
        cached = geocache_get(endereco)
        if cached is not None:
            lats.append(cached[0])
            lons.append(cached[1])
            hits_cache += 1
            continue  # pula Nominatim e o sleep

        # 2. Cache miss → Nominatim
        try:
            loc = geolocator.geocode(endereco, timeout=10)
            if loc and coord_no_brasil(loc.latitude, loc.longitude):
                lats.append(loc.latitude)
                lons.append(loc.longitude)
                geocache_set(endereco, loc.latitude, loc.longitude)
            else:
                lats.append(None)
                lons.append(None)
                erros.append({
                    "cliente": str(row.get("NOME", "N/A")),
                    "rota": str(row.get("ROTA", "N/A")),
                    "endereco": str(row["ENDEREÇO"]),
                    "motivo": (
                        f"Fora do Brasil ({loc.latitude:.3f}, {loc.longitude:.3f})"
                        if loc else "Endereço não encontrado"
                    ),
                })
        except Exception as e:
            lats.append(None)
            lons.append(None)
            erros.append({
                "cliente": str(row.get("NOME", "N/A")),
                "rota": str(row.get("ROTA", "N/A")),
                "endereco": str(row["ENDEREÇO"]),
                "motivo": f"Erro: {type(e).__name__}",
            })

        # Throttle só em chamadas reais
        time.sleep(1.0)

    print(
        f"[geocoding] {hits_cache}/{total} hits no cache "
        f"({hits_cache / max(1, total) * 100:.0f}%)",
        flush=True,
    )

    df["lat"] = lats
    df["lon"] = lons
    return df.dropna(subset=["lat", "lon"]).reset_index(drop=True), erros
