from __future__ import annotations
import sys
from cli.bank import comando_banco
from cli.import_cpd import comando_import_cpd

AYUDA = """\
Uso:
  python -m cli inspect --config <archivo.json>
  python -m cli run --config <archivo.json> [--output <resultado.json> | --output-dir <directorio>]
  python -m cli import-cpd --config <importacion.json> --output <contact-plan.json>

Comandos:
  inspect                               Prepara e inspecciona la campaña que declara el documento, sin ejecutarla. Una suite muestra cada campaña en el orden declarado, sin ejecutarla.
  run                                   Ejecuta la campaña que declara el documento, muestra los resultados en consola y no genera un paquete reproducible de evidencia. Una suite ejecuta las campañas en el orden declarado.
  import-cpd                            Importa un plan.json nativo CPD al archivo ContactPlanDefinition. No ejecuta simulaciones ni campañas.

Opciones de inspect:
  --config ARCHIVO                      Documento individual del banco o documento de suite. La sección experiments.e1, experiments.e2, experiments.e3 o experiments.e3_sensitivity selecciona la campaña individual. Prepara e inspecciona, sin ejecutar.

Opciones de run:
  --config ARCHIVO                      Documento individual del banco o documento de suite. La sección experiments.e1, experiments.e2, experiments.e3 o experiments.e3_sensitivity selecciona la campaña individual. Muestra cada corrida en consola y no genera un paquete reproducible de evidencia.
  --output ARCHIVO                      Documento individual: guarda el resultado autocontenido. La ruta es relativa al directorio de trabajo. Suite: directorio nuevo cuyo padre ya existe.
  --output-dir DIRECTORIO               Documento individual (E1, E2 o E3): conserva un resultado por corrida en un directorio nuevo. El formato (campaign_run_set) difiere del JSON monolítico de --output. No admite suites ni --output en la misma invocación.
Opciones de import-cpd:
  --config ARCHIVO                      Documento JSON de importación CPD (plan_path, node_mapping, contact_plan_id, cpd_revision, plan_artifact_ref y metadatos opcionales declarados). plan_path se resuelve respecto del directorio de este archivo.
  --output ARCHIVO                      Destino del ContactPlanDefinition. No sobrescribe un archivo existente. Relativo al directorio de trabajo.

Ayuda:
  -h, --help                            Muestra esta ayuda.

Otras entradas:
  python -m cli.development --help
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
        return comando_banco(argumentos[1:], ayuda=AYUDA, comando="inspect")
    if comando == "run":
        return comando_banco(argumentos[1:], ayuda=AYUDA, comando="run")
    if comando == "import-cpd":
        return comando_import_cpd(argumentos[1:], ayuda=AYUDA)
    print(f"comando desconocido: {comando}", file=sys.stderr)
    print(AYUDA, end="", file=sys.stderr)
    return 2
