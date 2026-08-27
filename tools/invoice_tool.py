"""
Python_Validator + Invoice_Generator — usados exclusivamente por el
agente Facturador. Este agente NO tiene acceso a Banking_API_Connector
ni permiso de escribir estado de pago (separación de funciones, ver
sección 5.3 del documento de arquitectura).
"""
import json
import os
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


@tool("Validar y Generar Prefactura")
def validar_y_generar_factura(cliente_id: str, periodo: str, monto_a_facturar: float) -> str:
    """Cruza el monto propuesto contra el contrato y la OC del cliente para
    ese periodo. Si coincide, genera una prefactura. Si no coincide,
    devuelve un reporte de error explicando la discrepancia en vez de la
    factura (nunca emite una factura con datos inconsistentes)."""
    contratos = _load("contratos.json")
    ocs = _load("ordenes_compra.json")

    contrato = next((c for c in contratos if c["cliente_id"] == cliente_id), None)
    oc = next((o for o in ocs if o["cliente_id"] == cliente_id and o["periodo"] == periodo), None)

    if not contrato:
        return json.dumps({"status": "ERROR", "motivo": f"Sin contrato vigente para {cliente_id}"}, ensure_ascii=False)
    if not oc:
        return json.dumps({"status": "ERROR", "motivo": f"Sin OC registrada para {cliente_id} en {periodo}"}, ensure_ascii=False)

    if abs(monto_a_facturar - oc["monto_esperado"]) > 0.01:
        return json.dumps({
            "status": "RECHAZADO",
            "motivo": "El monto a facturar no coincide con la OC del cliente.",
            "clausula_contractual_citada": contrato.get("clausula_facturacion", "N/A"),
            "texto_clausula": contrato.get("texto_clausula_facturacion", ""),
            "monto_propuesto": monto_a_facturar,
            "monto_esperado_oc": oc["monto_esperado"],
            "accion_requerida": "Actualizar la OC antes de reintentar la emisión — revisión humana requerida.",
        }, ensure_ascii=False, indent=2)

    prefactura = {
        "status": "PRE-FACTURA VALIDADA",
        "cliente_id": cliente_id,
        "razon_social": contrato["razon_social"],
        "periodo": periodo,
        "monto": monto_a_facturar,
        "plazo_credito_dias": contrato["plazo_credito_dias"],
        "clausula_contractual_verificada": contrato.get("clausula_facturacion", "N/A"),
        "requiere_aprobacion_humana": monto_a_facturar > 5000.00,
    }
    return json.dumps(prefactura, ensure_ascii=False, indent=2)
