"""Cola de un enlace dirigido, ordenada para elegir la próxima SyncUnit.

El orden es ``(created_at_sim, submission_order)``. El identificador de la
unidad no participa. La prioridad de un ``TelemetryEvent`` tampoco: no es
un campo de esta cola.

Entre las unidades que caben completas antes del fin del contacto activo,
la siguiente es la mínima según ese orden. Una unidad que no cabe ahora no
puede caber más tarde en el mismo contacto, porque el tiempo restante solo
disminuye: queda bloqueada hasta el cierre, y vuelve a la cola sin
descartarse.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from heapq import heappop, heappush

from core.sync.unit import SyncUnit


def queue_order(unit: SyncUnit) -> tuple[float, int]:
    """Orden determinista: ``created_at_sim`` y después ``submission_order``."""
    return (unit.created_at_sim, unit.submission_order)


@dataclass
class OrderedFitQueue:
    """Cola de enlace que elige la mínima unidad que todavía cabe.

    El bloqueo es por contacto. ``release_contact`` reintegra lo bloqueado
    para una ventana futura. No fragmenta ni reemplaza la carga.
    """

    _units: dict[str, SyncUnit] = field(default_factory=dict)
    _queued_ids: set[str] = field(default_factory=set)
    _heap: list[tuple[float, int, int, str]] = field(default_factory=list)
    _live_seq: dict[str, int] = field(default_factory=dict)
    _seq: int = 0
    _blocked: dict[str, SyncUnit] = field(default_factory=dict)
    _blocked_contact_id: str | None = None

    def __len__(self) -> int:
        return len(self._queued_ids)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, SyncUnit):
            return item.sync_unit_id in self._queued_ids
        if isinstance(item, str):
            return item in self._queued_ids
        return False

    def contains(self, sync_unit_id: str) -> bool:
        return sync_unit_id in self._queued_ids

    def add(self, unit: SyncUnit) -> None:
        uid = unit.sync_unit_id
        if uid in self._queued_ids:
            raise ValueError(f"la SyncUnit ya está encolada: {uid}")
        self._units[uid] = unit
        self._queued_ids.add(uid)
        self._push(unit)
        self._maybe_compact()

    def withdraw(self, sync_unit_id: str) -> bool:
        """Quita una unidad que espera. La entrada del heap queda obsoleta."""
        if sync_unit_id not in self._queued_ids:
            return False
        self._queued_ids.discard(sync_unit_id)
        self._units.pop(sync_unit_id, None)
        self._blocked.pop(sync_unit_id, None)
        self._live_seq.pop(sync_unit_id, None)
        return True

    def pop_next_fitting(
        self,
        *,
        contact_id: str,
        fits: Callable[[SyncUnit], bool],
    ) -> SyncUnit | None:
        """Devuelve la unidad de menor orden que cabe, o ``None``.

        Las que no caben pasan al conjunto bloqueado de este contacto y no
        se vuelven a inspeccionar hasta ``release_contact``.
        """
        self._activate_contact(contact_id)
        while self._heap:
            _created, _order, seq, uid = heappop(self._heap)
            if self._live_seq.get(uid) != seq or uid not in self._queued_ids:
                continue
            if uid in self._blocked:
                continue
            unit = self._units[uid]
            if fits(unit):
                self._queued_ids.remove(uid)
                self._units.pop(uid)
                self._live_seq.pop(uid, None)
                return unit
            self._blocked[uid] = unit
            self._live_seq.pop(uid, None)
        return None

    def release_contact(self) -> None:
        """Devuelve a la cola lo bloqueado por el contacto que termina."""
        self._reintegrate_blocked()
        self._blocked_contact_id = None

    def iter_snapshot(self) -> tuple[SyncUnit, ...]:
        """Unidades encoladas, incluidas las bloqueadas en el contacto actual."""
        return tuple(self._units[uid] for uid in self._queued_ids)

    def blocked_ids(self) -> frozenset[str]:
        return frozenset(self._blocked)

    def _activate_contact(self, contact_id: str) -> None:
        if self._blocked_contact_id == contact_id:
            return
        self._reintegrate_blocked()
        self._blocked_contact_id = contact_id

    def _reintegrate_blocked(self) -> None:
        if not self._blocked:
            return
        blocked = list(self._blocked.values())
        self._blocked.clear()
        for unit in blocked:
            if unit.sync_unit_id in self._queued_ids:
                self._push(unit)

    def _push(self, unit: SyncUnit) -> None:
        self._seq += 1
        seq = self._seq
        uid = unit.sync_unit_id
        self._live_seq[uid] = seq
        created, order = queue_order(unit)
        heappush(self._heap, (created, order, seq, uid))

    def _maybe_compact(self) -> None:
        live_heap = len(self._queued_ids) - len(self._blocked)
        if live_heap < 1:
            live_heap = 1
        if len(self._heap) <= max(64, 4 * live_heap):
            return
        self._rebuild_heap()

    def _rebuild_heap(self) -> None:
        self._heap.clear()
        self._live_seq.clear()
        for uid, unit in self._units.items():
            if uid in self._blocked:
                continue
            self._push(unit)
