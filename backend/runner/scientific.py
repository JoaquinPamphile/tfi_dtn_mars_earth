"""Arma la entrada de métricas desde el estado público de una corrida.

No recalcula fórmulas. Solo lee contadores, registros e intentos que la
corrida ya dejó consultables.
"""

from __future__ import annotations

from core.metrics.delivery import FreshnessSample
from core.metrics.recovery import PersistenceObservation, SenderTimeoutObservation
from core.metrics.run import RunMetricsInput, ScientificRunMetrics, compute_run_metrics
from core.metrics.traffic import CreatedByteCounters
from core.recovery.policy import RecoveryPolicy
from core.runtime.stack import SimulationStack


def collect_scientific_metrics(
    stack: SimulationStack, recovery_mode: str
) -> ScientificRunMetrics:
    """Métricas de la corrida que ``stack`` ya ejecutó."""
    earth_status = stack.earth.status()
    mars_status = stack.mars.application_status()
    created = stack.session.created_sync_byte_counters()
    events = stack.mars.events_for_source()
    confirmed_at: list[tuple[str, float]] = []
    receipts: list[tuple[str, int]] = []
    attempts: list[tuple[str, tuple]] = []
    for event in events:
        event_id = str(event.event_id)
        at_sim = stack.mars.confirmed_at_sim(event.event_id)
        if at_sim is not None:
            confirmed_at.append((event_id, at_sim))
        receipts.append((event_id, stack.earth.duplicate_receipts_for(event.event_id)))
        attempts.append((event_id, tuple(stack.mars.sync_attempts_for_event(event.event_id))))
    recovery = stack.recovery
    issued = tuple(recovery.issued_requests) if recovery is not None else ()
    gap_attempts = (
        tuple(recovery.attempts.items()) if recovery is not None else ()
    )
    repairs = tuple(recovery.repair_submissions) if recovery is not None else ()
    return compute_run_metrics(
        RunMetricsInput(
            generated=mars_status.generated,
            confirmed=mars_status.confirmed,
            earth_persisted_unique=earth_status.persisted_unique,
            gaps_count=earth_status.gaps_count,
            duplicates_received=earth_status.duplicates_received,
            duplicates_stored=earth_status.duplicates_stored,
            retry_attempts_total=mars_status.retry_attempts_total,
            time_sim=stack.engine.now,
            engine_status=stack.engine.status.value,
            max_earth_generated_at_sim=stack.earth.max_generated_at_sim(),
            max_generated_at_sim=mars_status.max_generated_at_sim,
            last_confirmed_at_sim=mars_status.max_confirmed_at_sim,
            future_telemetry_generation_scheduled=False,
            continuous_generation_active=False,
            freshness_samples=tuple(
                FreshnessSample(
                    generated_at_sim=generated_at,
                    earth_persisted_at_sim=persisted_at,
                )
                for generated_at, persisted_at in stack.earth.persistence_samples()
            ),
            persistence=tuple(
                PersistenceObservation(
                    event_id=str(record.event_id),
                    source_id=record.source_id,
                    sequence_number=record.sequence_number,
                    generated_at_sim=record.generated_at_sim,
                    earth_first_persisted_at_sim=record.first_persisted_at_sim,
                )
                for record in stack.earth.persistence_records()
            ),
            confirmed_at_by_event_id=tuple(confirmed_at),
            duplicate_receipts_by_event_id=tuple(receipts),
            attempts_by_event_id=tuple(attempts),
            hop_records=stack.transport.hop_records(),
            contacts=stack.contact_plan.contacts,
            forced_cuts=stack.transport.forced_contact_cuts(),
            created=CreatedByteCounters(
                telemetry_syncunit_bytes_created=created.telemetry_syncunit_bytes_created,
                telemetry_initial_syncunit_bytes_created=(
                    created.telemetry_initial_syncunit_bytes_created
                ),
                telemetry_retry_syncunit_bytes_created=(
                    created.telemetry_retry_syncunit_bytes_created
                ),
                ack_syncunit_bytes_created=created.ack_syncunit_bytes_created,
            ),
            sync_units_created=created.sync_units_created,
            silent_drops=stack.failures.silent_forward_delivery_drops(),
            sender_timeouts=tuple(
                SenderTimeoutObservation(
                    attempt_id=item.attempt_id,
                    event_ids=item.event_ids,
                    at_sim=item.at_sim,
                )
                for item in stack.session.sender_ack_timeouts()
            ),
            issued_gap_requests=issued,
            gap_request_attempts=gap_attempts,
            receiver_repairs=repairs,
            recovery_policy=RecoveryPolicy(recovery_mode).metrics_name(),
        )
    )
