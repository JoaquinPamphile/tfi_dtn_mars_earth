"""Definición de fallos controlados: corte de contacto, pérdida de ACK y pérdida silenciosa."""

from core.failure.ack import ACK_DROP_FAILURE_ID, AckDropFailure
from core.failure.cut import (
    ContactCutFailure,
    FailurePlanError,
    contact_cut_failure_id,
    validate_contact_cut,
)
from core.failure.plan import FailurePlan, validate_failure_plan
from core.failure.silent import (
    FORWARD_HOP_RELAY_TO_EARTH,
    SILENT_FORWARD_DELIVERY_LOSS_FAILURE_PREFIX,
    TELEMETRY_EVENTS_PAYLOAD_KIND,
    SilentForwardDeliveryLossFailure,
    SilentForwardDeliveryLossHit,
    silent_forward_delivery_loss_failure_id,
)

__all__ = [
    "ACK_DROP_FAILURE_ID",
    "FORWARD_HOP_RELAY_TO_EARTH",
    "SILENT_FORWARD_DELIVERY_LOSS_FAILURE_PREFIX",
    "TELEMETRY_EVENTS_PAYLOAD_KIND",
    "AckDropFailure",
    "ContactCutFailure",
    "FailurePlan",
    "FailurePlanError",
    "SilentForwardDeliveryLossFailure",
    "SilentForwardDeliveryLossHit",
    "contact_cut_failure_id",
    "silent_forward_delivery_loss_failure_id",
    "validate_contact_cut",
    "validate_failure_plan",
]
