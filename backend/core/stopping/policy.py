from enum import StrEnum

class StopPolicy(StrEnum):
    """Cuándo una corrida científica deja de procesar acciones del scheduler.
    ``PROFILE_HORIZON``
        Procesa toda acción con tiempo menor o igual que el horizonte
        declarado y se detiene. El trabajo en vuelo programado después del
        horizonte queda sin procesar.
    ``PROFILE_HORIZON_SETTLED``
        Preferida cuando hay un horizonte de perfil:
        1. Procesa la carga y la actividad de contactos hasta el horizonte.
        2. Después del horizonte, procesa solo eventos ya programados de
           forma causal: ``TRANSMISSION_COMPLETED``, ``ARRIVED_AT_RELAY``,
           ``RELAY_QUEUED``, ``ARRIVED_AT_EARTH_TRANSPORT``,
           ``ARRIVED_AT_MARS_TRANSPORT``, ``CONTACT_CLOSE``,
           ``TRANSMISSION_INTERRUPTED`` y ``FAILURE_INJECTED``.
        3. Después del horizonte no procesa ``CONTACT_OPEN``, generación de
           telemetría, ``ACK_TIMEOUT`` ni ``RETRY_EVALUATION``. Esos eventos
           abrirían envíos nuevos o esperas de ACK fuera de la ventana útil.
        4. El backlog que queda después del asentamiento se informa. La falta
           de convergencia no es una condición de parada y no se oculta.
    ``UNTIL_IDLE``
        Procesa hasta vaciar el scheduler, incluidos los timeout de ACK
        futuros.
    El horizonte no es un campo de esta política. Cuando el escenario lo
    declara, es un float estrictamente positivo. No hay periodo de drenaje
    aparte, ni un máximo de pasos.
    Regla de evaluación, todavía no ejecutada: si el horizonte es ``None``,
    se procesa hasta vaciar el scheduler aunque la política sea otra. Si la
    política es ``UNTIL_IDLE``, también se procesa hasta vaciarlo. Recorrer
    el scheduler queda para el motor.
    """
    PROFILE_HORIZON = "PROFILE_HORIZON"
    PROFILE_HORIZON_SETTLED = "PROFILE_HORIZON_SETTLED"
    UNTIL_IDLE = "UNTIL_IDLE"

def resolve_stop_policy(
    explicit: StopPolicy | None,
    horizon_seconds: float | None,
) -> StopPolicy:
    """Elige la política efectiva antes de evaluar el scheduler.
    Una política explícita se conserva. Si no hay política y el horizonte
    no es ``None``, la política es ``PROFILE_HORIZON_SETTLED``. Si faltan
    las dos, la política es ``UNTIL_IDLE``.
    No rechaza un horizonte menor o igual que cero ni un valor no finito:
    esa cota pertenece al escenario que declara el horizonte. No recorre
    el scheduler.
    """
    if explicit is not None:
        return explicit
    if horizon_seconds is not None:
        return StopPolicy.PROFILE_HORIZON_SETTLED
    return StopPolicy.UNTIL_IDLE
