"""Sonda de E1 para tests. No es el diseño oficial y no es evidencia."""

from __future__ import annotations

from experiments.campaign import CampaignSpec
from experiments.e1 import E1_MAX_EVENTS, _campaign

E1_PROBE_CAMPAIGN_ID = "e1-probe"

E1_PROBE_DESCRIPTION = (
    "Sonda de E1 para tests. Conserva los factores del diseño oficial y "
    "cambia solo el conteo de eventos. No es el diseño oficial y no es evidencia."
)


def build_e1_probe_campaign(*, max_events: int) -> CampaignSpec:
    """Misma estructura que E1 con otro conteo. No es el diseño oficial."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("max_events de la sonda debe ser un entero >= 1")
    if max_events == E1_MAX_EVENTS:
        raise ValueError("la sonda no usa el conteo oficial; el diseño es build_e1_campaign")
    return _campaign(
        campaign_id=E1_PROBE_CAMPAIGN_ID,
        description=E1_PROBE_DESCRIPTION,
        max_events=max_events,
    )
