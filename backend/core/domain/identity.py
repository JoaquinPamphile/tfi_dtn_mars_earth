from collections.abc import Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

# Namespaces UUID5 estables. Estas constantes forman parte del contrato de
# reproducibilidad. Se derivan de NAMESPACE_URL (RFC 4122) para no depender
# de la aleatorización de hash() por proceso ni del reloj de pared.

EXPERIMENT_IDENTITY_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/experiment-identity"
)
DATASET_IDENTITY_NAMESPACE = EXPERIMENT_IDENTITY_NAMESPACE
EXECUTION_IDENTITY_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/execution-identity"
)
TELEMETRY_EVENT_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/telemetry-event"
)
GENERATION_PROFILE_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/generation-profile"
)
GAP_REQUEST_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/gap-request"
)
RECOVERY_EPISODE_NAMESPACE = uuid5(
    NAMESPACE_URL, "https://tfi.local/dtn-mars-earth-lab/recovery-episode"
)

def make_experiment_identity(scenario_id: str, seed: int) -> str:
    """Identidad de dataset de una configuración de generación de telemetría.

    Alias de ``make_dataset_identity``. Depende solo del escenario y de la
    semilla. La estrategia de sincronización, los fallos y el resto de la
    configuración de ejecución no entran aquí: no deben cambiar
    ``TelemetryEvent.event_id``.

    Es distinta de ``runtime_run_id``, identificador técnico único de una
    ejecución (uuid4), que no debe aparecer en las identidades científicas
    de los eventos.
    """
    return make_dataset_identity(scenario_id, seed)

def make_dataset_identity(scenario_id: str, seed: int) -> str:
    """Identidad lógica del dataset de telemetría.

    Las entradas son solo la configuración de generación (escenario, semilla).
    Cambiar Individual por Fixed Batch no debe cambiar este valor.
    """
    return str(uuid5(DATASET_IDENTITY_NAMESPACE, f"{scenario_id}\nseed={seed}"))

def make_execution_identity(
    scenario_id: str,
    seed: int,
    *,
    strategy_type: str,
    batch_size_events: int | None = None,
) -> str:
    """Identidad de una ejecución experimental.

    Puede depender además de la estrategia (y, más adelante, de fallos u
    otros ajustes de ejecución). Nunca debe usarse como entrada de
    ``TelemetryEvent.event_id``.
    """
    batch = "" if batch_size_events is None else str(batch_size_events)
    name = f"{scenario_id}\nseed={seed}\nstrategy={strategy_type}\nbatch={batch}"
    return str(uuid5(EXECUTION_IDENTITY_NAMESPACE, name))

def make_telemetry_event_id(
    *,
    source_id: str,
    sequence_number: int,
    generated_at_sim: float,
    event_type: str,
    dataset_identity: str | None = None,
    experiment_identity: str | None = None,
) -> UUID:
    """Identidad lógica y reproducible de un evento de telemetría generado en simulación.

    La entrada de identidad es la identidad de **dataset** (escenario + semilla
    + campos de generación), nunca la identidad de ejecución ni el tipo de
    estrategia. ``experiment_identity`` se acepta como alias de compatibilidad
    de ``dataset_identity``. No se usan marcas de reloj de pared ni hash().
    """
    identity = dataset_identity if dataset_identity is not None else experiment_identity
    if identity is None:
        raise TypeError("dataset_identity es obligatorio")
    name = (
        f"{identity}\n{source_id}\n{sequence_number}\n"
        f"{generated_at_sim:.9f}\n{event_type}"
    )
    return uuid5(TELEMETRY_EVENT_NAMESPACE, name)

def make_generation_profile_id(
    *,
    experiment_identity: str,
    event_type: str,
    priority: str,
    rate_events_per_second: float,
    start_time_sim: float,
    duration_seconds: float | None,
    max_events: int | None,
) -> str:
    duration = "" if duration_seconds is None else f"{duration_seconds:.9f}"
    maximum = "" if max_events is None else str(max_events)
    name = (
        f"{experiment_identity}\n{event_type}\n{priority}\n"
        f"{rate_events_per_second:.9f}\n{start_time_sim:.9f}\n"
        f"{duration}\n{maximum}"
    )
    return str(uuid5(GENERATION_PROFILE_NAMESPACE, name))

def make_gap_request_id(
    *,
    target_source_id: str,
    missing_ranges: Sequence[object],
    created_at_sim: float,
    requesting_node_id: str = "EARTH",
) -> str:
    """Identidad determinista de un GapRequest receiver-driven.

    Las entradas son la fuente destino, los rangos faltantes canónicos y
    la marca lógica de generación del pedido. No se usan el reloj de pared,
    el ``hash()`` de Python ni UUID aleatorios.
    """
    parts: list[str] = []
    for item in missing_ranges:
        if isinstance(item, tuple) and len(item) == 2:
            start, end = int(item[0]), int(item[1])
        else:
            start = int(getattr(item, "start_sequence"))
            end = int(getattr(item, "end_sequence"))
        parts.append(f"{start}:{end}")
    name = (
        f"{requesting_node_id}\n{target_source_id}\n"
        f"{','.join(parts)}\n{created_at_sim:.9f}"
    )
    return str(uuid5(GAP_REQUEST_NAMESPACE, name))

def make_recovery_episode_id(
    *,
    failure_type: str,
    source_id: str,
    sequence_number: int,
    failure_occurrence: int,
    telemetry_attempt_number: int = 1,
    hop: str = "RELAY_TO_EARTH",
) -> str:
    """Identidad determinista de un episodio de recuperación o de fallo.

    Las entradas son la identidad del fallo exógeno y el objetivo lógico de
    telemetría. No se usan la política de recuperación, run_id, el reloj de
    pared, el ``hash()`` de Python ni UUID aleatorios, de modo que la misma
    ocurrencia de pérdida silenciosa conserva el mismo identificador de
    episodio en las ejecuciones del emisor y del receptor.
    """
    name = (
        f"{failure_type}\n{source_id}\n{sequence_number}\n"
        f"{failure_occurrence}\n{telemetry_attempt_number}\n{hop}"
    )
    return str(uuid5(RECOVERY_EPISODE_NAMESPACE, name))
