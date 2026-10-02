from collections.abc import Callable
from copy import deepcopy
from enum import StrEnum
from typing import Any

from core.simulation.clock import SimulationClock
from core.simulation.scheduler import EventScheduler, ScheduledAction
from core.stopping.policy import StopPolicy, resolve_stop_policy
from core.trace.event import SimulationTraceEntry
from core.trace.level import TraceLevel, records_event_type
from core.trace.sink import MemoryTraceSink, TraceSink
from core.trace.types import SimulationEventType

EventHandler = Callable[[ScheduledAction], None]

# Tope defensivo de eventos consecutivos en el mismo instante.
# No limita la cantidad de pasos de una corrida.
ZERO_TIME_LOOP_THRESHOLD = 50_000

# ``emit_trace`` despacha handlers solo para estos tipos. No entran al
# scheduler. Así la observabilidad de una transmisión no depende de que
# el nivel de traza conserve el hecho.
_EMIT_TRACE_HANDLERS = frozenset(
    {
        SimulationEventType.TRANSMISSION_STARTED.value,
        SimulationEventType.TRANSMISSION_INTERRUPTED.value,
    }
)

# Después del horizonte, PROFILE_HORIZON_SETTLED solo ejecuta estos tipos.
# Cualquier otro tipo posterior se quita de la cola sin despacharlo.
_SETTLING_TYPES = frozenset(
    {
        SimulationEventType.TRANSMISSION_COMPLETED.value,
        SimulationEventType.ARRIVED_AT_RELAY.value,
        SimulationEventType.RELAY_QUEUED.value,
        SimulationEventType.ARRIVED_AT_EARTH_TRANSPORT.value,
        SimulationEventType.ARRIVED_AT_MARS_TRANSPORT.value,
        SimulationEventType.CONTACT_CLOSE.value,
        SimulationEventType.TRANSMISSION_INTERRUPTED.value,
        SimulationEventType.FAILURE_INJECTED.value,
    }
)


