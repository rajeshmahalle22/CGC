"""
Flash drum calculation with 3-tier thermodynamic backend:
  1. thermo (Peng-Robinson EOS with kij) — primary, pip-installable
  2. Simplified Raoult's law — fallback when thermo unavailable/fails
  3. DWSIM DTL — optional legacy support if installed locally
"""

from __future__ import annotations
import math
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cgc_dashboard.engine.constants import (
    COMPONENTS, MW, WATER_MW, K_OFFSET, ATM_KGCM2, DWSIM_NAMES,
)

logger = logging.getLogger(__name__)


@dataclass
class FlashResult:
    """Results from a PT flash calculation."""
    T_flash: float = 0.0           # Flash temperature [C]
    P_flash_kgcm2: float = 0.0    # Flash pressure [kg/cm2]
    vapor_fraction: float = 0.0    # Molar vapor fraction
    liquid_fraction: float = 0.0   # Molar liquid fraction

    vapor_flow_kmolh: float = 0.0  # Vapor molar flow [kmol/h]
    liquid_flow_kmolh: float = 0.0 # Liquid molar flow [kmol/h]
    vapor_flow_kgh: float = 0.0    # Vapor mass flow [kg/h]
    liquid_flow_kgh: float = 0.0   # Liquid mass flow [kg/h]

    # Compositions (component name -> fraction)
    y: Dict[str, float] = field(default_factory=dict)  # Vapor mole fracs
    x: Dict[str, float] = field(default_factory=dict)  # Liquid mole fracs
    K_values: Dict[str, float] = field(default_factory=dict)

    # Phase properties
    vapor_MW: float = 0.0
    liquid_MW: float = 0.0
    vapor_density: float = 0.0     # kg/m3
    liquid_density: float = 0.0    # kg/m3
    vapor_enthalpy: float = 0.0    # J/mol
    liquid_enthalpy: float = 0.0   # J/mol
    vapor_cp: float = 0.0          # J/mol/K
    liquid_cp: float = 0.0         # J/mol/K

    # Derived for next stage
    vapor_mass_flows: Dict[str, float] = field(default_factory=dict)
    vapor_dry_mass_flow: float = 0.0
    vapor_dry_mass_fracs: Dict[str, float] = field(default_factory=dict)
    vapor_water_mass_frac: float = 0.0

    is_approximate: bool = False
    method: str = ""               # Which backend was used
    error: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1: thermo (Peng-Robinson EOS)
# ═══════════════════════════════════════════════════════════════════════════════

# Map CGC component names -> thermo/chemicals identifiers
_THERMO_NAMES = {
    "H2":       "hydrogen",
    "CH4":      "methane",
    "C2H2":     "acetylene",
    "C2H4":     "ethylene",
    "C2H6":     "ethane",
    "C3H4":     "propadiene",
    "C3H6":     "propylene",
    "C3H8":     "propane",
    "C4s":      "1,3-butadiene",   # Representative C4 unsaturate
    "C5_Above": "n-pentane",       # Lump representative
    "C6_To_C8": "n-hexane",        # Lump representative
    "C9_Plus":  "n-nonane",        # Lump representative
    "Water":    "water",
}

# Lazy-initialized thermo flasher
_thermo_flasher = None
_thermo_constants = None
_thermo_init_attempted = False


def _init_thermo() -> bool:
    """Initialize the thermo PR flasher. Returns True on success."""
    global _thermo_flasher, _thermo_constants, _thermo_init_attempted

    if _thermo_init_attempted:
        return _thermo_flasher is not None
    _thermo_init_attempted = True

    try:
        from thermo import (
            ChemicalConstantsPackage, CEOSGas, CEOSLiquid,
            PRMIX, FlashVL,
        )
        from thermo.interaction_parameters import IPDB

        # Build component list in CGC order
        all_comps = COMPONENTS + ["Water"]
        thermo_ids = [_THERMO_NAMES[c] for c in all_comps]

        constants, properties = ChemicalConstantsPackage.from_IDs(thermo_ids)

        # Binary interaction parameters from ChemSep database
        kijs = IPDB.get_ip_asymmetric_matrix(
            'ChemSep PR', constants.CASs, 'kij'
        )

        eos_kwargs = {
            'Pcs': constants.Pcs,
            'Tcs': constants.Tcs,
            'omegas': constants.omegas,
            'kijs': kijs,
        }

        gas = CEOSGas(
            PRMIX, eos_kwargs=eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
        )
        liquid = CEOSLiquid(
            PRMIX, eos_kwargs=eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
        )

        _thermo_flasher = FlashVL(constants, properties,
                                   liquid=liquid, gas=gas)
        _thermo_constants = constants
        logger.info("thermo PR flasher initialized (%d components)", len(all_comps))
        return True

    except Exception as e:
        logger.warning("thermo initialization failed: %s", e)
        _thermo_flasher = None
        _thermo_constants = None
        return False


