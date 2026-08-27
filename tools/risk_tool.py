"""
Scikit_Learn_Wrapper (simplificado para el MVP) — usado por el Analista
BI. Solo lectura de histórico agregado; sin permiso de escritura en
ningún sistema transaccional (sus alertas van a un dashboard/gerencia,
nunca ejecutan una acción sobre la cuenta del cliente).

Para el hackathon se usa una regla simple sobre días de atraso
promedio y tendencia; en producción esto se reemplaza por un modelo
scikit-learn entrenado con histórico real.
"""
import json
import os
from collections import defaultdict
from crewai.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


@tool("Calcular Riesgo de Impago")
def calcular_riesgo(cliente_id: str) -> str:
    """Calcula un score de riesgo de impago simple basado en el
    histórico de días de atraso del cliente. Solo lectura de datos
    agregados; no modifica ningún sistema."""
    historial = _load("historial_pagos.json")
    registros = sorted(
        [h for h in historial if h["cliente_id"] == cliente_id],
        key=lambda r: r["periodo"],
    )
    if not registros:
        return json.dumps({"cliente_id": cliente_id, "status": "SIN_HISTORIAL"}, ensure_ascii=False)

    atrasos = [r["dias_de_atraso"] for r in registros]
    promedio = sum(atrasos) / len(atrasos)
    tendencia_creciente = atrasos == sorted(atrasos) and atrasos[-1] > atrasos[0]

    if promedio > 15 or (tendencia_creciente and atrasos[-1] > 10):
        nivel = "ALTO"
    elif promedio > 5:
        nivel = "MEDIO"
    else:
        nivel = "BAJO"

    # Acción de cobro sugerida por segmento de riesgo -- respalda la promesa
    # de "BI prescriptivo, no solo predictivo" del documento y del chatbot.
    acciones_por_nivel = {
        "ALTO": "Contacto proactivo antes del vencimiento + oferta de plan de pago "
                "fraccionado; escalar a gestor de cuenta senior.",
        "MEDIO": "Recordatorio automático 5 días antes del vencimiento por "
                 "correo/WhatsApp; sin escalamiento humano todavía.",
        "BAJO": "Mantener ciclo de facturación estándar; sin acción de cobranza "
                "adicional.",
    }

    return json.dumps({
        "cliente_id": cliente_id,
        "historial_dias_atraso": atrasos,
        "promedio_dias_atraso": round(promedio, 1),
        "tendencia_creciente": tendencia_creciente,
        "nivel_riesgo": nivel,
        "accion_cobro_sugerida": acciones_por_nivel[nivel],
        "patron_citado": f"promedio {round(promedio, 1)} días de atraso en {len(atrasos)} periodos, "
                          f"tendencia {'creciente' if tendencia_creciente else 'estable/decreciente'}",
        "nota": "Score basado en regla simple para el MVP. En producción: modelo scikit-learn entrenado con histórico completo.",
    }, ensure_ascii=False, indent=2)
