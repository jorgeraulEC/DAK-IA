from crewai import Task
from agents import orquestador, facturador, cobranzas, analista_bi

# Escenario de demo: 3 clientes REALES del dataset (anonimizado) SONIA_DESAFIO_03,
# periodo de facturación 2026-07 (último ciclo completo disponible en el dataset;
# hoy simulado es 2026-08-16, así que 2026-07 es el último periodo ya cerrado).
#
#   CLI 2005150947 (CLIENT_00073, San Isidro) -- flujo feliz: Trío FTTH S/281.89,
#       facturado y pagado exacto y antes del vencimiento dos meses seguidos.
#   CLI 2075533541 (CLIENT_00465, Huancayo) -- caso de discrepancia real: el banco
#       solo registró ~50% de lo facturado en mayo, junio y julio (pago consolidado
#       el 21/07 que no cubre el total de ninguna de las 3 facturas). Debe escalar.
#   CLI 2098283606 (CLIENT_00347, Comas) -- riesgo ALTO real: SUNAT BAJA DE OFICIO,
#       línea "Suspended", sin facturación desde marzo 2026 y, cuando facturaba,
#       pagos de ~5% del monto con hasta 214 días de atraso.

task_validar_osiptel = Task(
    description=(
        "Verifica el cumplimiento regulatorio (Osiptel + estado fiscal SUNAT) "
        "para los clientes 2005150947, 2075533541 y 2098283606 antes de "
        "continuar el ciclo O2C. Reporta cualquier alerta encontrada -- en "
        "particular, cualquier cliente cuyo RUC no esté HABIDO/ACTIVO en SUNAT "
        "debe quedar marcado para revisión humana antes de seguir el flujo."
    ),
    expected_output="Resumen de cumplimiento regulatorio y fiscal por cliente.",
    agent=orquestador,
)

task_facturar_2005150947 = Task(
    description=(
        "Valida y genera la prefactura del cliente 2005150947 para el periodo "
        "2026-07 por un monto de 281.89 (monto real facturado, sin descuentos). "
        "Usa el contrato y la OC del cliente para validar antes de emitir."
    ),
    expected_output="Prefactura validada o reporte de error, en formato JSON.",
    agent=facturador,
)

task_facturar_2075533541 = Task(
    description=(
        "Valida y genera la prefactura del cliente 2075533541 para el periodo "
        "2026-07 por un monto de 18.97 (monto real facturado ese mes). Usa el "
        "contrato y la OC del cliente."
    ),
    expected_output="Prefactura validada o reporte de error, en formato JSON.",
    agent=facturador,
)

task_conciliar_2005150947 = Task(
    description=(
        "Concilia el pago del cliente 2005150947: lee el voucher enviado por "
        "el cliente con OCR y CRUZA obligatoriamente el monto contra el "
        "extracto bancario real antes de dar por cerrada la deuda."
    ),
    expected_output="Resultado de conciliación: CONCILIADO o escalado a revisión humana.",
    agent=cobranzas,
)

task_conciliar_2075533541 = Task(
    description=(
        "Concilia el pago del cliente 2075533541: lee el voucher con OCR y "
        "CRUZA obligatoriamente el monto contra el extracto bancario real. "
        "Este caso es un caso REAL de discrepancia (pago parcial recurrente, "
        "~50% de lo facturado) -- si la encuentras, NO cierres la deuda: "
        "repórtalo como escalado a revisión humana."
    ),
    expected_output="Resultado de conciliación: CONCILIADO o escalado a revisión humana.",
    agent=cobranzas,
)

task_riesgo_2098283606 = Task(
    description=(
        "Calcula el riesgo de impago del cliente 2098283606 usando su "
        "historial de pagos real, y redacta una alerta breve en lenguaje "
        "natural para gerencia si el riesgo es MEDIO o ALTO. Menciona que el "
        "cliente no tiene facturación desde marzo 2026 y que su RUC figura "
        "como BAJA DE OFICIO en SUNAT. No ejecutes ninguna acción sobre la "
        "cuenta, solo informa."
    ),
    expected_output="Score de riesgo y alerta en lenguaje natural para gerencia.",
    agent=analista_bi,
)
