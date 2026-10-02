"""Volumen ofrecido canónico respecto de la capacidad Marte → relé.

La fracción ``f`` es adimensional: el volumen ofrecido en bytes es ``f * C``.
``C`` es la capacidad serializada Marte → relé, en bytes, sobre un intervalo
explícito. ``0.25`` es un cuarto de esa capacidad. No es el entero 25.

El conteo de eventos es el mismo para Individual y Fixed Batch. La tasa de
generación sale de ese conteo y de la duración del workload. Esta función
no ejecuta una campaña ni elige una grilla de experimentos.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.contact.contact import Contact, LogicalNode

from experiments.scenario import Scenario

# Intervalo de capacidad: desde el inicio del workload hasta el fin del
# último contacto Marte → relé. Incluye el drenaje posterior a la generación.
CAPACITY_INTERVAL_WORKLOAD_TO_LAST_MARS_RELAY_END = (
    "workload_start_to_last_mars_relay_end"
)

# Grilla canónica de fracciones. El workload genérico no la exige.
CANONICAL_OFFERED_LOAD_FRACTIONS: tuple[float, ...] = (
    0.25,
    0.50,
    0.75,
    0.90,
    1.00,
    1.20,
)


@dataclass(frozen=True, slots=True)
class ReferenceCapacity:
    """Capacidad Marte → relé sobre un intervalo ya elegido."""

    scenario_id: str
    interval_start_sim: float
    interval_end_sim: float
    serialized_capacity_bytes: float
    contact_count: int

    @property
    def interval_duration_seconds(self) -> float:
        return self.interval_end_sim - self.interval_start_sim


def mars_to_relay_contacts(scenario: Scenario) -> tuple[Contact, ...]:
    """Contactos dirigidos Marte → relé, en el orden del escenario."""
    return tuple(
        contact
        for contact in scenario.contacts
        if contact.source is LogicalNode.MARS and contact.destination is LogicalNode.RELAY
    )


def capacity_interval_to_last_mars_relay_end(
    scenario: Scenario,
    *,
    workload_start_sim: float,
) -> tuple[float, float]:
    """``[inicio del workload, fin del último contacto Marte → relé]``."""
    contacts = mars_to_relay_contacts(scenario)
    if not contacts:
        raise ValueError(
            f"{scenario.scenario_id} no tiene contactos Marte → relé para la capacidad"
        )
    last_end = max(contact.end_time_sim for contact in contacts)
    if last_end <= workload_start_sim:
        raise ValueError("el fin del último contacto Marte → relé debe ser posterior al inicio")
    return (workload_start_sim, last_end)


def reference_mars_to_relay_capacity(
    scenario: Scenario,
    *,
    interval_start_sim: float,
    interval_end_sim: float,
) -> ReferenceCapacity:
    """Suma los bytes serializables Marte → relé que solapan el intervalo.

    Cada contacto aporta ``duración_solapada * data_rate_bps / 8``.
    """
    if interval_end_sim <= interval_start_sim:
        raise ValueError("el fin del intervalo de capacidad debe ser posterior al inicio")
    total = 0.0
    used = 0
    for contact in mars_to_relay_contacts(scenario):
        contributed = _overlapping_serialized_bytes(
            contact, interval_start_sim, interval_end_sim
        )
        if contributed > 0:
            used += 1
            total += contributed
    return ReferenceCapacity(
        scenario_id=scenario.scenario_id,
        interval_start_sim=interval_start_sim,
        interval_end_sim=interval_end_sim,
        serialized_capacity_bytes=total,
        contact_count=used,
    )


def offered_load_event_count(
    *,
    load_fraction: float,
    capacity_bytes: float,
    canonical_individual_bytes: int,
) -> int:
    """Eventos cuyo volumen Individual canónico es ``load_fraction * C``.

    El conteo es ``floor(f * C / tamaño_individual)``. Individual y Fixed
    Batch comparten este conteo.
    """
    if load_fraction <= 0:
        raise ValueError("la fracción de carga debe ser mayor que 0")
    if canonical_individual_bytes <= 0:
        raise ValueError("el tamaño Individual canónico debe ser mayor que 0")
    if capacity_bytes <= 0:
        raise ValueError("la capacidad de referencia debe ser mayor que 0")
    return int(load_fraction * capacity_bytes // canonical_individual_bytes)


def generation_rate_for_event_count(*, event_count: int, duration_seconds: float) -> float:
    """Tasa uniforme ``eventos / duración`` que reparte ese conteo en la ventana."""
    if event_count < 1:
        raise ValueError("el conteo de eventos debe ser al menos 1")
    if duration_seconds <= 0:
        raise ValueError("la duración debe ser mayor que 0")
    return event_count / duration_seconds


def _overlapping_serialized_bytes(
    contact: Contact, interval_start: float, interval_end: float
) -> float:
    start = max(contact.start_time_sim, interval_start)
    end = min(contact.end_time_sim, interval_end)
    duration = max(0.0, end - start)
    return duration * contact.data_rate_bps / 8.0
