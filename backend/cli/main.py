"""Consola mínima para ejecutar la demostración local del motor.

La ejecución vive en ``runner``. Este módulo interpreta argumentos,
despacha el comando y presenta el resultado. El manejo de ``run``,
``scientific-run`` y ``scientific-campaign`` vive en ``cli.development``.
El manejo de ``e1``, ``e2``, ``e3`` y ``e3-sensitivity`` vive en
``cli.official``. El manejo de ``inspect-e1``, ``inspect-e2``,
``inspect-e3``, ``run-e1``, ``run-e2`` y ``run-e3`` vive en ``cli.bank``.
"""

from __future__ import annotations

import sys

from cli.bank import (
    comando_inspect_e1,
    comando_inspect_e2,
    comando_inspect_e3,
    comando_run_e1,
    comando_run_e2,
    comando_run_e3,
)
from cli.development import (
    comando_run,
    comando_scientific_campaign,
    comando_scientific_run,
)
from cli.official import comando_familia

AYUDA = """\
Uso:
  python -m cli run [opciones]
  python -m cli scientific-run
  python -m cli scientific-campaign
  python -m cli e1 [--json] [--export-evidence]
  python -m cli e2 [--json] [--export-evidence]
  python -m cli e3 [--json] [--export-evidence]
  python -m cli e3-sensitivity [--json] [--export-evidence]
  python -m cli inspect-e1 --config <archivo.json>
  python -m cli inspect-e2 --config <archivo.json>
  python -m cli inspect-e3 --config <archivo.json>
  python -m cli run-e1 --config <archivo.json> [--output <resultado.json>]
  python -m cli run-e2 --config <archivo.json> [--output <resultado.json>]
  python -m cli run-e3 --config <archivo.json> [--output <resultado.json>]

Comandos:
  run                  Ejecuta una demostración local.
  scientific-run       Ejecuta la corrida científica controlada.
  scientific-campaign  Ejecuta la campaña controlada de desarrollo.
  e1                   Ejecuta E1.
  e2                   Ejecuta E2.
  e3                   Ejecuta E3.
  e3-sensitivity       Ejecuta el análisis de sensibilidad de E3.
  inspect-e1           Prepara e inspecciona una campaña E1, sin ejecutarla.
  inspect-e2           Prepara e inspecciona una campaña E2, sin ejecutarla.
  inspect-e3           Prepara e inspecciona una campaña E3, sin ejecutarla.
  run-e1               Ejecuta una campaña E1 configurable, muestra los resultados en consola y no genera un paquete reproducible de evidencia.
  run-e2               Ejecuta una campaña E2 configurable, muestra los resultados en consola y no genera un paquete reproducible de evidencia.
  run-e3               Ejecuta una campaña E3 configurable, muestra los resultados en consola y no genera un paquete reproducible de evidencia.

Opciones de run:
  --strategy {individual,fixed_batch}   Estrategia. Por defecto: individual.
  --batch-size N                        Tamaño de lote. Obligatorio en fixed_batch.
  --events N                            Eventos a generar. Por defecto: 10.
  --recovery {none,sender-driven,receiver-driven}
                                        Recuperación. Por defecto: none.
  --fault silent-loss                   Inyecta una pérdida silenciosa.
  --json                                Resumen operativo en JSON.
  --show-trace                          Traza: tiempo, índice, tipo y entidad.
  --scientific-summary                  Métricas científicas de esta corrida.

Opciones de E1, E2, E3 y sensibilidad:
  --json                                Informe estructurado en JSON.
  --export-evidence                     Exporta evidencia bajo evidence/.

Opciones de inspect-e1:
  --config ARCHIVO                      Configuración E1. Prepara e inspecciona, sin ejecutar.

Opciones de inspect-e2:
  --config ARCHIVO                      Configuración E2. Prepara e inspecciona, sin ejecutar.

Opciones de inspect-e3:
  --config ARCHIVO                      Configuración E3. Prepara e inspecciona, sin ejecutar.

Opciones de run-e1:
  --config ARCHIVO                      Configuración E1. Muestra cada corrida en consola y no genera un paquete reproducible de evidencia.
  --output ARCHIVO                      Guarda el resultado autocontenido. La ruta es relativa al directorio de trabajo.

Opciones de run-e2:
  --config ARCHIVO                      Configuración E2. Muestra cada corrida en consola y no genera un paquete reproducible de evidencia.
  --output ARCHIVO                      Guarda el resultado autocontenido. La ruta es relativa al directorio de trabajo.

Opciones de run-e3:
  --config ARCHIVO                      Configuración E3. Muestra cada corrida en consola y no genera un paquete reproducible de evidencia.
  --output ARCHIVO                      Guarda el resultado autocontenido. La ruta es relativa al directorio de trabajo.

Ayuda:
  -h, --help                            Muestra esta ayuda.
"""

def main(argv: list[str] | None = None) -> int:
    """Ejecuta la consola y devuelve el código de salida."""
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if not argumentos:
        print(AYUDA, end="")
        return 2
    if argumentos[0] in {"-h", "--help", "help"}:
        print(AYUDA, end="")
        return 0
    comando = argumentos[0]
    if comando == "run":
        return comando_run(argumentos[1:], ayuda=AYUDA)
    if comando == "scientific-run":
        return comando_scientific_run(argumentos[1:], ayuda=AYUDA)
    if comando == "scientific-campaign":
        return comando_scientific_campaign(argumentos[1:], ayuda=AYUDA)
    if comando == "inspect-e1":
        return comando_inspect_e1(argumentos[1:], ayuda=AYUDA)
    if comando == "inspect-e2":
        return comando_inspect_e2(argumentos[1:], ayuda=AYUDA)
    if comando == "inspect-e3":
        return comando_inspect_e3(argumentos[1:], ayuda=AYUDA)
    if comando == "run-e1":
        return comando_run_e1(argumentos[1:], ayuda=AYUDA)
    if comando == "run-e2":
        return comando_run_e2(argumentos[1:], ayuda=AYUDA)
    if comando == "run-e3":
        return comando_run_e3(argumentos[1:], ayuda=AYUDA)
    if comando in {"e1", "e2", "e3", "e3-sensitivity"}:
        return comando_familia(comando, argumentos[1:], ayuda=AYUDA)
    print(f"comando desconocido: {comando}", file=sys.stderr)
    print(AYUDA, end="", file=sys.stderr)
    return 2
