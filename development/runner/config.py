"""Configuración mínima de una corrida headless.

No carga YAML y no describe una campaña ni un experimento.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.contact.plan import ContactPlan
from core.domain.priority import TelemetryPriority
from core.failure.plan import FailurePlan
from core.recovery.policy import RecoveryPolicy
from core.stopping.policy import StopPolicy

RECOVERY_NONE = RecoveryPolicy.NONE.value
RECOVERY_SENDER_DRIVEN = RecoveryPolicy.SENDER_DRIVEN.value
RECOVERY_RECEIVER_DRIVEN = RecoveryPolicy.RECEIVER_DRIVEN.value
RECOVERY_MODES = (
    RECOVERY_NONE,
    RECOVERY_SENDER_DRIVEN,
    RECOVERY_RECEIVER_DRIVEN,
)


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Parámetros con los que se arma y se ejecuta una corrida.

    El plan de contactos y la política de parada llegan ya construidos.
    ``horizon_seconds`` en ``None`` sigue la regla del motor: se vacía
    el scheduler.
    """

    experiment_identity: str
    source_id: str
    strategy_type: str
    batch_size_events: int | None
    event_count: int
    generated_at_sim: float
    ack_timeout_seconds: float
    stop_policy: StopPolicy
    contact_plan: ContactPlan
    event_type: str = "medicion"
    priority: TelemetryPriority = TelemetryPriority.NORMAL
    horizon_seconds: float | None = None
    recovery_policy: RecoveryPolicy = RecoveryPolicy.NONE
    gap_request_timeout_seconds: float | None = None
    failure_plan: FailurePlan | None = None

    @property
    def recovery_mode(self) -> str:
        """Valor de consola de la política. No decide qué mecanismo corre."""
        return self.recovery_policy.value

    def __post_init__(self) -> None:
        if self.experiment_identity.strip() == "":
            raise ValueError("experiment_identity no debe estar vacío")
        if self.source_id.strip() == "":
            raise ValueError("source_id no debe estar vacío")
        if self.event_type.strip() == "":
            raise ValueError("event_type no debe estar vacío")
        if self.event_count < 1:
            raise ValueError("la cantidad de eventos debe ser al menos 1")
        if self.generated_at_sim < 0:
            raise ValueError("generated_at_sim no debe ser negativo")
        if self.ack_timeout_seconds <= 0:
            raise ValueError("el timeout de ACK debe ser mayor que 0")
        if self.horizon_seconds is not None and self.horizon_seconds <= 0:
            raise ValueError("el horizonte debe ser mayor que 0")
        if not isinstance(self.recovery_policy, RecoveryPolicy):
            admitidos = ", ".join(RECOVERY_MODES)
            raise ValueError(
                "recuperación no admitida: "
                f"{self.recovery_policy}. Admitidas: {admitidos}."
            )
        if self.recovery_policy.receiver_driven_enabled and (
            self.gap_request_timeout_seconds is None
        ):
            raise ValueError("receiver-driven requiere el timeout del GapRequest")
        if (
            self.gap_request_timeout_seconds is not None
            and self.gap_request_timeout_seconds <= 0
        ):
            raise ValueError("el timeout del GapRequest debe ser mayor que 0")
