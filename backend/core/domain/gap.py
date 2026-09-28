"""Gaps internos de secuencia observados por el receptor."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.domain.identity import make_gap_request_id


class MissingSequenceRange(BaseModel):
    """Intervalo inclusivo y contiguo de números de secuencia faltantes de una fuente."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    start_sequence: int = Field(ge=0)
    end_sequence: int = Field(ge=0)

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> Self:
        if self.end_sequence < self.start_sequence:
            raise ValueError("end_sequence debe ser >= start_sequence")
        return self

    @property
    def count(self) -> int:
        return self.end_sequence - self.start_sequence + 1

def coerce_missing_range(value: object) -> MissingSequenceRange:
    if isinstance(value, MissingSequenceRange):
        return value
    if isinstance(value, bool):
        raise TypeError("un booleano no es un rango de secuencia")
    if isinstance(value, int):
        return MissingSequenceRange(start_sequence=value, end_sequence=value)
    if isinstance(value, dict):
        return MissingSequenceRange(
            start_sequence=int(value["start_sequence"]),  # type: ignore[arg-type]
            end_sequence=int(value["end_sequence"]),  # type: ignore[arg-type]
        )
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return MissingSequenceRange(
            start_sequence=int(value[0]),
            end_sequence=int(value[1]),
        )
    raise TypeError("el valor no es un rango de secuencia faltante")

def normalize_missing_ranges(
    values: Iterable[object],
) -> tuple[MissingSequenceRange, ...]:
    """Ordena, deduplica y fusiona rangos solapados o adyacentes."""
    ordered = sorted(
        (coerce_missing_range(item) for item in values),
        key=lambda item: (item.start_sequence, item.end_sequence),
    )
    if not ordered:
        return ()
    merged: list[MissingSequenceRange] = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start_sequence <= last.end_sequence + 1:
            merged[-1] = MissingSequenceRange(
                start_sequence=last.start_sequence,
                end_sequence=max(last.end_sequence, current.end_sequence),
            )
            continue
        merged.append(current)
    return tuple(merged)

def ranges_from_sequences(sequences: Iterable[int]) -> tuple[MissingSequenceRange, ...]:
    """Agrupa secuencias discretas en rangos inclusivos canónicos."""
    return normalize_missing_ranges(sequences)

def subtract_missing_ranges(
    have: Iterable[object],
    covered: Iterable[object],
) -> tuple[MissingSequenceRange, ...]:
    """Devuelve las porciones de ``have`` que ``covered`` no cubre."""

    remaining = list(normalize_missing_ranges(have))
    for mask in normalize_missing_ranges(covered):
        next_remaining: list[MissingSequenceRange] = []
        for item in remaining:
            if mask.end_sequence < item.start_sequence or mask.start_sequence > item.end_sequence:
                next_remaining.append(item)
                continue
            if item.start_sequence < mask.start_sequence:
                next_remaining.append(
                    MissingSequenceRange(
                        start_sequence=item.start_sequence,
                        end_sequence=mask.start_sequence - 1,
                    )
                )
            if item.end_sequence > mask.end_sequence:
                next_remaining.append(
                    MissingSequenceRange(
                        start_sequence=mask.end_sequence + 1,
                        end_sequence=item.end_sequence,
                    )
                )
        remaining = next_remaining
    return tuple(remaining)

def intersect_missing_ranges(
    left: Iterable[object],
    right: Iterable[object],
) -> tuple[MissingSequenceRange, ...]:
    """Solapamiento inclusivo de dos conjuntos canónicos de rangos."""

    overlap: list[MissingSequenceRange] = []
    right_ranges = normalize_missing_ranges(right)
    for item in normalize_missing_ranges(left):
        for other in right_ranges:
            start = max(item.start_sequence, other.start_sequence)
            end = min(item.end_sequence, other.end_sequence)
            if start <= end:
                overlap.append(MissingSequenceRange(start_sequence=start, end_sequence=end))
    return normalize_missing_ranges(overlap)


class GapRequest(BaseModel):
    """Tierra observó gaps internos de secuencia y pide una reparación selectiva.
    Es un pedido de reparación de **nivel de aplicación**: Tierra persistió
    algunas secuencias, detectó huecos por debajo de la secuencia observada
    más alta de una fuente y pide a Marte que reenvíe los ``TelemetryEvent``
    originales e inmutables de esos rangos.
    La reparación receiver-driven cubre solo los gaps internos observados.
    No infiere secuencias posteriores al valor persistido más alto.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    request_id: str = ""
    target_source_id: str
    missing_ranges: tuple[MissingSequenceRange, ...]
    created_at_sim: float = Field(ge=0)
    requesting_node_id: str = "EARTH"

    @field_validator("target_source_id", "requesting_node_id")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("missing_ranges", mode="before")
    @classmethod
    def coerce_ranges(cls, value: object) -> tuple[MissingSequenceRange, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("missing_ranges debe ser una secuencia")
        return normalize_missing_ranges(value)

    @model_validator(mode="after")
    def canonicalize(self) -> Self:
        normalized = normalize_missing_ranges(self.missing_ranges)
        if not normalized:
            raise ValueError("missing_ranges no debe estar vacío")
        if normalized != self.missing_ranges:
            object.__setattr__(self, "missing_ranges", normalized)
        if self.request_id.strip() == "":
            object.__setattr__(
                self,
                "request_id",
                make_gap_request_id(
                    target_source_id=self.target_source_id,
                    missing_ranges=normalized,
                    created_at_sim=self.created_at_sim,
                    requesting_node_id=self.requesting_node_id,
                ),
            )
        return self

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "target_source_id": self.target_source_id,
            "missing_ranges": [
                {
                    "start_sequence": item.start_sequence,
                    "end_sequence": item.end_sequence,
                }
                for item in self.missing_ranges
            ],
            "created_at_sim": self.created_at_sim,
            "requesting_node_id": self.requesting_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        return cls(
            request_id=str(data.get("request_id") or ""),
            target_source_id=str(data["target_source_id"]),
            missing_ranges=tuple(data.get("missing_ranges") or ()),  # type: ignore[arg-type]
            created_at_sim=float(data["created_at_sim"]),  # type: ignore[arg-type]
            requesting_node_id=str(data.get("requesting_node_id") or "EARTH"),
        )
