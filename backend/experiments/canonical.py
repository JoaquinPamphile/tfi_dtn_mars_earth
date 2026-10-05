"""JSON canónico de una especificación científica.

El resumen compacto y ordenado es el que ya entra en la identidad de
campaña. La huella de la corrida usa exactamente ese objeto. No se
redondean magnitudes y no se aplica ``default=str``.
"""

from __future__ import annotations

import json
import math
from enum import Enum
from typing import Any
from uuid import UUID

from experiments.spec import ScientificRunSpec

HASH_ALGORITHM = "sha256"
MANIFEST_SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 1
SOFTWARE_VERSION = "0.0.0"


def spec_payload(spec: ScientificRunSpec) -> dict[str, Any]:
    """Objeto JSON de la especificación completa.

    Incluye el escenario, la carga, la semilla, la estrategia, el lote,
    la política de recuperación, el retry, el plan de fallos, la parada,
    el horizonte vía el escenario, el timeout de GapRequest y el nivel de
    traza. No incluye identidades derivadas, huellas, resultados ni reloj
    de pared.
    """
    return {
        "scenario": spec.scenario.model_dump(mode="json"),
        "workload": spec.workload.model_dump(mode="json"),
        "seed": spec.seed,
        "strategy_type": spec.strategy_type,
        "batch_size_events": spec.batch_size_events,
        "recovery_policy": spec.recovery_policy.value,
        "retry_policy": spec.retry_policy.model_dump(mode="json"),
        "failure_plan": spec.failure_plan.model_dump(mode="json"),
        "stop_policy": spec.stop_policy.value,
        "trace_level": spec.trace_level.value,
        "gap_request_timeout_seconds": spec.gap_request_timeout_seconds,
    }


def jsonable(value: Any) -> Any:
    """Valor apto para JSON. Rechaza lo que no tiene forma contractual."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("un float no finito no se serializa")
        return value
    if isinstance(value, Enum):
        return jsonable(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    raise TypeError(f"tipo no serializable: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """JSON compacto, ordenado y estable. Las listas conservan su orden."""
    return json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_json_text(value: Any) -> str:
    """El mismo objeto, con sangría fija y salto de línea final."""
    return (
        json.dumps(
            jsonable(value),
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )
