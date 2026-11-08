"""Export the tidy data for redistribution → data/public/<dataset>.parquet + data/public/SOURCES.md.

Same long format as data/tidy/ (`series, date, value` [+ `vintage`]). Series whose provider requires
pre-approval for redistribution (FRED tag "copyrighted: pre-approval required") are dropped; they can
still be downloaded with collect.py. Run after collect.py and validate.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TIDY, OUT = ROOT / "data" / "tidy", ROOT / "data" / "public"

# FRED series tagged "copyrighted: pre-approval required" (checked on fred.stlouisfed.org, 2026-11-08)
RESTRICTED = {
    "SP500": "S&P Dow Jones Indices",
    "DJIA": "S&P Dow Jones Indices",
    "NASDAQCOM": "Nasdaq",
    "BAMLC0A0CM": "ICE Data Indices",
    "BAMLH0A0HYM2": "ICE Data Indices",
}

SOURCES = """# Sources and terms of the public data files

Each file is `data/public/<dataset>.parquet` in long format `series, date, value` (+ `vintage` for real-time data);
`data/CATALOG.md` describes every dataset. Please cite the original provider when you use the data.

| Prefix | Provider | Terms |
|---|---|---|
| `fred_*` | Federal Reserve Bank of St. Louis, FRED (and the original source named on each series page) | Public domain or "citation required" per series. Series needing pre-approval are removed: {restricted} |
| `ecb_*` | European Central Bank, ECB Data Portal | Free reuse with the ECB named as source |
| `eurostat_*` | Eurostat | Free reuse with Eurostat named as source (CC BY 4.0) |
| `rtdsm`, `spf_us` | Federal Reserve Bank of Philadelphia (Real-Time Data Set for Macroeconomists; Survey of Professional Forecasters) | Free, cite the Philadelphia Fed |
| `gsw_curve` | Federal Reserve Board; Gürkaynak, Sack and Wright (2007) | Public, cite Gürkaynak, Sack and Wright (2007) |
| `french` | Kenneth R. French Data Library | Free, cite the Kenneth R. French Data Library |
"""


def export(name: str) -> tuple[str, int, int]:
    """Copy one tidy dataset to data/public/, without restricted series; return (name, rows kept, rows dropped)."""
    df = pd.read_parquet(TIDY / f"{name}.parquet")
    keep = ~df["series"].isin(list(RESTRICTED))
    df[keep].to_parquet(OUT / f"{name}.parquet", index=False)
    return name, int(keep.sum()), int((~keep).sum())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [export(p.stem) for p in sorted(TIDY.glob("*.parquet"))]
    restricted = ", ".join(f"{s} ({o})" for s, o in RESTRICTED.items())
    (OUT / "SOURCES.md").write_text(SOURCES.format(restricted=restricted))
    for name, kept, dropped in rows:
        print(f"{name:32s} {kept:>10,d} rows" + (f"  ({dropped:,d} restricted rows dropped)" if dropped else ""))
    left = {s for p in OUT.glob("*.parquet") for s in pd.read_parquet(p, columns=["series"])["series"].unique()}
    assert not left & set(RESTRICTED), "restricted series left in data/public/"
    print(f"{len(rows)} datasets → {OUT.relative_to(ROOT)}; no restricted series left")
    return 0


if __name__ == "__main__":
    sys.exit(main())
