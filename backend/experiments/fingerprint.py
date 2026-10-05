"""Huellas deterministas de una corrida científica.

``configuration_hash`` resume la especificación completa. No reemplaza
``execution_identity``: esa identidad sigue siendo escenario, semilla,
estrategia y tamaño de lote. No incluye la versión de software, el
commit ni el estado del árbol.

``dataset_fingerprint`` resume el dataset materializado. Cada entrada es
el JSON canónico de un ``TelemetryEvent``, el mismo objeto que
``to_dict`` entrega al codec, en orden de secuencia. No usa la
representación textual de un objeto de Python.

Ese objeto lleva ``event_id``, ``source_id``, ``sequence_number``,
``generated_at_sim``, ``event_type``, ``payload``, ``priority`` y
``schema_version``. La estrategia, la recuperación, los fallos, la
parada y el nivel de traza no entran.

``flow`` no es un campo de ``TelemetryEvent`` ni de la SyncUnit. Es un
campo del ``Workload``. ``_payload_body`` lo copia dentro de ``payload``
(``payload["flow"]``). Cambia los bytes transmitidos del evento, así que
queda cubierto al hashear el payload y no se agrega como columna aparte.

``schema_version`` sí entra, porque viaja en el evento que el codec
serializa. ``telemetry_schema_version`` del manifiesto es la etiqueta
legible de ese mismo valor (``DEFAULT_SCHEMA_VERSION``). No se concatena
otra vez como prefijo de la huella.

Ninguna de las dos huellas usa UUID4 ni el reloj de pared.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import UUID

from core.domain.event import TelemetryEvent
from core.domain.identity import make_telemetry_event_id
from core.domain.priority import TelemetryPriority
from core.mars.node import DEFAULT_SCHEMA_VERSION

from experiments.canonical import HASH_ALGORITHM, canonical_json, spec_payload
from experiments.result import GeneratedTelemetry
from experiments.spec import ScientificRunSpec

DATASET_FINGERPRINT_FIELDS = (
    "event_id",
    "source_id",
    "sequence_number",
    "generated_at_sim",
    "event_type",
    "payload",
    "priority",
    "schema_version",
)

_FINGERPRINTS: dict[str, str] = {}


def configuration_hash(spec: ScientificRunSpec) -> str:
    """SHA-256 hexadecimal del JSON canónico de la especificación.

    Cambia si cambia cualquier campo de ``spec_payload``, incluido
    ``trace_level``. El nivel de traza es un ajuste de ejecución de
    software: distingue dos configuraciones y no es un factor científico.
    ``dataset_identity`` y ``execution_identity`` no se recalculan aquí.
    La procedencia de software tampoco entra.
    """
    if HASH_ALGORITHM != "sha256":
        raise RuntimeError("el algoritmo contractual de la huella es sha256")
    encoded = canonical_json(spec_payload(spec)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dataset_fingerprint(spec: ScientificRunSpec) -> str:
    """SHA-256 de los eventos que esta carga va a materializar.

    La clave de caché es el dataset y el workload, no la estrategia.
    """
    workload = spec.workload
    key = canonical_json(
        {
            "dataset_identity": spec.dataset_identity,
            "schema_version": DEFAULT_SCHEMA_VERSION,
            "workload": workload.model_dump(mode="json"),
        }
    )
    cached = _FINGERPRINTS.get(key)
    if cached is not None:
        return cached
    identity = spec.dataset_identity
    profile = workload.generation_profile(dataset_identity=identity)
    count = profile.expected_event_count()
    digest = hashlib.sha256()
    for sequence_number in range(count):
        generated_at_sim = profile.event_time(sequence_number)
        event = _materialized_event(
            workload_source_id=workload.source_id,
            workload_event_type=workload.event_type,
            workload_priority=workload.priority,
            dataset_identity=identity,
            sequence_number=sequence_number,
            generated_at_sim=generated_at_sim,
            payload=workload.payload_for(
                dataset_identity=identity,
                sequence_number=sequence_number,
                generated_at_sim=generated_at_sim,
                schema_version=DEFAULT_SCHEMA_VERSION,
            ),
        )
        digest.update(_canonical_event_bytes(event))
    value = digest.hexdigest()
    _FINGERPRINTS[key] = value
    return value


def dataset_fingerprint_from_events(events: Sequence[GeneratedTelemetry]) -> str:
    """La misma huella, leída de los eventos que una corrida ya persistió."""
    ordered = tuple(sorted(events, key=lambda item: item.sequence_number))
    digest = hashlib.sha256()
    for event in ordered:
        restored = TelemetryEvent(
            event_id=UUID(event.event_id),
            source_id=event.source_id,
            sequence_number=event.sequence_number,
            generated_at_sim=event.generated_at_sim,
            event_type=event.event_type,
            payload=event.payload,
            priority=TelemetryPriority(event.priority),
            schema_version=event.schema_version,
        )
        digest.update(_canonical_event_bytes(restored))
    return digest.hexdigest()


def dataset_event_count(spec: ScientificRunSpec) -> int:
    """Conteo de eventos que determina ``dataset_fingerprint``."""
    return spec.workload.expected_event_count()


def _materialized_event(
    *,
    workload_source_id: str,
    workload_event_type: str,
    workload_priority: TelemetryPriority,
    dataset_identity: str,
    sequence_number: int,
    generated_at_sim: float,
    payload: dict[str, object],
) -> TelemetryEvent:
    event_id = make_telemetry_event_id(
        dataset_identity=dataset_identity,
        source_id=workload_source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=workload_event_type,
    )
    return TelemetryEvent(
        event_id=event_id,
        source_id=workload_source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=workload_event_type,
        payload=payload,
        priority=workload_priority,
        schema_version=DEFAULT_SCHEMA_VERSION,
    )


def _canonical_event_bytes(event: TelemetryEvent) -> bytes:
    document = event.to_dict()
    if tuple(document) != DATASET_FINGERPRINT_FIELDS:
        raise RuntimeError("el evento materializado no tiene los campos contractuales")
    return (canonical_json(document) + "\n").encode("utf-8")
