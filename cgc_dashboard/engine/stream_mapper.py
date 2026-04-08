"""
Stream aggregation helpers — AS1 C3-Analyser mode, simple stream mass flows,
and scale-ratio calculation.

All formulas from CGC_Generic_Engine_v3.xlsx CALCULATIONS cells D30–D86.
"""

from __future__ import annotations
from typing import Dict
from cgc_dashboard.engine.constants import COMPONENTS


def as1_analyser(feed_tph: float, bottom_tph: float,
                 c3_pct: float) -> Dict[str, float]:
    """
    AS1 in C3-Analyser mode (D30–D44).

    Parameters
    ----------
    feed_tph   : Feed flow to upstream unit [t/h]
    bottom_tph : Bottom/product flow [t/h]
    c3_pct     : C3 content from analyser [mol%]

    Returns
    -------
    dict with keys: 'flow' (kg/h), 'mw', and component masses (kg/h).
    """
    flow = (feed_tph - bottom_tph) * 1000.0  # kg/h  (D30)

    # Weighted MW  (D31) — Excel uses pre-calculated blend constants 42.87 / 29.28
    # Formula: (C3_pct * 42.87 + (100 - C3_pct) * 29.28) / 100
    mw = (c3_pct * 42.87 + (100.0 - c3_pct) * 29.28) / 100.0
    molar = flow / mw  # kmol/h  (D32)

    c3_frac = c3_pct / 100.0
    non_c3_frac = (100.0 - c3_pct) / 100.0

    masses = {c: 0.0 for c in COMPONENTS}
    masses["C3H6"] = molar * 0.61 * c3_frac * 42      # D33
    masses["C3H8"] = molar * 0.39 * c3_frac * 44      # D34
    masses["C2H6"] = molar * 0.61 * non_c3_frac * 30  # D35
    masses["C2H4"] = molar * 0.39 * non_c3_frac * 28  # D36

    return {"flow": flow, "mw": mw, "molar": molar, "masses": masses}


def as1_direct(direct_flow: float,
               mass_fracs: Dict[str, float]) -> Dict[str, float]:
    """AS1 in direct mass-fraction mode."""
    masses = {c: direct_flow * mass_fracs.get(c, 0.0) for c in COMPONENTS}
    return {"flow": direct_flow, "mw": 28.0, "molar": direct_flow / 28.0,
            "masses": masses}


def simple_stream_masses(flow: float, mass_fracs: Dict[str, float],
                         active: bool) -> Dict[str, float]:
    """
    Component mass flows for a simple stream (RCY, AS2, AS3).
    Returns zeros if not active.
    """
    if not active or flow == 0:
        return {c: 0.0 for c in COMPONENTS}
    return {c: flow * mass_fracs.get(c, 0.0) for c in COMPONENTS}


def compute_as1_masses(inputs) -> Dict[str, float]:
    """
    Dispatch AS1 calculation based on inputs.
    *inputs* must have: as1_active, as1_use_analyser, as1_feed_tph,
    as1_bottom_tph, as1_c3_pct, as1_direct_flow, as1_mass_fracs.
    Returns component mass dict (all zeros if inactive).
    """
    if not inputs.get("as1_active", False):
        return {c: 0.0 for c in COMPONENTS}

    if inputs.get("as1_use_analyser", True):
        result = as1_analyser(
            inputs["as1_feed_tph"],
            inputs["as1_bottom_tph"],
            inputs["as1_c3_pct"],
        )
    else:
        result = as1_direct(
            inputs.get("as1_direct_flow", 0.0),
            inputs.get("as1_mass_fracs", {}),
        )
    return result["masses"]


def compute_as1_info(inputs) -> dict:
    """Return full AS1 result dict (flow, mw, molar, masses)."""
    if not inputs.get("as1_active", False):
        return {"flow": 0.0, "mw": 0.0, "molar": 0.0,
                "masses": {c: 0.0 for c in COMPONENTS}}

    if inputs.get("as1_use_analyser", True):
        return as1_analyser(
            inputs["as1_feed_tph"],
            inputs["as1_bottom_tph"],
            inputs["as1_c3_pct"],
        )
    else:
        return as1_direct(
            inputs.get("as1_direct_flow", 0.0),
            inputs.get("as1_mass_fracs", {}),
        )
