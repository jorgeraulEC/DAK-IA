"""
Osiptel_Validator — usado por el Orquestador para checks regulatorios
básicos (solo lectura). La llamada a Osiptel en sí sigue siendo un MOCK
(en producción se conecta al servicio/API real de Osiptel), pero ahora
se combina con el estado fiscal SUNAT real del cliente (columna
SUNAT_ESTADO_CONTRIBUYENTE del dataset 001_TBL_CLIENTES_B2B) como una
segunda señal de riesgo regulatorio/fiscal disponible en el MVP.

Un RUC en estado "BAJA DE OFICIO" o con SUNAT_ESTADO_RUC != "HABIDO"
no es en sí una alerta de Osiptel, pero es información real que el
Supervisor Agent debe conocer antes de dejar avanzar el ciclo O2C
(ver rol de "filtro de protección regulatoria" del Supervisor Agent).
"""
import json
import os
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load_clientes():
    with open(os.path.join(DATA_DIR, "clientes.json"), encoding="utf-8") as f:
        return json.load(f)


@tool("Validar Cumplimiento Regulatorio (Osiptel)")
def validar_regulatorio(cliente_id: str) -> str:
    """Verifica de forma simulada que el cliente no tenga alertas
    pendientes ante Osiptel (MOCK) y cruza además su estado fiscal SUNAT
    real (HABIDO/ACTIVO vs. NO HABIDO/BAJA DE OFICIO) antes de continuar
    el flujo. Si el estado SUNAT no es HABIDO/ACTIVO, se reporta como
    alerta para revisión humana en vez de dejar avanzar el ciclo O2C."""
    clientes = _load_clientes()
    cliente = next((c for c in clientes if c["cliente_id"] == cliente_id), None)

    alertas = []
    if cliente is None:
        alertas.append("Cliente no encontrado en el maestro SUNAT local del MVP.")
    else:
        if cliente["sunat_estado_ruc"] != "HABIDO":
            alertas.append(f"SUNAT_ESTADO_RUC = {cliente['sunat_estado_ruc']} (no HABIDO).")
        if cliente["sunat_estado_contribuyente"] != "ACTIVO":
            alertas.append(
                f"SUNAT_ESTADO_CONTRIBUYENTE = {cliente['sunat_estado_contribuyente']} (no ACTIVO)."
            )

    status = "ALERTA — REVISIÓN HUMANA" if alertas else "OK"
    return json.dumps({
        "cliente_id": cliente_id,
        "alertas_osiptel": [],
        "alertas_sunat": alertas,
        "status": status,
        "nota": "La consulta a Osiptel es un MOCK (siempre sin alertas en el MVP); "
                "el estado SUNAT sí proviene del dataset real 001_TBL_CLIENTES_B2B.",
    }, ensure_ascii=False, indent=2)
