"""Programa un ContactPlan ya construido en el motor de simulación.

No abre el contacto en el transporte. Eso ocurre cuando el motor
despacha ``CONTACT_OPEN``. No carga un escenario declarativo.
"""

from core.contact.contact import Contact
from core.contact.plan import ContactPlan
from core.simulation.engine import SimulationEngine
from core.trace.types import SimulationEventType


def schedule_contact_plan(engine: SimulationEngine, plan: ContactPlan) -> None:
    """Programa ``CONTACT_OPEN`` y ``CONTACT_CLOSE`` de cada contacto.

    El recorrido es el orden del plan, ``(start_time_sim, contact_id)``.
    Para cada contacto, la apertura queda en el inicio y el cierre en
    ``end_time_sim``. Si dos acciones comparten instante, el scheduler
    conserva este orden de programación. ``entity_id`` es ``contact_id``.
    """
    for contact in plan.contacts:
        payload = _contact_event_payload(contact)
        engine.schedule(
            time=contact.start_time_sim,
            event_type=SimulationEventType.CONTACT_OPEN.value,
            payload=payload,
            entity_id=contact.contact_id,
        )
        engine.schedule(
            time=contact.end_time_sim,
            event_type=SimulationEventType.CONTACT_CLOSE.value,
            payload=payload,
            entity_id=contact.contact_id,
        )


def _contact_event_payload(contact: Contact) -> dict[str, object]:
    """Hecho de apertura o cierre. La dirección es origen y destino."""
    return {
        "contact_id": contact.contact_id,
        "source": contact.source.value,
        "destination": contact.destination.value,
        "start_time_sim": contact.start_time_sim,
        "end_time_sim": contact.end_time_sim,
        "data_rate_bps": contact.data_rate_bps,
        "propagation_delay_s": contact.propagation_delay_s,
        "duration_seconds": contact.duration_seconds,
        "nominal_capacity_bits": contact.nominal_capacity_bits,
    }
