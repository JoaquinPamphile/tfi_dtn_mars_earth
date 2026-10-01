"""Métricas científicas de una sola corrida ya terminada.

No agrega campañas, no ejecuta el motor y no lee la consola. Las fórmulas
reciben el estado que la corrida ya produjo.

Las series temporales de intervalo no se arman aquí: harían falta muestras
tomadas durante la corrida, y E1, E2 y E3 responden con escalares de una
corrida.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from core.contact.contact import Contact
from core.domain.attempt import SyncAttempt
from core.domain.gap import GapRequest
from core.failure.runtime import SilentForwardDeliveryDropRecord
from core.metrics.delivery import (
    ConvergenceMetrics,
    FreshnessDistribution,
    FreshnessSample,
    application_state_ratios,
    backlog_events,
    completeness_ratio,
    convergence_reference_at_sim,
    experimental_converged_at_sim,
    freshness_coverage,
    freshness_distribution,
    live_converged,
    not_persisted_on_earth,
    persisted_on_earth_but_unconfirmed,
    scenario_completed_at_sim,
    time_to_convergence_seconds,
    view_age_seconds,
)
from core.metrics.recovery import (
    PersistenceObservation,
    RecoveryEpisodeInputs,
    RecoveryEpisodeResult,
    RecoveryRunSummary,
    SenderTimeoutObservation,
    build_recovery_episodes,
    recovery_run_summary,
)
from core.metrics.traffic import (
    ContactSummaryMetrics,
    CreatedByteCounters,
    TrafficMetrics,
    contact_summary,
    traffic_metrics,
)
from core.recovery.attempt import GapRequestAttemptState
from core.transport.accounting import ForcedContactCut, HopTransmissionRecord


@dataclass(frozen=True, slots=True)
class RunMetricsInput:
    """Entrada mínima, ya leída de las APIs públicas de la corrida."""

    generated: int
    confirmed: int
    earth_persisted_unique: int
    gaps_count: int
    duplicates_received: int
    duplicates_stored: int
    retry_attempts_total: int
    time_sim: float
    engine_status: str
    max_earth_generated_at_sim: float | None
    max_generated_at_sim: float | None
    last_confirmed_at_sim: float | None
    future_telemetry_generation_scheduled: bool
    continuous_generation_active: bool
    freshness_samples: tuple[FreshnessSample, ...]
    persistence: tuple[PersistenceObservation, ...]
    confirmed_at_by_event_id: tuple[tuple[str, float], ...]
    duplicate_receipts_by_event_id: tuple[tuple[str, int], ...]
    attempts_by_event_id: tuple[tuple[str, tuple[SyncAttempt, ...]], ...]
    hop_records: tuple[HopTransmissionRecord, ...]
    contacts: tuple[Contact, ...]
    forced_cuts: tuple[ForcedContactCut, ...]
    created: CreatedByteCounters
    sync_units_created: int
    silent_drops: tuple[SilentForwardDeliveryDropRecord, ...]
    sender_timeouts: tuple[SenderTimeoutObservation, ...]
    issued_gap_requests: tuple[GapRequest, ...]
    gap_request_attempts: tuple[tuple[str, GapRequestAttemptState], ...]
    receiver_repairs: tuple[tuple[str, int, str, float], ...]
    recovery_policy: str | None


@dataclass(frozen=True, slots=True)
class ScientificRunMetrics:
    """Métricas de una corrida. ``final_backlog`` es el backlog al cierre.

    ``completeness`` mide persistencia única en Tierra.
    ``confirmation_ratio`` mide confirmación de aplicación en Marte.
    """

    generated: int
    earth_persisted_unique: int
    confirmed: int
    backlog: int
    final_backlog: int
    not_persisted_on_earth: int
    persisted_on_earth_but_unconfirmed: int
    completeness: float | None
    confirmation_ratio: float | None
    confirmed_ratio: float | None
    persisted_unconfirmed_ratio: float | None
    not_persisted_ratio: float | None
    gaps_count: int
    duplicates_received: int
    duplicates_stored: int
    retry_attempts_total: int
    converged: bool
    convergence: ConvergenceMetrics
    time_sim: float
    scenario_completed_at_sim: float | None
    view_age_seconds: float | None
    freshness: FreshnessDistribution
    freshness_coverage: float | None
    traffic: TrafficMetrics
    contacts: ContactSummaryMetrics
    sync_units_created: int
    recovery: RecoveryRunSummary
    episodes: tuple[RecoveryEpisodeResult, ...]

    def to_dict(self) -> dict[str, object]:
        """Estructura JSON de la corrida. Los ausentes quedan en ``None``."""
        ratios = {
            "confirmation_ratio": self.confirmation_ratio,
            "confirmed_ratio": self.confirmed_ratio,
            "persisted_unconfirmed_ratio": self.persisted_unconfirmed_ratio,
            "not_persisted_ratio": self.not_persisted_ratio,
        }
        payload: dict[str, object] = {
            "generated": self.generated,
            "earth_persisted_unique": self.earth_persisted_unique,
            "confirmed": self.confirmed,
            "backlog": self.backlog,
            "final_backlog": self.final_backlog,
            "not_persisted_on_earth": self.not_persisted_on_earth,
            "persisted_on_earth_but_unconfirmed": self.persisted_on_earth_but_unconfirmed,
            "completeness": self.completeness,
            **ratios,
            "gaps_count": self.gaps_count,
            "duplicates_received": self.duplicates_received,
            "duplicates_stored": self.duplicates_stored,
            "retry_attempts_total": self.retry_attempts_total,
            "converged": self.converged,
            "convergence_reference_at_sim": self.convergence.reference_at_sim,
            "converged_at_sim": self.convergence.converged_at_sim,
            "time_to_convergence_seconds": self.convergence.time_to_convergence_seconds,
            "time_sim": self.time_sim,
            "scenario_completed_at_sim": self.scenario_completed_at_sim,
            "view_age_seconds": self.view_age_seconds,
            "freshness": asdict(self.freshness),
            "freshness_sample_count": self.freshness.count,
            "freshness_coverage": self.freshness_coverage,
            "freshness_min_seconds": self.freshness.min_seconds,
            "freshness_p50_seconds": self.freshness.p50_seconds,
            "freshness_p95_seconds": self.freshness.p95_seconds,
            "freshness_max_seconds": self.freshness.max_seconds,
            "freshness_mean_seconds": self.freshness.mean_seconds,
            "sync_units_created": self.sync_units_created,
            "traffic": asdict(self.traffic),
            "contacts": _contact_dict(self.contacts),
            "recovery": _recovery_dict(self.recovery, self.episodes),
        }
        return payload


def compute_run_metrics(inputs: RunMetricsInput) -> ScientificRunMetrics:
    """Calcula las métricas. No consulta reloj de pared ni reordena al azar."""
    backlog = backlog_events(inputs.generated, inputs.confirmed)
    missing = not_persisted_on_earth(inputs.generated, inputs.earth_persisted_unique)
    unconfirmed = persisted_on_earth_but_unconfirmed(
        inputs.earth_persisted_unique, inputs.confirmed
    )
    ratios = application_state_ratios(
        inputs.generated, inputs.earth_persisted_unique, inputs.confirmed
    )
    reference = convergence_reference_at_sim(
        generated=inputs.generated,
        max_generated_at_sim=inputs.max_generated_at_sim,
        future_telemetry_generation_scheduled=inputs.future_telemetry_generation_scheduled,
        continuous_generation_active=inputs.continuous_generation_active,
    )
    converged_at = experimental_converged_at_sim(
        reference_at_sim=reference,
        time_sim=inputs.time_sim,
        last_confirmed_at_sim=inputs.last_confirmed_at_sim,
        generated=inputs.generated,
        backlog=backlog,
        gaps_count=inputs.gaps_count,
    )
    freshness = freshness_distribution(inputs.freshness_samples)
    episodes = build_recovery_episodes(
        RecoveryEpisodeInputs(
            recovery_policy=inputs.recovery_policy,
            persistence=inputs.persistence,
            confirmed_at_by_event_id=dict(inputs.confirmed_at_by_event_id),
            duplicate_receipts_by_event_id=dict(inputs.duplicate_receipts_by_event_id),
            attempts_by_event_id=dict(inputs.attempts_by_event_id),
            hop_records=inputs.hop_records,
            silent_drops=inputs.silent_drops,
            sender_timeouts=inputs.sender_timeouts,
            issued_gap_requests=inputs.issued_gap_requests,
            gap_request_attempts=dict(inputs.gap_request_attempts),
            receiver_repairs=inputs.receiver_repairs,
        )
    )
    return ScientificRunMetrics(
        generated=inputs.generated,
        earth_persisted_unique=inputs.earth_persisted_unique,
        confirmed=inputs.confirmed,
        backlog=backlog,
        final_backlog=backlog,
        not_persisted_on_earth=missing,
        persisted_on_earth_but_unconfirmed=unconfirmed,
        completeness=completeness_ratio(inputs.generated, inputs.earth_persisted_unique),
        confirmation_ratio=ratios["confirmation_ratio"],
        confirmed_ratio=ratios["confirmed_ratio"],
        persisted_unconfirmed_ratio=ratios["persisted_unconfirmed_ratio"],
        not_persisted_ratio=ratios["not_persisted_ratio"],
        gaps_count=inputs.gaps_count,
        duplicates_received=inputs.duplicates_received,
        duplicates_stored=inputs.duplicates_stored,
        retry_attempts_total=inputs.retry_attempts_total,
        converged=live_converged(
            generated=inputs.generated, backlog=backlog, gaps_count=inputs.gaps_count
        ),
        convergence=ConvergenceMetrics(
            reference_at_sim=reference,
            converged_at_sim=converged_at,
            time_to_convergence_seconds=time_to_convergence_seconds(converged_at, reference),
        ),
        time_sim=inputs.time_sim,
        scenario_completed_at_sim=scenario_completed_at_sim(
            engine_status=inputs.engine_status, time_sim=inputs.time_sim
        ),
        view_age_seconds=view_age_seconds(
            time_sim=inputs.time_sim,
            max_earth_generated_at_sim=inputs.max_earth_generated_at_sim,
        ),
        freshness=freshness,
        freshness_coverage=freshness_coverage(freshness.count, inputs.generated),
        traffic=traffic_metrics(created=inputs.created, hop_records=inputs.hop_records),
        contacts=contact_summary(
            contacts=inputs.contacts,
            forced_cuts=inputs.forced_cuts,
            hop_records=inputs.hop_records,
            time_sim=inputs.time_sim,
        ),
        sync_units_created=inputs.sync_units_created,
        recovery=recovery_run_summary(episodes),
        episodes=episodes,
    )


def _contact_dict(contacts: ContactSummaryMetrics) -> dict[str, object]:
    return {
        "contacts_total": contacts.contacts_total,
        "contacts_used": contacts.contacts_used,
        "contacts_forced_cut": contacts.contacts_forced_cut,
        "contact_utilization_mean": contacts.contact_utilization_mean,
        "contact_utilization_weighted": contacts.contact_utilization_weighted,
        "forward_contact_utilization_weighted": (
            contacts.forward_contact_utilization_weighted
        ),
        "reverse_contact_utilization_weighted": (
            contacts.reverse_contact_utilization_weighted
        ),
    }


def _recovery_dict(
    summary: RecoveryRunSummary, episodes: tuple[RecoveryEpisodeResult, ...]
) -> dict[str, object]:
    payload = asdict(summary)
    payload["episodes"] = [asdict(item) for item in episodes]
    return payload
