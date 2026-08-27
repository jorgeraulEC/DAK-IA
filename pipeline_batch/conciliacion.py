"""
conciliacion.py — El guardrail central del proyecto, en versión batch.

Mismo principio que tools/banking_tool.py::conciliar_pago() del MVP
("el OCR/comprobante nunca es fuente de verdad por sí solo; si no hay
coincidencia exacta, se escala a revisión humana"), aplicado ahora a
las 3364 facturas y 3548 pagos reales del dataset completo en vez de a
3 clientes de demo.

Regla de oro (pedida explícitamente): el agente de Cobranzas puede
cerrar una factura automáticamente SOLO cuando el cruce es inequívoco.
Esto pasa en dos casos, y en ningún otro:
  1) El pago referencia el número de factura EXACTO (join directo).
  2) El pago referencia un número de factura con un problema de
     formato 100% determinístico y verificable contra las facturas
     reales del mismo prefijo (ver `normalizar_referencias_pago`) --
     nunca se asume una corrección, se prueba contra el dato real.
Cualquier otro caso (pago parcial, sobrepago, referencia que no
resuelve a ninguna factura real) se reporta para revisión humana. El
pipeline nunca "adivina" a qué factura pertenece un pago por
similitud de cliente o de monto.
"""
import pandas as pd

import config


def construir_longitudes_esperadas(facturas: pd.DataFrame) -> dict:
    """Para cada prefijo de NRO_DOC_FISCAL (p.ej. 'S300', 'S9AA'), calcula
    la longitud estándar real observada en las facturas. Se usa para
    detectar (nunca asumir) referencias de pago que solo difieren en
    padding de ceros a la izquierda."""
    prefijos = facturas["NRO_DOC_FISCAL"].str.extract(r"^([A-Z0-9]+)-")[0]
    longitudes = facturas["NRO_DOC_FISCAL"].str.len()
    tabla = pd.DataFrame({"prefijo": prefijos, "longitud": longitudes})
    moda_por_prefijo = tabla.groupby("prefijo")["longitud"].agg(lambda s: s.mode()[0])
    return moda_por_prefijo.to_dict()


def normalizar_referencias_pago(pagos: pd.DataFrame, facturas: pd.DataFrame) -> pd.DataFrame:
    """Devuelve `pagos` con 3 columnas nuevas:
      - FACTURA_REF_RESUELTA: la referencia que sí matchea una factura real
        (igual a la original si no hizo falta corregir), o NaN si no se
        pudo resolver.
      - fue_corregida_automaticamente: True si hubo que rellenar con ceros
        a la izquierda para encontrar la factura real (y SÍ se encontró).
      - referencia_original: se conserva para auditoría.
    """
    facturas_validas = set(facturas["NRO_DOC_FISCAL"])
    longitudes_esperadas = construir_longitudes_esperadas(facturas)

    def _resolver(ref):
        ref = str(ref)
        if ref in facturas_validas:
            return ref, False
        if "-" in ref:
            prefijo, numero = ref.split("-", 1)
            largo_esperado = longitudes_esperadas.get(prefijo)
            if largo_esperado and len(numero) < (largo_esperado - len(prefijo) - 1):
                numero_relleno = numero.zfill(largo_esperado - len(prefijo) - 1)
                candidato = f"{prefijo}-{numero_relleno}"
                if candidato in facturas_validas:
                    return candidato, True
        return None, False

    resueltas = pagos["FACTURA_AFECTADA"].map(_resolver)
    pagos = pagos.copy()
    pagos["referencia_original"] = pagos["FACTURA_AFECTADA"]
    pagos["FACTURA_REF_RESUELTA"] = resueltas.map(lambda t: t[0])
    pagos["fue_corregida_automaticamente"] = resueltas.map(lambda t: t[1])
    return pagos


