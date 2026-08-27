"""
demo_reparto_multifactura.py — Corre reparto_multifactura.py contra 2
casos REALES del dataset (no inventados), a modo de prueba ciega:

  1) Cliente 62740575, abono del 2026-06-18: se fusionan 20 pagos
     reales en 1 solo monto (S/814.73), simulando que el banco lo
     hubiera mandado sin desglosar. Candidatas: sus 22 facturas del
     mismo ciclo. Con 14 de esas 22 valiendo lo mismo (S/37.03, plan
     tarifa plana), el algoritmo encuentra 92 combinaciones distintas
     que suman exacto -- y correctamente escala en vez de adivinar.

  2) Cliente 3677575, abono del 2026-06-14 (S/82.88): 4 facturas
     candidatas, montos ya lo bastante distintos como para que exista
     una sola combinación posible -- se asigna automático, y coincide
     exacto con lo que realmente se pagó (ground truth verificado).

Uso:
    python demo_reparto_multifactura.py
"""
import carga_datos
from reparto_multifactura import asignar_pago_multifactura


def _candidatas_del_ciclo(facturas, cod_cliente, periodo_yyyymm):
    sub = facturas[
        (facturas["COD_CLIENTE"] == cod_cliente)
        & (facturas["FECHA_EMISION"].dt.strftime("%Y-%m") == periodo_yyyymm)
    ]
    return [{"NRO_DOC_FISCAL": r.NRO_DOC_FISCAL, "monto": r.CHARGE_TOTAL_AMOUNT} for r in sub.itertuples()]


def main():
    tablas = carga_datos.cargar_todas_las_tablas(verbose=False)
    pagos, facturas = tablas["pagos"], tablas["facturas"]

    print("=" * 70)
    print("CASO 1 -- ambiguo de verdad (montos repetidos, plan tarifa plana)")
    print("=" * 70)
    real_1 = pagos[(pagos["COD_CLIENTE"] == 62740575) & (pagos["FECHA_PAGO"] == "2026-06-18")]
    monto_1 = round(real_1["MONTO_PAGADO"].sum(), 2)
    candidatas_1 = _candidatas_del_ciclo(facturas, 62740575, "2026-06")
    r1 = asignar_pago_multifactura(monto_1, candidatas_1)
    print(f"Abono consolidado real: S/{monto_1} | candidatas: {len(candidatas_1)}")
    print(f"-> {r1.status}: {r1.motivo}\n")

    print("=" * 70)
    print("CASO 2 -- se resuelve solo, y coincide con lo que de verdad pasó")
    print("=" * 70)
    real_2 = pagos[(pagos["COD_CLIENTE"] == 3677575) & (pagos["FECHA_PAGO"] == "2026-06-14")]
    monto_2 = round(real_2["MONTO_PAGADO"].sum(), 2)
    ground_truth_2 = sorted(real_2["FACTURA_AFECTADA"].tolist())
    candidatas_2 = _candidatas_del_ciclo(facturas, 3677575, "2026-06")
    r2 = asignar_pago_multifactura(monto_2, candidatas_2)
    print(f"Abono consolidado real: S/{monto_2} | candidatas: {len(candidatas_2)}")
    print(f"-> {r2.status}: {r2.motivo}")
    print(f"   Asignó: {r2.facturas_asignadas}")
    print(f"   Lo que de verdad se pagó: {ground_truth_2}")
    print(f"   ¿Coincide exacto? {r2.facturas_asignadas == ground_truth_2}")


if __name__ == "__main__":
    main()
