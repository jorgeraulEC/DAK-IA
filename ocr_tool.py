"""
OCR_Processor — usado por el agente Cobranzas para leer comprobantes de
pago (PDF/foto). IMPORTANTE: el resultado de este tool NUNCA se usa por
sí solo para cerrar una deuda. Es solo un dato de apoyo que debe
cruzarse obligatoriamente contra Banking_API_Connector (ver banking_tool.py
y la guarda ASI02 en el documento de arquitectura de seguridad).
"""
import json
import os
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


@tool("Leer Comprobante de Pago (OCR)")
def leer_voucher(cliente_id: str) -> str:
    """Extrae monto y fecha de un comprobante de pago enviado por el
    cliente mediante OCR. ADVERTENCIA para el agente: este resultado es
    NO AUTORITATIVO. Debe validarse contra el extracto bancario real
    (herramienta consultar_extracto_bancario) antes de marcar cualquier
    deuda como pagada."""
    vouchers = _load("vouchers.json")
    match = next((v for v in vouchers if v["cliente_id"] == cliente_id), None)
    if not match or match["calidad_ocr"] == "sin_voucher":
        return json.dumps({
            "status": "SIN_VOUCHER",
            "nota": "El cliente aún no ha enviado comprobante de pago.",
        }, ensure_ascii=False)
    result = dict(match)
    result["advertencia"] = "DATO NO AUTORITATIVO — cruzar obligatoriamente contra el extracto bancario real."
    return json.dumps(result, ensure_ascii=False, indent=2)
