"""
reparto_multifactura.py — Asignación de un pago SIN desglosar contra
las facturas abiertas de un cliente ("una empresa tiene 100 facturas
y paga todo el monto en un solo pago").

Por qué existe este módulo (ver conversación): el dataset
SONIA_DESAFIO_03 ya llega con los pagos pre-asignados a nivel de
factura -- cada fila de 004_TBL_PAGOS_B2B trae su propia
FACTURA_AFECTADA. No hay en el dataset crudo un caso real de "un
monto sin desglosar cubre N facturas". Esto resuelve el problema para
cuando SÍ llega así -- el escenario real descrito por el equipo: el
banco manda un abono consolidado y hay que decidir a qué facturas
corresponde, sin que nadie te diga cuáles.

Algoritmo: suma-de-subconjuntos exacta, en centavos (sin tolerancia de
redondeo -- no hace falta, ya se trabaja en enteros). Se cuenta cuántos
subconjuntos DISTINTOS de las facturas candidatas suman exactamente el
monto pagado:

  - 0 subconjuntos  -> SIN_COINCIDENCIA. Escalar.
  - 1 subconjunto   -> ASIGNADO. Se aplica automáticamente.
  - 2+ subconjuntos -> AMBIGUO. Escalar -- aunque el monto total
    coincida, no hay forma segura de saber CUÁL combinación de
    facturas es la correcta. Esto pasa más seguido de lo que parece:
    con montos repetidos (planes con tarifa plana), sobran candidatas
    intercambiables y el guardrail lo detecta en vez de adivinar.

Se usa programación dinámica (conteo por suma alcanzable) en vez de
enumerar cada subconjunto con itertools -- con N facturas candidatas
hay hasta 2^N subconjuntos posibles, y esta tabla los cuenta sin
generarlos uno por uno. Solo si el conteo da exactamente 1 se
reconstruye (retrocediendo sobre la tabla) cuál es esa única
combinación.
"""
from dataclasses import dataclass, field


def _centavos(monto: float) -> int:
    return round(monto * 100)


@dataclass
class ResultadoReparto:
    status: str  # "ASIGNADO" | "SIN_COINCIDENCIA" | "AMBIGUO"
    monto_pagado: float
    cantidad_candidatas: int
    facturas_asignadas: list = field(default_factory=list)
    combinaciones_posibles: int = 0
    motivo: str = ""


def asignar_pago_multifactura(monto_pagado: float, facturas_abiertas: list[dict]) -> ResultadoReparto:
    """facturas_abiertas: lista de {"NRO_DOC_FISCAL": str, "monto": float}
    -- las facturas candidatas de ESE cliente a las que este pago
    podría corresponder (p.ej. las emitidas en el ciclo vigente)."""
    objetivo = _centavos(monto_pagado)
    items = [(f["NRO_DOC_FISCAL"], _centavos(f["monto"])) for f in facturas_abiertas]

    # --- Fase 1: contar subconjuntos por suma alcanzable (sin enumerar) ---
    # dp_historial[i] = {suma_centavos: cantidad_de_formas} usando las
    # primeras i facturas. Se guarda cada paso para poder reconstruir
    # después si el conteo final da exactamente 1.
    dp_historial = [{0: 1}]
    for _, monto_c in items:
        dp_prev = dp_historial[-1]
        dp_next = dict(dp_prev)
        for suma, cantidad in dp_prev.items():
            nueva_suma = suma + monto_c
            if nueva_suma <= objetivo:  # todo monto es positivo -> nunca hace falta pasarse
                dp_next[nueva_suma] = dp_next.get(nueva_suma, 0) + cantidad
        dp_historial.append(dp_next)

    total_combinaciones = dp_historial[-1].get(objetivo, 0)

    if total_combinaciones == 0:
        return ResultadoReparto(
            status="SIN_COINCIDENCIA", monto_pagado=monto_pagado,
            cantidad_candidatas=len(items),
            motivo="Ningún subconjunto de las facturas candidatas suma exacto este monto. Escalar a revisión humana.",
        )

    if total_combinaciones > 1:
        return ResultadoReparto(
            status="AMBIGUO", monto_pagado=monto_pagado,
            cantidad_candidatas=len(items),
            combinaciones_posibles=total_combinaciones,
            motivo=(
                f"{total_combinaciones} combinaciones distintas de facturas suman "
                f"exacto este monto -- típico cuando hay montos repetidos (planes "
                f"tarifa plana). No se puede saber cuál es la correcta sin más "
                f"información. Escalar a revisión humana."
            ),
        )

    # --- Fase 2: hay EXACTAMENTE 1 -> reconstruir cuál, retrocediendo ---
    asignadas = []
    suma_restante = objetivo
    for i in range(len(items) - 1, -1, -1):
        nro_doc, monto_c = items[i]
        dp_antes = dp_historial[i]  # tabla usando solo las facturas 0..i-1
        # ¿Esta factura fue parte de la única combinación? Lo fue si,
        # al excluirla, el resto ya no podría alcanzar la suma restante
        # (dp_antes no tiene esa suma) pero incluyéndola sí calza.
        si_se_incluye = (suma_restante - monto_c) in dp_antes
        si_se_excluye = suma_restante in dp_antes
        if si_se_incluye and not si_se_excluye:
            asignadas.append(nro_doc)
            suma_restante -= monto_c

    return ResultadoReparto(
        status="ASIGNADO", monto_pagado=monto_pagado,
        cantidad_candidatas=len(items),
        facturas_asignadas=sorted(asignadas),
        combinaciones_posibles=1,
        motivo="Coincidencia única entre las candidatas -- se aplica automáticamente.",
    )


if __name__ == "__main__":
    # Ejemplo mínimo, sin depender del dataset -- ver
    # demo_reparto_multifactura.py para el caso con datos reales.
    candidatas = [
        {"NRO_DOC_FISCAL": "A", "monto": 100.00},
        {"NRO_DOC_FISCAL": "B", "monto": 50.00},
        {"NRO_DOC_FISCAL": "C", "monto": 30.00},
    ]
    print(asignar_pago_multifactura(150.00, candidatas))   # A+B -> único -> ASIGNADO
    print(asignar_pago_multifactura(999.00, candidatas))   # nada suma esto -> SIN_COINCIDENCIA
    candidatas_ambiguas = candidatas + [{"NRO_DOC_FISCAL": "D", "monto": 20.00}, {"NRO_DOC_FISCAL": "E", "monto": 10.00}]
    print(asignar_pago_multifactura(30.00, candidatas_ambiguas))  # C, o D+E -> AMBIGUO
