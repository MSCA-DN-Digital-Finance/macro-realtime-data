# Real-time macro data layer (US, euro area, Italy)

A validated, reproducible data layer for forecasting **interest rates, inflation and unemployment** in the US, the
euro area and Italy, with **real-time vintages**: a forecaster at any date sees only the data published by that point.

Part of IRP 15, *Deep Generation of Financial Time Series*, in the MSCA Doctoral Network
[Digital Finance](https://www.digital-finance-msca.com/) (Horizon Europe, GA 101119635). It feeds the project's
macro-forecasting benchmark (P1) and forecast-conditioned scenario generation (P2).

**Status (2026-10-29):** 27 datasets, 1,060 series, 7.2 M observations; **133/133 validation checks pass.**

- [`data/CATALOG.md`](data/CATALOG.md): every dataset with its source, coverage, row count and role.
- [`data/VALIDATION.md`](data/VALIDATION.md): the 133 checks and their results.
- [`data/manifest_raw.csv`](data/manifest_raw.csv): sha256 of every raw file, so a rebuilt snapshot can be verified.

## Sources (all free and official)

| Source | What |
|---|---|
| [FRED](https://fred.stlouisfed.org) | US rates, prices, labour, expectations, markets; a FRED-MD panel rebuilt from FRED ids (117 series) |
| [ECB Data Portal](https://data.ecb.europa.eu) | policy and money-market rates, €STR/EONIA, HICP, yield curves, ECB SPF, ECB Real-Time Database |
| [Eurostat](https://ec.europa.eu/eurostat/web/main/data/database) | unemployment, HICP (ECOICOP v2) cross-checks |
| [Philadelphia Fed RTDSM](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists) | real-time vintages: CPI, core CPI, payrolls, IP, unemployment, real GDP |
| [Philadelphia Fed SPF](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters) | US professional forecasts (benchmark) |
| [Federal Reserve Board](https://www.federalreserve.gov/data/nominal-yield-curve.htm) | Gürkaynak–Sack–Wright zero-coupon curve |
| [Kenneth French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | daily factor and industry returns |

No API keys are needed. The data themselves are **not** redistributed here: each provider's terms apply, and
`collect.py` downloads them directly.

## Data-quality rules

1. Raw files are stored exactly as served and never edited; every file is hashed in the manifest.
2. The tidy step only reshapes (long format `series, date, value`, plus `vintage` for real-time data).
   Transformations happen later, in analysis code.
3. Every collection is followed by `validate.py`: no gaps, duplicates or missing values, freshness, plausibility,
   and exact cross-source matches. For example, the ECB deposit rate equals FRED's on 10,164 days, and ECB HICP
   equals Eurostat's on 357 months for the euro area, Italy and Germany.
4. A dated copy of the raw data is frozen before any result is reported.

## Data problems found and how they are handled

| Problem | Effect | Handling |
|---|---|---|
| HICP moved to the ECOICOP v2 classification in January 2026 | History revised: 7 % of euro-area y/y rates changed by 0.1 pp | Both classifications kept, so forecasts can be scored on what was known at the time |
| ECB Real-Time Database core HICP stops at 2025-05 | No real-time euro-area core inflation after that | Rebuilt from the new series' release history |
| Euro area became EA21 (Bulgaria) in January 2026 | Eurostat and ECB aggregates differ | The aggregate used is recorded for every result |
| €STR starts Oct 2019, EONIA ends Jan 2022 | No single overnight-rate history | Spliced with the ECB's own definition (EONIA = €STR + 8.5 bp) |
| US government shutdown: no October 2025 CPI or unemployment release | A missing month in the targets | Recorded as missing, not filled |
| The official FRED-MD file blocks scripted downloads | Standard macro panel cannot be fetched automatically | Rebuilt from FRED ids; every difference listed in `dgfts/spec/fredmd_notes.txt` |

## Use

Python ≥ 3.10 with `numpy`, `pandas`, `pyarrow`, `requests`, `openpyxl`.

```sh
python scripts/collect.py              # everything, ~10 min → data/raw/ (as served) + data/tidy/*.parquet
python scripts/collect.py ecb_spf rtdsm  # or only some datasets
python scripts/validate.py             # → data/VALIDATION.md, data/CATALOG.md; exit code 1 if any check fails
```

| Path | What |
|---|---|
| `dgfts/sources.py` | one download + parse pair per source |
| `dgfts/catalog.py` | what is collected and why (series lists, ECB keys, Eurostat filters) |
| `dgfts/spec/` | FRED-MD series list, transformation codes, differences from the official file |
| `scripts/collect.py` | download, tidy, hash |
| `scripts/validate.py` | integrity, freshness, plausibility and cross-source checks |

## Licence and citation

Code: MIT ([LICENSE](LICENSE)). Data: the terms of each provider above.

Author: A.-T. Ginavar, MSCA Digital Finance doctoral candidate (IRP 15).
