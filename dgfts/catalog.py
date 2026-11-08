"""What we collect, and why. One entry = one tidy dataset `data/tidy/<name>.parquet`.

`paper` says which paper the data serve (P1 forecasting benchmark, P2 scenario generation,
P3 causal inference). `role` is the job the data do in the design (see README.md).
"""
from __future__ import annotations

import csv
from pathlib import Path

SPEC = Path(__file__).parent / "spec"

FREDMD_IDS = [r["fred_id"] for r in csv.DictReader(open(SPEC / "fredmd_series.csv"))]

# ---- FRED, beyond the FRED-MD panel ------------------------------------------------------------
FRED_US_RATES = [  # policy + Treasury curve (daily), the "interest rates" targets
    "DFF", "EFFR", "SOFR", "DTB3", "DGS1MO", "DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS3", "DGS5",
    "DGS7", "DGS10", "DGS20", "DGS30", "DFEDTARU", "DFEDTARL", "DFEDTAR",
]
FRED_US_PRICES_LABOR = [  # inflation / unemployment targets and their close relatives
    "CPIAUCSL", "CPIAUCNS", "CPILFESL", "PCEPI", "PCEPILFE", "UNRATE", "NROU", "PAYEMS",
    "GDPC1", "GDPPOT", "USREC", "USRECD",
]
FRED_EXPECTATIONS = [  # market- and survey-based expectations (benchmarks + conditioning info)
    "T5YIE", "T10YIE", "T5YIFR", "DFII5", "DFII10", "MICH", "EXPINF1YR", "EXPINF10YR",
]
FRED_MARKETS = [  # daily market variables for scenario generation
    "SP500", "NASDAQCOM", "DJIA", "VIXCLS", "DEXUSEU", "DEXJPUS", "DEXUSUK", "DEXCHUS", "DTWEXBGS",
    "DCOILWTICO", "DCOILBRENTEU", "BAMLH0A0HYM2", "BAMLC0A0CM", "DBAA", "DAAA", "T10Y2Y", "T10Y3M",
    "NFCI", "STLFSI4", "WALCL",
]
FRED_EA_ON_FRED = [  # euro-area / Italy series that FRED mirrors (used for cross-checks)
    "ECBDFR", "ECBMRRFR", "IRLTLT01ITM156N", "IRLTLT01DEM156N", "IRLTLT01FRM156N", "IRLTLT01ESM156N",
]

# ---- ECB Data Portal (flow, key) ---------------------------------------------------------------
ECB = {
    "ecb_policy_rates": ("FM", "D.U2.EUR.4F.KR.DFR+MRR_FR+MRR_RT+MLFR.LEV"),
    "ecb_estr": ("EST", "B.EU000A2X2A25.WT"),
    "ecb_eonia": ("EON", "D.EONIA_TO.RATE"),
    "ecb_euribor": ("FM", "M.U2.EUR.RT.MM.EURIBOR1MD_+EURIBOR3MD_+EURIBOR6MD_+EURIBOR1YD_.HSTA"),
    # AAA-rated (G_N_A) and all-issuer (G_N_C) spot curves + Svensson parameters, daily from 2004
    "ecb_yc_spot": ("YC", "B.U2.EUR.4F.G_N_A+G_N_C.SV_C_YM.SR_3M+SR_6M+SR_1Y+SR_2Y+SR_3Y+SR_5Y+SR_7Y+SR_10Y+SR_15Y+SR_20Y+SR_30Y"),
    "ecb_yc_params": ("YC", "B.U2.EUR.4F.G_N_A+G_N_C.SV_C_YM.BETA0+BETA1+BETA2+BETA3+TAU1+TAU2"),
    # HICP: euro area + big-4; headline (000000), core ex energy & food (XEF000), energy, food,
    # services, non-energy industrial goods. The `HICP` flow (ECOICOP v2, from 2026) carries the full
    # history; the old `ICP` flow stops at 2025-12 and is kept only to compare old vs new classification.
    "ecb_hicp_rate": ("HICP", "M.U2+IT+DE+FR+ES.N.000000+XEF000+NRGY00+FOOD00+SERV00+IGXE00.4D0.ANR"),
    "ecb_hicp_index": ("HICP", "M.U2+IT+DE+FR+ES.N+Y.000000+XEF000..INX"),
    "ecb_icp_legacy_rate": ("ICP", "M.U2+IT+DE+FR+ES.N.000000+XEF000.4.ANR"),
    # 10-year government bond yields for convergence purposes (BTP, Bund, OAT, Bonos)
    "ecb_lt_yields": ("IRS", "M.IT+DE+FR+ES+NL+PT+GR.L.L40.CI.0000.EUR.N.Z"),
    "ecb_usd_fx": ("EXR", "D.USD+GBP+JPY+CHF.EUR.SP00.A"),
    # ECB Survey of Professional Forecasters: aggregate point forecasts, all horizons
    "ecb_spf": ("SPF", "Q.U2.HICP+CORE+UNEM+RGDP.POINT..Q.AVG"),
}

# ECB Real-Time Database: every published revision (vintage = VALID_FROM). Euro area, moving
# composition: unemployment, HICP headline index + annual rate, core HICP, real GDP (quarterly).
ECB_RTD = ("RTD", "M+Q.S0.S+N.L_UNETO+P_C_OV+P_C_XEFUN+YER.F+A+X+E")

