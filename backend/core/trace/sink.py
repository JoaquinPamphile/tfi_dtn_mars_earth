from collections.abc import Sequence
from typing import Any, Protocol
from core.trace.event import SimulationTraceEntry

class TraceSink(Protocol):
    """Contrato de un almacén de traza."""

    def append(self, entry: SimulationTraceEntry) -> None: ...

    def __len__(self) -> int: ...

    def as_tuple(self) -> tuple[SimulationTraceEntry, ...]: ...

    def after(self, after_sequence: int) -> Sequence[SimulationTraceEntry]: ...

    def page(
        self, after_sequence: int, limit: int
    ) -> tuple[Sequence[SimulationTraceEntry], bool]: ...

    def tail(self, count: int) -> Sequence[SimulationTraceEntry]: ...

    def annotate_last(self, extra: dict[str, Any]) -> None: ...

    def close(self) -> None: ...

class MemoryTraceSink:
    """Traza en memoria.
    Conserva el orden de ``append``, también cuando varios registros
    comparten ``simulation_time``. ``after`` y ``page`` recorren la posición
    en esa lista: la posición 0 es el primer registro. El campo
    ``sequence_index`` permanece como llegó.
    """

    def __init__(self) -> None:
        self._records: list[SimulationTraceEntry] = []

    def append(self, entry: SimulationTraceEntry) -> None:
        """Agrega el registro al final, sin copiarlo."""
        self._records.append(entry)

    def __len__(self) -> int:
        return len(self._records)

    def as_tuple(self) -> tuple[SimulationTraceEntry, ...]:
        """Todos los registros, en el orden de registro."""
        return tuple(self._records)

    def after(self, after_sequence: int) -> Sequence[SimulationTraceEntry]:
        """Registros en posiciones posteriores a ``after_sequence``.

        Un índice negativo se toma como el inicio. Si el inicio queda fuera
        de la lista, el resultado es una tupla vacía. En caso contrario es
        una lista nueva con los mismos registros.
        """
        start = after_sequence + 1
        if start < 0:
            start = 0
        if start >= len(self._records):
            return ()
        return self._records[start:]

    def page(
        self, after_sequence: int, limit: int
    ) -> tuple[Sequence[SimulationTraceEntry], bool]:
        """Trozo de a lo sumo ``limit`` registros desde la posición siguiente.

        El booleano es verdadero cuando la traza continúa después del trozo.
        """
        start = after_sequence + 1
        if start < 0:
            start = 0
        total = len(self._records)
        if start >= total:
            return (), False
        end = start + limit
        return self._records[start:end], end < total

    def tail(self, count: int) -> Sequence[SimulationTraceEntry]:
        """Últimos ``count`` registros. ``count`` debe ser >= 1."""
        if count < 1:
            raise ValueError("la cantidad debe ser >= 1")
        return self._records[-count:]

    def annotate_last(self, extra: dict[str, Any]) -> None:
        """Incorpora claves en los detalles del último registro.

        Si la traza está vacía, no hace nada. Las claves de ``extra`` se
        copian por referencia dentro del diccionario ya almacenado.
        """
        if not self._records:
            return
        self._records[-1].details.update(extra)

    def close(self) -> None:
        """No retiene recursos. La traza en memoria sigue disponible."""
        return
