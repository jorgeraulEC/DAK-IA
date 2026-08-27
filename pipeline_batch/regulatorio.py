"""
regulatorio.py — Validación regulatoria/fiscal por cliente, en batch.

Extiende tools/osiptel_tool.py del MVP (que revisaba 1 cliente a la
vez) a los 1000 clientes. La llamada a Osiptel en sí sigue siendo un
MOCK (el dataset no trae ese dato) -- lo real es el estado SUNAT
(001_TBL_CLIENTES_B2B) y, ahora que se procesa el dataset completo,
también el estado de la línea/servicio (STATUS_DESC en planta fija,
ESTADO_LINEA en planta móvil), que en el demo original solo se
mencionaba en las notas del cliente de Comas, sin calcularse en batch.

Hallazgo del dataset completo que el demo de 3 clientes no podía ver:
el propio tools/osiptel_tool.py YA contemplaba el caso "cliente no
encontrado en el maestro SUNAT local del MVP" -- corriendo el batch
completo, ese caso no es una excepción rara: ~45% de los RUC que
facturan o pagan NO tienen fila en 001_TBL_CLIENTES_B2B. Este módulo
convierte ese caso, ya previsto en el código original, en su propia
alerta explícita en vez de dejarlo como columnas vacías.
"""
import pandas as pd


def validar_regulatorio_por_cliente(tablas: dict) -> pd.DataFrame:
    clientes = tablas["clientes"]
    pfija = tablas["planta_fija"]
    pmovil = tablas["planta_movil"]

    lineas_fijas_activas = (
        pfija[pfija["STATUS_DESC"] == "Active"].groupby("RUC").size().rename("lineas_fijas_activas")
    )
    lineas_fijas_totales = pfija.groupby("RUC").size().rename("lineas_fijas_totales")
    lineas_movil_activas = (
        pmovil[pmovil["ESTADO_LINEA"] == "Activo"].groupby("RUC").size().rename("lineas_movil_activas")
    )
    lineas_movil_totales = pmovil.groupby("RUC").size().rename("lineas_movil_totales")

    r = clientes.set_index("RUC").join(
        [lineas_fijas_activas, lineas_fijas_totales, lineas_movil_activas, lineas_movil_totales]
    ).fillna(0)
    for col in ["lineas_fijas_activas", "lineas_fijas_totales", "lineas_movil_activas", "lineas_movil_totales"]:
        r[col] = r[col].astype(int)

    def _alertas(row):
        alertas = []
        if row["SUNAT_ESTADO_RUC"] != "HABIDO":
            alertas.append(f"SUNAT_ESTADO_RUC={row['SUNAT_ESTADO_RUC']} (no HABIDO)")
        if row["SUNAT_ESTADO_CONTRIBUYENTE"] != "ACTIVO":
            alertas.append(f"SUNAT_ESTADO_CONTRIBUYENTE={row['SUNAT_ESTADO_CONTRIBUYENTE']} (no ACTIVO)")
        tiene_lineas = (row["lineas_fijas_totales"] + row["lineas_movil_totales"]) > 0
        tiene_lineas_activas = (row["lineas_fijas_activas"] + row["lineas_movil_activas"]) > 0
        if tiene_lineas and not tiene_lineas_activas:
            alertas.append("Todas sus líneas (fija/móvil) están inactivas o suspendidas")
        return alertas

    r["alertas_regulatorias"] = r.apply(_alertas, axis=1)
    r["status_regulatorio"] = r["alertas_regulatorias"].apply(
        lambda a: "ALERTA — REVISIÓN HUMANA" if a else "OK"
    )
    r["tiene_ficha_maestro_clientes"] = True
    r["nota"] = (
        "La consulta a Osiptel es un MOCK (sin dataset propio); el estado SUNAT "
        "y el estado de línea sí provienen de datos reales del dataset."
    )
    r = r.reset_index()

    # --- RUC que facturan/pagan pero no tienen fila en 001_TBL_CLIENTES_B2B ---
    # Mismo caso que ya anticipaba tools/osiptel_tool.py ("Cliente no
    # encontrado en el maestro SUNAT local del MVP") -- aquí se cuantifica.
    ruc_con_ficha = set(clientes["RUC"])
    ruc_facturan_o_pagan = set(tablas["facturas"]["RUC"]) | set(tablas["pagos"]["RUC"])
    ruc_sin_ficha = sorted(ruc_facturan_o_pagan - ruc_con_ficha)
    if ruc_sin_ficha:
        faltantes = pd.DataFrame({"RUC": ruc_sin_ficha})
        faltantes["RAZON_SOCIAL"] = None
        faltantes["alertas_regulatorias"] = [
            ["Cliente no encontrado en el maestro SUNAT (001_TBL_CLIENTES_B2B) -- "
             "no se puede validar SUNAT/Osiptel para este RUC."]
        ] * len(faltantes)
        faltantes["status_regulatorio"] = "ALERTA — REVISIÓN HUMANA"
        faltantes["tiene_ficha_maestro_clientes"] = False
        faltantes["nota"] = (
            "RUC presente en facturación/pagos pero ausente del maestro de clientes. "
            "Ver resumen_estadisticas.json -> clientes.sin_ficha_maestro_clientes."
        )
        r = pd.concat([r, faltantes], ignore_index=True)

    return r


if __name__ == "__main__":
    import carga_datos

    tablas = carga_datos.cargar_todas_las_tablas(verbose=False)
    reg = validar_regulatorio_por_cliente(tablas)
    print(reg["status_regulatorio"].value_counts())
    print("\nEjemplos con alerta:")
    print(
        reg[reg["status_regulatorio"] != "OK"]
        [["RUC", "RAZON_SOCIAL", "alertas_regulatorias"]]
        .head(5).to_string(index=False)
    )
