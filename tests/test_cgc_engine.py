"""
Validation of CGC stage engine against CGC_Generic_Engine_v3.xlsx
reference values (Stage 2 configuration).
"""

import math
import pytest
from cgc_dashboard.engine.cgc_stage import StageInputs, calculate_stage
from cgc_dashboard.engine.shomate_cp import shomate_cp
from cgc_dashboard.engine.stream_mapper import as1_analyser


# ── Reference Stage 2 Inputs (from INPUTS sheet) ─────────────────────

def _stage2_inputs() -> StageInputs:
    return StageInputs(
        # Stage conditions
        T_suc=35.692,
        P_suc=8.429,
        T_dis=86.777,
        P_dis=19.685,
        T_AC_out=40.725,
        water_mass_frac=0.0044244,

        # Flows
        next_stage_dry_flow=457720.0,
        prev_stage_dry_flow=409210.0,

        # Previous stage
        prev_water_mf=0.0092378,
        prev_bfw_flow=0.0,
        prev_wash_oil_flow=421.16,

        # QO composition
        qo_mass_fracs={
            "H2": 0.025179, "CH4": 0.15068, "C2H2": 0.0,
            "C2H4": 0.36706, "C2H6": 0.20647, "C3H4": 0.0,
            "C3H6": 0.086862, "C3H8": 0.1145, "C4s": 0.024041,
            "C5_Above": 0.025199, "C6_To_C8": 0.0, "C9_Plus": 0.0,
        },

        # Current stage injections
        bfw_flow=5000.0,
        wash_oil_flow=345.33,
        wash_oil_molar_flow=2.7329,

        # AS1 — C3 Analyser mode
        as1_active=True,
        as1_use_analyser=True,
        as1_feed_tph=137.52,
        as1_bottom_tph=107.13,
        as1_c3_pct=20.142,

        # Other streams inactive
        rcy_active=False, rcy_flow=0.0,
        as2_active=False, as2_flow=0.0,
        as3_active=False, as3_flow=0.0,

        # Auxiliary
        bfw_temp=35.846,
        cw_supply_temp=33.961,
        caustic_dp=-0.024974,
        caustic_top_p=18.903,
        wash_oil_mw=126.24,
        cgc_speed=3646.7,

        # Next stage link
        next_suc_pressure=18.808,
        next_suc_temperature=45.907,
    )


# ── Shomate Cp Validation ─────────────────────────────────────────────

class TestShomateCp:
    """Verify Cp values at T_dis = 86.777 °C (D113–D125)."""

    @pytest.mark.parametrize("comp,expected", [
        ("H2",       29.1040),
        ("CH4",      38.3437),
        ("C2H2",     48.3406),
        ("C2H4",     49.1125),
        ("C2H6",     61.3101),
        ("C3H4",     66.9566),
        ("C3H6",     75.5306),
        ("C3H8",     87.3126),
        ("C4s",      114.423),
        ("C5_Above", 101.290),
        ("C6_To_C8", 14.6253),
        ("C9_Plus",  60.5914),
        ("Water",    75.7184),
    ])
    def test_cp_at_discharge_temp(self, comp, expected):
        cp = shomate_cp(comp, 86.777)
        assert abs(cp - expected) < 0.01, f"{comp}: {cp} != {expected}"

    @pytest.mark.parametrize("comp,expected", [
        ("H2",       28.9306),
        ("CH4",      36.2252),
        ("C2H4",     44.4456),
        ("C2H6",     55.5640),
        ("C3H6",     68.7784),
        ("C3H8",     78.8641),
        ("Water",    75.2632),
    ])
    def test_cp_at_ac_outlet_temp(self, comp, expected):
        cp = shomate_cp(comp, 40.725)
        assert abs(cp - expected) < 0.01, f"{comp}: {cp} != {expected}"


# ── AS1 Analyser Validation ───────────────────────────────────────────

class TestAS1Analyser:
    def test_as1_analyser_mode(self):
        result = as1_analyser(137.52, 107.13, 20.142)
        assert abs(result["flow"] - 30390.0) < 1.0
        assert abs(result["mw"] - 32.017) < 0.01
        assert abs(result["molar"] - 949.174) < 0.1
        assert abs(result["masses"]["C3H6"] - 4898.10) < 1.0
        assert abs(result["masses"]["C3H8"] - 3280.70) < 1.0
        assert abs(result["masses"]["C2H6"] - 13871.25) < 1.0
        assert abs(result["masses"]["C2H4"] - 8277.27) < 1.0


# ── Full Stage Calculation Validation ─────────────────────────────────

