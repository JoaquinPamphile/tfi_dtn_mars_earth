"""Contexto de release armado solo con el archivo de un commit.

El tar lo produce ``git archive``. Este módulo no copia el working tree
y no recibe ``source_state``. El sello ``git_archive`` lo escribe el
mismo paso que extrajo ese tar.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from experiments.software_provenance import release_stamp_payload

STAMP_FILENAME = "software_provenance.json"


def git_archive_command(commit: str) -> list[str]:
    """Tar del commit, sin la conversión de fin de línea del working tree.

    En Windows, ``core.autocrlf`` puede hacer que ``git archive`` escriba
    CRLF. El blob del commit no. Forzar ``false`` deja los bytes del
    objeto. El build después los compara con ``git cat-file``.
    """
    return [
        "git",
        "-c",
        "core.autocrlf=false",
        "archive",
        "--format=tar",
        commit,
    ]

# Receta cerrada. El script la compara con docker/Dockerfile.release.
# No hay ARG ni SOURCE_STATE: clean no entra por el usuario.
RELEASE_DOCKERFILE_LINES = (
    "FROM python:3.12-slim",
    "WORKDIR /app",
    "ENV PYTHONDONTWRITEBYTECODE=1",
    "ENV PYTHONUNBUFFERED=1",
    "ENV PYTHONPATH=/app/backend",
    "ENV SOFTWARE_PROVENANCE_FILE=/app/software_provenance.json",
    "COPY pyproject.toml ./",
    "COPY backend ./backend",
    "COPY software_provenance.json /app/software_provenance.json",
    'RUN pip install --no-cache-dir ".[test]"',
    'CMD ["pytest"]',
)


class ReleaseContextError(ValueError):
    """El contexto no es el archivo de un commit, o la receta no es la cerrada."""


def validate_release_dockerfile(text: str) -> None:
    """Rechaza una receta que no sea la cerrada o que acepte un estado externo."""
    if "SOURCE_STATE" in text or "build-arg" in text:
        raise ReleaseContextError(
            "la receta de release no acepta un source_state pasado por el usuario"
        )
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        lines.append(stripped)
    if tuple(lines) != RELEASE_DOCKERFILE_LINES:
        raise ReleaseContextError(
            "Dockerfile.release no coincide con la receta cerrada de release"
        )


def context_files(destination: Path) -> set[str]:
    """Rutas de archivo del contexto, con separador ``/``."""
    found: set[str] = set()
    for path in destination.rglob("*"):
        if path.is_file():
            found.add(path.relative_to(destination).as_posix())
    return found


def materialize_release_context(
    archive: bytes,
    destination: Path,
    source_revision: str,
) -> dict[str, str]:
    """Extrae el tar en un directorio vacío y escribe el sello verificado.

    ``source_revision`` tiene que ser el commit de ese tar. Un SHA inválido
    aborta antes de extraer. Un miembro que escape del destino aborta.
    Si el tar traía un sello, este paso lo reemplaza.
    """
    payload = release_stamp_payload(source_revision)
    if not destination.is_dir():
        raise ReleaseContextError("el destino tiene que ser un directorio")
    if any(destination.iterdir()):
        raise ReleaseContextError("el destino del contexto tiene que estar vacío")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(destination, filter="data")
    except (tarfile.TarError, OSError, ValueError) as exc:
        raise ReleaseContextError(
            "el archivo tar del commit no se puede extraer"
        ) from exc
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    (destination / STAMP_FILENAME).write_text(text, encoding="utf-8", newline="\n")
    return payload


def assert_context_matches_blobs(
    destination: Path,
    committed_blobs: dict[str, bytes],
) -> None:
    """El contexto, sin el sello, es exactamente ese conjunto de blobs.

    Un archivo de más, uno de menos, o bytes distintos, no es el commit.
    """
    present = context_files(destination)
    committed = set(committed_blobs)
    extra = present - committed - {STAMP_FILENAME}
    missing = committed - present
    if missing or extra:
        raise ReleaseContextError(
            "el contexto no es el árbol del commit: "
            f"faltan {sorted(missing)} sobran {sorted(extra)}"
        )
    for path, blob in committed_blobs.items():
        got = (destination / path).read_bytes()
        if got != blob:
            raise ReleaseContextError(
                f"el contexto no coincide con el blob del commit: {path}"
            )
