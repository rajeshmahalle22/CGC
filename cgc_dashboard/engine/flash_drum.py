"""
Flash drum calculation using DWSIM Standalone Thermodynamics Library (DTL).
Falls back gracefully when DTL is unavailable.
"""

from __future__ import annotations
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cgc_dashboard.engine.constants import (
    COMPONENTS, MW, WATER_MW, K_OFFSET, ATM_KGCM2, DWSIM_NAMES,
)


@dataclass
class FlashResult:
    """Results from a PT flash calculation."""
    T_flash: float = 0.0           # Flash temperature [°C]
    P_flash_kgcm2: float = 0.0    # Flash pressure [kg/cm²]
    vapor_fraction: float = 0.0    # Molar vapor fraction
    liquid_fraction: float = 0.0   # Molar liquid fraction

    vapor_flow_kmolh: float = 0.0  # Vapor molar flow [kmol/h]
    liquid_flow_kmolh: float = 0.0 # Liquid molar flow [kmol/h]
    vapor_flow_kgh: float = 0.0    # Vapor mass flow [kg/h]
    liquid_flow_kgh: float = 0.0   # Liquid mass flow [kg/h]

    # Compositions (component name → fraction)
    y: Dict[str, float] = field(default_factory=dict)  # Vapor mole fracs
    x: Dict[str, float] = field(default_factory=dict)  # Liquid mole fracs
    K_values: Dict[str, float] = field(default_factory=dict)

    # Phase properties
    vapor_MW: float = 0.0
    liquid_MW: float = 0.0
    vapor_density: float = 0.0     # kg/m³
    liquid_density: float = 0.0    # kg/m³
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
    error: str = ""


# ---------------------------------------------------------------------------
# DTL Flash Drum (DWSIM integration)
# ---------------------------------------------------------------------------

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

        # Add DLL references
        dwsim_dir = dtl_path
        if os.path.isfile(dtl_path):
            dwsim_dir = os.path.dirname(dtl_path)

        # Try standalone thermodynamics library first
        dtl_dll = os.path.join(dwsim_dir, "DWSIM.Thermodynamics.StandaloneLibrary.dll")
        if not os.path.exists(dtl_dll):
            # Try full DWSIM automation
            dtl_dll = os.path.join(dwsim_dir, "DWSIM.Thermodynamics.dll")
        if not os.path.exists(dtl_dll):
            # Try common DWSIM installation
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
        return True

    except Exception:
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
    """
    Run a DWSIM DTL PT flash on the aftercooler outlet stream.

    Parameters
    ----------
    ac_molar   : Aftercooler molar flows per component [kmol/h]
    water_moles: Water molar flow [kmol/h]
    T_AC_out   : Aftercooler outlet temperature [°C]
    P_dis      : Stage discharge pressure [kg/cm²]
    dp_drum    : Flash drum pressure drop [kg/cm²]
    """
    if _dtl_calculator is None:
        return FlashResult(error="DTL not initialized")

    result = FlashResult(
        T_flash=T_AC_out,
        P_flash_kgcm2=P_dis - dp_drum,
    )

    try:
        # Build component list and mole fractions
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

        # Create material stream and run flash
        ms = _dtl_calculator.CreateMaterialStream(comp_array, frac_array)
        ms.SetPropertyPackage(_dtl_property_package)
        ms.SetTemperature(T_AC_out + K_OFFSET)
        P_flash_Pa = (P_dis - dp_drum + ATM_KGCM2) * 1e5  # kg/cm² gauge → Pa
        ms.SetPressure(P_flash_Pa)
        ms.SetMolarFlow(total_molar / 3.6)  # kmol/h → mol/s
        ms.SetFlashSpec("PT")
        ms.Calculate()

        # Extract results
        result.vapor_fraction = float(ms.GetProp("phasemolarfraction", "Vapor", "", "", "")[0])
        result.liquid_fraction = 1.0 - result.vapor_fraction

        result.vapor_flow_kmolh = total_molar * result.vapor_fraction
        result.liquid_flow_kmolh = total_molar * result.liquid_fraction

        # Extract compositions
        comp_map_rev = {v: k for k, v in DWSIM_NAMES.items()}
        for i, name in enumerate(comp_names):
            cgc_name = comp_map_rev.get(name, name)
            yi = float(ms.GetProp("fraction", "Vapor", "", name, "mole")[0]) if result.vapor_fraction > 1e-12 else 0.0
            xi = float(ms.GetProp("fraction", "Liquid1", "", name, "mole")[0]) if result.liquid_fraction > 1e-12 else 0.0
            result.y[cgc_name] = yi
            result.x[cgc_name] = xi
            result.K_values[cgc_name] = yi / xi if xi > 1e-15 else float('inf')

        # Fill missing components with zero
        for c in all_comps:
            result.y.setdefault(c, 0.0)
            result.x.setdefault(c, 0.0)
            result.K_values.setdefault(c, 0.0)

        # Mass flows from vapor
        _compute_vapor_mass_flows(result)

        return result

    except Exception as e:
        result.error = str(e)
        result.is_approximate = True
        return result


# ---------------------------------------------------------------------------
# Simplified flash (Raoult's law fallback)
# ---------------------------------------------------------------------------

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
    return 10.0 ** log_p_mmhg / 750.062  # mmHg → bar


def flash_drum_simplified(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
) -> FlashResult:
    """Simplified Raoult's-law flash when DTL is unavailable."""
    result = FlashResult(
        T_flash=T_AC_out,
        P_flash_kgcm2=P_dis - dp_drum,
        is_approximate=True,
    )

    P_bar = (P_dis - dp_drum + ATM_KGCM2) * 0.980665  # kg/cm² → bar

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


# ---------------------------------------------------------------------------
# Common helper
# ---------------------------------------------------------------------------

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


def run_flash(
    ac_molar: Dict[str, float],
    water_moles: float,
    T_AC_out: float,
    P_dis: float,
    dp_drum: float,
    dtl_path: str = "",
) -> FlashResult:
    """
    Run flash drum — uses DTL if available, otherwise simplified Raoult's.
    """
    if dtl_path and not is_dtl_available():
        _init_dtl(dtl_path)

    if is_dtl_available():
        return flash_drum_dtl(ac_molar, water_moles, T_AC_out, P_dis, dp_drum)
    else:
        return flash_drum_simplified(ac_molar, water_moles, T_AC_out, P_dis, dp_drum)
