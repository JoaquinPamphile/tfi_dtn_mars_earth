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

La capacidad nominal de un contacto, en bits, sigue siendo
``Contact.nominal_capacity_bits``. Este módulo no la recalcula.
"""

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
