"""Procedencia del software que ejecuta una corrida.

La versión de release tiene una sola fuente: el archivo ``VERSION`` de
este paquete. ``pyproject.toml`` la lee al instalar. El manifiesto usa
el texto de ese archivo, no una copia escrita en otro módulo.

``source_revision`` es el commit HEAD cuando pudo leerse.
``source_state`` es ``clean``, ``dirty`` o ``unknown``.

``clean`` y ``dirty`` solo salen de ``git status`` ejecutado en el mismo
proceso, sobre el árbol que va a correr. El build de Docker copia ``.git``
para leer HEAD y borra el directorio. No ejecuta ``git status``: con
``core.autocrlf`` en el host, el estado dentro del contenedor no es
fiable. Ese sello queda en ``unknown``. No se reescribe como ``clean``.

La evidencia ``official`` y ``sensitivity`` exige ``clean`` y un SHA de
40 hexadecimales. ``development`` registra el estado observado.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_CLEAN = "clean"
SOURCE_DIRTY = "dirty"
SOURCE_UNKNOWN = "unknown"
_SOURCE_STATES = frozenset({SOURCE_CLEAN, SOURCE_DIRTY, SOURCE_UNKNOWN})
_SHA = re.compile(r"[0-9a-f]{40}")
_OBSERVATION_HEAD = "git_head_unverified"


class ProvenanceError(ValueError):
    """La evidencia pide un árbol congelado y la observación no lo prueba."""


@dataclass(frozen=True, slots=True)
class SoftwareProvenance:
    """Versión de release y revisión observada. No entra en ``configuration_hash``."""

    software_version: str
    source_revision: str | None
    source_state: str

    def __post_init__(self) -> None:
        if self.software_version.strip() == "":
            raise ValueError("software_version no debe estar vacío")
        if self.source_state not in _SOURCE_STATES:
            raise ValueError("source_state debe ser clean, dirty o unknown")
        if self.source_revision is not None and _SHA.fullmatch(self.source_revision) is None:
            raise ValueError("source_revision debe ser un SHA de 40 hexadecimales o null")
        if self.source_state in {SOURCE_CLEAN, SOURCE_DIRTY} and self.source_revision is None:
            raise ValueError("clean y dirty exigen un source_revision conocido")


def software_version() -> str:
    """Texto de ``VERSION``. No consulta la metadata normalizada del instalador."""
    path = Path(__file__).with_name("VERSION")
    text = path.read_text(encoding="utf-8").strip()
    if text == "" or any(character.isspace() for character in text):
        raise RuntimeError("VERSION debe contener una sola versión, sin espacios")
    return text


def current_provenance() -> SoftwareProvenance:
    """Procedencia de este proceso.

    Si ``SOFTWARE_PROVENANCE_FILE`` está definido, ese sello aporta el
    commit y el estado queda ``unknown``. Si no hay sello, se consulta
    git en el directorio de trabajo.
    """
    version = software_version()
    stamp = os.environ.get("SOFTWARE_PROVENANCE_FILE")
    if stamp:
        return _from_stamp(Path(stamp), version)
    return _from_git(version)


def observe_worktree(
    *,
    software_version: str,
    source_revision: str,
    status_porcelain: str,
) -> SoftwareProvenance:
    """Interpreta una salida ya obtenida de ``git status --porcelain``.

    Una salida vacía es ``clean``. Cualquier línea es ``dirty``. Un SHA
    que no tiene 40 hexadecimales no se promociona a limpio ni a sucio.
    """
    if _SHA.fullmatch(source_revision) is None:
        return SoftwareProvenance(software_version, None, SOURCE_UNKNOWN)
    state = SOURCE_DIRTY if status_porcelain.strip() else SOURCE_CLEAN
    return SoftwareProvenance(software_version, source_revision, state)


def require_frozen_source(role: str, provenance: SoftwareProvenance) -> None:
    """``official`` y ``sensitivity`` solo se exportan desde un árbol limpio.

    ``development`` no pasa por esta regla. ``unknown`` no se trata como
    ``clean``.
    """
    if role not in {"official", "sensitivity"}:
        return
    if provenance.source_state == SOURCE_CLEAN and _SHA.fullmatch(
        provenance.source_revision or ""
    ):
        return
    raise ProvenanceError(
        f"la evidencia {role} no se exporta: exige source_state clean "
        f"y un source_revision de 40 hexadecimales; "
        f"observado state={provenance.source_state} "
        f"revision={provenance.source_revision}"
    )


def _from_stamp(path: Path, version: str) -> SoftwareProvenance:
    """Lee el commit del sello. El archivo no puede declarar ``clean``."""
    revision = _stamp_revision(path)
    return SoftwareProvenance(version, revision, SOURCE_UNKNOWN)


def _stamp_revision(path: Path) -> str | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    revision = loaded.get("source_revision")
    if not isinstance(revision, str) or _SHA.fullmatch(revision) is None:
        return None
    return revision


def _from_git(version: str) -> SoftwareProvenance:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return SoftwareProvenance(version, None, SOURCE_UNKNOWN)
    return observe_worktree(
        software_version=version,
        source_revision=head.stdout.strip(),
        status_porcelain=status.stdout,
    )


def _read_git_head(git_dir: Path) -> str | None:
    """Resuelve HEAD leyendo refs. No ejecuta git ni mira el worktree."""
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None
    if head.startswith("ref: "):
        ref = head[5:].strip()
        if ref == "" or ref.startswith("/") or ".." in Path(ref).parts:
            return None
        return _read_ref(git_dir, ref)
    if _SHA.fullmatch(head) is None:
        return None
    return head


def _read_ref(git_dir: Path, ref: str) -> str | None:
    loose = git_dir / ref
    try:
        if loose.is_file():
            sha = loose.read_text(encoding="utf-8").strip()
            if _SHA.fullmatch(sha):
                return sha
    except (OSError, UnicodeError):
        return None
    packed = git_dir / "packed-refs"
    try:
        lines = packed.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in lines:
        if line == "" or line.startswith("#") or line.startswith("^"):
            continue
        sha, _separator, name = line.partition(" ")
        if name == ref and _SHA.fullmatch(sha):
            return sha
    return None


def _write_stamp(path: Path, git_dir: Path) -> None:
    payload = {
        "observation": _OBSERVATION_HEAD,
        "source_revision": _read_git_head(git_dir),
        "source_state": SOURCE_UNKNOWN,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    """Escribe el sello de build. Lo usa el Dockerfile, no la corrida científica."""
    if len(argv) != 4 or argv[0] != "--write-stamp" or argv[2] != "--git-dir":
        print(
            "uso: software_provenance.py --write-stamp PATH --git-dir GIT",
            file=sys.stderr,
        )
        return 2
    _write_stamp(Path(argv[1]), Path(argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
