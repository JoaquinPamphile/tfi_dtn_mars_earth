"""Configuración de demostración local del motor.

Los contactos son explícitos y alcanzan para un round trip
Marte → relé → Tierra → relé → Marte. No provienen de Alessi y no
constituyen evidencia científica.
"""

from __future__ import annotations

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan
from core.domain.identity import make_experiment_identity
from core.domain.retry import DEFAULT_ACK_TIMEOUT_SECONDS
from core.failure.plan import FailurePlan
from core.failure.silent import (
    FORWARD_HOP_RELAY_TO_EARTH,
    SilentForwardDeliveryLossFailure,
    silent_forward_delivery_loss_failure_id,
)
from core.mars.node import DEFAULT_SOURCE_ID
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL
from runner.config import (
    RECOVERY_NONE,
    RECOVERY_RECEIVER_DRIVEN,
    RECOVERY_SENDER_DRIVEN,
    RunConfig,
)

DEMO_SCENARIO_ID = "demo-local-motor"
DEMO_RECOVERY_SCENARIO_ID = "demo-local-recuperacion"
DEMO_SEED = 1
DEMO_NOTICE = "Demostración local del motor. No es evidencia científica."
DEMO_RECOVERY_NOTICE = (
    "Demostración local de recuperación. No es evidencia científica."
)
DEMO_DEFAULT_EVENTS = 10
DEMO_SILENT_LOSS_SEQUENCE = 1
DEMO_SILENT_LOSS_ATTEMPT = 1
DEMO_SILENT_LOSS_MIN_EVENTS = 3
FAULT_NONE = "none"
FAULT_SILENT_LOSS = "silent-loss"
FAULT_MODES = (FAULT_NONE, FAULT_SILENT_LOSS)
DEMO_EVENT_TYPE = "medicion"
DEMO_GENERATED_AT_SIM = 0.0
DEMO_CONTACT_START_S = 10.0
DEMO_CONTACT_END_S = 500.0
DEMO_RECOVERY_CONTACT_END_S = 800.0
DEMO_RECOVERY_SENDER_ACK_TIMEOUT_S = 40.0
DEMO_RECOVERY_RECEIVER_ACK_TIMEOUT_S = 100_000.0
DEMO_RECOVERY_GAP_TIMEOUT_S = 200.0
DEMO_DATA_RATE_BPS = 8_000_000
DEMO_PROPAGATION_DELAY_S = 1.0


def demo_contact_plan() -> ContactPlan:
    """Cuatro ventanas simultáneas, una por cada sentido del round trip.

    Comparten inicio, fin, tasa y demora. Sirven para comprobar el motor
    desde consola. No son un escenario científico.
    """
    return ContactPlan(
        (
            _contacto("demo-mars-relay", LogicalNode.MARS, LogicalNode.RELAY),
            _contacto("demo-relay-earth", LogicalNode.RELAY, LogicalNode.EARTH),
            _contacto("demo-earth-relay", LogicalNode.EARTH, LogicalNode.RELAY),
            _contacto("demo-relay-mars", LogicalNode.RELAY, LogicalNode.MARS),
        )
    )


def recovery_demo_contact_plan() -> ContactPlan:
    """Ventanas largas para que un retry o una reparación terminen.

    Siguen siendo contactos explícitos de la demostración local. No
    provienen de Alessi y no son un escenario científico.
    """
    return ContactPlan(
        (
            _contacto(
                "recovery-mars-relay",
                LogicalNode.MARS,
                LogicalNode.RELAY,
                fin=DEMO_RECOVERY_CONTACT_END_S,
            ),
            _contacto(
                "recovery-relay-earth",
                LogicalNode.RELAY,
                LogicalNode.EARTH,
                fin=DEMO_RECOVERY_CONTACT_END_S,
            ),
            _contacto(
                "recovery-earth-relay",
                LogicalNode.EARTH,
                LogicalNode.RELAY,
                fin=DEMO_RECOVERY_CONTACT_END_S,
            ),
            _contacto(
                "recovery-relay-mars",
                LogicalNode.RELAY,
                LogicalNode.MARS,
                fin=DEMO_RECOVERY_CONTACT_END_S,
            ),
        )
    )


