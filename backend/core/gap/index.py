"""Índice incremental de huecos internos de secuencia.
Cada ``source_id`` tiene su propio índice. La serie de esa fuente empieza
en 0: el primer número observado no desplaza el origen. Un hueco es un
entero faltante estrictamente menor que la secuencia más alta ya observada.
Lo que todavía no llegó por encima de ese máximo no es un hueco.
Actualizar tras una secuencia nueva es logarítmico en la cantidad de
intervalos, no en el valor de la secuencia más alta. No se materializa
``range(0, máxima + 1)`` ni se guarda cada secuencia recibida.
El estado por fuente es el máximo observado y los rangos faltantes, ya
ordenados, disjuntos y no adyacentes. Un duplicado no cambia ese estado.
Este módulo no construye un ``GapRequest``, no lo envía y no reintenta.
"""
from __future__ import annotations
from bisect import bisect_right
from collections.abc import Iterable
from core.domain.gap import MissingSequenceRange

class IncrementalGapIndex:
    """Rangos faltantes de una sola fuente, ordenados y sin solaparse."""
    def __init__(self) -> None:
        self._ranges: list[MissingSequenceRange] = []
        self._highest: int | None = None

    def observe(self, sequence: int) -> None:
        """Incorpora una secuencia recibida y actualiza los huecos internos.
        La primera observación de ``n > 0`` abre el rango inclusivo ``0..n-1``.
        La primera observación de ``0`` no abre ningún rango. Una secuencia
        posterior al máximo abre, si hace falta, el intervalo que queda entre
        ambos. Una secuencia ya cubierta, o igual al máximo, no altera el
        índice. Una secuencia interior a un rango lo parte, lo acorta o lo
        elimina.
        """
        if sequence < 0:
            raise ValueError("sequence debe ser >= 0")
        if self._highest is None:
            if sequence > 0:
                self._ranges = [
                    MissingSequenceRange(start_sequence=0, end_sequence=sequence - 1)
                ]
            else:
                self._ranges = []
            self._highest = sequence
            return
        if sequence > self._highest:
            if sequence > self._highest + 1:
                self._ranges.append(
                    MissingSequenceRange(
                        start_sequence=self._highest + 1,
                        end_sequence=sequence - 1,
                    )
                )
            self._highest = sequence
            return
        if sequence == self._highest:
            return
        self._fill_internal(sequence)

    def rebuild(self, sequences: Iterable[int]) -> None:
        """Reconstruye el índice observando cada secuencia distinta, en orden.
        Una secuencia negativa interrumpe la reconstrucción: el índice ya
        fue vaciado y la excepción sale sin incorporar el resto.
        """
        self._ranges = []
        self._highest = None
        for sequence in sorted(set(sequences)):
            self.observe(sequence)

    def ranges(self) -> tuple[MissingSequenceRange, ...]:
        """Rangos inclusivos faltantes, de menor a mayor ``start_sequence``."""
        return tuple(self._ranges)

    @property
    def highest(self) -> int | None:
        """Secuencia más alta observada, o ``None`` si todavía no hubo ninguna."""
        return self._highest

    @property
    def count(self) -> int:
        """Cantidad de enteros faltantes por debajo del máximo observado."""
        return sum(item.count for item in self._ranges)

    def _fill_internal(self, sequence: int) -> None:
        starts = [item.start_sequence for item in self._ranges]
        index = bisect_right(starts, sequence) - 1
        if index < 0:
            return
        current = self._ranges[index]
        if sequence < current.start_sequence or sequence > current.end_sequence:
            return
        replacement: list[MissingSequenceRange] = []
        if current.start_sequence < sequence:
            replacement.append(
                MissingSequenceRange(
                    start_sequence=current.start_sequence,
                    end_sequence=sequence - 1,
                )
            )
        if sequence < current.end_sequence:
            replacement.append(
                MissingSequenceRange(
                    start_sequence=sequence + 1,
                    end_sequence=current.end_sequence,
                )
            )
        self._ranges[index : index + 1] = replacement

class EarthGapRangeStore:
    """``source_id`` → índice incremental de huecos internos.
    Fuentes distintas no comparten máximo ni rangos. Consultar una fuente
    que todavía no fue observada devuelve una tupla vacía. ``source_id``
    vacío es una clave distinta: no se rechaza.
    """

    def __init__(self) -> None:
        self._by_source: dict[str, IncrementalGapIndex] = {}

    def observe(self, source_id: str, sequence: int) -> None:
        self._by_source.setdefault(source_id, IncrementalGapIndex()).observe(sequence)

    def rebuild(self, sequences_by_source: dict[str, set[int]]) -> None:
        """Reemplaza todo el estado por los conjuntos recibidos.

        Una fuente ausente en ``sequences_by_source`` deja de tener índice.
        """
        self._by_source = {}
        for source_id, values in sequences_by_source.items():
            index = IncrementalGapIndex()
            index.rebuild(values)
            self._by_source[source_id] = index

    def ranges_for_source(self, source_id: str) -> tuple[MissingSequenceRange, ...]:
        index = self._by_source.get(source_id)
        if index is None:
            return ()
        return index.ranges()

    def clear(self) -> None:
        self._by_source.clear()
