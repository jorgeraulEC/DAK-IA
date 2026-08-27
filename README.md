# SON-IA — Sistema Order-to-Cash (Movistar · Hackathon Telecom AI)

Dos piezas, ya conectadas: el MVP interactivo (4 agentes + Streamlit,
detalle completo en `README_MVP_CREWAI.md`) y el pipeline batch
(dataset completo, detalle en `pipeline_batch/README_PIPELINE.md`),
viviendo en el mismo dashboard.

## Para la demo de 30 segundos — el camino más corto

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # abre .env y pega tu GEMINI_API_KEY ahí
streamlit run app.py
```

Se abre el navegador solo. Lo primero que ves es **"0️⃣ Panel
general"**: 4 métricas grandes (3364 facturas, S/447,965 facturado,
79% conciliado sin intervención) y 3 pestañas (Clientes en riesgo /
Errores de conciliación / Tokenización) — eso ya demuestra que corre
contra el dataset completo, no contra 3 clientes armados a mano. Baja
un scroll y siguen las 4 secciones originales (Orquestador,
Facturador, Cobranzas, Analista BI) con los 3 clientes narrados.

Si en vez del dashboard quieres el chat conversacional:

```bash
streamlit run chat_demo.py
```

Pregúntale "dame un resumen" o "cuántos clientes en riesgo" (dataset
completo) o "concilia el pago de CLIENT_00465" (el caso de
discrepancia de siempre) — ambos mundos responden ahí mismo.

## Tu API key — por qué NO está en ningún archivo de este paquete

Me pasaste tu `GEMINI_API_KEY` en el chat. A propósito **no la puse
en ningún archivo** — ni en `.env.example`, ni hardcodeada en
`agents.py` ni en `app.py`. Dos razones:

1. Van a subir esto a GitHub (lo hablamos hace un momento). Si la
   key queda escrita en un archivo del repo, apenas hagan `git push`
   queda expuesta públicamente, aunque después la borren en un commit
   futuro — git recuerda el historial.
2. Una key pegada en texto plano en cualquier chat (este incluido) ya
   se considera potencialmente expuesta como buena práctica. Yo no la
   voy a usar ni a repetir, pero igual te recomiendo **regenerarla**
   en Google AI Studio antes del pitch, por las dudas — toma 30
   segundos y evita un dolor de cabeza después.

Ponla en tu `.env` local (ya está en `.gitignore`, nunca se sube):

```
GEMINI_API_KEY=tu_key_regenerada_aqui
```

Si vas a usar Streamlit Community Cloud para un link en vivo, la key
va como "secret" en su dashboard, no en el repo tampoco.

## Qué corre y qué no corre solo

| Comando | Qué muestra | Requiere API key |
|---|---|---|
| `streamlit run app.py` | Dashboard: panel general (dataset completo) + demo de 3 clientes + chat BI | Solo el chat BI y el botón "Modo IA Completo" |
| `streamlit run chat_demo.py` | Chat guionado, dataset completo + 3 clientes | No |
| `python crew.py` | Los 4 agentes razonando en vivo con Gemini | Sí |
| `python pipeline_batch/run_pipeline.py` | Recalcula `pipeline_batch/salidas/` desde los 6 CSV crudos | No |

Ya viene una corrida de `run_pipeline.py` hecha (`pipeline_batch/salidas/`
tiene los CSV reales), así que `app.py` y `chat_demo.py` funcionan
apenas instalas dependencias — no hace falta correr el pipeline batch
primero, solo si cambias los datos de `pipeline_batch/data_raw/`.

## Lo que se conversó y quedó fuera a propósito

- **Automatización diaria:** no se construyó — quedó claro que era
  solo para entender el concepto ("esto representa lo que correría
  cada día"), no algo que la demo necesite de verdad.
- **`pipeline_batch/reparto_multifactura.py`:** está ahí, probado,
  pero nadie lo llama todavía — ni `run_pipeline.py` ni `app.py` lo
  invocan. Es la pieza que resuelve "un pago cubre varias facturas
  sin desglosar"; el dataset real no trae ningún caso así (ya llega
  desglosado), así que se queda de reserva por si la sustentación lo
  pide. Para probarla: `python pipeline_batch/demo_reparto_multifactura.py`.

## Estructura

```
├── app.py, chat_demo.py, crew.py, agents.py, tasks.py
├── tools/                    (los 6 tools originales, sin cambios)
├── data/                     (3 clientes anonimizados, demo interactiva)
├── pipeline_batch/
│   ├── run_pipeline.py  config.py  carga_datos.py  conciliacion.py
│   ├── riesgo.py  regulatorio.py  tokenizacion.py
│   ├── reparto_multifactura.py + demo_reparto_multifactura.py
│   ├── data_raw/             (los 6 CSV completos del reto)
│   └── salidas/              (resultados ya calculados -- esto lee app.py)
├── requirements.txt
├── .env.example               (plantilla -- tu key va en tu .env local)
└── .gitignore
```
