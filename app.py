"""
Interfaz visual del demo — Streamlit.

Modo Rápido: corre la lógica de las herramientas directamente (sin LLM).
  Es instantáneo, gratis, y NUNCA falla por wifi o API caída — ideal
  como respaldo garantizado durante el pitch.

Modo IA Completo: corre el crew real de CrewAI con los 4 agentes
  razonando con LLM (requiere tu GEMINI_API_KEY). Es la demo "real"
  pero depende de conexión a internet y de la API.

Datos: 3 clientes reales (anonimizados) del dataset SONIA_DESAFIO_03,
  periodo de facturación 2026-07. Ver README.md para el detalle de
  cómo se derivó cada archivo en data/ a partir de las tablas
  001-006 del dataset.

Uso:
    pip install -r requirements.txt
    streamlit run app.py
"""
import json
from pathlib import Path

import pandas as pd
import os
import streamlit as st

if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]


from tools.db_tool import get_contrato, get_orden_compra
from tools.invoice_tool import validar_y_generar_factura
from tools.ocr_tool import leer_voucher
from tools.banking_tool import consultar_extracto_bancario, conciliar_pago
from tools.risk_tool import calcular_riesgo
from tools.osiptel_tool import validar_regulatorio


def run_tool(tool, **kwargs):
    return json.loads(tool.run(**kwargs))


# --- Panel general: resultados del pipeline batch (dataset completo) ------
# pipeline_batch/run_pipeline.py corre las 3364 facturas / 3548 pagos /
# 1000 clientes reales (no solo los 3 de la demo interactiva de abajo) y
# deja los resultados en pipeline_batch/salidas/. Esta función solo LEE
# esos CSV/JSON ya calculados -- no repite ningún cálculo aquí.
SALIDAS_DIR = Path(__file__).parent / "pipeline_batch" / "salidas"


@st.cache_data
def cargar_salidas_pipeline():
    if not SALIDAS_DIR.exists():
        return None
    try:
        return {
            "resumen": json.loads((SALIDAS_DIR / "resumen_estadisticas.json").read_text(encoding="utf-8")),
            "clientes": pd.read_csv(SALIDAS_DIR / "clientes_clasificados.csv"),
            "clientes_tok": pd.read_csv(SALIDAS_DIR / "clientes_clasificados_TOKENIZADO_para_IA.csv"),
            "errores": pd.read_csv(SALIDAS_DIR / "reporte_errores_conciliacion.csv"),
        }
    except FileNotFoundError:
        return None


st.set_page_config(page_title="O2C Multi-Agente · Movistar Hackathon", layout="wide")

st.title("Sistema Multi-Agente Order-to-Cash B2B")
st.caption("MVP · Hackathon Telecom AI · Datos reales anonimizados")

with st.sidebar:
    st.header("Configuración")
    modo = st.radio(
        "Modo de ejecución",
        ["Rápido (determinístico, sin LLM)", "IA Completo (CrewAI + LLM en vivo)"],
        index=0,
        help="El modo rápido corre la lógica de negocio directamente y nunca falla. "
             "El modo IA completo hace razonar a los 4 agentes con Gemini en vivo.",
    )
    api_key = None
    if modo.startswith("🤖"):
        api_key = st.text_input("GEMINI_API_KEY", type="password")
        st.caption("Necesaria solo para el modo IA completo (Google AI Studio).")
    st.divider()
    st.markdown(
        "**Qué es real vs. mock:**\n"
        "- Real: arquitectura de 4 agentes, permisos separados, guardrail de "
        "conciliación, y los montos/fechas/RUC de contratos, facturas, pagos "
        "y estado SUNAT (derivados de las tablas 001-006 del dataset).\n"
        "- Mock: la llamada en sí a Osiptel (siempre 'sin alertas' en el MVP) "
        "y el comprobante/voucher OCR que sube el cliente (el dataset no trae "
        "OCR, así que se calibró contra los montos reales del extracto)."
    )

st.subheader("Panel general — dataset completo, sin LLM ")
st.caption("Los mismos 4 guardrails de abajo, corridos contra las 3364 facturas reales en vez de solo 3 clientes.")

salidas = cargar_salidas_pipeline()
if salidas is None:
    st.info(
        "Corre `python run_pipeline.py` dentro de `pipeline_batch/` para generar "
        "`pipeline_batch/salidas/` y activar este panel con el dataset completo."
    )
