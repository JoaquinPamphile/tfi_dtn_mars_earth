"""Codec del contenido lógico de una SyncUnit.
Construye e interpreta la carga de telemetría, de ACK de aplicación y de
gap request. Recibe el conjunto ya decidido: no elige eventos, no transmite
y no ejecuta recuperación.
"""
from __future__ import annotations
import json
from collections.abc import Sequence

from core.contact import LogicalNode
from core.domain.ack import ApplicationAck, ApplicationAckStatus
from core.domain.attempt import attempt_id_for_group, sync_group_id_for
from core.domain.event import TelemetryEvent
from core.domain.gap import GapRequest
from core.sync.unit import SyncUnit

KIND_TELEMETRY_EVENTS = "telemetry_events"
KIND_APPLICATION_ACK = "application_ack"
KIND_GAP_REQUEST = "gap_request"
# Etiqueta registrada en la carga cuando el llamador no indica otra.
# No selecciona eventos ni define una estrategia.
DEFAULT_STRATEGY_TYPE = "individual"

def encode_telemetry_event(
    event: TelemetryEvent,
    created_at_sim: float,
    *,
    attempt_id: str | None = None,
    attempt_number: int = 1,
    strategy_type: str = DEFAULT_STRATEGY_TYPE,
) -> SyncUnit:
    """Codifica un único evento de telemetría ya elegido."""
    resolved_attempt = (
        attempt_id
        if attempt_id is not None
        else attempt_id_for_group((event.event_id,), attempt_number)
    )
    return encode_telemetry_events(
        (event,),
        created_at_sim,
        attempt_id=resolved_attempt,
        attempt_number=attempt_number,
        strategy_type=strategy_type,
    )

def encode_telemetry_events(
    events: Sequence[TelemetryEvent],
    created_at_sim: float,
    *,
    attempt_id: str,
    attempt_number: int,
    strategy_type: str = DEFAULT_STRATEGY_TYPE,
    sync_group_id: str | None = None,
) -> SyncUnit:
    """Codifica la secuencia de eventos ya formada en una SyncUnit.

    ``payload_size_bytes`` es la longitud en bytes UTF-8 del JSON canónico
    de ``payload``. No incluye cabeceras de transporte ni sobrecarga de
    enlace. La envoltura se escribe una vez por unidad.

    Con un evento, ``sync_unit_id`` es ``tel-{event_id}-a{attempt_number}``.
    Con varios, es ``tel-{group_id}-a{attempt_number}``. ``group_id`` es
    ``sync_group_id`` si viene informado; si no, ``sync_group_id_for`` de
    los ``event_id`` en el orden recibido.

    El origen es Marte y el destino es el relé. ``submission_order`` queda
    en 0. ``created_at_sim`` es el instante recibido, no el de generación
    de los eventos.
    """
    event_list = tuple(events)
    if not event_list:
        raise ValueError("la lista de eventos no debe estar vacía")
    group_id = (
        sync_group_id
        if sync_group_id is not None
        else sync_group_id_for(tuple(event.event_id for event in event_list))
    )
    payload = {
        "kind": KIND_TELEMETRY_EVENTS,
        "strategy_type": strategy_type,
        "sync_group_id": group_id,
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "events": [event.to_dict() for event in event_list],
    }
    raw = canonical_dumps(payload)
    if len(event_list) == 1:
        sync_unit_id = f"tel-{event_list[0].event_id}-a{attempt_number}"
    else:
        sync_unit_id = f"tel-{group_id}-a{attempt_number}"
    return SyncUnit(
        sync_unit_id=sync_unit_id,
        source_node=LogicalNode.MARS,
        destination_node=LogicalNode.RELAY,
        payload_size_bytes=len(raw.encode("utf-8")),
        event_ids=tuple(event.event_id for event in event_list),
        created_at_sim=created_at_sim,
        payload=payload,
    )

def encode_application_ack(ack: ApplicationAck, created_at_sim: float) -> SyncUnit:
    """Codifica un ApplicationAck ya construido.

    ``sync_unit_id`` es ``acku-{ack_id}``. ``event_ids`` son los de la
    membresía del ACK. El origen es Tierra y el destino es el relé.
    """
    payload = {"kind": KIND_APPLICATION_ACK, "ack": ack.to_dict()}
    raw = canonical_dumps(payload)
    return SyncUnit(
        sync_unit_id=f"acku-{ack.ack_id}",
        source_node=LogicalNode.EARTH,
        destination_node=LogicalNode.RELAY,
        payload_size_bytes=len(raw.encode("utf-8")),
        event_ids=ack.event_ids,
        created_at_sim=created_at_sim,
        payload=payload,
    )

