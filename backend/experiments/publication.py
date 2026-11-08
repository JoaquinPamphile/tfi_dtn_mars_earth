from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_exclusive_canonical_json(path: Path, serialized: Any) -> Path:
    if not isinstance(path, Path):
        raise TypeError("path debe ser un Path")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    descriptor_open = True
    try:
        with os.fdopen(
            descriptor,
            mode="w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            descriptor_open = False
            encoder = json.JSONEncoder(
                sort_keys=True,
                indent=2,
                ensure_ascii=True,
                allow_nan=False,
            )
            for chunk in encoder.iterencode(serialized):
                stream.write(chunk)
            stream.write("\n")
        os.link(temporary, path)
    finally:
        if descriptor_open:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return path
