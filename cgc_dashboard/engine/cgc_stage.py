"""
CGC Generic Stage Calculation Engine — Steps 1–12
Every formula extracted verbatim from CGC_Generic_Engine_v3.xlsx CALCULATIONS sheet.

Variable names in comments reference Excel cell addresses (e.g. D6, D86).
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, Optional

from cgc_dashboard.engine.constants import (
    COMPONENTS, MW, R_GAS, ATM_KGCM2, G, K_OFFSET,
    Z_SUC, Z_DIS, Z_HEAD, EPSILON, AIR_MW, WATER_MW,
    WASH_OIL_CP, VOL_CONST, NEXT_STAGE_WATER_MF_CONST,
    WASH_OIL_HEAT_CONST,
)
from cgc_dashboard.engine.shomate_cp import shomate_cp
from cgc_dashboard.engine.stream_mapper import (
    compute_as1_info, simple_stream_masses,
)


# ---------------------------------------------------------------------------
# Input / Output data structures
# ---------------------------------------------------------------------------

@dataclass
class StageInputs:
    """All inputs for a single CGC stage calculation."""
    # Stage conditions
    T_suc: float            # Suction temperature [°C]
    P_suc: float            # Suction pressure [kg/cm²]
    T_dis: float            # Discharge temperature (measured) [°C]
    P_dis: float            # Discharge pressure [kg/cm²]
    T_AC_out: float         # Aftercooler outlet temperature [°C]
    water_mass_frac: float  # Current stage water mass fraction [—]

    # Flows
    next_stage_dry_flow: float    # [kg/h]
    prev_stage_dry_flow: float    # [kg/h]

    # Previous stage parameters
    prev_water_mf: float          # Previous stage water mass fraction
    prev_bfw_flow: float          # Previous stage BFW injection [kg/h]
    prev_wash_oil_flow: float     # Previous stage wash oil flow [kg/h]

    # QO component mass fractions (12 components)
    qo_mass_fracs: Dict[str, float] = field(default_factory=dict)

    # Current stage injections
    bfw_flow: float = 0.0              # BFW injection [kg/h]
    wash_oil_flow: float = 0.0         # Wash oil injection [kg/h]
    wash_oil_molar_flow: float = 0.0   # Wash oil molar flow [kmol/h]

    # Additional streams
    as1_active: bool = False
    as1_use_analyser: bool = True
    as1_feed_tph: float = 0.0
    as1_bottom_tph: float = 0.0
    as1_c3_pct: float = 0.0
    as1_direct_flow: float = 0.0
    as1_mass_fracs: Dict[str, float] = field(default_factory=dict)

    rcy_active: bool = False
    rcy_flow: float = 0.0
    rcy_mass_fracs: Dict[str, float] = field(default_factory=dict)

    as2_active: bool = False
    as2_flow: float = 0.0
    as2_mass_fracs: Dict[str, float] = field(default_factory=dict)

    as3_active: bool = False
    as3_flow: float = 0.0
    as3_mass_fracs: Dict[str, float] = field(default_factory=dict)

    # Auxiliary / global
    bfw_temp: float = 35.0         # BFW temperature [°C]
    cw_supply_temp: float = 33.0   # Cooling water supply temperature [°C]
    caustic_dp: float = 0.0        # Caustic tower DP [kg/cm²]
    caustic_top_p: float = 0.0     # Caustic tower top pressure [kg/cm²]
    wash_oil_mw: float = 126.24    # Wash oil molecular weight [kg/kmol]
    cgc_speed: float = 0.0         # Compressor speed [RPM]

    # Next stage link (for aftercooler calcs)
    next_suc_pressure: float = 0.0  # [kg/cm²]
    next_suc_temperature: float = 0.0  # [°C]


@dataclass
class StageResult:
    """Complete calculation results including all intermediates."""
    # Step 1
    T_ratio_raw: float = 0.0
    P_ratio: float = 0.0
    ln_P_ln_T: float = 0.0
    T_dis_corr: float = 0.0

    # Step 2
    prev_mass: Dict[str, float] = field(default_factory=dict)

    # Step 3
    prev_water_flow: float = 0.0
    prev_discharge_flow: float = 0.0

    # Step 4
    as1_info: dict = field(default_factory=dict)
    as1_masses: Dict[str, float] = field(default_factory=dict)
    rcy_masses: Dict[str, float] = field(default_factory=dict)
    as2_masses: Dict[str, float] = field(default_factory=dict)
    as3_masses: Dict[str, float] = field(default_factory=dict)

    # Step 5
    ac_total_mass_flow: float = 0.0
    ac_scale_ratio: float = 0.0

    # Step 6
    ac_molar: Dict[str, float] = field(default_factory=dict)
    ac_water_moles: float = 0.0

    # Step 7
    water_flow: float = 0.0
    discharge_flow: float = 0.0
    water_moles_noBFW: float = 0.0
    total_moles_noBFW: float = 0.0
    total_moles_withBFW: float = 0.0
    MW_noBFW: float = 0.0
    MW_withBFW: float = 0.0

    # Step 8
    T_dis_factor: float = 0.0
    cp_at_Tdis: Dict[str, float] = field(default_factory=dict)
    mix_cp: float = 0.0
    bfw_cp: float = 0.0
    bfw_lambda: float = 0.0

    # Step 9
    T_dis_BFW: float = 0.0

    # Step 10
    T_ratio_BFW: float = 0.0
    ln_Pr: float = 0.0
    ln_Tr: float = 0.0
    MW_ratio: float = 0.0
    T_avg_K: float = 0.0
    K_value: float = 0.0
    K_factor: float = 0.0
    efficiency: float = 0.0
    N: float = 0.0
    N_inv: float = 0.0
    polytropic_head: float = 0.0
    power: float = 0.0

    # Step 11
    T_AC_factor: float = 0.0
    cp_at_TAC: Dict[str, float] = field(default_factory=dict)
    discharge_cp: float = 0.0
    ac_outlet_cp: float = 0.0
    avg_ac_cp: float = 0.0

    # Step 12
    water_condensed: float = 0.0
    ac_lambda: float = 0.0
    ac_duty: float = 0.0
    hot_approach: float = 0.0
    UA: float = 0.0
    fouling_index: float = 0.0
    ac_duty_normalised: float = 0.0
    vol_flow_suc: float = 0.0
    vol_flow_dis: float = 0.0
    caustic_inlet_p: float = 0.0
    ac_pressure_drop: float = 0.0
    norm_ac_dp: float = 0.0
    fouling_dp_pct: float = 0.0


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe(val: float) -> float:
    """Replicate Excel MAX(Epsilon, val) guard."""
    return max(EPSILON, val)


def _latent_heat(T: float, P: float) -> float:
    """
    BFW / AC latent heat correlation (D128, D168).
    T in °C, P in kg/cm² (gauge).
    """
    if T < 50:
        return 2353.819 + (T ** (1.0 / 6.0)) * (P ** 0.5) * (-52.6775)
    else:
        return 2356.178 + (T ** (1.0 / 6.0)) * (P ** 0.5) * (-50.15)


def _weighted_cp(ac_molar: Dict[str, float],
                 water_moles: float,
                 wo_molar: float,
                 T_celsius: float,
                 total_moles: float,
                 mw: float) -> float:
    """
    Molar-weighted average Cp [kJ/kg/K].
    Matches D126/D162/D163 pattern.
    """
    numerator = 0.0
    for c in COMPONENTS:
        numerator += ac_molar.get(c, 0.0) * shomate_cp(c, T_celsius)
    numerator += shomate_cp("Water", T_celsius) * water_moles
    numerator += wo_molar * WASH_OIL_CP
    return numerator / total_moles / mw


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

def calculate_stage(inp: StageInputs) -> StageResult:
    """Run the full 12-step CGC stage calculation."""
    r = StageResult()

    # ── STEP 1: Temperature & Pressure Ratios (D6–D9) ─────────────────
    T_suc_K = inp.T_suc + K_OFFSET
    T_dis_K = inp.T_dis + K_OFFSET

    r.T_ratio_raw = _safe(T_dis_K / T_suc_K)                         # D6
    r.P_ratio = (inp.P_dis + ATM_KGCM2) / (inp.P_suc + ATM_KGCM2)  # D7
    r.ln_P_ln_T = _safe(math.log(r.P_ratio) / math.log(r.T_ratio_raw))  # D8

    if r.ln_P_ln_T > 5.5:                                             # D9
        r.T_dis_corr = (math.exp(math.log(r.P_ratio) / 5.5)
                        * T_suc_K - K_OFFSET)
    else:
        r.T_dis_corr = inp.T_dis

    # ── STEP 2: Previous Stage Component Mass Flows (D12–D23) ─────────
    r.prev_mass = {
        c: inp.prev_stage_dry_flow * inp.qo_mass_fracs.get(c, 0.0)
        for c in COMPONENTS
    }

    # ── STEP 3: Previous Stage Water & Discharge Flow (D26–D27) ───────
    r.prev_water_flow = (
        inp.prev_stage_dry_flow * inp.prev_water_mf / (1 - inp.prev_water_mf)
        + inp.prev_bfw_flow
    )  # D26
    r.prev_discharge_flow = (
        inp.prev_stage_dry_flow + r.prev_water_flow + inp.prev_wash_oil_flow
    )  # D27

    # ── STEP 4: Additional Stream Component Flows (D30–D82) ───────────
    as1_inputs = {
        "as1_active": inp.as1_active,
        "as1_use_analyser": inp.as1_use_analyser,
        "as1_feed_tph": inp.as1_feed_tph,
        "as1_bottom_tph": inp.as1_bottom_tph,
        "as1_c3_pct": inp.as1_c3_pct,
        "as1_direct_flow": inp.as1_direct_flow,
        "as1_mass_fracs": inp.as1_mass_fracs,
    }
    r.as1_info = compute_as1_info(as1_inputs)
    r.as1_masses = r.as1_info["masses"]

    r.rcy_masses = simple_stream_masses(
        inp.rcy_flow, inp.rcy_mass_fracs, inp.rcy_active)
    r.as2_masses = simple_stream_masses(
        inp.as2_flow, inp.as2_mass_fracs, inp.as2_active)
    r.as3_masses = simple_stream_masses(
        inp.as3_flow, inp.as3_mass_fracs, inp.as3_active)

    # ── STEP 5: Aftercooler Total Mass Flow & Scale Ratio (D85–D86) ───
    r.ac_total_mass_flow = (
        inp.next_stage_dry_flow + r.prev_water_flow + inp.prev_wash_oil_flow
    )  # D85

    # Denominator: sum of ALL stream component masses + prev_discharge  (D86)
    denom_sum = 0.0
    for c in COMPONENTS:
        denom_sum += (r.as1_masses.get(c, 0.0)
                      + r.rcy_masses.get(c, 0.0)
                      + r.as2_masses.get(c, 0.0)
                      + r.as3_masses.get(c, 0.0))
    denom_sum += r.prev_discharge_flow
    r.ac_scale_ratio = r.ac_total_mass_flow / _safe(denom_sum)  # D86

    # ── STEP 6: Aftercooler Molar Flows (D89–D100) ────────────────────
    r.ac_molar = {}
    for c in COMPONENTS:
        total_mass_c = (r.prev_mass.get(c, 0.0)
                        + r.rcy_masses.get(c, 0.0)
                        + r.as1_masses.get(c, 0.0)
                        + r.as2_masses.get(c, 0.0)
                        + r.as3_masses.get(c, 0.0))
        r.ac_molar[c] = r.ac_scale_ratio * total_mass_c / MW[c]

    r.ac_water_moles = r.prev_water_flow * r.ac_scale_ratio / WATER_MW

    # ── STEP 7: Current Stage Discharge Flow & MW (D103–D109) ─────────
    r.water_flow = (
        inp.next_stage_dry_flow * inp.water_mass_frac
        / (1.0 - inp.water_mass_frac)
        + inp.bfw_flow
    )  # D103

    r.discharge_flow = _safe(
        r.water_flow + inp.next_stage_dry_flow + inp.wash_oil_flow
    )  # D104

    r.water_moles_noBFW = _safe(
        (r.water_flow - inp.bfw_flow) / WATER_MW
    )  # D105

    sum_ac_molar = sum(r.ac_molar[c] for c in COMPONENTS)
    r.total_moles_noBFW = _safe(
        sum_ac_molar + r.water_moles_noBFW + inp.wash_oil_molar_flow
    )  # D106

    r.total_moles_withBFW = _safe(
        sum_ac_molar + r.water_flow / WATER_MW + inp.wash_oil_molar_flow
    )  # D107

    r.MW_noBFW = _safe(
        (r.discharge_flow - inp.bfw_flow) / r.total_moles_noBFW
    )  # D108

    r.MW_withBFW = _safe(
        r.discharge_flow / r.total_moles_withBFW
    )  # D109

    # ── STEP 8: Shomate Cp at Discharge Temperature (D112–D128) ───────
    # IMPORTANT: uses RAW T_dis (D112), not T_dis_corr
    r.T_dis_factor = (inp.T_dis + K_OFFSET) * 0.001  # D112

    r.cp_at_Tdis = {}
    for c in COMPONENTS:
        r.cp_at_Tdis[c] = shomate_cp(c, inp.T_dis)
    r.cp_at_Tdis["Water"] = shomate_cp("Water", inp.T_dis)

    # Mix Cp  (D126) — excl BFW, with wash oil
    r.mix_cp = _weighted_cp(
        r.ac_molar, r.water_moles_noBFW, inp.wash_oil_molar_flow,
        inp.T_dis, r.total_moles_noBFW, r.MW_noBFW,
    )

    # BFW Cp  (D127)
    r.bfw_cp = shomate_cp("Water", inp.T_dis) / WATER_MW  # kJ/kg/K

    # BFW Lambda  (D128) — P_dis in kg/cm² gauge
    r.bfw_lambda = _latent_heat(inp.bfw_temp, inp.P_dis)

    # ── STEP 9: BFW-Corrected Discharge Temperature (D131) ────────────
    if inp.bfw_flow > 0 and r.mix_cp > 0 and r.discharge_flow > 0:
        numerator = (inp.bfw_flow * r.bfw_cp * (r.T_dis_corr - inp.bfw_temp)
                     + inp.bfw_flow * r.bfw_lambda)
        denominator = r.mix_cp * r.discharge_flow
        r.T_dis_BFW = _safe(r.T_dis_corr + numerator / denominator)
    else:
        r.T_dis_BFW = r.T_dis_corr

    # ── STEP 10: Polytropic Performance (D134–D145) ───────────────────
    T_dis_BFW_K = r.T_dis_BFW + K_OFFSET

    r.T_ratio_BFW = _safe(T_dis_BFW_K / T_suc_K)               # D134
    r.ln_Pr = _safe(math.log(r.P_ratio))                         # D135
    r.ln_Tr = _safe(math.log(r.T_ratio_BFW))                     # D136
    r.MW_ratio = _safe(r.MW_withBFW / AIR_MW)                    # D137
    r.T_avg_K = _safe((T_suc_K + T_dis_BFW_K) / 2.0)           # D138

    r.K_value = _safe(
        (1.46 - 0.16 * (r.MW_ratio - 0.55))
        * (1.0 - 0.067 * r.MW_ratio - 0.000272 * r.T_avg_K)
    )  # D139

    r.K_factor = _safe((r.K_value - 1.0) / r.K_value)            # D140

    r.efficiency = _safe(
        r.K_factor * r.ln_Pr / r.ln_Tr * 100.0
    )  # D141

    r.N = _safe(r.efficiency * 0.01 / r.K_factor)                # D142
    r.N_inv = _safe(1.0 / r.N)                                   # D143

    r.polytropic_head = _safe(
        ((1000.0 * Z_HEAD * (R_GAS / r.MW_withBFW) * T_suc_K) / G)
        * r.N * (r.P_ratio ** r.N_inv - 1.0)
    )  # D144

    r.power = _safe(
        (G * r.polytropic_head * r.discharge_flow * 1e-6)
        / (3.6 * r.efficiency * 0.01)
    )  # D145

    # ── STEP 11: Cp at Aftercooler Outlet Temperature (D148–D164) ─────
    r.T_AC_factor = (inp.T_AC_out + K_OFFSET) / 1000.0           # D148

    r.cp_at_TAC = {}
    for c in COMPONENTS:
        r.cp_at_TAC[c] = shomate_cp(c, inp.T_AC_out)
    r.cp_at_TAC["Water"] = shomate_cp("Water", inp.T_AC_out)

    # Discharge Cp  (D162) — includes BFW water, uses total_moles_withBFW
    water_moles_full = r.water_flow / WATER_MW
    r.discharge_cp = _weighted_cp(
        r.ac_molar, water_moles_full, inp.wash_oil_molar_flow,
        inp.T_dis, r.total_moles_withBFW, r.MW_withBFW,
    )

    # AC Outlet Cp  (D163) — same molar flows, evaluated at T_AC_out
    r.ac_outlet_cp = _weighted_cp(
        r.ac_molar, water_moles_full, inp.wash_oil_molar_flow,
        inp.T_AC_out, r.total_moles_withBFW, r.MW_withBFW,
    )

    # Average  (D164)
    r.avg_ac_cp = (r.discharge_cp + r.ac_outlet_cp) / 2.0

    # ── STEP 12: Aftercooler Performance (D167–D179) ──────────────────

    # Water condensed  (D167) — hardcoded 0.0038 for next stage
    next_residual_water = (inp.next_stage_dry_flow * NEXT_STAGE_WATER_MF_CONST
                           / (1.0 - NEXT_STAGE_WATER_MF_CONST))
    r.water_condensed = max(0.0, r.water_flow - next_residual_water)

    # AC Lambda  (D168) — uses next stage T and P
    r.ac_lambda = _latent_heat(inp.next_suc_temperature, inp.next_suc_pressure)

    # Aftercooler Duty  (D169)
    # NOTE: uses raw T_dis (not BFW-corrected), wash oil constant 650
    r.ac_duty = _safe(
        (r.water_condensed * r.ac_lambda
         + inp.wash_oil_flow * WASH_OIL_HEAT_CONST
         + r.discharge_flow * r.avg_ac_cp
         * (inp.T_dis - inp.T_AC_out))
        / 3600.0
    )

    # Hot approach  (D170)
    r.hot_approach = _safe(inp.T_AC_out - inp.cw_supply_temp)

    # UA  (D171)
    r.UA = _safe(r.ac_duty / r.hot_approach)

    # Fouling index  (D172)
    r.fouling_index = _safe(10000.0 / r.UA)

    # AC duty normalised  (D173)
    r.ac_duty_normalised = _safe(r.ac_duty / r.discharge_flow)

    # Volumetric flows  (D174, D175)
    r.vol_flow_suc = _safe(
        Z_SUC * VOL_CONST * r.discharge_flow * T_suc_K
        / (r.MW_withBFW * (inp.P_suc + ATM_KGCM2))
    )  # D174

    r.vol_flow_dis = _safe(
        Z_DIS * VOL_CONST * r.discharge_flow * T_dis_K
        / (r.MW_withBFW * (inp.P_dis + ATM_KGCM2))
    )  # D175  — uses raw T_dis

    # Caustic tower inlet  (D176)
    r.caustic_inlet_p = inp.caustic_top_p + max(0.0, inp.caustic_dp)

    # AC pressure drop  (D177)
    r.ac_pressure_drop = _safe(inp.P_dis - r.caustic_inlet_p)

    # Normalised AC ΔP  (D178)
    r.norm_ac_dp = _safe(r.ac_pressure_drop * 1e5 / r.vol_flow_dis)

    # Fouling DP %  (D179)
    fouling_raw = (1.0 - 2.6 / r.norm_ac_dp) * 100.0
    r.fouling_dp_pct = _safe(max(0.0, fouling_raw))

    return r
