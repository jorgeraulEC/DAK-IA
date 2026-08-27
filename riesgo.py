"""
riesgo.py — Scoring de riesgo de impago por cliente (RUC).

Extiende tools/risk_tool.py del MVP: allá el "historial de días de
atraso" venía pre-calculado en un JSON para 1 cliente de demo; acá se
calcula para los 1000 clientes a partir de las fechas reales:
  días_de_atraso = fecha del último pago que alcanza la factura - FECHA_VTO
(si la factura todavía no tiene ningún pago, se usa la fecha de
referencia del pipeline como "atraso en curso" para no perder la señal).

Mismos umbrales y misma regla de tendencia que el original -- el
chatbot de BI que ya existe en app.py sigue siendo consistente si se
conecta a esta versión batch en vez del historial_pagos.json de 3 clientes.
"""
import pandas as pd

import config
from conciliacion import normalizar_referencias_pago


def calcular_dias_atraso_por_factura(tablas: dict) -> pd.DataFrame:
    facturas = tablas["facturas"]
    pagos = normalizar_referencias_pago(tablas["pagos"], facturas)
    pagos_validos = pagos.dropna(subset=["FACTURA_REF_RESUELTA"])

    ultimo_pago = (
        pagos_validos.groupby("FACTURA_REF_RESUELTA")["FECHA_PAGO"].max()
        .rename("fecha_ultimo_pago")
    )
    f = facturas.set_index("NRO_DOC_FISCAL").join(ultimo_pago)
    f["fecha_ultimo_pago"] = f["fecha_ultimo_pago"].fillna(pd.Timestamp(config.FECHA_REFERENCIA))
    f["dias_de_atraso"] = (f["fecha_ultimo_pago"] - f["FECHA_VTO"]).dt.days
    return f.reset_index()[
        ["RUC", "NRO_DOC_FISCAL", "FECHA_VTO", "fecha_ultimo_pago", "dias_de_atraso"]
    ]


def calcular_riesgo_por_cliente(tablas: dict) -> pd.DataFrame:
    """Un renglón por RUC con su nivel de riesgo (ALTO/MEDIO/BAJO) y la
    acción de cobro sugerida -- listo para alimentar el 'chatbot BI' y
    la clasificación de usuarios del dashboard."""
    detalle = calcular_dias_atraso_por_factura(tablas).sort_values(["RUC", "FECHA_VTO"])

    filas = []
    for ruc, grupo in detalle.groupby("RUC"):
        atrasos = grupo["dias_de_atraso"].tolist()
        promedio = sum(atrasos) / len(atrasos)
        tendencia_creciente = atrasos == sorted(atrasos) and atrasos[-1] > atrasos[0]

        if promedio > config.UMBRAL_DIAS_ATRASO_ALTO or (
            tendencia_creciente and atrasos[-1] > config.UMBRAL_TENDENCIA_ALTO
        ):
            nivel = "ALTO"
        elif promedio > config.UMBRAL_DIAS_ATRASO_MEDIO:
            nivel = "MEDIO"
        else:
            nivel = "BAJO"

        filas.append({
            "RUC": ruc,
            "cantidad_facturas": len(atrasos),
            "promedio_dias_atraso": round(promedio, 1),
            "maximo_dias_atraso": int(max(atrasos)),
            "tendencia_creciente": tendencia_creciente,
            "nivel_riesgo": nivel,
            "patron_citado": (
                f"promedio {round(promedio, 1)} días de atraso en {len(atrasos)} "
                f"factura(s), tendencia {'creciente' if tendencia_creciente else 'estable/decreciente'}"
            ),
            "accion_cobro_sugerida": config.ACCIONES_POR_NIVEL[nivel],
        })
    return pd.DataFrame(filas)


if __name__ == "__main__":
    import carga_datos

    tablas = carga_datos.cargar_todas_las_tablas(verbose=False)
    riesgo = calcular_riesgo_por_cliente(tablas)
    print("Distribución de niveles de riesgo (", len(riesgo), "clientes ):")
    print(riesgo["nivel_riesgo"].value_counts())
    print("\nTop 5 clientes de mayor riesgo:")
    print(
        riesgo.sort_values("promedio_dias_atraso", ascending=False)
        .head(5)[["RUC", "promedio_dias_atraso", "maximo_dias_atraso", "nivel_riesgo"]]
        .to_string(index=False)
    )
