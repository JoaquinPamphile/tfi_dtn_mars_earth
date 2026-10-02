"""Calibra el payload para que la SyncUnit Individual inicial mida un tamaño dado.

El tamaño lo produce el codec. Esta función solo elige el padding.
La medición es siempre Individual, intento 1, aunque la corrida use Fixed Batch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from core.domain.event import TelemetryEvent
from core.domain.priority import TelemetryPriority
from core.sync.codec import encode_telemetry_event
from core.sync.strategy import STRATEGY_TYPE_INDIVIDUAL

_PADDING_CHAR = "x"


class PayloadCalibrationError(ValueError):
    """El padding no alcanza el tamaño Individual pedido."""


def calibrate_individual_syncunit_payload(
    *,
    make_payload: Callable[[str], dict[str, Any]],
    target_bytes: int,
    event_id: UUID,
    source_id: str,
    sequence_number: int,
    generated_at_sim: float,
    event_type: str,
    priority: TelemetryPriority,
    schema_version: int,
) -> dict[str, Any]:
    """Devuelve el payload cuyo Individual inicial mide ``target_bytes``.

    ``target_bytes`` incluye la envoltura canónica de la SyncUnit.
    Un carácter de padding ASCII suma un byte en el JSON canónico.
    """
    empty_size = _encoded_individual_size(
        event_id=event_id,
        source_id=source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=event_type,
        priority=priority,
        schema_version=schema_version,
        payload=make_payload(""),
    )
    missing = target_bytes - empty_size
    if missing < 0:
        raise PayloadCalibrationError(
            "la SyncUnit Individual ya supera "
            f"{target_bytes} bytes antes del padding "
            f"(tamaño codificado={empty_size})"
        )
    payload = make_payload(_PADDING_CHAR * missing)
    final_size = _encoded_individual_size(
        event_id=event_id,
        source_id=source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=event_type,
        priority=priority,
        schema_version=schema_version,
        payload=payload,
    )
    if final_size != target_bytes:
        raise PayloadCalibrationError(
            "el padding no alcanzó el tamaño Individual "
            f"{target_bytes} (vacío={empty_size}, faltante={missing}, "
            f"final={final_size})"
        )
    return payload


def _encoded_individual_size(
    *,
    event_id: UUID,
    source_id: str,
    sequence_number: int,
    generated_at_sim: float,
    event_type: str,
    priority: TelemetryPriority,
    schema_version: int,
    payload: dict[str, Any],
) -> int:
    event = TelemetryEvent(
        event_id=event_id,
        source_id=source_id,
        sequence_number=sequence_number,
        generated_at_sim=generated_at_sim,
        event_type=event_type,
        payload=payload,
        priority=priority,
        schema_version=schema_version,
    )
    unit = encode_telemetry_event(
        event,
        generated_at_sim,
        attempt_number=1,
        strategy_type=STRATEGY_TYPE_INDIVIDUAL,
    )
    return unit.payload_size_bytes