class SimulationStatus(StrEnum):
    """Estado del motor."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SimulationStateError(RuntimeError):
    """El motor está en un estado terminal y no acepta más trabajo."""

class SimulationError(RuntimeError):
    """Fallo defensivo del bucle de eventos discretos.
    No es una métrica científica. Conserva el instante, el tipo y el tamaño
    de la cola en el momento del fallo.
    """
    def __init__(
        self,
        message: str,
        *,
        simulation_time: float,
        event_type: str,
        entity_id: str | None,
        events_processed_at_timestamp: int,
        queue_size: int,
    ) -> None:
        super().__init__(message)
        self.simulation_time = simulation_time
        self.event_type = event_type
        self.entity_id = entity_id
        self.events_processed_at_timestamp = events_processed_at_timestamp
        self.queue_size = queue_size


class SimulationEngine:
    """Motor de eventos discretos. El tiempo es lógico y no se espera.
    Conecta el reloj, el scheduler, la traza y la política de parada.
    Despacha cada ``ScheduledAction`` a los handlers registrados para su
    ``event_type``. La tabla empieza vacía: este módulo no incorpora
    handlers de dominio.
    Procesar una acción puede registrar una entrada de traza. Esa entrada
    no es la acción: ``emit_trace`` también registra hechos en el instante
    actual, y ``TraceLevel`` puede no conservar el tipo. ``sequence_index``
    lo asigna el motor al construir la entrada, con el largo actual de la
    traza almacenada.
    """
    def __init__(
        self,
        trace_level: TraceLevel = TraceLevel.FULL,
        trace_sink: TraceSink | None = None,
    ) -> None:
        self._clock = SimulationClock()
        self._scheduler = EventScheduler()
        self._trace_sink: TraceSink = (
            trace_sink if trace_sink is not None else MemoryTraceSink()
        )
        self._trace_level = trace_level
        self._status = SimulationStatus.CREATED
        self._handlers: dict[str, list[EventHandler]] = {}
        self._after_action: list[EventHandler] = []
        self._actions_processed = 0
        self._next_submission_order = 0
        self._same_time: float | None = None
        self._same_time_count = 0

    @property
    def trace_level(self) -> TraceLevel:
        return self._trace_level

    @property
    def actions_processed(self) -> int:
        return self._actions_processed

    @property
    def clock(self) -> SimulationClock:
        return self._clock

    @property
    def now(self) -> float:
        return self._clock.now

    @property
    def status(self) -> SimulationStatus:
        return self._status

    @property
    def trace(self) -> tuple[SimulationTraceEntry, ...]:
        """Registros almacenados, en el orden de inserción."""
        return self._trace_sink.as_tuple()

    @property
    def queue_length(self) -> int:
        return len(self._scheduler)

    def peek_time(self) -> float | None:
        """Instante de la próxima acción, o ``None`` si el scheduler está vacío."""
        return self._scheduler.peek_time()

    def peek_action(self) -> ScheduledAction | None:
        """Próxima acción sin extraerla, o ``None`` si el scheduler está vacío."""
        return self._scheduler.peek()

    def has_scheduled(self, event_type: str) -> bool:
        """Indica si queda alguna acción de ese tipo en el scheduler."""
        return self._scheduler.has_event_type(event_type)

    def skip_next(self) -> ScheduledAction | None:
        """Quita la próxima acción sin ejecutarla, sin traza y sin mover el reloj."""
        self._ensure_not_terminal()
        return self._scheduler.pop_next()

    def annotate_last_trace(self, extra: dict[str, Any]) -> None:
        """Incorpora claves en los detalles del último registro almacenado."""
        self._trace_sink.annotate_last(extra)

    def allocate_submission_order(self) -> int:
        """Clave monótona para ordenar una SyncUnit en la cola de transporte.
        Empieza en 0 y aumenta en 1 con cada llamada. El contador es del
        motor, no de un enlace. No depende del identificador de la unidad.
        Una llamada ya consumida no se reutiliza, tampoco si quien llama
        rechaza después esa presentación.
        """
        value = self._next_submission_order
        self._next_submission_order += 1
        return value

    def schedule(
        self,
        time: float,
        event_type: str,
        payload: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> None:
        """Programa una acción en un instante futuro o igual al reloj actual.
        Un tiempo anterior al reloj actual se rechaza, también ``-inf``.
        Un tiempo no finito que no es anterior, y un ``event_type`` vacío,
        los rechaza el scheduler.
        Si el motor ya había completado la cola, vuelve a ``PAUSED``.
        """
        self._ensure_not_terminal()
        if time < self.now:
            raise ValueError("no se puede programar una acción en el pasado")
        self._scheduler.schedule(
            time=time,
            event_type=event_type,
            payload=payload,
            entity_id=entity_id,
        )
        if self._status is SimulationStatus.COMPLETED:
            self._status = SimulationStatus.PAUSED

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Agrega un handler para ese ``event_type``. El orden es el de registro."""
        self._handlers.setdefault(event_type, []).append(handler)

    def register_after_action(self, handler: EventHandler) -> None:
        """Agrega un callback que corre después de los handlers de la acción."""
        self._after_action.append(handler)

    def cancel(self, predicate: Callable[[ScheduledAction], bool]) -> int:
        """Quita las acciones futuras que cumplen el predicado. Devuelve cuántas."""
        self._ensure_not_terminal()
        return self._scheduler.cancel(predicate)

    def emit_trace(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        entity_id: str | None = None,
    ) -> SimulationTraceEntry:
        """Registra un hecho en el instante actual del reloj.
        No extrae nada del scheduler. ``details`` es una copia del payload.
        ``sequence_index`` es el largo de la traza almacenada en ese momento.
        Si el nivel no conserva el tipo, la entrada se devuelve y no se guarda,
        así que no consume un índice. No crea ni extrae una acción del
        scheduler. ``TRANSMISSION_STARTED`` y ``TRANSMISSION_INTERRUPTED``
        sí despachan sus handlers, con una acción en el instante actual,
        aunque el nivel no haya guardado la entrada. El resto de los tipos
        no despacha handlers.
        """
        if event_type.strip() == "":
            raise ValueError("event_type no debe estar vacío")
        entry = self._record_trace(event_type, payload, entity_id, self.now)
        if event_type in _EMIT_TRACE_HANDLERS:
            action = ScheduledAction(
                time=self.now,
                tie_breaker=-1,
                event_type=event_type,
                payload=entry.details,
                entity_id=entity_id,
            )
            for handler in list(self._handlers.get(event_type, ())):
                handler(action)
        return entry

    def step(self) -> SimulationTraceEntry | None:
        """Procesa la próxima acción y devuelve su entrada de traza.
        Con el scheduler vacío devuelve ``None`` y el estado pasa a
        ``COMPLETED``. El reloj no se mueve. No es un error.
        Si hay acción, el reloj avanza hasta su instante, se cuenta, se
        construye la entrada y se despachan los handlers. Un handler ausente
        no es un error: la acción igual queda procesada. Si un handler lanza,
        el estado pasa a ``FAILED`` y la excepción sigue su curso, sin envolver.
        """
        self._ensure_not_terminal()
        action = self._scheduler.pop_next()
        if action is None:
            self._status = SimulationStatus.COMPLETED
            return None
        try:
            self._status = SimulationStatus.RUNNING
            return self._process(action)
        except Exception:
            self._status = SimulationStatus.FAILED
            raise
        finally:
            if self._status is SimulationStatus.RUNNING:
                self._status = (
                    SimulationStatus.PAUSED
                    if not self._scheduler.is_empty()
                    else SimulationStatus.COMPLETED
                )

    def run_until(self, time: float) -> None:
        """Procesa las acciones con tiempo menor o igual que ``time``.
        Las posteriores quedan en el scheduler. Si ``time`` es posterior al
        reloj, el reloj avanza hasta ``time`` aunque no haya una acción ahí.
        Un ``time`` anterior al reloj se rechaza y no cambia el estado.
        """
        self._ensure_not_terminal()
        if time < self.now:
            raise ValueError(
                "el instante objetivo es anterior al tiempo actual de simulación"
            )
        try:
            self._status = SimulationStatus.RUNNING
            while True:
                peek = self._scheduler.peek_time()
                if peek is None or peek > time:
                    break
                action = self._scheduler.pop_next()
                if action is None:
                    break
                self._process(action)
            if time > self.now:
                self._clock.advance_to(time)
        except Exception:
            self._status = SimulationStatus.FAILED
            raise
        self._status = (
            SimulationStatus.PAUSED
            if not self._scheduler.is_empty()
            else SimulationStatus.COMPLETED
        )

    def run_until_idle(self) -> None:
        """Procesa hasta vaciar el scheduler. El reloj queda en la última acción."""
        self._ensure_not_terminal()
        try:
            self._status = SimulationStatus.RUNNING
            while not self._scheduler.is_empty():
                action = self._scheduler.pop_next()
                if action is None:
                    break
                self._process(action)
        except Exception:
            self._status = SimulationStatus.FAILED
            raise
        self._status = SimulationStatus.COMPLETED

    def run(
        self,
        policy: StopPolicy | None = None,
        horizon_seconds: float | None = None,
    ) -> int:
        """Aplica la política efectiva y devuelve cuántas acciones ejecutó.
        La política sale de ``resolve_stop_policy``. ``UNTIL_IDLE``, y también
        cualquier política con horizonte ``None``, vacían el scheduler.
        ``PROFILE_HORIZON`` ejecuta hasta el horizonte inclusive y deja el
        resto pendiente; el reloj avanza hasta ese horizonte si aún no llegó.
        ``PROFILE_HORIZON_SETTLED`` ejecuta hasta el horizonte inclusive y,
        después, solo los tipos de asentamiento. El resto posterior se
        descarta sin despacho, sin traza y sin mover el reloj por ese descarte.
        Lo descartado no entra en el conteo devuelto.
        """
        effective = resolve_stop_policy(policy, horizon_seconds)
        before = self._actions_processed
        if effective is StopPolicy.UNTIL_IDLE or horizon_seconds is None:
            self.run_until_idle()
            return self._actions_processed - before
        assert horizon_seconds is not None
        if effective is StopPolicy.PROFILE_HORIZON:
            self.run_until(horizon_seconds)
            return self._actions_processed - before
        self._run_until_settled(horizon_seconds)
        return self._actions_processed - before

    def pause(self) -> None:
        """Pasa a ``PAUSED``. En ``CREATED`` con la cola vacía no cambia nada."""
        self._ensure_not_terminal()
        if self._status is SimulationStatus.CREATED and self._scheduler.is_empty():
            return
        self._status = SimulationStatus.PAUSED

    def stop(self) -> None:
        """Pasa a ``STOPPED``. Si el estado ya es ``FAILED``, lo rechaza."""
        if self._status is SimulationStatus.FAILED:
            raise SimulationStateError("la simulación falló")
        self._status = SimulationStatus.STOPPED

    def _run_until_settled(self, horizon_seconds: float) -> None:
        while True:
            peek = self.peek_action()
            if peek is None:
                break
            if peek.time <= horizon_seconds:
                self.step()
                continue
            if _is_settling(peek):
                self.step()
                continue
            self.skip_next()

    def _process(self, action: ScheduledAction) -> SimulationTraceEntry:
        self._clock.advance_to(action.time)
        self._guard_zero_time_loop(action)
        self._actions_processed += 1
        entry = self._record_trace(
            action.event_type,
            action.payload,
            action.entity_id,
            action.time,
        )
        for handler in list(self._handlers.get(action.event_type, ())):
            handler(action)
        for observer in list(self._after_action):
            observer(action)
        return entry

    def _record_trace(
        self,
        event_type: str,
        payload: dict[str, Any] | None,
        entity_id: str | None,
        simulation_time: float,
    ) -> SimulationTraceEntry:
        details = deepcopy(payload) if payload is not None else {}
        entry = SimulationTraceEntry(
            simulation_time=simulation_time,
            sequence_index=len(self._trace_sink),
            event_type=event_type,
            entity_id=entity_id,
            details=details,
        )
        if records_event_type(self._trace_level, event_type):
            self._trace_sink.append(entry)
        return entry

    def _guard_zero_time_loop(self, action: ScheduledAction) -> None:
        if self._same_time is None or action.time != self._same_time:
            self._same_time = action.time
            self._same_time_count = 1
            return
        self._same_time_count += 1
        if self._same_time_count <= ZERO_TIME_LOOP_THRESHOLD:
            return
        raise SimulationError(
            "bucle de eventos en el mismo instante detectado en "
            f"t={action.time}: {self._same_time_count} eventos consecutivos "
            "sin avanzar el tiempo "
            f"(último tipo={action.event_type}, entity_id={action.entity_id}, "
            f"cola={len(self._scheduler)})",
            simulation_time=action.time,
            event_type=action.event_type,
            entity_id=action.entity_id,
            events_processed_at_timestamp=self._same_time_count,
            queue_size=len(self._scheduler),
        )

    def _ensure_not_terminal(self) -> None:
        if self._status in {SimulationStatus.STOPPED, SimulationStatus.FAILED}:
            raise SimulationStateError(
                f"la simulación no puede aceptar trabajo en estado {self._status}"
            )

def _is_settling(action: ScheduledAction) -> bool:
    return action.event_type in _SETTLING_TYPES
