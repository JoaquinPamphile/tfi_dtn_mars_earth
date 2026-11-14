"""Almacenamiento privado de cuerpos observados; sin motor ni manifiestos."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from experiments.experiment_bank_result import _result_remainder
from experiments.publication import canonical_json_encoder


class BankResultSpool:
    """Un fallo antes del enlace deshabilita publicación; limpiar es best effort.

    Los fragmentos se limpian antes del enlace final. Un fallo de limpieza
    posterior al enlace se informa aparte: el archivo ya existe y aún no
    tiene integridad confirmada. Las interrupciones nunca se interceptan.
    """

    def __init__(self, target: Path):
        self.target = target
        self.directory: Path | None = None
        self.fragments: list[Path] = []
        self.assembled: Path | None = None
        self.error: str | None = None
        self.cleanup_error: str | None = None
        self.published = False
        try:
            self.directory = Path(tempfile.mkdtemp(prefix='.e2-spool-', dir=target.parent))
        except OSError as exc:
            self.fail('creación privada', exc)

    def fail(self, stage, exc):
        if self.error is None:
            self.error = f'{stage}: {type(exc).__name__}: {exc}'

    def append(self, index, result):
        if self.error is not None:
            return
        path = self.directory / f'{index:04d}.fragment'
        self.fragments.append(path)  # También permite retirar un fragmento incompleto.
        try:
            body = {'result': None if result is None else _result_remainder(result)}
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                for chunk in canonical_json_encoder().iterencode(body):
                    stream.write(chunk)
        except (OSError, TypeError, ValueError) as exc:
            self.fail(f'fragmento {index}', exc)
            self._clean_fragments()

    def _clean_fragments(self):
        errors = []
        for path in self.fragments:
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                errors.append(str(exc))
        if self.directory is not None:
            try:
                self.directory.rmdir()
                self.directory = None
            except FileNotFoundError:
                self.directory = None
            except OSError as exc:
                errors.append(str(exc))
        if errors:
            self.cleanup_error = 'limpieza privada: ' + '; '.join(errors)
            self.fail('limpieza privada', OSError('; '.join(errors)))
        return not errors

    def _compose(self, stream, metadata):
        encoder = canonical_json_encoder()
        keys = sorted((*metadata, 'run_results'))
        stream.write('{\n')
        for position, key in enumerate(keys):
            stream.write('  ' + json.dumps(key) + ': ')
            if key == 'run_results':
                stream.write('[\n')
                for i, path in enumerate(self.fragments):
                    stream.write('    ')
                    with path.open(encoding='utf-8') as source:
                        for chunk in iter(lambda: source.read(65536), ''):
                            stream.write(chunk.replace('\n', '\n    '))
                    stream.write(',\n' if i + 1 < len(self.fragments) else '\n')
                stream.write('  ]')
            else:
                for chunk in encoder.iterencode(metadata[key]):
                    stream.write(chunk.replace('\n', '\n  '))
            stream.write(',\n' if position + 1 < len(keys) else '\n')
        stream.write('}\n')

    def publish(self, metadata):
        if self.error is not None:
            return
        stage = 'composición'
        try:
            fd, name = tempfile.mkstemp(prefix=f'.{self.target.name}.', suffix='.tmp', dir=self.target.parent)
            self.assembled = Path(name)
            try:
                stream = os.fdopen(fd, 'w', encoding='utf-8', newline='\n')
            except BaseException:
                os.close(fd)
                raise
            with stream:
                self._compose(stream, metadata)
            if not self._clean_fragments():
                return
            stage = 'enlace exclusivo'
            os.link(self.assembled, self.target)
            self.published = True
            try:
                self.assembled.unlink()
                self.assembled = None
            except OSError as exc:
                self.cleanup_error = f'limpieza tras publicación: {exc}'
        except (OSError, TypeError, ValueError) as exc:
            self.fail(stage, exc)

    def close(self):
        self._clean_fragments()
        if self.assembled is not None:
            try:
                self.assembled.unlink(missing_ok=True)
                self.assembled = None
            except OSError as exc:
                self.cleanup_error = f'limpieza de composición: {exc}'
                self.fail('limpieza de composición', exc)
