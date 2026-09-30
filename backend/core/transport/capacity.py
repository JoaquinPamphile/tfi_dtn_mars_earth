"""Capacidad transmisible de una carga, en tiempo lógico de simulación.

Relaciona el tamaño en bytes, la tasa en bits por segundo y el intervalo
disponible. No elige unidades, no las encola y no abre una transmisión.

``payload_size_bytes`` está en bytes y se recibe ya calculado.
``data_rate_bps`` está en bits por segundo.

La duración, en segundos, es ``(payload_size_bytes * 8) / data_rate_bps``.
El factor 8 pasa de bytes a bits. El cociente queda en ``float``, sin
``ceil``, ``floor`` ni otra cuantización.

Una carga entra en el intervalo si
``start_time_sim + duración <= end_time_sim``.
La comparación es exacta: no hay tolerancia.
``start_time_sim`` es el instante en que empezaría la transmisión y puede
ser posterior al inicio del contacto. El retardo de propagación no consume
tasa ni entra en la duración.

La duración es la de la carga completa. No representa un envío interrumpido
ni bytes restantes.

Los bytes consumidos antes de un corte son otra cuenta:
``floor(elapsed_sim * data_rate_bps / 8 + 0.5)``, recortada al tamaño de la
carga. No acortan la unidad ni definen una duración parcial reutilizable.

La capacidad nominal de un contacto, en bits, sigue siendo
``Contact.nominal_capacity_bits``. Este módulo no la recalcula.
"""

from math import floor


def transmission_seconds(payload_size_bytes: int, data_rate_bps: int) -> float:
    """Duración lógica de transmitir la carga completa, en segundos.
    ``payload_size_bytes`` se convierte a bits (``* 8``) y se divide por
    ``data_rate_bps``. El resultado es ``float``. No se redondea ni se trunca.
    """
    if payload_size_bytes <= 0:
        raise ValueError("payload_size_bytes debe ser mayor que 0")
    if data_rate_bps <= 0:
        raise ValueError("data_rate_bps debe ser mayor que 0")
    return (payload_size_bytes * 8) / data_rate_bps


def fits(
    payload_size_bytes: int,
    data_rate_bps: int,
    *,
    start_time_sim: float,
    end_time_sim: float,
) -> bool:
    """Indica si la carga completa termina a más tardar en ``end_time_sim``.
    El instante de inicio es ``start_time_sim``. La comparación es
    ``start_time_sim + transmission_seconds(...) <= end_time_sim``.
    Si ambos lados son iguales, la carga entra.
    """
    return (
        start_time_sim + transmission_seconds(payload_size_bytes, data_rate_bps)
        <= end_time_sim
    )


def round_half_up_non_negative(value: float) -> int:
    """Redondeo determinista ``floor(x + 0.5)`` para una cantidad no negativa.
    Es half-up: el empate ``n + 0.5`` sube. No es el redondeo del banquero.
    Un valor negativo se rechaza, porque una cuenta de bytes no puede serlo.
    """
    if value < 0:
        raise ValueError("no se puede redondear una cantidad negativa de bytes")
    return int(floor(value + 0.5))


def transmitted_before_interrupt_bytes(
    *,
    elapsed_sim: float,
    data_rate_bps: int,
    payload_size_bytes: int,
) -> int:
    """Bytes de carga ya consumidos de la capacidad del contacto al cortar.
    La cuenta es ``round_half_up(elapsed_sim * data_rate_bps / 8)``,
    recortada al intervalo ``[0, payload_size_bytes]``.
    ``elapsed_sim`` es solo tiempo de serialización. Un transcurso negativo
    cuenta como cero. El retardo de propagación no entra en la cuenta.
    """
    if payload_size_bytes < 0:
        raise ValueError("payload_size_bytes debe ser mayor o igual que 0")
    if data_rate_bps <= 0:
        raise ValueError("data_rate_bps debe ser mayor que 0")
    elapsed = max(0.0, elapsed_sim)
    raw = elapsed * data_rate_bps / 8.0
    rounded = round_half_up_non_negative(raw)
    return max(0, min(payload_size_bytes, rounded))