def decode_telemetry_events(unit: SyncUnit) -> tuple[TelemetryEvent, ...]:
    """Reconstruye los eventos de telemetría codificados en la unidad."""
    if unit.payload.get("kind") != KIND_TELEMETRY_EVENTS:
        raise ValueError("la unidad no contiene eventos de telemetría")
    raw_events = unit.payload.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("la carga de telemetría debe incluir eventos")
    events = tuple(TelemetryEvent.from_dict(item) for item in raw_events)
    if tuple(event.event_id for event in events) != unit.event_ids:
        raise ValueError("event_ids no coincide con la telemetría codificada")
    return events

def decode_application_ack(unit: SyncUnit) -> ApplicationAck:
    """Reconstruye el ApplicationAck codificado en la unidad."""
    if unit.payload.get("kind") != KIND_APPLICATION_ACK:
        raise ValueError("la unidad no contiene un ACK de aplicación")
    raw_ack = unit.payload.get("ack")
    if not isinstance(raw_ack, dict):
        raise ValueError("la carga del ACK debe ser un objeto")
    ack = ApplicationAck.from_dict(raw_ack)
    if ack.status is not ApplicationAckStatus.ACCEPTED:
        raise ValueError("el ACK no representa la aceptación durable en Tierra")
    return ack

def encode_gap_request(request: GapRequest, *, attempt_number: int = 1) -> SyncUnit:
    """Codifica un GapRequest ya construido.

    ``sync_unit_id`` es ``gapreq-{request_id}-a{attempt_number}``.
    ``attempt_number`` identifica el intento de este pedido; el
    ``request_id`` no cambia entre intentos. ``event_ids`` queda vacío.
    El origen es Tierra, el destino es el relé y ``created_at_sim`` es el
    del pedido.
    """
    if attempt_number < 1:
        raise ValueError("attempt_number debe ser >= 1")
    payload = {
        "kind": KIND_GAP_REQUEST,
        "gap_request": request.to_dict(),
        "attempt_number": attempt_number,
    }
    raw = canonical_dumps(payload)
    return SyncUnit(
        sync_unit_id=f"gapreq-{request.request_id}-a{attempt_number}",
        source_node=LogicalNode.EARTH,
        destination_node=LogicalNode.RELAY,
        payload_size_bytes=len(raw.encode("utf-8")),
        event_ids=(),
        created_at_sim=request.created_at_sim,
        payload=payload,
    )

def decode_gap_request(unit: SyncUnit) -> GapRequest:
    """Reconstruye el GapRequest codificado en la unidad."""
    if unit.payload.get("kind") != KIND_GAP_REQUEST:
        raise ValueError("la unidad no contiene un gap request")
    raw_request = unit.payload.get("gap_request")
    if not isinstance(raw_request, dict):
        raise ValueError("la carga del gap request debe ser un objeto")
    return GapRequest.from_dict(raw_request)

def is_telemetry_unit(unit: SyncUnit) -> bool:
    """Indica si la carga declara telemetría."""
    return unit.payload.get("kind") == KIND_TELEMETRY_EVENTS

def is_ack_unit(unit: SyncUnit) -> bool:
    """Indica si la carga declara un ACK de aplicación."""
    return unit.payload.get("kind") == KIND_APPLICATION_ACK

def is_gap_request_unit(unit: SyncUnit) -> bool:
    """Indica si la carga declara un gap request."""
    return unit.payload.get("kind") == KIND_GAP_REQUEST

def gap_request_attempt_number(unit: SyncUnit) -> int:
    """Número de intento presente en la carga. Si falta la clave, es 1."""
    raw = unit.payload.get("attempt_number")
    if raw is None:
        return 1
    return int(raw)

def attempt_id_from_unit(unit: SyncUnit) -> str | None:
    """``attempt_id`` de la carga, o ``None`` si la clave no está."""
    raw = unit.payload.get("attempt_id")
    if raw is None:
        return None
    return str(raw)

def retry_telemetry_unit(event: TelemetryEvent, created_at_sim: float, attempt: int) -> SyncUnit:
    """Nueva SyncUnit del mismo evento para el intento siguiente.

    ``attempt`` es el número ya usado. La unidad nueva usa ``attempt + 1``.
    No detecta pérdidas ni programa el reenvío: solo codifica el intento
    que el llamador ya decidió.
    """
    attempt_number = attempt + 1
    return encode_telemetry_event(
        event,
        created_at_sim,
        attempt_id=attempt_id_for_group((event.event_id,), attempt_number),
        attempt_number=attempt_number,
    )

def canonical_dumps(payload: dict[str, object]) -> str:
    """JSON canónico de la carga, como texto ASCII.

    Las opciones son exactamente ``sort_keys=True``,
    ``separators=(",", ":")`` y ``ensure_ascii=True``. Cada objeto ordena
    sus claves. No hay espacios. Un carácter no ASCII se escribe como
    ``\\uXXXX``. Las listas y las tuplas pasan a arreglos, ``None`` pasa a
    ``null`` y un valor no serializable propaga ``TypeError``.

    El texto es ASCII, así que la cantidad de caracteres coincide con la
    longitud en bytes UTF-8. Esa longitud es ``payload_size_bytes``.
    """
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=True,
        sort_keys=True,
    )
