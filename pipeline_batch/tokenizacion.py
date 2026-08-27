"""
tokenizacion.py — Pseudonimización de identificadores antes de que
cualquier dato salga hacia un LLM/agente de IA.

Idea central: los 4 agentes (Orquestador, Facturador, Cobranzas,
Analista BI) NUNCA deben ver un RUC real. Ven un token determinístico
(mismo RUC -> mismo token, siempre) que les permite razonar y cruzar
información sin poder reconstruir la identidad del cliente. El mapeo
inverso token -> RUC vive SOLO en el backend (tabla `mapa_reverso`,
nunca se serializa hacia afuera ni se le pasa a un prompt).

Esto es pseudonimización con clave (HMAC-SHA256 truncado), no
"encriptación reversible por cualquiera" -- es intencional: nadie que
solo tenga el token (incluida la IA) puede recuperar el RUC sin la
clave + la tabla, que quedan del lado del backend.
"""
import hashlib
import hmac

import pandas as pd

import config


def tokenizar_valor(valor: str, prefijo: str = "TKN") -> str:
    """Determinístico: el mismo valor siempre produce el mismo token,
    lo que permite seguir haciendo joins/agrupaciones sobre datos
    tokenizados sin exponer el RUC real."""
    firma = hmac.new(
        config.CLAVE_TOKENIZACION.encode("utf-8"),
        str(valor).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]
    return f"{prefijo}_{firma}"


def construir_mapa_tokens(valores: pd.Series, prefijo: str = "RUC") -> dict:
    """Construye el mapa {valor_real: token} para una columna (p.ej. todos
    los RUC únicos). Este dict es el único lugar donde token y valor real
    conviven -- se guarda aparte (mapa_reverso.csv) y NUNCA se manda a la IA."""
    unicos = valores.dropna().astype(str).unique()
    return {v: tokenizar_valor(v, prefijo) for v in unicos}


def tokenizar_dataframe(df: pd.DataFrame, columna: str, mapa: dict, columna_token: str = None) -> pd.DataFrame:
    """Agrega una columna con el token correspondiente a `columna`,
    dejando la columna original intacta (el caller decide si la elimina
    antes de exponer el resultado a un agente de IA -- ver
    vista_segura_para_ia más abajo)."""
    columna_token = columna_token or f"{columna}_TOKEN"
    df = df.copy()
    df[columna_token] = df[columna].astype(str).map(mapa)
    return df


def vista_segura_para_ia(df: pd.DataFrame, columnas_sensibles: list[str], columnas_token: dict[str, str]) -> pd.DataFrame:
    """Devuelve una copia del DataFrame lista para pasarle a un LLM:
    reemplaza cada columna sensible por su token y ELIMINA la columna
    original. `columnas_token` mapea columna_original -> columna_token
    ya presente en df (generada previamente con tokenizar_dataframe)."""
    vista = df.copy()
    for col in columnas_sensibles:
        col_token = columnas_token.get(col)
        if col_token and col_token in vista.columns:
            vista[col] = vista[col_token]
            vista = vista.drop(columns=[col_token])
        else:
            vista = vista.drop(columns=[col], errors="ignore")
    return vista


def guardar_mapa_reverso(mapa: dict, ruta) -> None:
    """Persiste el mapa token -> valor real. Este archivo es la ÚNICA
    pieza que puede volver a asociar un token con un cliente real -- debe
    quedar en almacenamiento restringido (no en el mismo bucket que las
    vistas 'seguras para IA', no versionado en git público)."""
    pd.DataFrame(
        [{"token": tok, "valor_real": val} for val, tok in mapa.items()]
    ).to_csv(ruta, index=False)


if __name__ == "__main__":
    import carga_datos

    tablas = carga_datos.cargar_todas_las_tablas(verbose=False)
    mapa_ruc = construir_mapa_tokens(tablas["clientes"]["RUC"], prefijo="RUC")
    clientes_tok = tokenizar_dataframe(tablas["clientes"], "RUC", mapa_ruc)
    print(clientes_tok[["RUC", "RUC_TOKEN", "RAZON_SOCIAL"]].head(3).to_string(index=False))
    vista_ia = vista_segura_para_ia(
        clientes_tok, columnas_sensibles=["RUC"], columnas_token={"RUC": "RUC_TOKEN"}
    )
    print("\nColumnas en la vista que efectivamente vería la IA:", list(vista_ia.columns))
    assert "RUC" not in vista_ia.columns or vista_ia["RUC"].equals(clientes_tok["RUC_TOKEN"])
