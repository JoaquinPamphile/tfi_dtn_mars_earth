from collections.abc import Mapping
from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator
from core.contact import ContactPlan
from core.failure.ack import AckDropFailure
from core.failure.cut import ContactCutFailure, FailurePlanError, validate_contact_cut
from core.failure.silent import SilentForwardDeliveryLossFailure, SilentForwardDeliveryLossHit

class FailurePlan(BaseModel):
    """Conjunto de fallos de una corrida. No modifica el escenario de origen.
    Los ``failure_id`` son únicos entre cortes, pérdidas de ACK y pérdidas
    silenciosas. Hay como máximo un corte por ``contact_id`` y como máximo
    una pérdida de ACK.
    Dos pérdidas silenciosas pueden compartir identidad lógica si sus
    ``failure_id`` difieren. La coincidencia recorre la tupla en orden y se
    queda con la primera que aún tiene ocurrencias disponibles.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    contact_cuts: tuple[ContactCutFailure, ...] = ()
    ack_drops: tuple[AckDropFailure, ...] = ()
    silent_forward_delivery_losses: tuple[SilentForwardDeliveryLossFailure, ...] = ()

    @model_validator(mode="after")
    def unique_ids_and_contacts(self) -> Self:
        failure_ids = [item.failure_id for item in self.contact_cuts]
        failure_ids.extend(item.failure_id for item in self.ack_drops)
        failure_ids.extend(item.failure_id for item in self.silent_forward_delivery_losses)
        if len(failure_ids) != len(set(failure_ids)):
            raise ValueError("los failure_id deben ser únicos")
        contact_ids = [item.contact_id for item in self.contact_cuts]
        if len(contact_ids) != len(set(contact_ids)):
            raise ValueError("como máximo un corte por contact_id")
        if len(self.ack_drops) > 1:
            raise ValueError("como máximo un fallo de pérdida de ACK")
        return self

    def contact_cut_for(self, contact_id: str) -> ContactCutFailure | None:
        """Devuelve el corte de ese contacto, si está configurado."""
        for cut in self.contact_cuts:
            if cut.contact_id == contact_id:
                return cut
        return None

    def ack_drop(self) -> AckDropFailure | None:
        """Devuelve la pérdida de ACK activa.

        Una configuración con ``count`` menor o igual que cero no está activa.
        """
        if not self.ack_drops:
            return None
        drop = self.ack_drops[0]
        if drop.count <= 0:
            return None
        return drop

    def match_ack_drop(self, acks_already_dropped: int) -> AckDropFailure | None:
        """Devuelve la pérdida de ACK si el siguiente ACK generado debe perderse.
        ``acks_already_dropped`` es cuántos ACK ya se perdieron. Esta consulta
        no incrementa ese contador.
        """
        drop = self.ack_drop()
        if drop is None:
            return None
        if acks_already_dropped >= drop.count:
            return None
        return drop

    def match_silent_forward_delivery_loss(
        self,
        *,
        source_id: str,
        sequence_number: int,
        telemetry_attempt_number: int,
        hop: str,
        payload_kind: str | None,
        event_count: int,
        occurrences_used: Mapping[str, int] | None = None,
    ) -> SilentForwardDeliveryLossHit | None:
        """Devuelve la primera pérdida silenciosa que coincide, sin consumirla.
        El recorrido sigue el orden de ``silent_forward_delivery_losses``.
        ``occurrences_used`` mapea ``failure_id`` a ocurrencias ya contabilizadas;
        una clave ausente vale 0. Esta consulta no modifica el mapa.
        """
        used_by_id: Mapping[str, int] = {} if occurrences_used is None else occurrences_used
        for spec in self.silent_forward_delivery_losses:
            used = used_by_id.get(spec.failure_id, 0)
            if not spec.matches(
                source_id=source_id,
                sequence_number=sequence_number,
                telemetry_attempt_number=telemetry_attempt_number,
                hop=hop,
                payload_kind=payload_kind,
                event_count=event_count,
                occurrences_used=used,
            ):
                continue
            return SilentForwardDeliveryLossHit(
                failure=spec,
                occurrence_number=used + 1,
            )
        return None

def validate_failure_plan(plan: FailurePlan, contact_plan: ContactPlan) -> None:
    """Comprueba que cada corte apunte a un contacto del plan y caiga dentro de su ventana."""
    for cut in plan.contact_cuts:
        try:
            contact = contact_plan.get(cut.contact_id)
        except KeyError as exc:
            raise FailurePlanError(
                f"el contact_id '{cut.contact_id}' no existe en el plan cargado"
            ) from exc
        validate_contact_cut(contact, cut.cut_at_sim)
