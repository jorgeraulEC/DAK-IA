"""
carga_datos.py — Carga y limpieza de las 6 tablas crudas (001..006).

Este módulo es el "Bronze -> Silver" del pipeline: lee los CSV tal como
llegan (separador '|', encoding ISO-8859-1, fechas en 3 formatos
distintos según la tabla) y devuelve DataFrames con tipos y fechas ya
normalizados, listos para conciliación/riesgo/regulatorio.

No oculta problemas de calidad de dato -- los reporta. Por ejemplo,
FECHA_VTO en 005_TBL_FACTURAS_B2B viene en dos formatos distintos
(YYYY-MM-DD para AMDOCS, YYYYMMDD para ISIS); este módulo los normaliza
para poder operar, pero conserva de dónde vino cada fila (columna
SISTEMA/FUENTE) para que conciliacion.py pueda explicar el patrón, no
solo "arreglarlo" en silencio.
"""
import sys
import pandas as pd

import config


def _leer_csv(nombre_logico: str) -> pd.DataFrame:
    ruta = config.RUTA_DATOS_CRUDOS / config.ARCHIVOS_CRUDOS[nombre_logico]
    if not ruta.exists():
        sys.exit(
            f"[carga_datos] No encuentro '{ruta}'.\n"
            f"Copia las 6 tablas 001_..006_TBL_*_B2B.csv dentro de "
            f"'{config.RUTA_DATOS_CRUDOS}' (o ajusta RUTA_DATOS_CRUDOS en config.py)."
        )
    return pd.read_csv(ruta, sep=config.CSV_SEP, encoding=config.CSV_ENCODING)


def _normalizar_fecha_mixta(serie: pd.Series) -> pd.Series:
    """Normaliza una columna de fecha que mezcla 'YYYY-MM-DD' (str) y
    'YYYYMMDD' (str/int sin separadores) al mismo formato antes de
    convertir a datetime. Caso real: FECHA_VTO en 005_TBL_FACTURAS_B2B."""
    def _fmt(valor):
        s = str(valor).strip()
        if "-" in s:
            return s
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return pd.to_datetime(serie.map(_fmt), format="%Y-%m-%d", errors="coerce")


def cargar_clientes() -> pd.DataFrame:
    df = _leer_csv("clientes")
    df = df.rename(columns={"NUMERO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    return df


def cargar_planta_fija() -> pd.DataFrame:
    df = _leer_csv("planta_fija")
    df = df.rename(columns={"NUMERO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    df["FECHAALTA"] = pd.to_datetime(df["FECHAALTA"], errors="coerce")
    return df


def cargar_planta_movil() -> pd.DataFrame:
    df = _leer_csv("planta_movil")
    df = df.rename(columns={"NUMERO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    df["FECHA_ALTA"] = pd.to_datetime(df["FECHA_ALTA"], format="%d/%m/%Y", errors="coerce")
    return df


def cargar_pagos() -> pd.DataFrame:
    df = _leer_csv("pagos")
    df = df.rename(columns={"NRO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    df["FECHA_PAGO"] = pd.to_datetime(df["FECHA_PAGO"], errors="coerce")
    return df


def cargar_facturas() -> pd.DataFrame:
    df = _leer_csv("facturas")
    df = df.rename(columns={"NUMERO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    df["FECHA_EMISION"] = pd.to_datetime(df["FECHA_EMISION"], format="%Y%m%d", errors="coerce")
    df["origen_fecha_vto_mal_formada"] = ~df["FECHA_VTO"].astype(str).str.contains("-")
    df["FECHA_VTO"] = _normalizar_fecha_mixta(df["FECHA_VTO"])
    return df


def cargar_notas_credito() -> pd.DataFrame:
    df = _leer_csv("notas_credito")
    df = df.rename(columns={"NUMERO_IDENTIFICACION_FISCAL": "RUC"})
    df["RUC"] = df["RUC"].astype(str)
    df["FECHAEMISION"] = pd.to_datetime(df["FECHAEMISION"], format="%Y%m%d", errors="coerce")
    return df


def cargar_todas_las_tablas(verbose: bool = True) -> dict:
    """Punto de entrada único: carga y limpia las 6 tablas y devuelve un
    dict {nombre_logico: DataFrame}. Imprime un resumen corto de calidad
    de dato si verbose=True (no bloquea el pipeline, solo informa)."""
    tablas = {
        "clientes": cargar_clientes(),
        "planta_fija": cargar_planta_fija(),
        "planta_movil": cargar_planta_movil(),
        "pagos": cargar_pagos(),
        "facturas": cargar_facturas(),
        "notas_credito": cargar_notas_credito(),
    }

    if verbose:
        print("[carga_datos] Filas por tabla:")
        for nombre, df in tablas.items():
            print(f"   {nombre:14s} {len(df):5d} filas, {df.shape[1]:2d} columnas")
        n_mal = tablas["facturas"]["origen_fecha_vto_mal_formada"].sum()
        if n_mal:
            sistemas = (
                tablas["facturas"]
                .loc[tablas["facturas"]["origen_fecha_vto_mal_formada"], "SISTEMA"]
                .value_counts().to_dict()
            )
            print(
                f"[carga_datos] AVISO: {n_mal} facturas con FECHA_VTO en formato "
                f"YYYYMMDD en vez de YYYY-MM-DD (sistema(s) de origen: {sistemas}). "
                f"Se normalizaron para poder operar, pero quedan marcadas en "
                f"'origen_fecha_vto_mal_formada' para el reporte de errores."
            )
    return tablas


if __name__ == "__main__":
    cargar_todas_las_tablas()
