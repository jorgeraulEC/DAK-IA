"""
Punto de entrada del demo. Corre el crew completo de forma secuencial
sobre el escenario sintético de 3 clientes.

Uso:
    export GEMINI_API_KEY=tu_api_key
    python crew.py
"""
from crewai import Crew, Process

from agents import orquestador, facturador, cobranzas, analista_bi
from tasks import (
    task_validar_osiptel,
    task_facturar_2005150947,
    task_facturar_2075533541,
    task_conciliar_2005150947,
    task_conciliar_2075533541,
    task_riesgo_2098283606,
)

crew = Crew(
    agents=[orquestador, facturador, cobranzas, analista_bi],
    tasks=[
        task_validar_osiptel,
        task_facturar_2005150947,
        task_facturar_2075533541,
        task_conciliar_2005150947,
        task_conciliar_2075533541,
        task_riesgo_2098283606,
    ],
    process=Process.sequential,
    verbose=True,
)

if __name__ == "__main__":
    resultado = crew.kickoff()
    print("\n\n=========== RESULTADO FINAL DEL CREW ===========\n")
    print(resultado)
