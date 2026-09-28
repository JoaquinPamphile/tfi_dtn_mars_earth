from math import floor, inf, nextafter
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.domain.priority import TelemetryPriority


class TelemetryGenerationProfile(BaseModel):
    """Generación continua y determinista de telemetría, gobernada por el tiempo de simulación.

    El evento N se programa en ``start_time_sim + N / rate_events_per_second``.
    Esa fórmula se usa para cada N; las marcas de tiempo no se derivan del
    instante previamente generado, así el error de punto flotante no se acumula.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    priority: TelemetryPriority
    rate_events_per_second: float = Field(gt=0)
    start_time_sim: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    max_events: int | None = Field(default=None, gt=0)
    enabled: bool = True

    @field_validator("profile_id", "event_type")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @model_validator(mode="after")
    def require_termination(self) -> "TelemetryGenerationProfile":
        if self.duration_seconds is None and self.max_events is None:
            raise ValueError(
                "se requiere al menos uno de duration_seconds o max_events"
            )
        return self

    def event_time(self, n: int) -> float:
        """Tiempo de simulación del índice de generación N: inicio + N / tasa."""
        if n < 0:
            raise ValueError("el índice de generación debe ser >= 0")
        return self.start_time_sim + n / self.rate_events_per_second

    def allows_event_time(self, event_time: float) -> bool:
        """Verdadero cuando start_time_sim <= event_time < start_time_sim + duration.

        Si se omite duration_seconds, solo aplica la cota de inicio; quien
        llama también debe respetar max_events.
        """
        if event_time < self.start_time_sim:
            return False
        if self.duration_seconds is not None:
            return event_time < self.start_time_sim + self.duration_seconds
        return True

    def scheduled_end_at_sim(self) -> float | None:
        """Primer tiempo de simulación en el que ya no se generarán más eventos."""
        ends: list[float] = []
        if self.duration_seconds is not None:
            ends.append(self.start_time_sim + self.duration_seconds)
        if self.max_events is not None:
            ends.append(
                self.start_time_sim + self.max_events / self.rate_events_per_second
            )
        return min(ends) if ends else None

    def expected_event_count(self) -> int:
        """Conteo finito implicado por la duración y/o max_events. Solo observabilidad.

        El evento ``n`` existe si y solo si ``n / rate < duration`` (de forma
        equivalente, ``n < duration * rate`` en los reales). El conteo debe
        coincidir con el generador, que usa ``allows_event_time`` y no un
        épsilon absoluto sobre el producto en punto flotante.
        """
        counts: list[int] = []
        if self.duration_seconds is not None:
            counts.append(
                duration_limited_event_count(
                    self.duration_seconds, self.rate_events_per_second
                )
            )
        if self.max_events is not None:
            counts.append(self.max_events)
        return min(counts) if counts else 0

    def last_generation_at_sim(self) -> float | None:
        """Instante del último evento que este perfil emitirá, si hay alguno."""
        count = self.expected_event_count()
        if count <= 0:
            return None
        return self.event_time(count - 1)


def duration_limited_event_count(
    duration_seconds: float, rate_events_per_second: float
) -> int:
    """Cuenta los enteros ``n >= 0`` que cumplen ``n / rate < duration``.

    Usa ``math.nextafter`` sobre el producto de valor real y luego camina
    hasta el mismo predicado de tiempo exclusivo que aplica el generador.
    No se usa un épsilon absoluto como ``1e-15``: en límites enteros grandes
    ese épsilon es menor que una unidad en el último lugar.
    """

    if duration_seconds <= 0 or rate_events_per_second <= 0:
        return 0
    limit = duration_seconds * rate_events_per_second
    exclusive = nextafter(limit, -inf)
    if exclusive < 0:
        candidate = 0
    else:
        candidate = floor(exclusive) + 1
    while candidate > 0 and not (
        (candidate - 1) / rate_events_per_second < duration_seconds
    ):
        candidate -= 1
    while candidate / rate_events_per_second < duration_seconds:
        candidate += 1
    return candidate
