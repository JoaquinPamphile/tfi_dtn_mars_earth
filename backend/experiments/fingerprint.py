"""Huellas deterministas de una corrida científica.

``configuration_hash`` resume la especificación completa. No reemplaza
``execution_identity``: esa identidad sigue siendo escenario, semilla,
estrategia y tamaño de lote.

``dataset_fingerprint`` resume el dataset materializado: una línea por
evento generado, no la estrategia ni el plan de fallos.

Ninguna de las dos usa UUID4 ni el reloj de pared.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from core.domain.identity import make_telemetry_event_id

from experiments.canonical import HASH_ALGORITHM, canonical_json, spec_payload
from experiments.result import GeneratedTelemetry
from experiments.spec import ScientificRunSpec


def configuration_hash(spec: ScientificRunSpec) -> str:
    """SHA-256 hexadecimal del JSON canónico de la especificación.

    Cambia si cambia cualquier campo de ``spec_payload``, incluido
    ``trace_level``. El nivel de traza es un ajuste de ejecución de
    software: distingue dos configuraciones y no es un factor científico.
    ``dataset_identity`` y ``execution_identity`` no se recalculan aquí.
    """
    if HASH_ALGORITHM != "sha256":
        raise RuntimeError("el algoritmo contractual de la huella es sha256")
    encoded = canonical_json(spec_payload(spec)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dataset_fingerprint(spec: ScientificRunSpec) -> str:
    """SHA-256 de las identidades de evento que esta carga va a generar.

    Las entradas son la identidad de dataset y, en orden de secuencia, el
    evento que Marte asignaría. La estrategia, la recuperación, los fallos,
    la parada y el nivel de traza no entran.
    """
    workload = spec.workload
    identity = spec.dataset_identity
    profile = workload.generation_profile(dataset_identity=identity)
    count = profile.expected_event_count()
    priority = workload.priority.value
    digest = hashlib.sha256()
    for sequence_number in range(count):
        generated_at_sim = profile.event_time(sequence_number)
        event_id = make_telemetry_event_id(
            dataset_identity=identity,
            source_id=workload.source_id,
            sequence_number=sequence_number,
            generated_at_sim=generated_at_sim,
            event_type=workload.event_type,
        )
        digest.update(
            _event_line(
                event_id=str(event_id),
                source_id=workload.source_id,
                sequence_number=sequence_number,
                generated_at_sim=generated_at_sim,
                event_type=workload.event_type,
                priority=priority,
            )
        )
    return digest.hexdigest()


def dataset_fingerprint_from_events(
    events: Sequence[GeneratedTelemetry],
    *,
    priority: str,
) -> str:
    """La misma huella, leída de los eventos que una corrida ya persistió."""
    ordered = tuple(sorted(events, key=lambda item: item.sequence_number))
    digest = hashlib.sha256()
    for event in ordered:
        digest.update(
            _event_line(
                event_id=event.event_id,
                source_id=event.source_id,
                sequence_number=event.sequence_number,
                generated_at_sim=event.generated_at_sim,
                event_type=event.event_type,
                priority=priority,
            )
        )
    return digest.hexdigest()


def dataset_event_count(spec: ScientificRunSpec) -> int:
    """Conteo de eventos que determina ``dataset_fingerprint``."""
    return spec.workload.expected_event_count()


def _event_line(
    *,
    event_id: str,
    source_id: str,
    sequence_number: int,
    generated_at_sim: float,
    event_type: str,
    priority: str,
) -> bytes:
    return (
        f"{event_id}\t{source_id}\t{sequence_number}\t"
        f"{generated_at_sim:.9f}\t{event_type}\t{priority}\n"
    ).encode("utf-8")
