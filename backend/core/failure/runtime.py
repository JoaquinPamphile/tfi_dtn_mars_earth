"""Estado mutable de un FailurePlan durante una corrida.

La definición permanece congelada. Este objeto solo cuenta ocurrencias
ya consumidas y los descartes que ya alcanzaron el punto de entrega.
No vive en EarthNode ni modifica el modelo de configuración.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.failure.plan import FailurePlan
from core.failure.silent import SilentForwardDeliveryLossHit

@dataclass(frozen=True, slots=True)
class SilentForwardDeliveryDropRecord:
    """Ocurrencia ya suprimida en el punto de entrega hacia Tierra.

    Es independiente del nivel de traza: se anota cuando el hop ya
    consumió capacidad, terminó la transmisión y cumplió la propagación.
    """

    failure_id: str
    occurrence_number: int
    source_id: str
    event_id: str
    sequence_number: int
    telemetry_attempt_number: int
    hop: str
    lost_at_sim: float
    payload_size_bytes: int
    sync_unit_id: str


class FailureRuntime:
    """Contadores de una corrida para el plan recibido.

    ``plan`` no se muta. Cada ``failure_id`` de pérdida silenciosa lleva
    cuántas coincidencias ya consumió. La primera coincidencia es la
    ocurrencia 1. Al llegar a ``max_occurrences`` esa definición deja de
    coincidir.

    El corte de contacto y la pérdida de ACK siguen definidos en el plan.
    Su efecto operacional no se aplica aquí: el corte cerraría la ventana
    con ``force_close_contact`` al vencer ``FAILURE_INJECTED``, y la
    pérdida de ACK se consultaría después de generar el ACK y antes de
    presentarlo al transporte.
    """

    def __init__(self, plan: FailurePlan | None = None) -> None:
        self.plan = plan if plan is not None else FailurePlan()
        self._silent_loss_occurrences: dict[str, int] = {}
        self._silent_loss_drops: list[SilentForwardDeliveryDropRecord] = []

    def occurrences_for(self, failure_id: str) -> int:
        """Ocurrencias ya consumidas de esa definición. Una clave ausente vale 0."""
        return self._silent_loss_occurrences.get(failure_id, 0)

    def silent_loss_occurrences(self) -> int:
        """Suma de coincidencias silenciosas ya consumidas."""
        return sum(self._silent_loss_occurrences.values())

    def silent_forward_delivery_drops(
        self,
    ) -> tuple[SilentForwardDeliveryDropRecord, ...]:
        """Descartes silenciosos ya registrados, en orden de entrega."""
        return tuple(self._silent_loss_drops)

    def consume_silent_forward_delivery_loss(
        self,
        *,
        source_id: str,
        sequence_number: int,
        telemetry_attempt_number: int,
        hop: str,
        payload_kind: str | None,
        event_count: int,
    ) -> SilentForwardDeliveryLossHit | None:
        """Consume la primera coincidencia que todavía tiene cupo.

        No usa un identificador transitorio de transporte ni una semilla.
        Si no hay coincidencia, los contadores quedan como estaban.
        """
        hit = self.plan.match_silent_forward_delivery_loss(
            source_id=source_id,
            sequence_number=sequence_number,
            telemetry_attempt_number=telemetry_attempt_number,
            hop=hop,
            payload_kind=payload_kind,
            event_count=event_count,
            occurrences_used=self._silent_loss_occurrences,
        )
        if hit is None:
            return None
        self._silent_loss_occurrences[hit.failure.failure_id] = hit.occurrence_number
        return hit

    def record_silent_forward_delivery_drop(
        self, record: SilentForwardDeliveryDropRecord
    ) -> None:
        """Anota un descarte que ya llegó al instante de entrega."""
        self._silent_loss_drops.append(record)
