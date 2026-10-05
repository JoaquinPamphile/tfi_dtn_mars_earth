"""Construye la imagen de release desde el commit HEAD.

El contexto es el tar de ``git archive`` de ese commit, más el sello
``git_archive``. No copia el working tree. No hay ``--build-arg`` de
``SOURCE_STATE``: ``clean`` lo escribe este proceso porque el contexto
acaba de salir de ese archivo.

La versión de la etiqueta se lee de ``backend/experiments/VERSION`` en
el commit. No hay una segunda constante de versión.

Uso, desde cualquier directorio:

    python scripts/build_release_image.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from experiments.release_context import (  # noqa: E402
    STAMP_FILENAME,
    assert_context_matches_blobs,
    git_archive_command,
    materialize_release_context,
    validate_release_dockerfile,
)
from experiments.software_provenance import OBSERVATION_GIT_ARCHIVE  # noqa: E402

IMAGE = "tfi-dtn-mars-earth-release"
_TAG = r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$"


def main() -> int:
    """Resuelve HEAD, arma el contexto del commit y construye la imagen."""
    commit = _git_text(REPO, ["git", "rev-parse", "--verify", "HEAD^{commit}"]).strip()
    version = _version_from_commit(commit)
    if re.fullmatch(_TAG, version) is None:
        print(f"VERSION del commit no es una etiqueta Docker válida: {version}", file=sys.stderr)
        return 1
    dockerfile = REPO / "docker" / "Dockerfile.release"
    try:
        validate_release_dockerfile(dockerfile.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    archive = _git_bytes(REPO, git_archive_command(commit))
    blobs = _blobs(commit)
    with tempfile.TemporaryDirectory(prefix="tfi-release-") as tmp:
        destination = Path(tmp)
        payload = materialize_release_context(archive, destination, commit)
        try:
            assert_context_matches_blobs(destination, blobs)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        loader = destination / "backend" / "experiments" / "software_provenance.py"
        loader_text = loader.read_text(encoding="utf-8")
        tag_version = f"{IMAGE}:{version}"
        tag_commit = f"{IMAGE}:{commit}"
        _run_visible(
            [
                "docker",
                "build",
                "-f",
                str(dockerfile),
                "-t",
                tag_version,
                "-t",
                tag_commit,
                str(destination),
            ],
            cwd=REPO,
        )
    print(f"source_revision {commit}")
    print(f"software_version {version}")
    print(f"stamp_file {STAMP_FILENAME}")
    print(f"observation {payload['observation']}")
    print(f"source_state {payload['source_state']}")
    print(f"image {tag_version}")
    print(f"image {tag_commit}")
    observado = _campos(_probe(tag_version))
    for clave in (
        "stamp_observation",
        "stamp_source_revision",
        "stamp_source_state",
        "software_version",
        "source_revision",
        "source_state",
        "official_guard",
        "sensitivity_guard",
    ):
        print(f"{clave} {observado[clave]}")
    if OBSERVATION_GIT_ARCHIVE not in loader_text:
        print(
            "aviso: este commit no contiene el loader de git_archive. "
            "El archivo del sello dice clean porque el contexto es ese "
            "commit, pero el código empaquetado deja current_provenance() "
            "en unknown. Un release que reporte clean requiere que ese "
            "loader esté dentro del commit.",
            file=sys.stderr,
        )
        return 0
    if observado["source_state"] != "clean" or observado["official_guard"] != "accepted":
        print("la imagen no reportó un release clean verificable", file=sys.stderr)
        return 1
    return 0


def _campos(texto: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for line in texto.splitlines():
        clave, separador, valor = line.partition(" ")
        if separador != " ":
            raise SystemExit(f"línea inesperada del probe: {line}")
        campos[clave] = valor
    return campos


def _probe(image: str) -> str:
    code = (
        "import json\n"
        "from pathlib import Path\n"
        "from experiments.software_provenance import (\n"
        "    ProvenanceError,\n"
        "    current_provenance,\n"
        "    require_frozen_source,\n"
        ")\n"
        "stamp = json.loads(Path('/app/software_provenance.json').read_text(encoding='utf-8'))\n"
        "print('stamp_observation', stamp.get('observation'))\n"
        "print('stamp_source_revision', stamp.get('source_revision'))\n"
        "print('stamp_source_state', stamp.get('source_state'))\n"
        "p = current_provenance()\n"
        "print('software_version', p.software_version)\n"
        "print('source_revision', p.source_revision)\n"
        "print('source_state', p.source_state)\n"
        "for role in ('official', 'sensitivity'):\n"
        "    try:\n"
        "        require_frozen_source(role, p)\n"
        "    except ProvenanceError:\n"
        "        print(role + '_guard', 'rejected')\n"
        "    else:\n"
        "        print(role + '_guard', 'accepted')\n"
    )
    completed = _run(
        ["docker", "run", "--rm", "--entrypoint", "python", image, "-c", code],
        cwd=REPO,
    )
    return completed.stdout.decode("utf-8")


def _version_from_commit(commit: str) -> str:
    raw = _git_bytes(REPO, ["git", "cat-file", "blob", f"{commit}:backend/experiments/VERSION"])
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeError as exc:
        raise SystemExit("VERSION del commit no es UTF-8") from exc
    if text == "" or any(character.isspace() for character in text):
        raise SystemExit("VERSION del commit debe contener una sola versión, sin espacios")
    return text


def _blobs(commit: str) -> dict[str, bytes]:
    listing = _git_text(REPO, ["git", "ls-tree", "-r", commit])
    blobs: dict[str, bytes] = {}
    for line in listing.splitlines():
        if line == "":
            continue
        meta, separator, path = line.partition("\t")
        if separator != "\t" or path == "":
            raise SystemExit(f"línea inesperada de git ls-tree: {line}")
        kind = meta.split()[1]
        if kind != "blob":
            raise SystemExit(f"el commit tiene una entrada que no es un blob: {path}")
        blobs[path] = _git_bytes(REPO, ["git", "cat-file", "blob", f"{commit}:{path}"])
    if not blobs:
        raise SystemExit("el commit no tiene archivos")
    return blobs


def _git_text(repo: Path, args: list[str]) -> str:
    completed = _run(args, cwd=repo)
    return completed.stdout.decode("utf-8")


def _git_bytes(repo: Path, args: list[str]) -> bytes:
    return _run(args, cwd=repo).stdout


def _run_visible(args: list[str], *, cwd: Path) -> None:
    try:
        subprocess.run(args, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"no se encontró el comando {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"falló: {' '.join(args)}") from exc


def _run(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(f"no se encontró el comando {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", "replace").strip()
        message = f"falló: {' '.join(args)}"
        if detail:
            message = f"{message}\n{detail}"
        raise SystemExit(message) from exc


if __name__ == "__main__":
    raise SystemExit(main())
