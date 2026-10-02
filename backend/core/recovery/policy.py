"""Política explícita de recuperación de aplicación.

Los tres modos son excluyentes. No hay un modo que encienda las dos.
"""

from enum import StrEnum


class RecoveryPolicy(StrEnum):
    """Qué mecanismos de recuperación existen en una corrida.

    ``NONE`` no programa timeout de ACK ni crea GapRequest.
    ``SENDER_DRIVEN`` reintenta por timeout de ACK y no pide huecos.
    ``RECEIVER_DRIVEN`` pide los huecos que Tierra observa y no
    reintenta por timeout de ACK.
    """

    NONE = "none"
    SENDER_DRIVEN = "sender-driven"
    RECEIVER_DRIVEN = "receiver-driven"

    @property
    def sender_driven_enabled(self) -> bool:
        """El emisor programa ``ACK_TIMEOUT`` y puede crear un retry."""
        return self is RecoveryPolicy.SENDER_DRIVEN

    @property
    def receiver_driven_enabled(self) -> bool:
        """Tierra puede crear un GapRequest y Marte puede reparar."""
        return self is RecoveryPolicy.RECEIVER_DRIVEN

    def metrics_name(self) -> str | None:
        """Nombre que las métricas ya usan, o ``None`` si no hay política."""
        if self is RecoveryPolicy.SENDER_DRIVEN:
            return "SENDER_DRIVEN"
        if self is RecoveryPolicy.RECEIVER_DRIVEN:
            return "RECEIVER_DRIVEN"
        return None
