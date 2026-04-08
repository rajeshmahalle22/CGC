"""
Shomate Cp polynomials — coefficients extracted from CGC_Generic_Engine_v3.xlsx
CALCULATIONS sheet cells D113–D125 (discharge T) and D149–D161 (AC outlet T).

Standard Shomate: Cp = A + B*t + C*t² + D*t³ + E/t²  [J/mol/K],  t = T(K)/1000
Linear species:   Cp = slope*t + intercept             [J/mol/K]
"""

from cgc_dashboard.engine.constants import K_OFFSET

# 5-term Shomate coefficients: (A, B, C, D, E)
_SHOMATE_5 = {
    "H2":       (33.066178, -11.363417, 11.432816, -2.772874, -0.158558),
    "CH4":      (-0.703029, 108.4773, -42.52157, 5.862788, 0.678565),
    "C2H2":     (40.68697, 40.73279, -16.1784, 3.669741, -0.658411),
    "C2H4":     (-6.38788, 184.4019, -112.9718, 28.49593, 0.31554),
    "C2H6":     (6.08160993967773, 173.58246031667, -66.9190547406319,
                 9.08912024736972, 0.129136456966982),
    "C3H6":     (13.9948838501972, 197.060432042919, -78.0916333928503,
                 10.8145462152084, 0.0285826552711022),
    "C3H8":     (12.6608072783283, 232.070245794953, -70.3446118121155,
                 0.60714221002859, 0.0269571781100411),
    "C6_To_C8": (10.259, -0.206, 39.064, -13.301, 0.0),
    "C9_Plus":  (-65.13, 284.87, -53.98, 0.0, 3.91),
    "Water":    (-203.606, 1523.29, -3196.41, 2474.455, 3.855326),
}

# Linear species: Cp = slope * t + intercept
_LINEAR = {
    "C3H4":     (128.1, 20.85),
    "C4s":      (258.2, 21.49),
    "C5_Above": (305.2, -8.56),
}


def shomate_cp(component: str, T_celsius: float) -> float:
    """Return Cp in J/(mol·K) for *component* at *T_celsius* °C."""
    t = (T_celsius + K_OFFSET) / 1000.0  # kilo-Kelvin factor

    if component in _LINEAR:
        slope, intercept = _LINEAR[component]
        return slope * t + intercept

    if component in _SHOMATE_5:
        A, B, C, D, E = _SHOMATE_5[component]
        return A + B * t + C * t**2 + D * t**3 + E / t**2

    raise ValueError(f"Unknown component: {component}")