# ---- Eurostat (dataset, filters) ---------------------------------------------------------------
EUROSTAT = {
    "eurostat_unemployment": ("une_rt_m", {"s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT", "sex": "T",
                                           "geo": ["EA21", "EU27_2020", "IT", "DE", "FR", "ES"]}),
    "eurostat_youth_unemployment": ("une_rt_m", {"s_adj": "SA", "age": "Y_LT25", "unit": "PC_ACT", "sex": "T",
                                                 "geo": ["EA21", "IT", "DE", "FR", "ES"]}),
    # HICP under ECOICOP v2 (coicop18 codes), full history 1997-: cross-check of the ECB HICP flow.
    "eurostat_hicp_ecoicop2": ("prc_hicp_minr", {"unit": "RCH_A", "coicop18": ["TOTAL", "TOT_X_NRG_FOOD"],
                                                 "geo": ["EA", "IT", "DE", "FR", "ES"]}),
    # Stops at 2025-12 (old ECOICOP); kept to cross-check the legacy ECB ICP series.
    "eurostat_hicp_manr": ("prc_hicp_manr", {"unit": "RCH_A", "coicop": ["CP00", "TOT_X_NRG_FOOD"],
                                             "geo": ["EA", "IT", "DE", "FR", "ES"]}),
}

# ---- Philadelphia Fed --------------------------------------------------------------------------
# Real-time vintage matrices (MvMd = monthly vintages of monthly data; QvMd = quarterly vintages).
RTDSM = ["pcpiMvMd", "pcpixMvMd", "employMvMd", "iptMvMd", "rucQvMd", "routputMvQd"]
SPF_US = ["medianLevel", "medianGrowth"]

# ---- Ken French data library -------------------------------------------------------------------
FRENCH = [
    "F-F_Research_Data_Factors_daily_CSV", "F-F_Research_Data_5_Factors_2x3_daily_CSV",
    "F-F_Momentum_Factor_daily_CSV", "49_Industry_Portfolios_daily_CSV",
    "F-F_Research_Data_Factors_CSV", "10_Industry_Portfolios_daily_CSV",
]

# name -> (paper, role, source description)
INFO = {
    "fred_md_panel": ("P1", "predictor panel (US, 117 series, levels)", "FRED, FRED-MD ids rebuilt"),
    "fred_us_rates": ("P1,P2", "targets: policy rate + Treasury curve", "FRED daily"),
    "fred_us_prices_labor": ("P1", "targets: inflation, unemployment, output gap", "FRED"),
    "fred_expectations": ("P1,P2", "market/survey expectations", "FRED"),
    "fred_markets": ("P2", "market variables for scenarios", "FRED daily"),
    "fred_ea_mirror": ("check", "cross-check of ECB data", "FRED"),
    "ecb_policy_rates": ("P1,P3", "targets: ECB policy rates", "ECB FM"),
    "ecb_estr": ("P1,P2", "overnight rate (2019-)", "ECB EST"),
    "ecb_eonia": ("P1,P2", "overnight rate (1999-2022)", "ECB EON"),
    "ecb_euribor": ("P1,P2", "money-market rates", "ECB FM"),
    "ecb_yc_spot": ("P1,P2", "euro-area zero curve (2004-)", "ECB YC"),
    "ecb_yc_params": ("P2", "Svensson factors of the curve", "ECB YC"),
    "ecb_hicp_rate": ("P1", "targets: euro-area/big-4 inflation", "ECB HICP"),
    "ecb_hicp_index": ("P1", "HICP index levels (NSA + SA)", "ECB HICP"),
    "ecb_icp_legacy_rate": ("check", "HICP, old classification (to 2025-12)", "ECB ICP"),
    "eurostat_hicp_ecoicop2": ("check", "cross-check of ECB HICP (ECOICOP v2)", "Eurostat prc_hicp_minr"),
    "ecb_lt_yields": ("P1,P2", "10y sovereign yields incl. BTP", "ECB IRS"),
    "ecb_usd_fx": ("P2", "EUR FX reference rates", "ECB EXR"),
    "ecb_spf": ("P1", "benchmark: ECB professional forecasters", "ECB SPF"),
    "ecb_rtd": ("P1", "real-time vintages of EA targets", "ECB RTD (includeHistory)"),
    "eurostat_unemployment": ("P1", "targets: unemployment EA/big-4", "Eurostat une_rt_m"),
    "eurostat_youth_unemployment": ("P1", "youth unemployment", "Eurostat une_rt_m"),
    "eurostat_hicp_manr": ("check", "cross-check of ECB HICP (to 2025-12)", "Eurostat"),
    "rtdsm": ("P1", "real-time vintages of US targets", "Philadelphia Fed RTDSM"),
    "spf_us": ("P1", "benchmark: US professional forecasters", "Philadelphia Fed SPF"),
    "french": ("P2", "daily equity factor/industry returns (1926-)", "Ken French library"),
    "gsw_curve": ("P2", "daily US zero curve 1961- (Svensson)", "Fed Board feds200628"),
}