def demo_silent_loss_plan(source_id: str = DEFAULT_SOURCE_ID) -> FailurePlan:
    """Pierde una sola vez la secuencia intermedia 1, intento 1, relé → Tierra.

    Con al menos tres eventos, la 0 y la 2 pueden llegar y el receptor
    observa el hueco 1..1. El reintento usa otro ``telemetry_attempt_number``
    y ya no coincide.
    """
    failure_id = silent_forward_delivery_loss_failure_id(
        source_id,
        DEMO_SILENT_LOSS_SEQUENCE,
        DEMO_SILENT_LOSS_ATTEMPT,
        FORWARD_HOP_RELAY_TO_EARTH,
    )
    return FailurePlan(
        silent_forward_delivery_losses=(
            SilentForwardDeliveryLossFailure(
                failure_id=failure_id,
                source_id=source_id,
                sequence_number=DEMO_SILENT_LOSS_SEQUENCE,
                telemetry_attempt_number=DEMO_SILENT_LOSS_ATTEMPT,
                hop=FORWARD_HOP_RELAY_TO_EARTH,
                max_occurrences=1,
            ),
        )
    )


def demo_run_config(
    *,
    strategy_type: str = STRATEGY_TYPE_INDIVIDUAL,
    batch_size_events: int | None = None,
    event_count: int = DEMO_DEFAULT_EVENTS,
    recovery: str = RECOVERY_NONE,
    fault: str = FAULT_NONE,
) -> RunConfig:
    """Arma la demostración local con la estrategia y la cantidad pedidas.

    La identidad de dataset sale de ``make_experiment_identity`` con el
    escenario y la semilla fijos. No depende de la estrategia, así los
    ``event_id`` siguen siendo deterministas.

    Sin ``fault`` ni un ``recovery`` distinto de ``none``, el plan y el
    timeout son los de la demostración normal. ``silent-loss`` pierde la
    secuencia 1 y, si hay recuperación, usa ventanas que alcanzan para
    cerrar el retry o la reparación.
    """
    if recovery not in (RECOVERY_NONE, RECOVERY_SENDER_DRIVEN, RECOVERY_RECEIVER_DRIVEN):
        raise ValueError(
            "recuperación no admitida: "
            f"{recovery}. Admitidas: none, sender-driven, receiver-driven."
        )
    if fault not in FAULT_MODES:
        raise ValueError(f"falla no admitida: {fault}. Admitida: {FAULT_SILENT_LOSS}.")
    if fault == FAULT_SILENT_LOSS and event_count < DEMO_SILENT_LOSS_MIN_EVENTS:
        raise ValueError(
            "la pérdida silenciosa de demostración exige al menos "
            f"{DEMO_SILENT_LOSS_MIN_EVENTS} eventos"
        )
    if fault == FAULT_SILENT_LOSS and strategy_type != STRATEGY_TYPE_INDIVIDUAL:
        raise ValueError(
            "la pérdida silenciosa de demostración exige la estrategia individual"
        )
    scenario_id = DEMO_SCENARIO_ID
    contact_plan = demo_contact_plan()
    ack_timeout_seconds = DEFAULT_ACK_TIMEOUT_SECONDS
    gap_request_timeout_seconds = None
    failure_plan = None
    if recovery == RECOVERY_RECEIVER_DRIVEN:
        gap_request_timeout_seconds = DEMO_RECOVERY_GAP_TIMEOUT_S
    if fault == FAULT_SILENT_LOSS:
        failure_plan = demo_silent_loss_plan()
        if recovery != RECOVERY_NONE:
            scenario_id = DEMO_RECOVERY_SCENARIO_ID
            contact_plan = recovery_demo_contact_plan()
            if recovery == RECOVERY_SENDER_DRIVEN:
                ack_timeout_seconds = DEMO_RECOVERY_SENDER_ACK_TIMEOUT_S
            else:
                ack_timeout_seconds = DEMO_RECOVERY_RECEIVER_ACK_TIMEOUT_S
    return RunConfig(
        experiment_identity=make_experiment_identity(scenario_id, DEMO_SEED),
        source_id=DEFAULT_SOURCE_ID,
        strategy_type=strategy_type,
        batch_size_events=batch_size_events,
        event_count=event_count,
        generated_at_sim=DEMO_GENERATED_AT_SIM,
        ack_timeout_seconds=ack_timeout_seconds,
        stop_policy=StopPolicy.UNTIL_IDLE,
        contact_plan=contact_plan,
        event_type=DEMO_EVENT_TYPE,
        recovery_mode=recovery,
        gap_request_timeout_seconds=gap_request_timeout_seconds,
        failure_plan=failure_plan,
    )


def _contacto(
    contact_id: str,
    source: LogicalNode,
    destination: LogicalNode,
    *,
    fin: float = DEMO_CONTACT_END_S,
) -> Contact:
    return Contact(
        contact_id=contact_id,
        source=source,
        destination=destination,
        start_time_sim=DEMO_CONTACT_START_S,
        end_time_sim=fin,
        data_rate_bps=DEMO_DATA_RATE_BPS,
        propagation_delay_s=DEMO_PROPAGATION_DELAY_S,
    )
