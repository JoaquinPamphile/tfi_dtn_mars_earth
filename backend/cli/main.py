from __future__ import annotations
import sys

AYUDA = """\
Uso:
  python -m cli inspect --config <archivo.json>
  python -m cli run --config <archivo.json> [--output <ruta> | --output-dir <directorio>]

Comandos:
  inspect                               Prepara e inspecciona las campañas seleccionadas, sin ejecutar.
  run                                   Ejecuta las campañas seleccionadas; no genera evidencia oficial.

Opciones de inspect:
  --config ARCHIVO                      Banco schema_version: 2 con parámetros científicos explícitos.

Opciones de run:
  --config ARCHIVO                      Banco schema_version: 2; E1, E2, E3 y/o sensibilidad E3.
  --output RUTA                         Directorio nuevo con un JSON por experimento, índices parciales inmutables e índice global final. El padre debe existir.
  --output-dir DIRECTORIO               No admitido para bancos V2. Use --output.
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
