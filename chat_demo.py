"""
chat_demo.py — Simulación de chat conversacional para el video pitch.

No depende de ningún LLM en vivo: el "entendimiento" es un router simple
por palabras clave, pensado para que el video sea 100% predecible y
nunca falle en cámara. Cada respuesta se arma en lenguaje natural a
partir del mismo resultado real de las tools que ya usa app.py, así que
sigue siendo el mismo guardrail y la misma lógica de siempre, solo con
una cara conversacional.

Colocar este archivo en la raíz del proyecto, junto a app.py, para que
los imports de tools/ funcionen.

Uso:
    streamlit run chat_demo.py
"""
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from tools.banking_tool import conciliar_pago
from tools.invoice_tool import validar_y_generar_factura
from tools.ocr_tool import leer_voucher
from tools.osiptel_tool import validar_regulatorio
from tools.risk_tool import calcular_riesgo

# --- Dataset completo (pipeline batch), aparte de los 3 clientes de demo ---
SALIDAS_DIR = Path(__file__).parent / "pipeline_batch" / "salidas"
SEÑALES_DATASET_COMPLETO = [
    "todos los clientes", "todas las facturas", "dataset completo", "en general",
    "cuántas facturas", "cuantas facturas", "cuántos clientes", "cuantos clientes",
    "total facturado", "resumen", "estadísticas", "estadisticas",
]


@st.cache_data
def cargar_salidas_pipeline():
    if not SALIDAS_DIR.exists():
        return None
    try:
        return {
            "resumen": json.loads((SALIDAS_DIR / "resumen_estadisticas.json").read_text(encoding="utf-8")),
            "clientes": pd.read_csv(SALIDAS_DIR / "clientes_clasificados.csv"),
        }
    except FileNotFoundError:
        return None


def responder_dataset_completo(texto_l):
    """Preguntas a nivel de TODO el dataset (batch), no de 1 cliente puntual
    -- usa los resultados ya calculados por pipeline_batch/run_pipeline.py."""
    salidas = cargar_salidas_pipeline()
    if salidas is None:
        return "🧭 Orquestador", (
            "Todavía no corrí el pipeline batch -- ejecuta `python run_pipeline.py` "
            "dentro de `pipeline_batch/` primero."
        )
    r = salidas["resumen"]
    if any(p in texto_l for p in ["riesgo", "riesgoso"]):
        alto = int((salidas["clientes"]["segmento_riesgo_final"] == "ALTO").sum())
        return "📊 Analista BI", f"De los {len(salidas['clientes']):,} clientes del dataset completo, {alto} están en riesgo ALTO."
    if any(p in texto_l for p in ["error", "concilia"]):
        return "💳 Cobranzas", (
            f"De {r['conciliacion_pagos']['pagos_totales']:,} pagos reales, "
            f"{r['conciliacion_pagos']['sin_resolver_requieren_revision']} no se pudieron vincular a "
            f"ninguna factura y quedaron escalados a revisión humana."
        )
    return "🧭 Orquestador", (
        f"Dataset completo: {r['facturas']['total']:,} facturas por S/ {r['facturas']['monto_total_facturado']:,.2f}, "
        f"{r['facturas']['procesadas']:,} conciliadas sin intervención humana "
        f"({r['facturas']['procesadas'] / r['facturas']['total']:.0%})."
    )


CLIENTES = {
    "2005150947": {"nombre": "CLIENT_00073", "monto": 281.89, "periodo": "2026-07"},
    "2075533541": {"nombre": "CLIENT_00465", "monto": 18.97, "periodo": "2026-07"},
    "2098283606": {"nombre": "CLIENT_00347", "monto": None, "periodo": "2026-07"},
}


def run(tool, **kwargs):
    return json.loads(tool.run(**kwargs))


def extraer_cliente(texto):
    m = re.search(r"\b(20\d{8})\b", texto)
    if m:
        return m.group(1)
    for cid, info in CLIENTES.items():
        if info["nombre"].lower() in texto.lower():
            return cid
    return None


