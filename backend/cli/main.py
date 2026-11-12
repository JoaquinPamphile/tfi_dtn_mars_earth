from __future__ import annotations
import sys

AYUDA = """\
Uso:
  python -m cli inspect --config <archivo.json>
  python -m cli run --config <archivo.json> [--output <ruta> | --output-dir <directorio>]

Comandos:
  inspect                               Prepara e inspecciona la campaña que declara el documento, sin ejecutarla. Una suite muestra cada campaña en el orden declarado, sin ejecutarla.
  run                                   Ejecuta la campaña que declara el documento, muestra los resultados en consola y no genera un paquete reproducible de evidencia. Una suite ejecuta las campañas en el orden declarado.

Opciones de inspect:
  --config ARCHIVO                      Documento individual v1, banco multi-experimento v2 o suite v1. Prepara e inspecciona sin ejecutar.

Opciones de run:
  --config ARCHIVO                      Documento individual v1, banco multi-experimento v2 o suite v1. Ejecuta las campañas declaradas y no genera evidencia oficial.
  --output RUTA                         Documento individual v1: archivo autocontenido. Banco v2: directorio nuevo con un JSON por experimento, índices parciales inmutables e índice global final. Suite v1: directorio nuevo con resumen. El padre debe existir.
  --output-dir DIRECTORIO               Documento individual (E1, E2 o E3): conserva un resultado por corrida en un directorio nuevo. El formato (campaign_run_set) difiere del JSON monolítico de --output. No admite suites ni --output en la misma invocación.
Ayuda:
  -h, --help                            Muestra esta ayuda.

Otras entradas:
  python -m development.cli --help
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
        from cli.bank import comando_banco
        return comando_banco(argumentos[1:], ayuda=AYUDA, comando="inspect")
    if comando == "run":
        from cli.bank import comando_banco
        return comando_banco(argumentos[1:], ayuda=AYUDA, comando="run")
    print(f"comando desconocido: {comando}", file=sys.stderr)
    print(AYUDA, end="", file=sys.stderr)
    return 2