def is_thermo_available() -> bool:
    """Check if thermo library is initialized and ready."""
    if not _thermo_init_attempted:
        _init_thermo()
    return _thermo_flasher is not None


def flash_drum_thermo(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
) -> FlashResult:
    """
    Run a Peng-Robinson PT flash using the `thermo` library.

    Parameters
    ----------
    ac_molar   : Aftercooler molar flows per component [kmol/h]
    water_moles: Water molar flow [kmol/h]
    T_AC_out   : Aftercooler outlet temperature [C]
    P_dis      : Stage discharge pressure [kg/cm2 gauge]
    dp_drum    : Flash drum pressure drop [kg/cm2]
    """
    result = FlashResult(
        T_flash=T_AC_out,
        P_flash_kgcm2=P_dis - dp_drum,
        method="thermo-PR",
    )

    all_comps = COMPONENTS + ["Water"]

    # Build molar flows in CGC order
    molar_flows = []
    for c in all_comps:
        flow = water_moles if c == "Water" else ac_molar.get(c, 0.0)
        molar_flows.append(max(flow, 0.0))

    total_molar = sum(molar_flows)
    if total_molar <= 0:
        result.error = "No flow to flash"
        return result

    # Mole fractions (in CGC component order = thermo init order)
    zs = [f / total_molar for f in molar_flows]

    # Convert pressure: kg/cm2 gauge -> Pa absolute
    P_abs_Pa = (P_dis - dp_drum + ATM_KGCM2) * 98066.5  # kg/cm2 -> Pa

    # Temperature in K
    T_K = T_AC_out + K_OFFSET

    try:
        flash_res = _thermo_flasher.flash(T=T_K, P=P_abs_Pa, zs=zs)

        # Determine phase state
        VF = flash_res.VF if flash_res.VF is not None else 0.0
        if VF >= 1.0:
            VF = 1.0  # All vapor
        elif VF <= 0.0:
            VF = 0.0  # All liquid

        result.vapor_fraction = VF
        result.liquid_fraction = 1.0 - VF
        result.vapor_flow_kmolh = total_molar * VF
        result.liquid_flow_kmolh = total_molar * (1.0 - VF)

        # Extract compositions
        for i, c in enumerate(all_comps):
            if VF > 1e-12 and hasattr(flash_res, 'gas') and flash_res.gas:
                result.y[c] = flash_res.gas.zs[i]
            else:
                result.y[c] = zs[i] if VF >= 1.0 else 0.0

            if (1.0 - VF) > 1e-12 and hasattr(flash_res, 'liquid0') and flash_res.liquid0:
                result.x[c] = flash_res.liquid0.zs[i]
            else:
                result.x[c] = zs[i] if VF <= 0.0 else 0.0

            # K-values
            if result.x[c] > 1e-15:
                result.K_values[c] = result.y[c] / result.x[c]
            elif result.y[c] > 1e-15:
                result.K_values[c] = float('inf')
            else:
                result.K_values[c] = 0.0

        # Phase molecular weights
        if hasattr(flash_res, 'gas') and flash_res.gas:
            result.vapor_MW = flash_res.gas.MW()
        if hasattr(flash_res, 'liquid0') and flash_res.liquid0:
            result.liquid_MW = flash_res.liquid0.MW()

        _compute_vapor_mass_flows(result)
        return result

    except Exception as e:
        result.error = f"thermo flash failed: {e}"
        result.is_approximate = True
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2: Simplified Raoult's law (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

# Antoine constants: log10(P_mmHg) = A - B / (C + T_celsius)
_ANTOINE = {
    "H2":       (6.774, 47.12, 264.65),
    "CH4":      (6.61184, 389.93, 266.0),
    "C2H2":     (7.09990, 711.00, 253.37),
    "C2H4":     (6.74756, 585.00, 255.0),
    "C2H6":     (6.80266, 656.40, 256.0),
    "C3H4":     (6.954, 803.0, 247.0),
    "C3H6":     (6.8196, 785.0, 247.0),
    "C3H8":     (6.82107, 803.81, 247.04),
    "C4s":      (6.82485, 943.45, 239.71),
    "C5_Above": (6.85221, 1064.63, 232.0),
    "C6_To_C8": (6.87776, 1171.53, 224.37),
    "C9_Plus":  (6.93370, 1429.46, 209.28),
    "Water":    (8.07131, 1730.63, 233.426),
}


def _antoine_pvap(component: str, T_celsius: float) -> float:
    """Vapor pressure in bar from Antoine equation."""
    if component not in _ANTOINE:
        return 0.0
    A, B, C = _ANTOINE[component]
    log_p_mmhg = A - B / (C + T_celsius)
    return 10.0 ** log_p_mmhg / 750.062  # mmHg -> bar


