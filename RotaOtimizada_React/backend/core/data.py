"""Normalização da planilha de entrada (multi-header com mesclagens)."""

import io
import unicodedata
import pandas as pd


def _ascii_upper(s) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper()


def normalizar_planilha(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Lê e normaliza planilha em qualquer dos layouts suportados.

    Resolve mesclagens em headers (PEÇAS GRANDES sobre POS/PB-TS/TOTAL),
    mesclagens em dados (ROTA, RACK GRANDE/MEDIO ffilladas), variações
    de nome/acentos. Retorna df com colunas canônicas:
        NOME, ROTA, ENDEREÇO, POS, PB_TS, PEÇAS GRANDES,
        PECAS_MEDIAS, PEÇAS PEQUENAS (alias), TOTAL.
    """
    is_excel = filename.lower().endswith((".xlsx", ".xls"))
    buf = io.BytesIO(file_bytes)
    if is_excel:
        df_raw = pd.read_excel(buf, header=None)
    else:
        df_raw = pd.read_csv(buf, header=None)

    if df_raw.empty:
        raise ValueError("Planilha vazia.")

    row0 = [str(v).strip() if pd.notna(v) else "" for v in df_raw.iloc[0].tolist()]
    row1 = [
        str(v).strip() if pd.notna(v) else ""
        for v in (df_raw.iloc[1].tolist() if len(df_raw) > 1 else [""] * len(row0))
    ]

    row0_ffill, last = [], ""
    for v in row0:
        if v:
            last = v
        row0_ffill.append(last)

    row1_norm = [_ascii_upper(v) for v in row1]
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

    # Resolve a ambiguidade do TOTAL (standalone vs PECAS TOTAIS)
    if "TOTAL" in df.columns and "PECAS TOTAIS" in df.columns:
        if "PEÇAS GRANDES" not in df.columns:
            df = df.rename(columns={"TOTAL": "PEÇAS GRANDES"})
        else:
            df = df.drop(columns=["TOTAL"])
    if "PECAS TOTAIS" in df.columns:
        df = df.rename(columns={"PECAS TOTAIS": "TOTAL"})

    for col in ("POS", "PB_TS", "PEÇAS GRANDES", "PECAS_MEDIAS"):
        if col not in df.columns:
            df[col] = 0

    for col in ("ROTA", "RACK GRANDE", "RACK MEDIO", "RACK MÉDIO"):
        if col in df.columns:
            df[col] = df[col].ffill()

    for col in ("POS", "PB_TS", "PEÇAS GRANDES", "PECAS_MEDIAS"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if df["PEÇAS GRANDES"].sum() == 0:
        df["PEÇAS GRANDES"] = df["POS"] + df["PB_TS"]

    if "TOTAL" not in df.columns:
        df["TOTAL"] = df["PEÇAS GRANDES"] + df["PECAS_MEDIAS"]
    else:
        total_num = pd.to_numeric(df["TOTAL"], errors="coerce")
        df["TOTAL"] = total_num.fillna(df["PEÇAS GRANDES"] + df["PECAS_MEDIAS"])

    df["PEÇAS PEQUENAS"] = df["PECAS_MEDIAS"]

    if "NOME" in df.columns:
        df = df.dropna(subset=["NOME"])
        nome_str = df["NOME"].astype(str).str.strip()
        df = df[(nome_str != "") & (~nome_str.str.upper().isin(("NAN", "NONE")))]

    return df.reset_index(drop=True)


def planilha_tem_rota_valida(df: pd.DataFrame) -> bool:
    if "ROTA" not in df.columns:
        return False
    serie = df["ROTA"].fillna("").astype(str).str.strip()
    serie = serie.replace(["nan", "NaN", "None", "<NA>"], "")
    return serie.ne("").any()
