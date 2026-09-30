"""Orden de los eventos que entran a una estrategia de sincronización.

La estrategia conserva el orden recibido. Esta capa lo fija antes.
"""

from collections.abc import Sequence
from uuid import UUID

from core.domain.event import TelemetryEvent


def order_eligible_events(events: Sequence[TelemetryEvent]) -> list[TelemetryEvent]:
    """Orden determinista: ``source_id`` y, dentro de la fuente, ``sequence_number``.

    El identificador del evento y el orden de inserción no deciden el grupo.
    """
    return sorted(events, key=lambda event: (event.source_id, event.sequence_number))


def unique_in_order(events: Sequence[TelemetryEvent]) -> list[TelemetryEvent]:
    """Deja la primera aparición de cada ``event_id`` después de ordenar."""
    seen: set[UUID] = set()
    unique: list[TelemetryEvent] = []
    for event in order_eligible_events(events):
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        unique.append(event)
    return unique