def flash_drum_simplified(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
) -> FlashResult:
    """Simplified Raoult's-law flash (Antoine + Rachford-Rice)."""
    result = FlashResult(
        T_flash=T_AC_out,
        P_flash_kgcm2=P_dis - dp_drum,
        is_approximate=True,
        method="raoult-antoine",
    )

    P_bar = (P_dis - dp_drum + ATM_KGCM2) * 0.980665  # kg/cm2 -> bar

    all_comps = COMPONENTS + ["Water"]
    z = {}  # Feed mole fractions
    total_moles = 0.0
    for c in COMPONENTS:
        z[c] = ac_molar.get(c, 0.0)
        total_moles += z[c]
    z["Water"] = water_moles
    total_moles += water_moles

    if total_moles <= 0:
        result.error = "No flow to flash"
        return result

    for c in all_comps:
        z[c] /= total_moles

    # K-values from Raoult
    K = {}
    for c in all_comps:
        Pvap = _antoine_pvap(c, T_AC_out)
        K[c] = Pvap / P_bar if P_bar > 0 else 1.0

    # Rachford-Rice solve for vapor fraction V
    def rachford_rice(V):
        return sum(z[c] * (K[c] - 1.0) / (1.0 + V * (K[c] - 1.0))
                   for c in all_comps if z[c] > 1e-15)

    V_lo, V_hi = 0.0, 1.0
    for _ in range(200):
        V_mid = (V_lo + V_hi) / 2.0
        if rachford_rice(V_mid) > 0:
            V_lo = V_mid
        else:
            V_hi = V_mid
        if V_hi - V_lo < 1e-12:
            break
    V = (V_lo + V_hi) / 2.0

    result.vapor_fraction = V
    result.liquid_fraction = 1.0 - V
    result.vapor_flow_kmolh = total_moles * V
    result.liquid_flow_kmolh = total_moles * (1.0 - V)

    for c in all_comps:
        denom = 1.0 + V * (K[c] - 1.0)
        result.x[c] = z[c] / denom if denom != 0 else 0.0
        result.y[c] = K[c] * result.x[c]
        result.K_values[c] = K[c]

    _compute_vapor_mass_flows(result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3: DWSIM DTL (legacy, optional)
# ═══════════════════════════════════════════════════════════════════════════════

_dtl_calculator = None
_dtl_property_package = None


def _init_dtl(dtl_path: str) -> bool:
    """Initialize DWSIM DTL. Returns True on success."""
    global _dtl_calculator, _dtl_property_package

    if _dtl_calculator is not None:
        return True

    try:
        import clr
        import System

        dwsim_dir = dtl_path
        if os.path.isfile(dtl_path):
            dwsim_dir = os.path.dirname(dtl_path)

        dtl_dll = os.path.join(dwsim_dir, "DWSIM.Thermodynamics.StandaloneLibrary.dll")
        if not os.path.exists(dtl_dll):
            dtl_dll = os.path.join(dwsim_dir, "DWSIM.Thermodynamics.dll")
        if not os.path.exists(dtl_dll):
            for candidate in [
                os.path.join(dwsim_dir, "DWSIM.MathOps.dll"),
                os.path.join(dwsim_dir, "CapeOpen.dll"),
            ]:
                if os.path.exists(candidate):
                    clr.AddReference(candidate)

        clr.AddReference(dtl_dll)

        from DWSIM.Thermodynamics import CalculatorInterface, PropertyPackages

        calc = CalculatorInterface.Calculator()
        calc.Initialize()

        pr = PropertyPackages.PengRobinsonPropertyPackage(True)
        calc.TransferCompounds(pr)

        _dtl_calculator = calc
        _dtl_property_package = pr
        logger.info("DWSIM DTL initialized from %s", dtl_path)
        return True

    except Exception as e:
        logger.warning("DWSIM DTL initialization failed: %s", e)
        _dtl_calculator = None
        _dtl_property_package = None
        return False


def is_dtl_available() -> bool:
    return _dtl_calculator is not None


def flash_drum_dtl(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
) -> FlashResult:
    """Run a DWSIM DTL PT flash on the aftercooler outlet stream."""
    if _dtl_calculator is None:
        return FlashResult(error="DTL not initialized")

    result = FlashResult(
        T_flash=T_AC_out,
        P_flash_kgcm2=P_dis - dp_drum,
        method="dwsim-dtl-PR",
    )

    try:
        all_comps = COMPONENTS + ["Water"]
        comp_names = []
        molar_flows = []

        for c in all_comps:
            flow = water_moles if c == "Water" else ac_molar.get(c, 0.0)
            if flow > 1e-9:
                comp_names.append(DWSIM_NAMES[c])
                molar_flows.append(flow)

        total_molar = sum(molar_flows)
        if total_molar <= 0:
            result.error = "No flow to flash"
            return result

        mole_fracs = [f / total_molar for f in molar_flows]

        import System
        comp_array = System.Array[System.String](comp_names)
        frac_array = System.Array[System.Double](mole_fracs)

        ms = _dtl_calculator.CreateMaterialStream(comp_array, frac_array)
        ms.SetPropertyPackage(_dtl_property_package)
        ms.SetTemperature(T_AC_out + K_OFFSET)
        P_flash_Pa = (P_dis - dp_drum + ATM_KGCM2) * 1e5
        ms.SetPressure(P_flash_Pa)
        ms.SetMolarFlow(total_molar / 3.6)
        ms.SetFlashSpec("PT")
        ms.Calculate()

        result.vapor_fraction = float(ms.GetProp("phasemolarfraction", "Vapor", "", "", "")[0])
        result.liquid_fraction = 1.0 - result.vapor_fraction
        result.vapor_flow_kmolh = total_molar * result.vapor_fraction
        result.liquid_flow_kmolh = total_molar * result.liquid_fraction

        comp_map_rev = {v: k for k, v in DWSIM_NAMES.items()}
        for i, name in enumerate(comp_names):
            cgc_name = comp_map_rev.get(name, name)
            yi = float(ms.GetProp("fraction", "Vapor", "", name, "mole")[0]) if result.vapor_fraction > 1e-12 else 0.0
            xi = float(ms.GetProp("fraction", "Liquid1", "", name, "mole")[0]) if result.liquid_fraction > 1e-12 else 0.0
            result.y[cgc_name] = yi
            result.x[cgc_name] = xi
            result.K_values[cgc_name] = yi / xi if xi > 1e-15 else float('inf')

        for c in all_comps:
            result.y.setdefault(c, 0.0)
            result.x.setdefault(c, 0.0)
            result.K_values.setdefault(c, 0.0)

        _compute_vapor_mass_flows(result)
        return result

    except Exception as e:
        result.error = str(e)
        result.is_approximate = True
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Common helper
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_vapor_mass_flows(result: FlashResult):
    """Compute vapor mass flows and dry mass fractions from vapor mole fracs."""
    all_comps = COMPONENTS + ["Water"]
    total_mass = 0.0
    water_mass = 0.0

    for c in all_comps:
        mw_c = MW.get(c, WATER_MW)
        mass_c = result.y.get(c, 0.0) * result.vapor_flow_kmolh * mw_c
        result.vapor_mass_flows[c] = mass_c
        total_mass += mass_c
        if c == "Water":
            water_mass = mass_c

    result.vapor_flow_kgh = total_mass
    dry_mass = total_mass - water_mass
    result.vapor_dry_mass_flow = dry_mass

    if dry_mass > 0:
        for c in COMPONENTS:
            result.vapor_dry_mass_fracs[c] = result.vapor_mass_flows.get(c, 0.0) / dry_mass
    result.vapor_water_mass_frac = water_mass / total_mass if total_mass > 0 else 0.0

    # Liquid mass flow
    liquid_mass = 0.0
    for c in all_comps:
        mw_c = MW.get(c, WATER_MW)
        liquid_mass += result.x.get(c, 0.0) * result.liquid_flow_kmolh * mw_c
    result.liquid_flow_kgh = liquid_mass


# ═══════════════════════════════════════════════════════════════════════════════
# Main dispatcher: 3-tier cascade
# ═══════════════════════════════════════════════════════════════════════════════

def run_flash(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
    dtl_path: str = "",
) -> FlashResult:
    """
    Run flash drum with 3-tier cascade:
      1. thermo (PR EOS) -- pip-installable, production-grade
      2. Simplified Raoult's law -- zero-dependency fallback
      3. DWSIM DTL -- optional if installed locally

    If DTL path is provided and DTL is available, it takes priority.
    Otherwise thermo is tried first, then Raoult's law.
    """

    # Tier 3 (highest priority if explicitly configured): DWSIM DTL
    if dtl_path:
        if not is_dtl_available():
            _init_dtl(dtl_path)
        if is_dtl_available():
            dtl_result = flash_drum_dtl(ac_molar, water_moles, T_AC_out, P_dis, dp_drum)
            if not dtl_result.error:
                return dtl_result
            logger.warning("DTL flash failed (%s), falling through to thermo", dtl_result.error)

    # Tier 1: thermo (PR EOS)
    if is_thermo_available():
        thermo_result = flash_drum_thermo(ac_molar, water_moles, T_AC_out, P_dis, dp_drum)
        if not thermo_result.error:
            return thermo_result
        logger.warning("thermo flash failed (%s), falling back to Raoult's law", thermo_result.error)

    # Tier 2: Simplified Raoult's law
    return flash_drum_simplified(ac_molar, water_moles, T_AC_out, P_dis, dp_drum)
