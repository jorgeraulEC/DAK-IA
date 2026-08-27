# MVP — Sistema Multi-Agente O2C (CrewAI) · Hackathon Telecom AI

MVP funcional para el pitch. Corre con **datos reales anonimizados**
(carpeta `data/`), derivados del dataset del reto `SONIA_DESAFIO_03`
(tablas `001_TBL_CLIENTES_B2B` … `006_TBL_NOTAS_CREDITO_B2B`) — no se
conecta en vivo a ningún sistema de Movistar, pero los montos, fechas,
RUC y estado SUNAT de los 3 clientes de la demo son reales, no
inventados. Está diseñado para demostrar el flujo completo y, en
particular, el guardrail de seguridad más importante del diseño: *el
OCR nunca decide solo, siempre se cruza contra el extracto bancario
real.*

## 1. Instalación (5 minutos)

```bash
python3 -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configurar tu API key

Los 4 agentes usan modelos Gemini (por economía). Necesitas una API key
de Google AI Studio (aistudio.google.com):

```bash
export GEMINI_API_KEY=tu_api_key_aqui
```

(Si prefieres cambiar el proveedor de algún agente, edita el `model=`
correspondiente en `agents.py` — CrewAI es agnóstico al proveedor vía
LiteLLM. Verifica siempre el nombre exacto del modelo vigente en la
documentación de Google, porque cambia con frecuencia.)

## 3. Correr el demo

```bash
python crew.py
```

Vas a ver en la terminal el razonamiento de cada uno de los 4 agentes
en tiempo real (`verbose=True`), y al final el resultado consolidado.
También puedes correr `streamlit run app.py` para el modo visual
(rápido/sin LLM por defecto, con opción de modo IA completo).

## 4. Qué hace el escenario de demo

El archivo `tasks.py` corre 3 casos **reales** (RUC/montos/fechas del
dataset anonimizado), periodo de facturación **2026-07** — el último
ciclo completo disponible en el dataset:

| Cliente (RUC) | Qué demuestra | Evidencia real |
|---|---|---|
| **2005150947** (CLIENT_00073, San Isidro) | Flujo feliz: factura validada contra contrato/OC (S/281.89), pago conciliado exacto contra el banco, antes del vencimiento. | Facturas `S7AA-0067575326` / `S9AA-0082939903`, pagadas el mismo monto en jun y jul 2026, 3-7 días antes de vencer. |
| **2075533541** (CLIENT_00465, Huancayo) | **El caso más importante para el jurado.** El voucher (OCR) que dice haber pagado el cliente indica S/18.97 (el total facturado), pero el extracto bancario real solo registró S/9.49 — el agente de Cobranzas detecta la discrepancia y **escala a revisión humana en vez de cerrar la deuda solo.** El mismo patrón de pago parcial (~50%) se repite en mayo y junio 2026. | Facturas `S9AA-0080856506/0082123951/0082588997` vs. pagos reales por la mitad del monto en cada una. |
| **2098283606** (CLIENT_00347, Comas) | El Analista BI calcula riesgo de impago **ALTO** por historial real de atrasos (94 a 214 días) y pagos de solo ~5% del monto facturado. Además, el Orquestador detecta que el RUC está **BAJA DE OFICIO** en SUNAT y la línea está `Suspended` — alerta regulatoria antes de que el ciclo avance. Sin facturación desde marzo 2026. | Historial real nov-2025 a mar-2026 (`historial_pagos.json`), `SUNAT_ESTADO_CONTRIBUYENTE` real (`clientes.json`). |

## 5. Cómo se derivó `data/` del dataset real

El dataset `SONIA_DESAFIO_03` trae 6 tablas B2B (clientes, planta fija,
planta móvil, pagos, facturas, notas de crédito) pero **no** trae
contratos formales, órdenes de compra, extracto bancario "de banco" ni
comprobantes OCR como archivos separados — son conceptos que en el
mundo real viven en otros sistemas (CRM/contratos, tesorería, buzón de
correo). Se derivó cada uno del dato real más cercano disponible:

| Archivo | Origen real | Nota |
|---|---|---|
| `clientes.json` | `001_TBL_CLIENTES_B2B` (RUC, SUNAT) | Sin cambios, solo los 3 clientes de la demo. |
| `contratos.json` | `002/003_TBL_PLANTA_*` (servicio, fecha de alta) + `005_TBL_FACTURAS_B2B` (monto mensual típico) | `plazo_credito_dias=16` se calculó restando `FECHA_EMISION` a `FECHA_VTO` en cientos de facturas reales — es un valor consistente en todo el dataset, no inventado. |
| `ordenes_compra.json` | `005_TBL_FACTURAS_B2B`, periodo 2026-07 | Al no existir OC real, se usa el monto realmente facturado ese mes como "monto esperado" que el Facturador valida. El cliente riesgo no tiene entrada porque no hay factura real de julio 2026 para él (coincide con la narrativa: servicio suspendido). |
| `extracto_bancario.json` | `004_TBL_PAGOS_B2B` | Fechas y montos 100% reales; `movimiento_id` es una clave sintética (el dataset no trae ID de movimiento bancario, solo el objeto pagado y la factura afectada). |
| `vouchers.json` | No existe en el dataset (es un input del cliente, no un dato de Movistar) | Es la única pieza necesariamente simulada — pero calibrada contra los montos reales del extracto bancario para reproducir fielmente el patrón de pago parcial encontrado en los datos. |
| `historial_pagos.json` | `FECHA_VTO` (facturas) vs. `FECHA_PAGO` (pagos), ambas reales | Días de atraso calculados, no inventados. |

## 6. Si algo falla en vivo durante la presentación

Corre esto antes del pitch y guarda la salida como respaldo (no
depende de ninguna API key, corre offline):

```bash
python -c "
from tools.banking_tool import conciliar_pago
from tools.ocr_tool import leer_voucher
from tools.risk_tool import calcular_riesgo
from tools.osiptel_tool import validar_regulatorio
import json

