"""
Train Runner — orchestrates N CGC stages + N-1 flash drums sequentially.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cgc_dashboard.engine.constants import COMPONENTS
from cgc_dashboard.engine.cgc_stage import StageInputs, StageResult, calculate_stage
from cgc_dashboard.engine.flash_drum import FlashResult, run_flash


@dataclass
class TrainConfig:
    """Configuration for the entire CGC train."""
    num_stages: int = 4
    stages: List[dict] = field(default_factory=list)
    global_params: dict = field(default_factory=dict)
    flash_dp: List[float] = field(default_factory=list)  # dP per drum [kg/cm²]
    dtl_path: str = ""
    auto_fill_from_flash: List[bool] = field(default_factory=list)


@dataclass
class TrainResult:
    """Complete train calculation results."""
    stage_results: List[StageResult] = field(default_factory=list)
    flash_results: List[Optional[FlashResult]] = field(default_factory=list)
    stage_inputs_used: List[StageInputs] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _build_stage_inputs(stage_cfg: dict, gp: dict,
                        prev_flash: Optional[FlashResult],
                        auto_fill: bool) -> StageInputs:
    """Build StageInputs from config dict, optionally auto-filling from flash."""
    sc = stage_cfg

    # QO composition — auto-fill from previous flash drum vapor
    qo_mf = {c: sc.get(f"qo_mf_{c}", 0.0) for c in COMPONENTS}
    prev_dry = sc.get("prev_stage_dry_flow", 0.0)
    prev_water_mf = sc.get("prev_water_mf", 0.0)
    prev_bfw = sc.get("prev_bfw_flow", 0.0)
    prev_wo = sc.get("prev_wash_oil_flow", 0.0)

    if auto_fill and prev_flash is not None and not prev_flash.error:
        qo_mf = dict(prev_flash.vapor_dry_mass_fracs)
        prev_dry = prev_flash.vapor_dry_mass_flow
        prev_water_mf = prev_flash.vapor_water_mass_frac

    return StageInputs(
        T_suc=sc.get("T_suc", 0.0),
        P_suc=sc.get("P_suc", 0.0),
        T_dis=sc.get("T_dis", 0.0),
        P_dis=sc.get("P_dis", 0.0),
        T_AC_out=sc.get("T_AC_out", 0.0),
        water_mass_frac=sc.get("water_mass_frac", 0.0),
        next_stage_dry_flow=sc.get("next_stage_dry_flow", 0.0),
        prev_stage_dry_flow=prev_dry,
        prev_water_mf=prev_water_mf,
        prev_bfw_flow=prev_bfw,
        prev_wash_oil_flow=prev_wo,
        qo_mass_fracs=qo_mf,
        bfw_flow=sc.get("bfw_flow", 0.0),
        wash_oil_flow=sc.get("wash_oil_flow", 0.0),
        wash_oil_molar_flow=sc.get("wash_oil_molar_flow", 0.0),
        as1_active=sc.get("as1_active", False),
        as1_use_analyser=sc.get("as1_use_analyser", True),
        as1_feed_tph=sc.get("as1_feed_tph", 0.0),
        as1_bottom_tph=sc.get("as1_bottom_tph", 0.0),
        as1_c3_pct=sc.get("as1_c3_pct", 0.0),
        as1_direct_flow=sc.get("as1_direct_flow", 0.0),
        as1_mass_fracs={c: sc.get(f"as1_mf_{c}", 0.0) for c in COMPONENTS},
        rcy_active=sc.get("rcy_active", False),
        rcy_flow=sc.get("rcy_flow", 0.0),
        rcy_mass_fracs={c: sc.get(f"rcy_mf_{c}", 0.0) for c in COMPONENTS},
        as2_active=sc.get("as2_active", False),
        as2_flow=sc.get("as2_flow", 0.0),
        as2_mass_fracs={c: sc.get(f"as2_mf_{c}", 0.0) for c in COMPONENTS},
        as3_active=sc.get("as3_active", False),
        as3_flow=sc.get("as3_flow", 0.0),
        as3_mass_fracs={c: sc.get(f"as3_mf_{c}", 0.0) for c in COMPONENTS},
        bfw_temp=gp.get("bfw_temp", 35.0),
        cw_supply_temp=gp.get("cw_supply_temp", 33.0),
        caustic_dp=gp.get("caustic_dp", 0.0),
        caustic_top_p=gp.get("caustic_top_p", 0.0),
        wash_oil_mw=gp.get("wash_oil_mw", 126.24),
        cgc_speed=gp.get("cgc_speed", 0.0),
        next_suc_pressure=sc.get("next_suc_pressure", 0.0),
        next_suc_temperature=sc.get("next_suc_temperature", 0.0),
    )


def run_train(config: TrainConfig) -> TrainResult:
    """Execute the full CGC train calculation."""
    result = TrainResult()
    prev_flash: Optional[FlashResult] = None

    for i in range(config.num_stages):
        if i >= len(config.stages):
            result.errors.append(f"Missing config for stage {i+1}")
            break

        auto_fill = (config.auto_fill_from_flash[i]
                     if i < len(config.auto_fill_from_flash) else True)

        try:
            inp = _build_stage_inputs(
                config.stages[i], config.global_params,
                prev_flash if i > 0 else None,
                auto_fill and i > 0,
            )
            result.stage_inputs_used.append(inp)

            stage_result = calculate_stage(inp)
            result.stage_results.append(stage_result)

            # Run flash drum for all stages except the last
            if i < config.num_stages - 1:
                dp = (config.flash_dp[i]
                      if i < len(config.flash_dp) else 0.3)
                flash = run_flash(
                    ac_molar=stage_result.ac_molar,
                    water_moles=stage_result.water_flow / 18.0,
                    T_AC_out=inp.T_AC_out,
                    P_dis=inp.P_dis,
                    dp_drum=dp,
                    dtl_path=config.dtl_path,
                )
                result.flash_results.append(flash)
                prev_flash = flash
            else:
                result.flash_results.append(None)

        except Exception as e:
            result.errors.append(f"Stage {i+1}: {e}")
            result.stage_results.append(StageResult())
            result.flash_results.append(None)

    return result