def conciliar(tablas: dict, fecha_referencia=None) -> dict:
    """Ejecuta la conciliación completa. Devuelve un dict con:
      - facturas_procesadas: DataFrame (el sistema las resolvió solo)
      - facturas_no_procesadas: DataFrame (requieren revisión humana)
      - reporte_errores_pagos: pagos que ningún ajuste determinístico
        logró vincular a una factura real
      - correcciones_aplicadas: auditoría de qué referencias se
        corrigieron automáticamente y cómo
    """
    fecha_referencia = pd.Timestamp(fecha_referencia or config.FECHA_REFERENCIA)
    facturas = tablas["facturas"]
    pagos_resueltos = normalizar_referencias_pago(tablas["pagos"], facturas)
    notas = tablas["notas_credito"]

    # --- Pagos que NINGUNA corrección determinística logra vincular ---
    reporte_errores_pagos = pagos_resueltos[pagos_resueltos["FACTURA_REF_RESUELTA"].isna()].copy()
    reporte_errores_pagos = reporte_errores_pagos[[
        "RUC", "COD_CLIENTE", "COD_CUENTA", "SISTEMA", "referencia_original",
        "FECHA_PAGO", "MONTO_PAGADO",
    ]]
    reporte_errores_pagos["motivo"] = (
        "Sin factura real que coincida (ni exacta ni con normalización de "
        "ceros) -- no se cierra ni se descarta solo: derivar a revisión humana."
    )

    correcciones_aplicadas = pagos_resueltos[pagos_resueltos["fue_corregida_automaticamente"]][[
        "RUC", "referencia_original", "FACTURA_REF_RESUELTA", "FECHA_PAGO", "MONTO_PAGADO",
    ]].copy()

    # --- Agregar pagos y notas de crédito por factura ---
    pagos_validos = pagos_resueltos.dropna(subset=["FACTURA_REF_RESUELTA"])
    total_pagado = (
        pagos_validos.groupby("FACTURA_REF_RESUELTA")["MONTO_PAGADO"].sum()
        .rename("total_pagado")
    )
    n_pagos = (
        pagos_validos.groupby("FACTURA_REF_RESUELTA").size().rename("cantidad_pagos")
    )
    hubo_correccion = (
        pagos_validos.groupby("FACTURA_REF_RESUELTA")["fue_corregida_automaticamente"].any()
        .rename("requirio_correccion_formato")
    )
    total_nota_credito = notas.groupby("FACTURA_AFECTADA")["MONTO"].sum().rename("total_nota_credito")

    f = facturas.set_index("NRO_DOC_FISCAL").join(
        [total_pagado, n_pagos, hubo_correccion, total_nota_credito]
    )
    f["total_pagado"] = f["total_pagado"].fillna(0.0)
    f["cantidad_pagos"] = f["cantidad_pagos"].fillna(0).astype(int)
    f["requirio_correccion_formato"] = f["requirio_correccion_formato"].fillna(False)
    f["total_nota_credito"] = f["total_nota_credito"].fillna(0.0)
    f["monto_neto_a_pagar"] = f["CHARGE_TOTAL_AMOUNT"] - f["total_nota_credito"]
    f["diferencia"] = f["total_pagado"] - f["monto_neto_a_pagar"]
    f["esta_vencida"] = f["FECHA_VTO"] < fecha_referencia

    def _estado(row):
        if abs(row["diferencia"]) < config.TOLERANCIA_MONTO:
            return "CONCILIADA_CON_NORMALIZACION" if row["requirio_correccion_formato"] else "CONCILIADA_EXACTA"
        if row["total_pagado"] == 0:
            return "VENCIDA_SIN_PAGO" if row["esta_vencida"] else "PENDIENTE_DENTRO_DE_PLAZO"
        if row["diferencia"] < 0:
            return "PAGO_PARCIAL"
        return "SOBREPAGO"

    f["estado_conciliacion"] = f.apply(_estado, axis=1)
    # Ayuda a priorizar la cola de revisión humana sin reclasificar nada:
    # una PAGO_PARCIAL/SOBREPAGO de S/0.05 o menos suele ser ruido de
    # redondeo de IGV entre pagos fraccionados, no una discrepancia real
    # (el dataset completo muestra mediana ~S/19.60 en PAGO_PARCIAL, así
    # que la mayoría SÍ son discrepancias sustantivas -- esto solo separa
    # el 7% que probablemente no lo es).
    f["diferencia_es_trivial_redondeo"] = f["diferencia"].abs() <= 0.05
    f = f.reset_index()

    ESTADOS_PROCESADOS = {"CONCILIADA_EXACTA", "CONCILIADA_CON_NORMALIZACION", "PENDIENTE_DENTRO_DE_PLAZO"}
    facturas_procesadas = f[f["estado_conciliacion"].isin(ESTADOS_PROCESADOS)].copy()
    facturas_no_procesadas = f[~f["estado_conciliacion"].isin(ESTADOS_PROCESADOS)].copy()

    return {
        "facturas_procesadas": facturas_procesadas,
        "facturas_no_procesadas": facturas_no_procesadas,
        "reporte_errores_pagos": reporte_errores_pagos,
        "correcciones_aplicadas": correcciones_aplicadas,
    }


if __name__ == "__main__":
    import carga_datos

    tablas = carga_datos.cargar_todas_las_tablas(verbose=False)
    resultado = conciliar(tablas)
    print("Facturas procesadas:", len(resultado["facturas_procesadas"]))
    print(resultado["facturas_procesadas"]["estado_conciliacion"].value_counts())
    print("\nFacturas NO procesadas (revisión humana):", len(resultado["facturas_no_procesadas"]))
    print(resultado["facturas_no_procesadas"]["estado_conciliacion"].value_counts())
    print("\nPagos corregidos automáticamente (formato):", len(resultado["correcciones_aplicadas"]))
    print("Pagos sin resolver (error real de conciliación):", len(resultado["reporte_errores_pagos"]))
