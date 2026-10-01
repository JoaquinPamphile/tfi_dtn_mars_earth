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
from core.mars.node import DEFAULT_SOURCE_ID
from core.stopping.policy import StopPolicy
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL
from runner.config import RunConfig

DEMO_SCENARIO_ID = "demo-local-motor"
DEMO_SEED = 1
DEMO_NOTICE = "Demostración local del motor. No es evidencia científica."
DEMO_DEFAULT_EVENTS = 10
DEMO_EVENT_TYPE = "medicion"
DEMO_GENERATED_AT_SIM = 0.0
DEMO_CONTACT_START_S = 10.0
DEMO_CONTACT_END_S = 500.0
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


def demo_run_config(
    *,
    strategy_type: str = STRATEGY_TYPE_INDIVIDUAL,
    batch_size_events: int | None = None,
    event_count: int = DEMO_DEFAULT_EVENTS,
) -> RunConfig:
    """Arma la demostración local con la estrategia y la cantidad pedidas.

    La identidad de dataset sale de ``make_experiment_identity`` con el
    escenario y la semilla fijos. No depende de la estrategia, así los
    ``event_id`` siguen siendo deterministas.
    """
    return RunConfig(
        experiment_identity=make_experiment_identity(DEMO_SCENARIO_ID, DEMO_SEED),
        source_id=DEFAULT_SOURCE_ID,
        strategy_type=strategy_type,
        batch_size_events=batch_size_events,
        event_count=event_count,
        generated_at_sim=DEMO_GENERATED_AT_SIM,
        ack_timeout_seconds=DEFAULT_ACK_TIMEOUT_SECONDS,
        stop_policy=StopPolicy.UNTIL_IDLE,
        contact_plan=demo_contact_plan(),
        event_type=DEMO_EVENT_TYPE,
    )


def _contacto(
    contact_id: str,
    source: LogicalNode,
    destination: LogicalNode,
) -> Contact:
    return Contact(
        contact_id=contact_id,
        source=source,
        destination=destination,
        start_time_sim=DEMO_CONTACT_START_S,
        end_time_sim=DEMO_CONTACT_END_S,
        data_rate_bps=DEMO_DATA_RATE_BPS,
        propagation_delay_s=DEMO_PROPAGATION_DELAY_S,
    )
