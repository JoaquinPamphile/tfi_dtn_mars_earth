"""Reenvío store-and-forward de una SyncUnit ya entregada por un hop.

La unidad es carga opaca. Este nodo no abre contactos, no calcula
capacidad y no administra un intento de serialización.
"""

from __future__ import annotations

from typing import Protocol

from core.contact.contact import LogicalNode
from core.simulation.engine import SimulationEngine
from core.sync.unit import SyncUnit
from core.trace.types import SimulationEventType
from core.transport.emulated import DeliveryHandler, TransportDelivery

# Llegadas que sueltan la custodia. No son una cola de envío.
_LIBERA_CUSTODIA = (
    SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value,
    SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value,
    SimulationEventType.SILENT_FORWARD_DELIVERY_DROPPED.value,
)


class RelayTransport(Protocol):
    """Frontera mínima con el hop saliente.

    El relé presenta una unidad y observa llegadas. No usa contactos,
    capacidad ni intentos de serialización.
    """

    def submit(self, unit: SyncUnit) -> None:
        """Acepta una unidad ya dirigida a los extremos de su enlace."""

    def register_delivery_handler(self, handler: DeliveryHandler) -> None:
        """Recibe cada llegada que el transporte ya entregó."""


class RelayNode:
    """Custodia y reenvío entre los dos sentidos del enlace.

    Al llegar una unidad destinada a este nodo, la guarda por
    ``sync_unit_id`` y, si ese id todavía no fue reenviado, la presenta
    al transporte del salto siguiente. La presentación es inmediata:
    la espera de un contacto queda en la cola del transporte.

    Ida: origen Marte, salto siguiente relé hacia Tierra.
    Vuelta: origen Tierra, salto siguiente relé hacia Marte.
    Un origen que no es ninguno de esos dos no tiene ruta.

    La custodia sigue hasta una llegada al transporte de Tierra, al
    transporte de Marte, o ``SILENT_FORWARD_DELIVERY_DROPPED`` de esa
    misma unidad. Una interrupción del enlace no se notifica aquí.
    """

    def __init__(self, engine: SimulationEngine, transport: RelayTransport) -> None:
        self._engine = engine
        self._transport = transport
        self._store: dict[str, SyncUnit] = {}
        self._forwarded: dict[str, None] = {}
        transport.register_delivery_handler(self.handle_delivery)

    def stored(self) -> tuple[SyncUnit, ...]:
        """Unidades todavía en custodia.

        El orden es ``created_at_sim`` y después ``submission_order``.
        No es la cola de envío del transporte. Un empate conserva el
        orden de la primera inserción de ese id.
        """
        return tuple(
            sorted(
                self._store.values(),
                key=lambda unit: (unit.created_at_sim, unit.submission_order),
            )
        )

    def handle_delivery(self, delivery: TransportDelivery) -> None:
        """Recibe una llegada ya producida por un hop.

        ``ARRIVED_AT_RELAY`` guarda la unidad y la presenta al salto
        siguiente. Las llegadas de ``_LIBERA_CUSTODIA`` quitan ese id
        del almacén. Cualquier otro ``event_type`` no hace nada.
        ``time_sim`` y ``contact_id`` no se consultan.
        """
        if delivery.event_type == SimulationEventType.ARRIVED_AT_RELAY.value:
            self._receive_at_relay(delivery.sync_unit)
        elif delivery.event_type in _LIBERA_CUSTODIA:
            self._store.pop(delivery.sync_unit.sync_unit_id, None)

    def _receive_at_relay(self, unit: SyncUnit) -> None:
        """Guarda la unidad llegada y, si cabe, la reenvía.

        Un id ya presente se reemplaza. El hecho ``RELAY_QUEUED``
        describe el hop de llegada, no el salto siguiente.
        """
        self._store[unit.sync_unit_id] = unit
        self._engine.emit_trace(
            SimulationEventType.RELAY_QUEUED.value,
            {
                "sync_unit_id": unit.sync_unit_id,
                "source_node": unit.source_node.value,
                "destination_node": unit.destination_node.value,
                "payload_size_bytes": unit.payload_size_bytes,
                "event_ids": [str(event_id) for event_id in unit.event_ids],
                "created_at_sim": unit.created_at_sim,
                "queued_at_sim": self._engine.now,
            },
            entity_id=unit.sync_unit_id,
        )
        self._forward(unit)

    def _forward(self, unit: SyncUnit) -> None:
        """Presenta el salto siguiente una sola vez por ``sync_unit_id``.

        La marca se anota antes de ``submit``. Si el transporte rechaza
        esa presentación, una llegada posterior del mismo id no vuelve
        a presentarla. ``submission_order`` no se asigna aquí: la unidad
        sale con el orden del hop de llegada y el transporte lo reemplaza.
        """
        if unit.sync_unit_id in self._forwarded:
            return
        next_source, next_destination = _next_hop(unit)
        self._forwarded[unit.sync_unit_id] = None
        self._transport.submit(unit.for_hop(next_source, next_destination))


def _next_hop(unit: SyncUnit) -> tuple[LogicalNode, LogicalNode]:
    """Extremos del único salto que corresponde al origen de la unidad."""
    if unit.source_node is LogicalNode.MARS:
        return LogicalNode.RELAY, LogicalNode.EARTH
    if unit.source_node is LogicalNode.EARTH:
        return LogicalNode.RELAY, LogicalNode.MARS
    raise RuntimeError(
        f"el relay no tiene próximo hop para el origen {unit.source_node.value}"
    )
