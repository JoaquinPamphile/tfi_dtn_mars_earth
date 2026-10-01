"""Rangos de GapRequest todavía abiertos.

La ingesta normal de Tierra no registra ni emite tráfico de GapRequest.
Este registro lo consulta solo un ``ReceiverDrivenRecoveryController``.

La cobertura es por rangos: un pedido abierto de ``[2..4]`` cubre todo el
intervalo. Una observación posterior del mismo hueco no emite otro pedido
solapado.

Cierre parcial: si Tierra pidió ``[2..4]`` y después persiste 2 y 4, la
cobertura que queda es ``[3..3]``. El pedido original no queda satisfecho
por completo. No se emite un pedido nuevo por ese resto mientras siga
cubierto por un rango abierto.

Un hueco posterior que no solapa la cobertura abierta puede crear un
segundo GapRequest lógico. Los huecos que solapan siguen cubiertos por el
pedido original.

Un intento de transporte perdido se reintenta sin registrar un segundo
pedido lógico. La cobertura abierta sigue suprimiendo pedidos solapados
mientras el original no se resuelva.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from core.domain.gap import (
    GapRequest,
    MissingSequenceRange,
    intersect_missing_ranges,
    normalize_missing_ranges,
    subtract_missing_ranges,
)


@dataclass
class _OpenRequest:
    request: GapRequest
    remaining: tuple[MissingSequenceRange, ...]


class GapRequestTracker:
    """Rangos de GapRequest ya emitidos que esperan reparación, por fuente."""

    def __init__(self) -> None:
        self._open: dict[str, list[_OpenRequest]] = {}

    def outstanding_ranges_for_source(
        self, source_id: str
    ) -> tuple[MissingSequenceRange, ...]:
        ranges: list[MissingSequenceRange] = []
        for item in self._open.get(source_id, ()):
            ranges.extend(item.remaining)
        return normalize_missing_ranges(ranges)

    def outstanding_requests_for_source(self, source_id: str) -> tuple[GapRequest, ...]:
        return tuple(item.request for item in self._open.get(source_id, ()))

    def uncovered_ranges(
        self,
        source_id: str,
        current_gaps: Sequence[object],
    ) -> tuple[MissingSequenceRange, ...]:
        return subtract_missing_ranges(
            current_gaps, self.outstanding_ranges_for_source(source_id)
        )

    def record(self, request: GapRequest) -> None:
        self._open.setdefault(request.target_source_id, []).append(
            _OpenRequest(request=request, remaining=request.missing_ranges)
        )

    def trim_to_current_gaps(
        self,
        source_id: str,
        current_gaps: Sequence[object],
    ) -> tuple[str, ...]:
        """Intersecta la cobertura abierta con los huecos vigentes de Tierra.

        Un pedido sin resto se cierra. Uno reparado en parte conserva solo
        la intersección que sigue faltando. Devuelve los ``request_id`` que
        quedaron vacíos, es decir, satisfechos por completo.
        """

        current = tuple(current_gaps)
        still_open: list[_OpenRequest] = []
        closed_ids: list[str] = []
        for item in self._open.get(source_id, ()):
            leftover = intersect_missing_ranges(item.remaining, current)
            if leftover:
                still_open.append(
                    _OpenRequest(request=item.request, remaining=leftover)
                )
            else:
                closed_ids.append(item.request.request_id)
        if still_open:
            self._open[source_id] = still_open
        else:
            self._open.pop(source_id, None)
        return tuple(closed_ids)

    def clear(self) -> None:
        self._open.clear()