else:
    r = salidas["resumen"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Facturas reales", f"{r['facturas']['total']:,}")
    k2.metric("Monto facturado", f"S/ {r['facturas']['monto_total_facturado']:,.0f}")
    k3.metric("Monto pagado", f"S/ {r['facturas']['monto_total_pagado']:,.0f}")
    k4.metric("Conciliado sin intervención", f"{r['facturas']['procesadas'] / r['facturas']['total']:.0%}")
    st.caption(
        f"{r['conciliacion_pagos']['corregidos_automaticamente_por_formato']} pagos corregidos "
        f"automáticamente por formato de documento · "
        f"{r['conciliacion_pagos']['sin_resolver_requieren_revision']} sin resolver, "
        f"escalados a revisión humana (nunca cerrados a ciegas)."
    )

    tab_riesgo, tab_errores, tab_token = st.tabs(["Clientes en riesgo", "Errores de conciliación", "Tokenización"])

    with tab_riesgo:
        clientes_df = salidas["clientes"].copy()
        clientes_df["RAZON_SOCIAL"] = clientes_df["RAZON_SOCIAL"].fillna("(sin ficha SUNAT)")
        alto = clientes_df[clientes_df["segmento_riesgo_final"] == "ALTO"].sort_values(
            "promedio_dias_atraso", ascending=False
        )
        st.caption(f"{len(alto)} clientes en segmento ALTO, de {len(clientes_df):,} clasificados en total.")
        st.dataframe(
            alto[["RUC", "RAZON_SOCIAL", "promedio_dias_atraso", "status_regulatorio", "accion_cobro_sugerida"]].head(15),
            width="stretch", hide_index=True,
        )

    with tab_errores:
        st.caption(f"{len(salidas['errores'])} pagos que ningún ajuste automático logró vincular a una factura real.")
        st.dataframe(salidas["errores"], width="stretch", hide_index=True)

    with tab_token:
        st.caption("Lo que ve un humano en el backend, vs. lo único que le llega a un agente de IA. Nunca conviven en el mismo archivo.")
        colr, colt = st.columns(2)
        with colr:
            st.markdown("**RUC real (backend)**")
            st.dataframe(salidas["clientes"][["RUC", "RAZON_SOCIAL"]].head(5), hide_index=True)
        with colt:
            st.markdown("**RUC tokenizado (lo que ve la IA)**")
            st.dataframe(salidas["clientes_tok"][["RUC", "RAZON_SOCIAL"]].head(5), hide_index=True)

st.divider()

clientes = {
    "2005150947": "CLIENT_00073 (San Isidro, Lima) — flujo feliz",
    "2075533541": "CLIENT_00465 (Huancayo, Junín) — caso de discrepancia real (guardrail)",
    "2098283606": "CLIENT_00347 (Comas, Lima) — riesgo de impago (SUNAT: BAJA DE OFICIO)",
}

st.subheader("1️⃣ Orquestador — validación regulatoria y fiscal previa (Osiptel + SUNAT)")
if st.button("Validar cumplimiento regulatorio", key="osiptel"):
    cols = st.columns(3)
    for col, cid in zip(cols, clientes):
        with col:
            st.caption(clientes[cid])
            r = run_tool(validar_regulatorio, cliente_id=cid)
            if r["status"] == "OK":
                st.success(f"{cid}: sin alertas ✅")
            else:
                st.error(f"{cid}: {', '.join(r['alertas_sunat'])}")
            st.json(r)

st.divider()
st.subheader("2️⃣ Facturador — validación de prefacturas")
fcol1, fcol2 = st.columns(2)
with fcol1:
    st.markdown("**2005150947** — CLIENT_00073, Trío FTTH S/281.89")
    if st.button("Validar y generar prefactura — 2005150947"):
        r = run_tool(validar_y_generar_factura, cliente_id="2005150947", periodo="2026-07", monto_a_facturar=281.89)
        if r["status"] == "PRE-FACTURA VALIDADA":
            st.success(f"✅ {r['status']} — {r['razon_social']} — S/ {r['monto']}")
        else:
            st.error(r)
        st.json(r)
with fcol2:
    st.markdown("**2075533541** — CLIENT_00465, línea móvil S/18.97")
    if st.button("Validar y generar prefactura — 2075533541"):
        r = run_tool(validar_y_generar_factura, cliente_id="2075533541", periodo="2026-07", monto_a_facturar=18.97)
        if r["status"] == "PRE-FACTURA VALIDADA":
            st.success(f"✅ {r['status']} — {r['razon_social']} — S/ {r['monto']}")
        else:
            st.error(r)
        st.json(r)

st.divider()
st.subheader("3️⃣ Cobranzas — conciliación (el guardrail de seguridad)")
ccol1, ccol2 = st.columns(2)
with ccol1:
    st.markdown("**2005150947** — se espera coincidencia exacta")
    if st.button("Conciliar pago — 2005150947"):
        v = run_tool(leer_voucher, cliente_id="2005150947")
        r = run_tool(conciliar_pago, cliente_id="2005150947", monto_voucher_ocr=v["monto_extraido"])
        if r["status"] == "CONCILIADO":
            st.success(f"✅ CONCILIADO — ID transacción: {r['id_transaccion']}")
        st.json(r)
with ccol2:
    st.markdown("**2075533541** — voucher dice S/18.97, banco solo registró S/9.49")
    if st.button("Conciliar pago — 2075533541"):
        v = run_tool(leer_voucher, cliente_id="2075533541")
        r = run_tool(conciliar_pago, cliente_id="2075533541", monto_voucher_ocr=v["monto_extraido"])
        if "ESCALADO" in r["status"]:
            st.warning(f"⚠️ {r['status']}\n\nEl sistema NO cerró la deuda solo — detectó la discrepancia y escaló.")
        st.json(r)

st.divider()
st.subheader("4️⃣ Analista BI — riesgo de impago")
if st.button("Calcular riesgo — 2098283606"):
    r = run_tool(calcular_riesgo, cliente_id="2098283606")
    color = {"ALTO": st.error, "MEDIO": st.warning, "BAJO": st.success}[r["nivel_riesgo"]]
    color(f"Nivel de riesgo: {r['nivel_riesgo']} — promedio {r['promedio_dias_atraso']} días de atraso, tendencia creciente: {r['tendencia_creciente']}")
    st.caption("Sin facturación registrada desde marzo 2026. Línea 'Suspended'. SUNAT: BAJA DE OFICIO.")
    st.json(r)

st.divider()
st.subheader("💬 Conversar con el Agente de BI")
st.caption(
    "Esto es el 'chatbot de gestión' del documento: preguntas en lenguaje natural, "
    "respondidas por Gemini pero ancladas SIEMPRE a los datos reales de calcular_riesgo "
    "-- el agente no puede inventar un dato que no esté en ese JSON. Requiere API key "
    "(consume tu cuota igual que el modo IA Completo)."
)

if "chat_api_key" not in st.session_state:
    st.session_state.chat_api_key = api_key or ""
if "chat_bi_historial" not in st.session_state:
    st.session_state.chat_bi_historial = []

chat_key = st.text_input(
    "GEMINI_API_KEY para el chat", value=st.session_state.chat_api_key,
    type="password", key="chat_key_input",
    help="La misma key del modo IA Completo. Se queda solo en esta sesión del navegador.",
)
cliente_chat = st.selectbox(
    "Cliente sobre el que preguntar", options=list(clientes.keys()),
    format_func=lambda c: f"{c} — {clientes[c]}", key="cliente_chat_bi",
)

for msg in st.session_state.chat_bi_historial:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

pregunta = st.chat_input("Ej: ¿por qué este cliente tiene riesgo alto? ¿qué acción de cobro recomiendas?")
if pregunta:
    if not chat_key:
        st.error("Ingresa tu GEMINI_API_KEY arriba para poder chatear con el agente.")
    else:
        st.session_state.chat_api_key = chat_key
        st.session_state.chat_bi_historial.append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("El Agente de BI está consultando el histórico real del cliente..."):
                import os
                os.environ["GEMINI_API_KEY"] = chat_key
                datos_riesgo = run_tool(calcular_riesgo, cliente_id=cliente_chat)
                from agents import llm_analista_bi
                prompt = (
                    "Eres el Agente de BI de SON-IA, el sistema de gestión del ciclo de "
                    "ingreso B2B de Movistar. Un gerente te hace esta pregunta sobre un "
                    f"cliente: \"{pregunta}\"\n\n"
                    f"Cliente: {cliente_chat} — {clientes[cliente_chat]}\n"
                    "Datos de riesgo calculados -- ÚNICA fuente de verdad, no inventes "
                    f"nada fuera de este JSON:\n{json.dumps(datos_riesgo, ensure_ascii=False, indent=2)}\n\n"
                    "Responde en español, 3-5 líneas, tono profesional y directo para "
                    "gerencia. Cita explícitamente el patrón de pago (patron_citado) que "
                    "sustenta tu respuesta. Si preguntan por una acción de cobro, usa el "
                    "campo accion_cobro_sugerida. No ejecutes ninguna acción ni prometas "
                    "nada fuera de informar y sugerir."
                )
                try:
                    respuesta = llm_analista_bi.call(prompt)
                except Exception as e:
                    respuesta = f"⚠️ Error llamando al LLM: {e}"
                st.markdown(respuesta)
        st.session_state.chat_bi_historial.append({"role": "assistant", "content": respuesta})

st.divider()
if modo.startswith("🤖"):
    st.subheader("🤖 Modo IA Completo — correr los 4 agentes con Gemini razonando en vivo")
    st.caption("Esto puede tardar 1-2 minutos y consume tu API key. Úsalo como demo principal; ten el modo rápido como respaldo.")
    if st.button("Ejecutar ciclo O2C completo con IA"):
        if not api_key:
            st.error("Ingresa tu GEMINI_API_KEY en la barra lateral primero.")
        else:
            import os
            os.environ["GEMINI_API_KEY"] = api_key
            with st.spinner("Los 4 agentes están coordinando el ciclo Order-to-Cash..."):
                from crew import crew
                resultado = crew.kickoff()
            st.success("Ciclo completado")
            st.markdown(str(resultado))
