"""Validate data/tidy/*.parquet and write data/CATALOG.md + data/VALIDATION.md.

Three kinds of check:
  1. integrity: each dataset is non-empty, has no NaN values and no duplicate (series, date[, vintage]);
  2. freshness + plausibility: the headline targets end recently and stay inside sane ranges;
  3. cross-source agreement: the same quantity from two independent sources must agree
     (exactly where both copy one primary source, within a stated tolerance otherwise).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TIDY = ROOT / "data" / "tidy"
TODAY = pd.Timestamp.today().normalize()

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return ok


def info(name: str, detail: str):
    results.append((name, None, detail))
    print(f"INFO  {name}  {detail}")


def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(TIDY / f"{name}.parquet")


def series(ds: pd.DataFrame, sid: str) -> pd.Series:
    s = ds[ds["series"] == sid].set_index("date")["value"].sort_index()
    if s.empty:
        raise KeyError(sid)
    return s


# ------------------------------------------------------------------------------------------------
def integrity(data: dict[str, pd.DataFrame]):
    for name, df in data.items():
        keys = ["series", "date"] + (["vintage"] if "vintage" in df.columns else [])
        check(f"{name}: non-empty", len(df) > 0, f"{len(df):,} rows")
        check(f"{name}: no NaN", not df["value"].isna().any())
        check(f"{name}: no duplicate keys", not df.duplicated(keys).any())


# (dataset, series, max age of last obs in days, (lo, hi))
FRESH = [
    ("fred_us_rates", "DFF", 10, (0, 25)),
    ("fred_us_rates", "DGS10", 10, (0, 20)),
    ("fred_us_prices_labor", "CPIAUCSL", 75, (20, 500)),
    ("fred_us_prices_labor", "PCEPI", 75, (10, 200)),
    ("fred_us_prices_labor", "UNRATE", 75, (2, 16)),
    ("fred_markets", "VIXCLS", 10, (5, 100)),
    ("ecb_policy_rates", "FM.D.U2.EUR.4F.KR.DFR.LEV", 10, (-1, 6)),
    ("ecb_estr", "EST.B.EU000A2X2A25.WT", 10, (-1, 6)),
    ("ecb_yc_spot", "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", 10, (-1.5, 6)),
    ("ecb_hicp_rate", "HICP.M.U2.N.000000.4D0.ANR", 75, (-3, 12)),
    ("ecb_hicp_rate", "HICP.M.U2.N.XEF000.4D0.ANR", 75, (-1, 8)),
    ("ecb_hicp_rate", "HICP.M.IT.N.000000.4D0.ANR", 75, (-3, 15)),
    ("ecb_rtd", "RTD.M.S0.S.L_UNETO.F", 120, (5, 13)),
    ("ecb_eonia", "EON.D.EONIA_TO.RATE", 10**4, (-1, 7)),
    ("ecb_lt_yields", "IRS.M.IT.L.L40.CI.0000.EUR.N.Z", 75, (-1, 15)),
    ("eurostat_unemployment", "eurostat_unemployment:SA.TOTAL.PC_ACT.T.EA21", 120, (4, 15)),
    ("eurostat_unemployment", "eurostat_unemployment:SA.TOTAL.PC_ACT.T.IT", 120, (4, 15)),
    ("gsw_curve", "SVENY10", 15, (0, 16)),
]


def freshness(data):
    for ds, sid, age, (lo, hi) in FRESH:
        try:
            s = series(data[ds], sid)
        except KeyError:
            check(f"{ds}/{sid}: present", False)
            continue
        days = (TODAY - s.index[-1]).days
        # monthly series are dated at the start of the month, so add a month of slack
        check(f"{sid}: last obs within {age} d", days <= age + 31 * (age >= 60), f"last {s.index[-1].date()}")
        check(f"{sid}: values in [{lo}, {hi}]", s.between(lo, hi).all(), f"min {s.min():.2f} max {s.max():.2f}")


# ------------------------------------------------------------------------------------------------
def cross_source(data):
    # 1. ECB deposit rate: ECB portal vs FRED's ECBDFR (FRED copies the ECB) → exact
    a = series(data["ecb_policy_rates"], "FM.D.U2.EUR.4F.KR.DFR.LEV")
    b = series(data["fred_ea_mirror"], "ECBDFR")
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    check("ECB DFR == FRED ECBDFR (exact, all common days)", (j.iloc[:, 0] == j.iloc[:, 1]).all(),
          f"{len(j)} days, {int((j.iloc[:, 0] != j.iloc[:, 1]).sum())} mismatches")

    # 2. HICP y/y, ECOICOP v2: ECB `HICP` flow vs Eurostat prc_hicp_minr (both one decimal) → equal
    for geo, ecb_area in [("EA", "U2"), ("IT", "IT"), ("DE", "DE")]:
        for ecb_item, es_item in [("000000", "TOTAL"), ("XEF000", "TOT_X_NRG_FOOD")]:
            a = series(data["ecb_hicp_rate"], f"HICP.M.{ecb_area}.N.{ecb_item}.4D0.ANR")
            b = series(data["eurostat_hicp_ecoicop2"], f"eurostat_hicp_ecoicop2:RCH_A.{es_item}.{geo}")
            j = pd.concat([a, b], axis=1, join="inner").dropna()
            d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
            bad = d[d > 0.05 + 1e-9]
            check(f"HICP {geo} {es_item} y/y: ECB vs Eurostat equal (ECOICOP v2)", bad.empty,
                  f"{len(j)} months {j.index[0].date()}–{j.index[-1].date()}, mismatches {len(bad)}"
                  + (f" at {[str(x.date()) for x in bad.index[:3]]}" if len(bad) else ""))

    # 2b. legacy (old ECOICOP) ECB vs Eurostat, to 2025-12
    a = series(data["ecb_icp_legacy_rate"], "ICP.M.U2.N.000000.4.ANR")
    b = series(data["eurostat_hicp_manr"], "eurostat_hicp_manr:RCH_A.CP00.EA")
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
    bad = d[d > 0.05 + 1e-9]
    check("HICP EA y/y legacy: ECB ICP vs Eurostat manr, ≤ 1 mismatch", len(bad) <= 1,
          f"{len(j)} months, mismatches {len(bad)} {[f'{x.date()}: {v:.1f}' for x, v in bad.items()]}")

    # 2c. information only: how much the 2026 reclassification revised history
    a = series(data["ecb_icp_legacy_rate"], "ICP.M.U2.N.000000.4.ANR")
    b = series(data["ecb_hicp_rate"], "HICP.M.U2.N.000000.4D0.ANR")
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
    info("HICP EA y/y: old vs new classification (history revision)",
         f"{len(j)} months, identical {(d < 0.05).mean():.1%}, max |diff| {d.max():.1f} pp")

    # 3. Italian 10y (BTP): ECB IRS vs FRED/OECD mirror → within 0.01 pp
    a = series(data["ecb_lt_yields"], "IRS.M.IT.L.L40.CI.0000.EUR.N.Z")
    b = series(data["fred_ea_mirror"], "IRLTLT01ITM156N")
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
    check("BTP 10y: ECB vs FRED(OECD) within 0.01 pp", (d <= 0.01 + 1e-9).mean() == 1.0,
          f"{len(j)} months, share within {(d <= 0.01 + 1e-9).mean():.3f}, max |diff| {d.max():.3f}")

    # 4. Real-time CPI: latest Philly vintage vs FRED today, on the last 10 years (CPI-U SA is
    #    revised only for seasonal factors each February; the vintage lags FRED by ≤ 1 release)
    rt = data["rtdsm"]
    p = rt[rt["series"] == "PCPI"]
    last = p[p["vintage"] == p["vintage"].max()].set_index("date")["value"]
    b = series(data["fred_us_prices_labor"], "CPIAUCSL")
    j = pd.concat([last, b], axis=1, join="inner").dropna().loc["2016":]
    d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
    check("CPI: latest RTDSM vintage == FRED CPIAUCSL (2016–, ±0.001)", (d <= 1e-3).all(),
          f"vintage {p['vintage'].max().date()}, {len(j)} months, max |diff| {d.max():.4f}")

    # 5. Unemployment: latest RTDSM vintage vs FRED (one decimal)
    u = rt[rt["series"] == "RUC"]
    last = u[u["vintage"] == u["vintage"].max()].set_index("date")["value"]
    j = pd.concat([last, series(data["fred_us_prices_labor"], "UNRATE")], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1]).abs()
    check("UNRATE: latest RTDSM vintage vs FRED, share equal ≥ 0.95", (d < 0.05).mean() >= 0.95,
          f"{len(j)} months, share equal {(d < 0.05).mean():.3f} (BLS revises SA history every January)")

    # 6. GSW 10y zero-coupon vs Treasury 10y par yield: different concepts, should be close
    a = series(data["gsw_curve"], "SVENY10")
    b = series(data["fred_us_rates"], "DGS10")
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1])
    check("GSW 10y zero vs DGS10 par: mean |diff| < 0.25 pp", d.abs().mean() < 0.25,
          f"{len(j)} days, mean |diff| {d.abs().mean():.3f}, corr of changes {j.diff().corr().iloc[0, 1]:.3f}")

    # 7. Ken French market return vs S&P 500 daily return (since FRED's SP500 starts ~10y ago)
    fr = data["french"]
    mkt = series(fr, "F-F_Research_Data_Factors_daily_CSV:main:Mkt-RF") + series(fr, "F-F_Research_Data_Factors_daily_CSV:main:RF")
    spx = series(data["fred_markets"], "SP500")
    j = pd.concat([mkt / 100, np.log(spx).diff()], axis=1, join="inner").dropna()
    c = j.corr().iloc[0, 1]
    check("French market return vs S&P 500: corr > 0.97", c > 0.97, f"{len(j)} days, corr {c:.4f}")

    # 8. Real-time panel shape: each vintage adds observations, vintages are monthly without gaps
    for sid in ["PCPI", "EMPLOY", "IPT"]:
        v = rt[rt["series"] == sid].groupby("vintage")["date"].max().sort_index()
        gaps = v.index.to_series().diff().dt.days.dropna()
        check(f"RTDSM {sid}: monthly vintages without gaps", gaps.between(28, 31).all(),
              f"{len(v)} vintages {v.index[0].date()}–{v.index[-1].date()}")


# ------------------------------------------------------------------------------------------------
def catalog(data):
    sys.path.insert(0, str(ROOT))
    from dgfts.catalog import INFO
    man = pd.read_csv(ROOT / "data" / "manifest_raw.csv")
    lines = ["# Data catalogue", "",
             f"*Generated by `scripts/validate.py` on {TODAY.date()}. Raw files: `data/raw/` (sha256 in "
             "`manifest_raw.csv`); tidy long tables: `data/tidy/<dataset>.parquet` with columns "
             "`series, date, value` (+ `vintage` for real-time data).*", "",
             "| dataset | paper | role | source | series | rows | first | last | raw MB |",
             "|---|---|---|---|---:|---:|---|---|---:|"]
    detail = []
    for name, df in data.items():
        paper, role, src = INFO.get(name, ("", "", ""))
        mb = man.loc[man["dataset"] == name, "bytes"].sum() / 1e6
        lines.append(f"| `{name}` | {paper} | {role} | {src} | {df['series'].nunique()} | {len(df):,} | "
                     f"{df['date'].min().date()} | {df['date'].max().date()} | {mb:.1f} |")
        g = df.groupby("series")["date"].agg(["min", "max", "count"])
        detail += [f"\n### `{name}`\n", "| series | first | last | n |", "|---|---|---|---:|"]
        detail += [f"| `{s}` | {r['min'].date()} | {r['max'].date()} | {r['count']:,} |" for s, r in g.iterrows()]
    (ROOT / "data" / "CATALOG.md").write_text("\n".join(lines + ["", "## Series by dataset"] + detail) + "\n")


def main():
    data = {p.stem: pd.read_parquet(p) for p in sorted(TIDY.glob("*.parquet"))}
    integrity(data)
    freshness(data)
    cross_source(data)
    catalog(data)
    graded = [ok for _, ok, _ in results if ok is not None]
    n_ok = sum(graded)
    md = [f"# Validation — {TODAY.date()}", "", f"**{n_ok}/{len(graded)} checks pass.**", "",
          "| | check | detail |", "|---|---|---|"]
    md += [f"| {'ℹ️' if ok is None else '✅' if ok else '❌'} | {n} | {d} |" for n, ok, d in results]
    (ROOT / "data" / "VALIDATION.md").write_text("\n".join(md) + "\n")
    print(f"\n{n_ok}/{len(graded)} checks pass")
    return n_ok == len(graded)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
