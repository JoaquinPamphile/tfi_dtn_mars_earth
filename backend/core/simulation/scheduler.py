from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from heapq import heapify, heappop, heappush
from math import isfinite
from typing import Any

@dataclass(slots=True)
class ScheduledAction:
    """Acción programada en un instante lógico de simulación, en segundos."""
    time: float
    tie_breaker: int
    event_type: str
    payload: dict[str, Any]
    entity_id: str | None

class EventScheduler:
    """Cola de prioridad de acciones futuras.
    El orden es el tiempo ascendente. Si dos acciones comparten el mismo
    tiempo, se ejecuta primero la que se programó antes.
    """
    def __init__(self) -> None:
        self._heap: list[tuple[float, int, ScheduledAction]] = []
        self._next_tie_breaker = 0
        self._type_counts: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return not self._heap

    def peek_time(self) -> float | None:
        if not self._heap:
            return None
        return self._heap[0][0]

    def peek(self) -> ScheduledAction | None:
        if not self._heap:
            return None
        return self._heap[0][2]

    def peek_time_matching(
        self, predicate: Callable[[ScheduledAction], bool]
    ) -> float | None:
        """Tiempo más temprano cuya acción cumple el predicado, o None."""
        times = [action.time for _, _, action in self._heap if predicate(action)]
        if not times:
            return None
        return min(times)

    def has_event_type(self, event_type: str) -> bool:
        return self._type_counts.get(event_type, 0) > 0

    def schedule(
        self,
        time: float,
        event_type: str,
        payload: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> ScheduledAction:
        if not isfinite(time) or time < 0:
            raise ValueError("el tiempo programado debe ser un valor finito >= 0")
        if event_type.strip() == "":
            raise ValueError("event_type no debe estar vacío")

        action = ScheduledAction(
            time=time,
            tie_breaker=self._next_tie_breaker,
            event_type=event_type,
            payload=deepcopy(payload) if payload is not None else {},
            entity_id=entity_id,
        )
        self._next_tie_breaker += 1
        heappush(self._heap, (action.time, action.tie_breaker, action))
        self._type_counts[event_type] = self._type_counts.get(event_type, 0) + 1
        return action

    def pop_next(self) -> ScheduledAction | None:
        if not self._heap:
            return None
        action = heappop(self._heap)[2]
        self._note_removed(action.event_type)
        return action

    def cancel(self, predicate: Callable[[ScheduledAction], bool]) -> int:
        """Quita las acciones futuras que cumplen el predicado. Devuelve cuántas canceló."""
        kept: list[tuple[float, int, ScheduledAction]] = []
        cancelled = 0
        for item in self._heap:
            if predicate(item[2]):
                cancelled += 1
                self._note_removed(item[2].event_type)
            else:
                kept.append(item)
        heapify(kept)
        self._heap = kept
        return cancelled

    def _note_removed(self, event_type: str) -> None:
        remaining = self._type_counts.get(event_type, 0) - 1
        if remaining <= 0:
            self._type_counts.pop(event_type, None)
        else:
            self._type_counts[event_type] = remaining
