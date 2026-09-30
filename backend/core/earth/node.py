"""Aplicación local de Tierra.

Una ``SyncUnit`` de telemetría ya entregada se decodifica y se persiste en
el repositorio inyectado. El ``ApplicationAck`` describe ese resultado de
aplicación. El envío de vuelta queda fuera de este nodo.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from core.domain.ack import ApplicationAck, ApplicationAckStatus
from core.domain.event import TelemetryEvent
from core.domain.gap import MissingSequenceRange
from core.earth.status import EarthNodeStatus
from core.state.ports import EarthPersistenceRecord, EarthStateRepository
from core.sync.codec import decode_telemetry_events
from core.sync.unit import SyncUnit


class EarthNode:
    """Receptor de aplicación en Tierra, con el estado inyectado.

    Recibe la unidad de telemetría, la decodifica y deja la idempotencia
    en el repositorio. Con el resultado arma el ACK local. No elige
    contacto, no calcula si el ACK entra en una ventana y no pide
    reparación de huecos.
    """

    def __init__(self, repository: EarthStateRepository) -> None:
        self._repository = repository

    def close(self) -> None:
        """Cierra el repositorio inyectado. No borra el estado."""
        self._repository.close()

    def wipe(self) -> None:
        """Vacía el repositorio inyectado."""
        self._repository.wipe()

    def ingest_sync_unit(self, unit: SyncUnit, arrived_at_sim: float) -> ApplicationAck:
        """Persiste la telemetría de la unidad y devuelve el ACK de ese resultado.

        La unidad se decodifica con el codec. Una carga que no es
        ``telemetry_events``, o que está mal formada, falla en ese decode
        y el repositorio queda como estaba. ``arrived_at_sim`` es el
        instante de la primera persistencia y también ``generated_at_sim``
        del ACK. ``event_ids`` sigue el orden de decode. Las altas nuevas
        van a ``accepted_event_ids`` y las repeticiones a
        ``duplicate_event_ids``, en ese mismo orden. ``rejected_event_ids``
        queda vacío y el estado es ``ACCEPTED``.
        """
        events = decode_telemetry_events(unit)
        result = self._repository.ingest(events, arrived_at_sim)
        event_ids = tuple(event.event_id for event in events)
        return ApplicationAck(
            ack_id=_ack_id(event_ids, arrived_at_sim),
            event_ids=event_ids,
            generated_at_sim=arrived_at_sim,
            status=ApplicationAckStatus.ACCEPTED,
            accepted_event_ids=result.persisted_event_ids,
            duplicate_event_ids=result.duplicate_event_ids,
            rejected_event_ids=(),
        )

    def get_event(self, event_id: UUID) -> TelemetryEvent | None:
        """Evento de la primera aceptación, o ``None`` si el id no está."""
        return self._repository.get_event(event_id)

    def max_generated_at_sim(self) -> float | None:
        """Mayor ``generated_at_sim`` entre los únicos, o ``None`` si no hay."""
        return self._repository.max_generated_at_sim()

    def persistence_sample_count(self) -> int:
        """Cantidad de pares de frescura, una por evento único."""
        return self._repository.persistence_sample_count()

    def persistence_samples(self) -> tuple[tuple[float, float], ...]:
        """Pares ``(generated_at_sim, first_persisted_at_sim)``, en orden de alta."""
        return self._repository.persistence_samples()

    def persistence_records(self) -> tuple[EarthPersistenceRecord, ...]:
        """Filas únicas en el orden en que fueron aceptadas."""
        return self._repository.persistence_records()

    def duplicate_receipts_for(self, event_id: UUID) -> int:
        """Recibos duplicados de ese id. Un id nunca visto vale 0."""
        return self._repository.duplicate_receipts_for(event_id)

    def gap_ranges_for_source(self, source_id: str) -> tuple[MissingSequenceRange, ...]:
        """Rangos faltantes que el repositorio ya observó para esa fuente."""
        return self._repository.gap_ranges_for_source(source_id)

    def status(self) -> EarthNodeStatus:
        """Contadores resumidos de la ingesta."""
        return EarthNodeStatus(
            persisted_unique=self._repository.unique_event_count(),
            gaps_count=self._repository.gaps_count(),
            duplicates_received=self._repository.duplicates_received(),
            duplicates_stored=self._repository.duplicates_stored(),
        )


def _ack_id(event_ids: Sequence[UUID], generated_at_sim: float) -> str:
    """Arma ``ack_id`` con los ``event_id`` de la unidad y el instante de ingesta.

    El orden es el de la membresía. El mismo par de entradas produce el
    mismo texto.
    """
    joined = "-".join(str(event_id) for event_id in event_ids)
    return f"ack-{joined}-{generated_at_sim}"
