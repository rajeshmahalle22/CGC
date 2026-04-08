"""
CGC Generic Stage Calculator — Constants & Coefficient Tables
All values extracted from CGC_Generic_Engine_v3.xlsx CALCULATIONS sheet formulas.
"""

# Component order (12 species)
COMPONENTS = [
    "H2", "CH4", "C2H2", "C2H4", "C2H6",
    "C3H4", "C3H6", "C3H8", "C4s", "C5_Above",
    "C6_To_C8", "C9_Plus",
]

# Molecular weights used in Step 6 molar-flow denominators (from Excel D89–D100)
# These are the ACTUAL values the Excel uses — heavier lumps differ from textbook values
MW = {
    "H2": 2.0,
    "CH4": 16.0,
    "C2H2": 26.0,
    "C2H4": 28.0,
    "C2H6": 30.0,
    "C3H4": 40.0,
    "C3H6": 42.0,
    "C3H8": 44.0,
    "C4s": 55.16,
    "C5_Above": 75.86,
    "C6_To_C8": 87.96,
    "C9_Plus": 166.56,
    "Water": 18.0,
}

# Physical constants
R_GAS = 8.314          # Universal gas constant [J/mol/K]
ATM_KGCM2 = 0.98066   # 1 atm in kg/cm²  (gauge → abs offset)
G = 9.81               # Gravity [m/s²]
K_OFFSET = 273.15      # °C to K

Z_SUC = 0.976          # Suction compressibility (vol flow suction)
Z_DIS = 0.971          # Discharge compressibility (vol flow discharge)
Z_HEAD = 0.974         # Compressibility used in polytropic head (D144)

EPSILON = -1e-6        # Guard value from Excel MAX(Epsilon, …)
AIR_MW = 28.97         # For MW ratio in K-value correlation (D137)
WATER_MW = 18.0
WASH_OIL_CP = 239.0    # Wash oil Cp constant [J/mol/K] used in Mix_Cp (D126)
VOL_CONST = 0.08478    # 8.478E-2 factor in volumetric flow formulas (D174/D175)

# Hardcoded next-stage water mass fraction for condensation calc (D167)
NEXT_STAGE_WATER_MF_CONST = 0.0038

# Wash oil heat constant for AC duty [kJ/kg] (from D169 formula: wash_oil_flow * 650)
WASH_OIL_HEAT_CONST = 650.0

# DWSIM compound name mapping
DWSIM_NAMES = {
    "H2": "Hydrogen",
    "CH4": "Methane",
    "C2H2": "Acetylene",
    "C2H4": "Ethylene",
    "C2H6": "Ethane",
    "C3H4": "Propadiene",
    "C3H6": "Propylene",
    "C3H8": "Propane",
    "C4s": "N-butane",
    "C5_Above": "N-pentane",
    "C6_To_C8": "N-hexane",
    "C9_Plus": "N-nonane",
    "Water": "Water",
}
