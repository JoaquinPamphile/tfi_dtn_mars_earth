from __future__ import annotations
import sys
from cli.bank import comando_inspect, comando_run

AYUDA = """\
Uso:
  python -m cli inspect --config <archivo.json>
  python -m cli run --config <archivo.json> [--output <resultado.json>]

Comandos:
  inspect                               Prepara e inspecciona la campaña que declara el documento, sin ejecutarla.
  run                                   Ejecuta la campaña que declara el documento, muestra los resultados en consola y no genera un paquete reproducible de evidencia.

Opciones de inspect:
  --config ARCHIVO                      Documento del banco. La sección experiments.e1, experiments.e2 o experiments.e3 selecciona la campaña. Prepara e inspecciona, sin ejecutar.

Opciones de run:
  --config ARCHIVO                      Documento del banco. La sección experiments.e1, experiments.e2 o experiments.e3 selecciona la campaña. Muestra cada corrida en consola y no genera un paquete reproducible de evidencia.
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
    if comando == "inspect":
        return comando_inspect(argumentos[1:], ayuda=AYUDA)
    if comando == "run":
        return comando_run(argumentos[1:], ayuda=AYUDA)
    print(f"comando desconocido: {comando}", file=sys.stderr)
    print(AYUDA, end="", file=sys.stderr)
    return 2