def run(tool, **kw): return tool.run(**kw)

v = json.loads(run(leer_voucher, cliente_id='2075533541'))
print(run(conciliar_pago, cliente_id='2075533541', monto_voucher_ocr=v['monto_extraido']))
print(run(calcular_riesgo, cliente_id='2098283606'))
print(run(validar_regulatorio, cliente_id='2098283606'))
"
```

Esto prueba la lógica del guardrail, el scoring de riesgo y el filtro
regulatorio/SUNAT sin depender de que el LLM responda en vivo — útil
como plan B si el wifi del venue falla.

## 7. Qué es real vs. qué es mock (sé transparente con el jurado)

- **Real:** la arquitectura de 4 agentes, la separación de permisos
  por agente, el guardrail de conciliación (OCR nunca es fuente de
  verdad), la lógica de validación de facturas contra contrato/OC, y
  **todos los montos/fechas/RUC/estado SUNAT** de los 3 clientes de
  la demo (ver tabla de la sección 5).
- **Mock (para el MVP):** las *conexiones en vivo* a sistemas de
  Movistar (`Banking_API_Connector`, `Osiptel_Validator`, `DB_API`)
  leen de JSON local en vez de sistemas reales — pero ese JSON local
  contiene datos reales del dataset, no sintéticos. La llamada a
  Osiptel en sí siempre devuelve "sin alertas" (no hay dataset de
  Osiptel); el comprobante/voucher OCR es la única pieza sin
  contraparte real en el dataset. El scoring de riesgo usa una regla
  simple en vez de un modelo scikit-learn entrenado.
- **Roadmap a producción:** documentado en `Especificacion_CrewAI_O2C.docx`
  (matriz de riesgos OWASP ASI, permisos mínimos, checkpoints humanos,
  plan de implementación por fases).

## 8. Estructura del proyecto

```
movistar-o2c-crew/
├── agents.py          # Los 4 agentes y su LLM asignado
├── tasks.py           # El escenario de demo (3 clientes reales, periodo 2026-07)
├── crew.py            # Punto de entrada — python crew.py
├── app.py             # Interfaz Streamlit (modo rápido / modo IA completo)
├── data/               # Datos derivados del dataset real (ver sección 5)
│   ├── clientes.json         # RUC + estado SUNAT real
│   ├── contratos.json
│   ├── ordenes_compra.json
│   ├── extracto_bancario.json
│   ├── vouchers.json          # única pieza simulada (no existe en el dataset)
│   └── historial_pagos.json
└── tools/              # Las 4 herramientas — aquí vive la lógica de seguridad
    ├── db_tool.py           # Solo lectura de contratos/OC
    ├── invoice_tool.py      # Validación + generación de factura
    ├── ocr_tool.py          # Lectura de voucher (marcado como no autoritativo)
    ├── banking_tool.py      # Fuente de verdad + guardrail de conciliación
    ├── osiptel_tool.py      # Mock de Osiptel + estado SUNAT real
    └── risk_tool.py         # Scoring de riesgo de impago
```
