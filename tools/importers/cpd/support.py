from __future__ import annotations
import json
import math
import struct
from typing import Any


class CpdSupportError(ValueError):
    """Bytes, JSON o magnitud no admisible para la cadena CPD."""


def decode_utf8(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CpdSupportError("el documento debe ser UTF-8") from exc


def loads_strict_json(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise CpdSupportError(f"JSON inválido: {exc.msg}") from exc


def loads_strict_utf8_json(raw: bytes) -> Any:
    return loads_strict_json(decode_utf8(raw))


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CpdSupportError(f"clave JSON duplicada: {key}")
        result[key] = value
    return result


def as_finite_float64(value: object) -> float:
    """Entero o float JSON finito representable exactamente en binary64."""
    if isinstance(value, bool) or isinstance(value, str):
        raise CpdSupportError("magnitud numérica con tipo inválido")
    if isinstance(value, int):
        try:
            as_float = float(value)
        except OverflowError as exc:
            raise CpdSupportError(
                "entero no representable exactamente en binary64"
            ) from exc
        if not math.isfinite(as_float) or int(as_float) != value:
            raise CpdSupportError(
                "entero no representable exactamente en binary64"
            )
        return as_float
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CpdSupportError("magnitud numérica no finita")
        return value
    raise CpdSupportError("magnitud numérica con tipo inválido")


def as_json_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CpdSupportError("debe ser entero JSON")
    return value


def as_positive_json_int(value: object) -> int:
    if isinstance(value, bool) or isinstance(value, float) or isinstance(value, str):
        raise CpdSupportError("debe ser entero JSON positivo")
    if not isinstance(value, int):
        raise CpdSupportError("debe ser entero JSON positivo")
    if value <= 0:
        raise CpdSupportError("debe ser entero JSON positivo")
    return value


def normalize_signed_zero(value: float) -> float:
    """``-0.0`` → ``+0.0`` para encoding de identidad; no altera otros valores."""
    if value == 0.0:
        return 0.0
    return value


def float64_hex(value: object) -> str:
    number = normalize_signed_zero(as_finite_float64(value))
    return struct.pack(">d", number).hex()
