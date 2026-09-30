"""Observación de secuencias y detección de huecos internos.

No construye ni envía un ``GapRequest``. No reintenta ni aplica un timeout.
"""

from core.gap.detection import missing_sequence_numbers, missing_sequence_ranges
from core.gap.index import EarthGapRangeStore, IncrementalGapIndex

__all__ = [
    "EarthGapRangeStore",
    "IncrementalGapIndex",
    "missing_sequence_numbers",
    "missing_sequence_ranges",
]
