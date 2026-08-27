"""
DB_API — acceso de SOLO LECTURA a contratos y órdenes de compra.
En el MVP lee de archivos JSON locales (data/). En producción, esto se
reemplaza por una conexión real a la base de datos de contratos/OC,
manteniendo el mismo contrato de solo-lectura para los agentes que no
deben poder escribir aquí (Cobranzas, Analista BI).
"""
import json
import os
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


@tool("Consultar Contrato Cliente")
def get_contrato(cliente_id: str) -> str:
    """Devuelve el contrato vigente de un cliente (monto pactado, plazo de
    crédito, descuentos activos). Acceso de solo lectura."""
    contratos = _load("contratos.json")
    match = next((c for c in contratos if c["cliente_id"] == cliente_id), None)
    if not match:
        return f"No se encontró contrato para {cliente_id}."
    return json.dumps(match, ensure_ascii=False, indent=2)


@tool("Consultar Orden de Compra")
def get_orden_compra(cliente_id: str, periodo: str) -> str:
    """Devuelve la orden de compra (OC) esperada para un cliente y periodo
    dado (formato periodo: 'YYYY-MM'). Acceso de solo lectura."""
    ocs = _load("ordenes_compra.json")
    match = next(
        (o for o in ocs if o["cliente_id"] == cliente_id and o["periodo"] == periodo),
        None,
    )
    if not match:
        return f"No se encontró OC para {cliente_id} en el periodo {periodo}."
    return json.dumps(match, ensure_ascii=False, indent=2)
