"""
run_pipeline.py — Punto de entrada único. Corre las 3364 facturas /
3548 pagos / 1000 clientes del dataset completo (no solo los 3
clientes del demo de CrewAI) y deja en salidas/ todo lo que la
interfaz (dashboard + chatbot BI) necesita para funcionar sin volver a
tocar los CSV crudos.

Uso:
    python run_pipeline.py

Requiere: pandas (pip install pandas)
"""
import json

import pandas as pd

import config
import carga_datos
import tokenizacion
import conciliacion
import riesgo
import regulatorio


def construir_clasificacion_clientes(tablas, resultado_conciliacion, riesgo_df, regulatorio_df) -> pd.DataFrame:
    """El 'gold layer' pedido explícitamente: una fila por cliente,
    lista para el tab de 'clasificación de usuarios / riesgo' del
    dashboard y para que el chatbot BI responda sin recalcular nada."""
    todas_facturas = pd.concat([
        resultado_conciliacion["facturas_procesadas"],
        resultado_conciliacion["facturas_no_procesadas"],
    ])
    pendientes_por_cliente = (
        todas_facturas[todas_facturas["estado_conciliacion"].isin(["PAGO_PARCIAL", "SOBREPAGO"])]
        .groupby("RUC").size().rename("facturas_pendientes_revision")
    )

    c = riesgo_df.set_index("RUC").join(regulatorio_df.set_index("RUC"), how="outer")
    c = c.join(pendientes_por_cliente).fillna({"facturas_pendientes_revision": 0})
    c["facturas_pendientes_revision"] = c["facturas_pendientes_revision"].astype(int)
    c["tiene_ficha_maestro_clientes"] = c["tiene_ficha_maestro_clientes"].fillna(False)

    # Importante: "sin ficha en el maestro SUNAT" es un problema de dato
    # (falta la fila en 001_TBL_CLIENTES_B2B), no una señal de riesgo de
    # pago -- el cruce pagos<->facturas (conciliacion.py) NO depende del
    # maestro de clientes y ya reconcilia estos casos con la misma tasa
    # que el resto (ver verificación: 79.4% vs 78.3%). Por eso NO se
    # escala a ALTO solo por faltar la ficha; se marca aparte para que
    # el dashboard la trate como su propia cola ("completar ficha SUNAT"),
    # separada de "cliente con historial de pago riesgoso".
    def _segmento_final(row):
        if row.get("tiene_ficha_maestro_clientes") and row.get("status_regulatorio") == "ALERTA — REVISIÓN HUMANA":
            return "ALTO"
        return row.get("nivel_riesgo") if pd.notna(row.get("nivel_riesgo")) else "SIN_HISTORIAL_DE_FACTURACION"

    c["segmento_riesgo_final"] = c.apply(_segmento_final, axis=1)
    c = c.reset_index()
    columnas = [
        "RUC", "RAZON_SOCIAL", "SUNAT_DEPARTAMENTO", "SUNAT_PROVINCIA", "SUNAT_DISTRITO",
        "segmento_riesgo_final", "nivel_riesgo", "promedio_dias_atraso", "maximo_dias_atraso",
        "tendencia_creciente", "tiene_ficha_maestro_clientes", "status_regulatorio", "alertas_regulatorias",
        "facturas_pendientes_revision", "accion_cobro_sugerida",
    ]
    return c[[col for col in columnas if col in c.columns]]


