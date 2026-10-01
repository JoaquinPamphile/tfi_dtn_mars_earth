"""Entrega, confirmación, frescura y convergencia de una corrida.

Persistir en Tierra no es confirmar en Marte. ``completeness`` usa los
eventos únicos de Tierra. ``confirmation_ratio`` usa los confirmados en
Marte. El backlog sigue siendo ``generated - confirmed``.

Los cocientes viven en ``[0, 1]``. Si no hay eventos generados, el
cociente es ``None``. Un instante que no ocurrió también es ``None``.
No se sustituye por 0.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.metrics.percentiles import inclusive_percentile

STATE_COMPOSITION_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class FreshnessSample:
    """Un evento único ya persistido en Tierra.

    La frescura es la edad al persistir: ``earth_persisted_at_sim -
    generated_at_sim``. No es la edad al confirmar ni la edad de la vista
    en el instante final.
    """

    generated_at_sim: float
    earth_persisted_at_sim: float

    @property
    def freshness_seconds(self) -> float:
        return self.earth_persisted_at_sim - self.generated_at_sim


@dataclass(frozen=True, slots=True)
class FreshnessDistribution:
    """Distribución de la frescura de los eventos únicos persistidos.

    Con cero observaciones todos los estadísticos son ``None``. Con una
    sola, mínimo, p50, p95, máximo y media coinciden con ese valor.
    """

    count: int
    min_seconds: float | None
    p50_seconds: float | None
    p95_seconds: float | None
    max_seconds: float | None
    mean_seconds: float | None


@dataclass(frozen=True, slots=True)
class ConvergenceMetrics:
    """Convergencia de aplicación, distinta del fin del escenario.

    ``reference_at_sim`` es el último instante en que se generó telemetría
    de la carga ya cerrada. ``converged_at_sim`` es la confirmación en
    Marte que deja backlog y huecos en cero después de esa referencia.
    ``time_to_convergence_seconds`` es la diferencia. Si la corrida no
    converge, los dos últimos quedan en ``None``.
    """

    reference_at_sim: float | None
    converged_at_sim: float | None
    time_to_convergence_seconds: float | None


def completeness_ratio(generated: int, earth_persisted_unique: int) -> float | None:
    """``earth_persisted_unique / generated``, o ``None`` si no hay generados."""
    if generated == 0:
        return None
    return earth_persisted_unique / generated


def confirmation_ratio(confirmed: int, generated: int) -> float | None:
    """``confirmed / generated``, o ``None`` si no hay generados."""
    if generated == 0:
        return None
    return confirmed / generated


def backlog_events(generated: int, confirmed: int) -> int:
    """Trabajo todavía no confirmado en Marte: ``generated - confirmed``."""
    return generated - confirmed


def not_persisted_on_earth(generated: int, earth_persisted_unique: int) -> int:
    """Generados que Tierra todavía no persistió."""
    return generated - earth_persisted_unique


def persisted_on_earth_but_unconfirmed(earth_persisted_unique: int, confirmed: int) -> int:
    """Persistidos en Tierra cuyo ACK todavía no confirmó Marte."""
    return earth_persisted_unique - confirmed


def application_state_ratios(
    generated: int, earth_persisted_unique: int, confirmed: int
) -> dict[str, float | None]:
    """Tres fracciones excluyentes de los eventos generados.

    Con generados mayores que cero suman 1. Sin generados, las tres son
    ``None``. ``confirmation_ratio`` y ``confirmed_ratio`` son el mismo
    cociente.
    """
    confirmed_frac = confirmation_ratio(confirmed, generated)
    return {
        "confirmation_ratio": confirmed_frac,
        "confirmed_ratio": confirmed_frac,
        "persisted_unconfirmed_ratio": _safe_ratio(
            earth_persisted_unique - confirmed, generated
        ),
        "not_persisted_ratio": _safe_ratio(generated - earth_persisted_unique, generated),
    }


def view_age_seconds(
    *, time_sim: float, max_earth_generated_at_sim: float | None
) -> float | None:
    """Edad de la telemetría más nueva visible en Tierra.

    Es ``time_sim - max(generated_at_sim)`` de lo ya persistido. No es
    frescura. Sin telemetría en Tierra es ``None``.
    """
    if max_earth_generated_at_sim is None:
        return None
    return time_sim - max_earth_generated_at_sim


def live_converged(*, generated: int, backlog: int, gaps_count: int) -> bool:
    """Verdadero solo si hay carga, backlog cero y ningún hueco interno."""
    return generated > 0 and backlog == 0 and gaps_count == 0


def convergence_reference_at_sim(
    *,
    generated: int,
    max_generated_at_sim: float | None,
    future_telemetry_generation_scheduled: bool,
    continuous_generation_active: bool,
) -> float | None:
    """Instante después del cual no se espera más telemetría de la carga.

    Es el máximo ``generated_at_sim`` ya ocurrido. Queda en ``None`` si
    no se generó nada, si la generación continua sigue activa o si todavía
    hay una generación futura programada. No usa el fin teórico del perfil
    cuando el último evento ocurrió antes.
    """
    if generated == 0:
        return None
    if continuous_generation_active or future_telemetry_generation_scheduled:
        return None
    return max_generated_at_sim


def experimental_converged_at_sim(
    *,
    reference_at_sim: float | None,
    time_sim: float,
    last_confirmed_at_sim: float | None,
    generated: int,
    backlog: int,
    gaps_count: int,
) -> float | None:
    """Primera confirmación en Marte que cierra la carga ya generada.

    Exige referencia, backlog cero y huecos cero. El instante es el de
    la última confirmación, no el fin del escenario ni un cierre de
    contacto posterior. Si no converge, es ``None``.
    """
    if reference_at_sim is None:
        return None
    if not (generated > 0 and backlog == 0 and gaps_count == 0):
        return None
    confirmed_at = last_confirmed_at_sim if last_confirmed_at_sim is not None else time_sim
    return max(reference_at_sim, confirmed_at)


def time_to_convergence_seconds(
    converged_at_sim: float | None, reference_at_sim: float | None
) -> float | None:
    """``converged_at_sim - reference_at_sim``, o ``None`` si falta uno."""
    if converged_at_sim is None or reference_at_sim is None:
        return None
    return converged_at_sim - reference_at_sim


def scenario_completed_at_sim(*, engine_status: str, time_sim: float) -> float | None:
    """Reloj al quedar el scheduler vacío. No es el tiempo de convergencia."""
    if engine_status == "COMPLETED":
        return time_sim
    return None


def freshness_distribution(samples: tuple[FreshnessSample, ...]) -> FreshnessDistribution:
    """Estadísticos de la frescura. Cero muestras dejan todo en ``None``."""
    values = [sample.freshness_seconds for sample in samples]
    count = len(values)
    if count == 0:
        return FreshnessDistribution(
            count=0,
            min_seconds=None,
            p50_seconds=None,
            p95_seconds=None,
            max_seconds=None,
            mean_seconds=None,
        )
    return FreshnessDistribution(
        count=count,
        min_seconds=min(values),
        p50_seconds=inclusive_percentile(values, 50),
        p95_seconds=inclusive_percentile(values, 95),
        max_seconds=max(values),
        mean_seconds=sum(values) / count,
    )


def freshness_coverage(sample_count: int, generated: int) -> float | None:
    """``sample_count / generated``, o ``None`` si no hay generados.

    No rellena los percentiles de los eventos que no llegaron a Tierra.
    """
    if generated == 0:
        return None
    return sample_count / generated


def _safe_ratio(numerator: int, generated: int) -> float | None:
    if generated == 0:
        return None
    return numerator / generated
