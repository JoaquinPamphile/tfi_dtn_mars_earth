"""Detección pura de huecos internos a partir de secuencias ya recibidas.
La serie de una fuente empieza en 0. Los huecos son los enteros faltantes
en ``0 .. máxima observada``. No se infiere un sufijo posterior a esa
máxima: esas secuencias todavía no fueron observadas.
No asigna ``range(0, máxima + 1)``. El mismo conjunto, en cualquier orden
y con duplicados, produce los mismos rangos. Una entrada vacía no tiene
máxima y por lo tanto no tiene huecos.
"""
from collections.abc import Iterable
from core.domain.gap import MissingSequenceRange

def missing_sequence_ranges(received: Iterable[int]) -> tuple[MissingSequenceRange, ...]:
    """Rangos inclusivos faltantes por debajo de la secuencia recibida más alta."""
    ordered = sorted(set(received))
    if not ordered:
        return ()
    ranges: list[MissingSequenceRange] = []
    expected = 0
    for sequence in ordered:
        if sequence > expected:
            ranges.append(
                MissingSequenceRange(
                    start_sequence=expected,
                    end_sequence=sequence - 1,
                )
            )
        if sequence >= expected:
            expected = sequence + 1
    return tuple(ranges)

def missing_sequence_numbers(received: Iterable[int]) -> tuple[int, ...]:
    """Enteros faltantes, en orden ascendente, expandidos desde los rangos."""
    missing: list[int] = []
    for item in missing_sequence_ranges(received):
        missing.extend(range(item.start_sequence, item.end_sequence + 1))
    return tuple(missing)