def construir_resumen_estadisticas(tablas, resultado_conciliacion, riesgo_df, clasificacion) -> dict:
    todas_facturas = pd.concat([
        resultado_conciliacion["facturas_procesadas"],
        resultado_conciliacion["facturas_no_procesadas"],
    ])
    return {
        "periodo_datos": {
            "facturas_desde": str(todas_facturas["FECHA_EMISION"].min().date()),
            "facturas_hasta": str(todas_facturas["FECHA_EMISION"].max().date()),
            "fecha_referencia_usada": str(config.FECHA_REFERENCIA),
        },
        "clientes": {
            "total_en_maestro_001": int(len(tablas["clientes"])),
            "con_alerta_regulatoria": int((clasificacion["status_regulatorio"] == "ALERTA — REVISIÓN HUMANA").sum()),
            "sin_ficha_en_maestro_001": int(clasificacion["RAZON_SOCIAL"].isna().sum()),
            "nota_sin_ficha": (
                "RUC que facturan y/o pagan pero no tienen fila en 001_TBL_CLIENTES_B2B "
                "-- no se les puede validar SUNAT/Osiptel con este extracto. Ver "
                "regulatorio_por_cliente.csv para el detalle."
            ),
        },
        "facturas": {
            "total": int(len(todas_facturas)),
            "monto_total_facturado": round(float(todas_facturas["CHARGE_TOTAL_AMOUNT"].sum()), 2),
            "monto_total_pagado": round(float(todas_facturas["total_pagado"].sum()), 2),
            "monto_total_notas_credito": round(float(todas_facturas["total_nota_credito"].sum()), 2),
            "procesadas": int(len(resultado_conciliacion["facturas_procesadas"])),
            "no_procesadas": int(len(resultado_conciliacion["facturas_no_procesadas"])),
            "por_estado": todas_facturas["estado_conciliacion"].value_counts().to_dict(),
        },
        "conciliacion_pagos": {
            "pagos_totales": int(len(tablas["pagos"])),
            "corregidos_automaticamente_por_formato": int(len(resultado_conciliacion["correcciones_aplicadas"])),
            "sin_resolver_requieren_revision": int(len(resultado_conciliacion["reporte_errores_pagos"])),
        },
        "conciliacion_no_depende_del_maestro_clientes": {
            "nota": (
                "La conciliación pagos<->facturas usa NRO_DOC_FISCAL/FACTURA_AFECTADA, "
                "nunca el maestro de clientes (001) -- por eso los RUC sin ficha SUNAT "
                "igual se reconcilian con normalidad. Cifras de verificación:"
            ),
            "facturas_de_ruc_sin_ficha_maestro": int((~todas_facturas["RUC"].isin(set(tablas["clientes"]["RUC"]))).sum()),
            "tasa_conciliacion_automatica_con_ficha": round(
                float(todas_facturas[todas_facturas["RUC"].isin(set(tablas["clientes"]["RUC"]))]
                      ["estado_conciliacion"].isin(["CONCILIADA_EXACTA", "CONCILIADA_CON_NORMALIZACION"]).mean()), 3),
            "tasa_conciliacion_automatica_sin_ficha": round(
                float(todas_facturas[~todas_facturas["RUC"].isin(set(tablas["clientes"]["RUC"]))]
                      ["estado_conciliacion"].isin(["CONCILIADA_EXACTA", "CONCILIADA_CON_NORMALIZACION"]).mean()), 3),
        },
        "riesgo_clientes": riesgo_df["nivel_riesgo"].value_counts().to_dict(),
        "segmento_riesgo_final_clientes": clasificacion["segmento_riesgo_final"].value_counts().to_dict(),
    }


def main():
    print("=" * 70)
    print(" PIPELINE O2C -- procesando dataset completo SONIA_DESAFIO_03")
    print("=" * 70)

    tablas = carga_datos.cargar_todas_las_tablas()

    print("\n[2/5] Conciliando pagos vs. facturas vs. notas de crédito...")
    resultado_conciliacion = conciliacion.conciliar(tablas)

    print("[3/5] Calculando riesgo de impago por cliente...")
    riesgo_df = riesgo.calcular_riesgo_por_cliente(tablas)

    print("[4/5] Validando estado regulatorio/fiscal (SUNAT) y de servicio...")
    regulatorio_df = regulatorio.validar_regulatorio_por_cliente(tablas)

    print("[5/5] Construyendo clasificación de clientes y tokenizando para la IA...")
    clasificacion = construir_clasificacion_clientes(tablas, resultado_conciliacion, riesgo_df, regulatorio_df)

    mapa_ruc = tokenizacion.construir_mapa_tokens(tablas["clientes"]["RUC"], prefijo="RUC")
    clasificacion_tok = tokenizacion.tokenizar_dataframe(clasificacion, "RUC", mapa_ruc)
    clasificacion_vista_ia = tokenizacion.vista_segura_para_ia(
        clasificacion_tok, columnas_sensibles=["RUC"], columnas_token={"RUC": "RUC_TOKEN"}
    )

    # --- Escribir salidas -------------------------------------------------
    config.RUTA_SALIDAS.mkdir(exist_ok=True)

    resultado_conciliacion["facturas_procesadas"].to_csv(config.RUTA_SALIDAS / "facturas_procesadas.csv", index=False)
    resultado_conciliacion["facturas_no_procesadas"].to_csv(config.RUTA_SALIDAS / "facturas_no_procesadas.csv", index=False)
    resultado_conciliacion["reporte_errores_pagos"].to_csv(config.RUTA_SALIDAS / "reporte_errores_conciliacion.csv", index=False)
    resultado_conciliacion["correcciones_aplicadas"].to_csv(config.RUTA_SALIDAS / "correcciones_automaticas_aplicadas.csv", index=False)
    riesgo_df.to_csv(config.RUTA_SALIDAS / "riesgo_por_cliente.csv", index=False)
    regulatorio_df.to_csv(config.RUTA_SALIDAS / "regulatorio_por_cliente.csv", index=False)
    clasificacion.to_csv(config.RUTA_SALIDAS / "clientes_clasificados.csv", index=False)
    clasificacion_vista_ia.to_csv(config.RUTA_SALIDAS / "clientes_clasificados_TOKENIZADO_para_IA.csv", index=False)
    tokenizacion.guardar_mapa_reverso(mapa_ruc, config.RUTA_SALIDAS / "mapa_reverso_NO_COMPARTIR.csv")

    resumen = construir_resumen_estadisticas(tablas, resultado_conciliacion, riesgo_df, clasificacion)
    with open(config.RUTA_SALIDAS / "resumen_estadisticas.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

    print(f"\nListo. Archivos escritos en: {config.RUTA_SALIDAS}")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