def responder(texto):
    texto_l = texto.lower()

    if any(p in texto_l for p in SEÑALES_DATASET_COMPLETO):
        return responder_dataset_completo(texto_l)

    cid = extraer_cliente(texto)

    if any(p in texto_l for p in ["sunat", "regulatori", "osiptel"]):
        if not cid:
            return "🧭 Orquestador", "¿De qué cliente necesitas el estado regulatorio?"
        r = run(validar_regulatorio, cliente_id=cid)
        if r["status"] == "OK":
            return "🧭 Orquestador", f"Revisé a {CLIENTES[cid]['nombre']}: sin alertas, el ciclo puede continuar."
        return "🧭 Orquestador", f"Alerta para {CLIENTES[cid]['nombre']}: {', '.join(r['alertas_sunat'])} Detengo el ciclo hasta revisión humana."

    if any(p in texto_l for p in ["factura", "prefactura", "emitir"]):
        if not cid:
            return "🧾 Facturador", "¿A qué cliente le genero la prefactura?"
        info = CLIENTES[cid]
        if info["monto"] is None:
            return "🧾 Facturador", f"{info['nombre']} no tiene facturación registrada este periodo, no hay nada que emitir."
        r = run(validar_y_generar_factura, cliente_id=cid, periodo=info["periodo"], monto_a_facturar=info["monto"])
        if r["status"] == "PRE-FACTURA VALIDADA":
            return "🧾 Facturador", f"Prefactura validada para {r['razon_social']}, S/ {r['monto']}. Coincide con el contrato y la OC, lista para emitir."
        return "🧾 Facturador", f"No emito la factura: {r.get('motivo')}"

    if any(p in texto_l for p in ["concilia", "pago", "voucher", "pagó", "cobr"]):
        if not cid:
            return "💳 Cobranzas", "¿De qué cliente reviso el pago?"
        v = run(leer_voucher, cliente_id=cid)
        if v.get("status") == "SIN_VOUCHER":
            return "💳 Cobranzas", f"{CLIENTES[cid]['nombre']} todavía no envió comprobante de pago."
        r = run(conciliar_pago, cliente_id=cid, monto_voucher_ocr=v["monto_extraido"])
        if r["status"] == "CONCILIADO":
            return "💳 Cobranzas", f"Concilié el pago de {CLIENTES[cid]['nombre']}: S/ {r['monto']}, coincide exacto con el banco. Deuda cerrada."
        return "💳 Cobranzas", (
            f"El comprobante de {CLIENTES[cid]['nombre']} no coincide con el extracto bancario real. "
            f"No cierro la deuda sola, la escalo a revisión humana."
        )

    if any(p in texto_l for p in ["riesgo", "impago", "morosidad"]):
        if not cid:
            return "📊 Analista BI", "¿De qué cliente calculo el riesgo?"
        r = run(calcular_riesgo, cliente_id=cid)
        return "📊 Analista BI", (
            f"{CLIENTES[cid]['nombre']} tiene riesgo {r['nivel_riesgo']}, promedio {r['promedio_dias_atraso']} días de atraso. "
            f"Genero la alerta para gerencia, no toco la cuenta."
        )

    return "🧭 Orquestador", "Puedo ayudarte con estado regulatorio, prefacturas, conciliación de pagos o riesgo de impago. ¿Sobre qué cliente?"


st.set_page_config(page_title="Chat O2C · Movistar Hackathon", page_icon="💬")
st.title("💬 SON-IA — flujo conversacional")
st.caption("Simulación sin LLM en vivo — pensada para grabar el video sin depender del wifi del venue.")
st.caption("Prueba también con el dataset completo: \"dame un resumen\", \"cuántos clientes en riesgo\", \"errores de conciliación\".")

if "historial" not in st.session_state:
    st.session_state.historial = []

for rol, msg in st.session_state.historial:
    avatar = "🧑‍💼" if rol == "user" else None
    with st.chat_message(rol, avatar=avatar):
        st.markdown(msg)

pregunta = st.chat_input("Escribe como si fueras el analista de Movistar...")
if pregunta:
    st.session_state.historial.append(("user", pregunta))
    agente, respuesta = responder(pregunta)
    st.session_state.historial.append(("assistant", f"**{agente}**: {respuesta}"))
    st.rerun()