class TestCGCStage:
    @pytest.fixture
    def result(self):
        return calculate_stage(_stage2_inputs())

    # Step 1
    def test_pressure_ratio(self, result):
        assert abs(result.P_ratio - 2.19622) < 0.001

    def test_temperature_ratio_raw(self, result):
        assert abs(result.T_ratio_raw - 1.16541) < 0.001

    def test_ln_P_ln_T(self, result):
        assert abs(result.ln_P_ln_T - 5.13967) < 0.001

    def test_T_dis_corr(self, result):
        assert abs(result.T_dis_corr - 86.777) < 0.001

    # Step 3
    def test_prev_water_flow(self, result):
        assert abs(result.prev_water_flow - 3815.45) < 1.0

    def test_prev_discharge_flow(self, result):
        assert abs(result.prev_discharge_flow - 413446.61) < 1.0

    # Step 5
    def test_ac_total_mass_flow(self, result):
        assert abs(result.ac_total_mass_flow - 461956.61) < 1.0

    def test_scale_ratio(self, result):
        assert abs(result.ac_scale_ratio - 1.04097) < 0.0001

    # Step 6
    def test_ac_molar_H2(self, result):
        assert abs(result.ac_molar["H2"] - 5362.83) < 1.0

    def test_ac_molar_CH4(self, result):
        assert abs(result.ac_molar["CH4"] - 4011.63) < 1.0

    def test_ac_molar_C2H4(self, result):
        assert abs(result.ac_molar["C2H4"] - 5891.98) < 1.0

    def test_ac_molar_C2H6(self, result):
        assert abs(result.ac_molar["C2H6"] - 3413.03) < 1.0

    def test_ac_molar_C3H6(self, result):
        assert abs(result.ac_molar["C3H6"] - 1002.38) < 1.0

    def test_ac_molar_C3H8(self, result):
        assert abs(result.ac_molar["C3H8"] - 1186.12) < 1.0

    def test_ac_molar_C4s(self, result):
        assert abs(result.ac_molar["C4s"] - 185.658) < 0.1

    def test_ac_molar_C5_Above(self, result):
        assert abs(result.ac_molar["C5_Above"] - 141.500) < 0.1

    # Step 7
    def test_water_flow(self, result):
        assert abs(result.water_flow - 7034.14) < 1.0

    def test_discharge_flow(self, result):
        assert abs(result.discharge_flow - 465099.47) < 1.0

    def test_MW_noBFW(self, result):
        assert abs(result.MW_noBFW - 21.5899) < 0.01

    def test_MW_withBFW(self, result):
        assert abs(result.MW_withBFW - 21.5437) < 0.01

    # Step 8
    def test_mix_cp(self, result):
        assert abs(result.mix_cp - 2.2443) < 0.001

    def test_bfw_cp(self, result):
        assert abs(result.bfw_cp - 4.2066) < 0.001

    def test_bfw_lambda(self, result):
        assert abs(result.bfw_lambda - 1929.43) < 1.0

    # Step 9
    def test_T_dis_BFW(self, result):
        assert abs(result.T_dis_BFW - 97.0455) < 0.01

    # Step 10
    def test_efficiency(self, result):
        assert abs(result.efficiency - 79.9916) < 0.01

    def test_polytropic_head(self, result):
        assert abs(result.polytropic_head - 10206.73) < 1.0

    def test_power(self, result):
        assert abs(result.power - 16171.67) < 1.0

    def test_K_value(self, result):
        assert abs(result.K_value - 1.22585) < 0.001

    def test_K_factor(self, result):
        assert abs(result.K_factor - 0.18424) < 0.001

    def test_N(self, result):
        assert abs(result.N - 4.34178) < 0.001

    # Step 11
    def test_discharge_cp(self, result):
        assert abs(result.discharge_cp - 2.26536) < 0.001

    def test_ac_outlet_cp(self, result):
        assert abs(result.ac_outlet_cp - 2.09829) < 0.001

    def test_avg_ac_cp(self, result):
        assert abs(result.avg_ac_cp - 2.18183) < 0.001

    # Step 12
    def test_ac_duty(self, result):
        assert abs(result.ac_duty - 15866.06) < 1.0

    def test_hot_approach(self, result):
        assert abs(result.hot_approach - 6.764) < 0.001

    def test_UA(self, result):
        assert abs(result.UA - 2345.66) < 1.0

    def test_fouling_index(self, result):
        assert abs(result.fouling_index - 4.2632) < 0.01

    def test_vol_flow_suc(self, result):
        assert abs(result.vol_flow_suc - 58631.53) < 1.0

    def test_vol_flow_dis(self, result):
        assert abs(result.vol_flow_dis - 30953.04) < 1.0

    def test_ac_pressure_drop(self, result):
        assert abs(result.ac_pressure_drop - 0.782) < 0.001

    def test_norm_ac_dp(self, result):
        assert abs(result.norm_ac_dp - 2.5264) < 0.01

    def test_fouling_dp_pct(self, result):
        assert result.fouling_dp_pct <= 0.0  # Should be 0 (or guarded by EPSILON)
