"""Percentil inclusivo tipo 7, el único método de las métricas de una corrida.

Para n observaciones ordenadas ``x[0] <= ... <= x[n-1]`` y un percentil
``p`` en ``[0, 100]``:

    h = (n - 1) * (p / 100)
    i = floor(h)
    f = h - i
    si i + 1 está fuera de rango: x[n - 1]
    si no: x[i] + f * (x[i + 1] - x[i])

No redondea el resultado.
"""

from __future__ import annotations

from math import floor


def inclusive_percentile(values: list[float], percentile: float) -> float:
    """Devuelve el percentil inclusivo tipo 7 de ``values``.

    ``values`` no tiene que llegar ordenado. ``percentile`` está en
    ``[0, 100]``. Una muestra vacía no tiene percentil.
    """
    if not values:
        raise ValueError("el percentil no está definido para una muestra vacía")
    if percentile < 0 or percentile > 100:
        raise ValueError("el percentil debe estar en [0, 100]")
    ordered = sorted(values)
    count = len(ordered)
    if count == 1:
        return ordered[0]
    position = (count - 1) * (percentile / 100.0)
    index = int(floor(position))
    fraction = position - index
    if index + 1 >= count:
        return ordered[-1]
    return ordered[index] + fraction * (ordered[index + 1] - ordered[index])
