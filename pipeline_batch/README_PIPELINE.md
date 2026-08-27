# Pipeline batch O2C — dataset completo (SONIA_DESAFIO_03)

Contraparte "todos los datos" de tu MVP de CrewAI (`tools/*.py`, que
razona 1 cliente a la vez con LLM). Esto corre los 1000 clientes /
3364 facturas / 3548 pagos reales sin necesitar ninguna API key —
mismo principio que el "Modo Rápido" de tu `app.py`: lógica
determinística, nunca falla por wifi o LLM caído.

## Instalación y uso

```bash
pip install pandas
```

Copia las 6 tablas del dataset (`001_TBL_CLIENTES_B2B.csv` …
`006_TBL_NOTAS_CREDITO_B2B.csv`) dentro de la carpeta `data_raw/`
que ya viene en este paquete (o edita `RUTA_DATOS_CRUDOS` en
`config.py` si prefieres apuntar a otra ruta). Luego:

```bash
python run_pipeline.py
```

Esto deja en `salidas/` todo lo que la interfaz (dashboard + chatbot)
necesita — ver mapeo abajo. Ya viene una corrida de ejemplo en
`salidas/` (contra tu dataset real) para que puedas revisar el
resultado sin instalar nada primero.

## Los 9 archivos

| Archivo | Qué hace | Contraparte en tu MVP actual |
|---|---|---|
| `config.py` | Rutas, umbrales, fecha de referencia | — |
| `carga_datos.py` | Carga + limpia las 6 tablas (separador `|`, encoding ISO-8859-1, 3 formatos de fecha distintos) | — |
| `tokenizacion.py` | Pseudonimiza RUC antes de que cualquier dato toque un LLM | (nuevo — no existía en el MVP) |
| `conciliacion.py` | El guardrail: cruza pagos↔facturas↔notas de crédito para los 3364, nunca "adivina" | `tools/banking_tool.py` + `tools/ocr_tool.py` |
| `riesgo.py` | Score de riesgo por cliente desde fechas reales | `tools/risk_tool.py` |
| `regulatorio.py` | Estado SUNAT + estado de línea, para los 1000 clientes | `tools/osiptel_tool.py` |
| `reparto_multifactura.py` | Asigna un pago consolidado (sin desglosar) contra las facturas abiertas de un cliente; escala si es ambiguo | (nuevo — no existía en el MVP) |
| `demo_reparto_multifactura.py` | Corre `reparto_multifactura.py` contra 2 casos reales (uno ambiguo, uno único) | — |
| `run_pipeline.py` | Orquesta todo y escribe `salidas/` | `crew.py` |

## Mapeo directo a lo que pediste para el dashboard

- **Facturas procesadas / no procesadas** → `salidas/facturas_procesadas.csv`
  y `salidas/facturas_no_procesadas.csv`.
- **Reportes por errores en la conciliación** → `salidas/reporte_errores_conciliacion.csv`
  (pagos que ningún ajuste determinístico logra vincular — cola real
  para revisión humana) + `salidas/correcciones_automaticas_aplicadas.csv`
  (auditoría de lo que SÍ se corrigió solo, y cómo).
- **Clasificación de usuarios / cuáles tienen riesgo** → `salidas/clientes_clasificados.csv`.
  Ojo: `segmento_riesgo_final` (riesgo de pago real) y
  `tiene_ficha_maestro_clientes` / `status_regulatorio` (si podemos
  validarle SUNAT) son columnas **separadas a propósito** — no mezcles
  "no tengo su ficha SUNAT" con "es un mal pagador", son problemas
  distintos con dueños distintos.
- **Datos tokenizados para la IA** → `salidas/clientes_clasificados_TOKENIZADO_para_IA.csv`
  (esto es lo único que debería tocar un prompt) vs.
  `salidas/mapa_reverso_NO_COMPARTIR.csv` (el mapeo inverso — se queda
  en el backend, nunca sale).
- **Estadísticas** → `salidas/resumen_estadisticas.json`.

## Decisiones de diseño que quizás te pregunten en la sustentación

1. **Nunca se hace matching pago↔factura por "mismo cliente + monto
   parecido".** Solo por número de documento exacto, o por una
   corrección de formato 100% determinística y verificada contra
   facturas reales (ceros a la izquierda). Si no hay match así, se
   reporta para revisión humana — igual que ya hace
   `conciliar_pago()` en tu MVP, ahora a escala.
2. **"Sin ficha en el maestro SUNAT" no es lo mismo que "riesgo de
   pago".** El cruce pagos↔facturas usa `NRO_DOC_FISCAL` /
   `FACTURA_AFECTADA`, nunca pasa por `001_TBL_CLIENTES_B2B` — por
   eso el ~45% de RUC sin ficha se concilian con la misma tasa
   (79.4%) que los que sí la tienen (78.3%). Solo se les bloquea la
   validación SUNAT/Osiptel, no la cobranza.
3. **Tolerancia de S/0.01**, igual que `invoice_tool.py` /
   `banking_tool.py` del MVP. `diferencia_es_trivial_redondeo` en
   `facturas_no_procesadas.csv` separa el ~7% que probablemente es
   solo redondeo de IGV del resto (mediana real ~S/19.60, sí son
   discrepancias sustantivas).
4. **`reparto_multifactura.py` nunca asigna por "el total cuadra".**
   Cuenta CUÁNTOS subconjuntos de facturas candidatas suman el monto
   exacto; con planes de tarifa plana (montos repetidos) suele haber
   decenas de combinaciones válidas — probado con un caso real de 22
   facturas candidatas donde salieron 92 combinaciones posibles, y el
   sistema escaló en vez de adivinar cuál.

## Qué es real vs. qué falta para que esto sea "operativo" (no solo simulación)

Sé transparente con el jurado — misma idea que ya tiene tu README
original en la sección 7, aplicada a esta parte:

**Real y verificado, no simulado:** las 1000 filas de clientes, 3364
facturas, 3548 pagos, 196 notas de crédito son el dataset completo,
no una muestra armada a mano. La conciliación, el riesgo, lo
regulatorio y el reparto multifactura corrieron de punta a punta
contra esos datos y cada número de este README (2611 conciliadas
exactas, 44 recuperadas por normalización, 8 pagos sin resolver, 92
combinaciones ambiguas, etc.) es el resultado real de esa corrida.

**Lo que esto NO es todavía:**
- **No corre solo.** Es `python run_pipeline.py` a mano contra un CSV
  estático — no hay scheduler, cron, ni la simulación de "los datos
  llegan cada madrugada" que se conversó (no llegó a construirse;
  avísame si la quieres para el video).
- **No está conectado a `app.py` ni a `chat_demo.py`.** Los outputs
  viven en `salidas/*.csv`; falta el trabajo de apuntar el
  dashboard/chat existente a esos archivos.
- **`reparto_multifactura.py` no se dispara automáticamente** dentro
  de `run_pipeline.py`. El dataset real ya llega pre-desglosado, así
  que hoy no hay ninguna fila que lo active — está listo y probado,
  pero como pieza aparte.
- **La capa de IA (los 4 agentes, el chat con Gemini) es la tuya de
  antes.** No se tocó ni se corrió en esta conversación (no hay
  acceso a tu `GEMINI_API_KEY`). Todo lo de este paquete es lógica
  determinística, sin LLM de por medio.
