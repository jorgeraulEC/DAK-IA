"""
Banking_API_Connector — SOLO LECTURA sobre el extracto bancario real.
Es la única fuente de verdad para confirmar un pago (ver ASI02 en el
documento de arquitectura de seguridad). El agente Facturador NO tiene
acceso a esta herramienta (separación de funciones).

conciliar_pago() es el guardrail central del proyecto: solo confirma
una conciliación si el monto del voucher (OCR, no confiable) coincide
EXACTAMENTE con un movimiento real del extracto bancario. Si no
coincide, escala a revisión humana en vez de cerrar la deuda.
"""
import json
import os
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


@tool("Consultar Extracto Bancario")
def consultar_extracto_bancario(cliente_id: str) -> str:
    """Devuelve los movimientos reales del extracto bancario relacionados
    a un cliente, buscando por su ID en la referencia del movimiento.
    Fuente de verdad para conciliación. Solo lectura."""
    extracto = _load("extracto_bancario.json")
    movimientos = [m for m in extracto if cliente_id in m["referencia"]]
    if not movimientos:
        return json.dumps({"status": "SIN_MOVIMIENTOS", "cliente_id": cliente_id}, ensure_ascii=False)
    return json.dumps(movimientos, ensure_ascii=False, indent=2)


@tool("Conciliar Pago (Guardrail)")
def conciliar_pago(cliente_id: str, monto_voucher_ocr: float) -> str:
    """Guardrail de seguridad central: compara el monto extraído por OCR
    de un voucher contra el extracto bancario REAL del cliente. Solo
    confirma la conciliación si hay una coincidencia exacta con un
    movimiento bancario real. Cualquier discrepancia se marca para
    revisión humana obligatoria — nunca se cierra automáticamente."""
    extracto = _load("extracto_bancario.json")
    movimientos = [m for m in extracto if cliente_id in m["referencia"]]

    if not movimientos:
        return json.dumps({
            "status": "NO_CONCILIADO",
            "motivo": "No hay movimiento bancario registrado para este cliente todavía.",
            "accion": "Esperar o escalar a analista si el cliente insiste en haber pagado.",
        }, ensure_ascii=False, indent=2)

    for mov in movimientos:
        if abs(mov["monto"] - monto_voucher_ocr) < 0.01:
            return json.dumps({
                "status": "CONCILIADO",
                "cliente_id": cliente_id,
                "monto": mov["monto"],
                "id_transaccion": mov["movimiento_id"],
                "fecha": mov["fecha"],
            }, ensure_ascii=False, indent=2)

    return json.dumps({
        "status": "DISCREPANCIA — ESCALADO A REVISIÓN HUMANA",
        "motivo": "El monto del voucher (OCR) no coincide con ningún movimiento real del banco.",
        "monto_voucher_ocr": monto_voucher_ocr,
        "movimientos_reales_encontrados": movimientos,
        "regla_aplicada": "El OCR nunca es fuente de verdad por sí solo (guardrail ASI02).",
    }, ensure_ascii=False, indent=2)
