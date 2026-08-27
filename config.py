"""
config.py — Rutas y constantes de negocio del pipeline batch.

Centraliza todo lo que antes estaba hardcodeado en las tools/*.py del
demo (3 clientes) para que ahora aplique al dataset completo
SONIA_DESAFIO_03 (1000 clientes, ~3364 facturas, ~3548 pagos).
"""
from pathlib import Path
from datetime import date

# --- Rutas -----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
RUTA_DATOS_CRUDOS = BASE_DIR / "data_raw"   # coloca aquí las 6 tablas 001..006
RUTA_SALIDAS = BASE_DIR / "salidas"

ARCHIVOS_CRUDOS = {
    "clientes": "001_TBL_CLIENTES_B2B.csv",
    "planta_fija": "002_TBL_PLANTA_FIJA_B2B.csv",
    "planta_movil": "003_TBL_PLANTA_MOVIL_B2B.csv",
    "pagos": "004_TBL_PAGOS_B2B.csv",
    "facturas": "005_TBL_FACTURAS_B2B.csv",
    "notas_credito": "006_TBL_NOTAS_CREDITO_B2B.csv",
}

# Las 6 tablas del reto vienen delimitadas por "|" y en ISO-8859-1
# (no UTF-8) -- confirmado inspeccionando los bytes crudos, no asumido.
CSV_SEP = "|"
CSV_ENCODING = "ISO-8859-1"

# --- Fecha de referencia ("hoy" simulado) -----------------------------
# Mismo valor que ya usa el README/demo original (2026-08-16) para que
# el batch sea consistente con el MVP de CrewAI. FECHA_VTO del dataset
# completo llega hasta 2026-08-18, así que sigue siendo una fecha de
# corte razonable (no deja "vencido" casi todo el dataset de golpe).
FECHA_REFERENCIA = date(2026, 8, 16)

# --- Tolerancias y reglas de conciliación -----------------------------
# Mismo umbral que ya usan invoice_tool.py / banking_tool.py (abs(...) < 0.01)
TOLERANCIA_MONTO = 0.01

# --- Umbrales de riesgo (idénticos a tools/risk_tool.py) --------------
UMBRAL_DIAS_ATRASO_ALTO = 15
UMBRAL_DIAS_ATRASO_MEDIO = 5
UMBRAL_TENDENCIA_ALTO = 10

ACCIONES_POR_NIVEL = {
    "ALTO": "Contacto proactivo antes del vencimiento + oferta de plan de pago "
            "fraccionado; escalar a gestor de cuenta senior.",
    "MEDIO": "Recordatorio automático 5 días antes del vencimiento por "
             "correo/WhatsApp; sin escalamiento humano todavía.",
    "BAJO": "Mantener ciclo de facturación estándar; sin acción de cobranza "
            "adicional.",
}

# --- Tokenización -------------------------------------------------------
# Clave usada para pseudonimizar RUC/códigos internos antes de que
# cualquier dato toque un LLM. En producción esto va en una variable de
# entorno o un secret manager (AWS Secrets Manager / GCP Secret Manager),
# NUNCA hardcodeada en el repo -- se deja aquí como placeholder explícito
# para que sea imposible no darse cuenta de que hay que reemplazarla.
CLAVE_TOKENIZACION = "REEMPLAZAR_EN_PRODUCCION_POR_SECRET_MANAGER"
