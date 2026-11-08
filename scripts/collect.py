"""Download every dataset in dgfts/catalog.py → data/raw (untouched) + data/tidy (long parquet).

    python3.12 scripts/collect.py              # everything
    python3.12 scripts/collect.py ecb_spf rtdsm  # only these datasets

Writes data/manifest_raw.csv (one row per raw file: bytes, sha256, download time) so a later run can
tell whether a source revised its data. Failures are logged and skipped, never fatal.
"""
from __future__ import annotations

import datetime as dt
import warnings
import hashlib
import sys
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dgfts import catalog as C, sources as S  # noqa: E402

warnings.filterwarnings("ignore", module="openpyxl")
RAW, TIDY = ROOT / "data" / "raw", ROOT / "data" / "tidy"


def _fred(name, ids):
    paths, failed = S.fred_download(ids, RAW / "fred")
    if failed:
        print(f"  FRED could not serve: {failed}")
    keep = {f"{i}.csv" for i in ids}
    paths = [p for p in paths if p.name in keep]
    return paths, pd.concat([S.fred_parse(p) for p in paths], ignore_index=True)


def jobs():
    j = {
        "fred_md_panel": lambda: _fred("fred_md_panel", C.FREDMD_IDS),
        "fred_us_rates": lambda: _fred("fred_us_rates", C.FRED_US_RATES),
        "fred_us_prices_labor": lambda: _fred("fred_us_prices_labor", C.FRED_US_PRICES_LABOR),
        "fred_expectations": lambda: _fred("fred_expectations", C.FRED_EXPECTATIONS),
        "fred_markets": lambda: _fred("fred_markets", C.FRED_MARKETS),
        "fred_ea_mirror": lambda: _fred("fred_ea_mirror", C.FRED_EA_ON_FRED),
    }
    for name, (flow, key) in C.ECB.items():
        j[name] = (lambda n=name, f=flow, k=key: (lambda p: ([p], S.ecb_parse(p)))(S.ecb_download(f, k, RAW / "ecb", n)))
    j["ecb_rtd"] = lambda: (lambda p: ([p], S.ecb_parse(p)))(S.ecb_download(*C.ECB_RTD, RAW / "ecb", "ecb_rtd", history=True))
    for name, (ds, flt) in C.EUROSTAT.items():
        j[name] = (lambda n=name, d=ds, f=flt: (lambda p: ([p], S.eurostat_parse(p)))(S.eurostat_download(d, f, RAW / "eurostat", n)))

    def rtdsm():
        ps = [S.philly_download(f"{S.PHIL_RT}/{f}.xlsx", RAW / "philly_rtdsm", f"{f}.xlsx") for f in C.RTDSM]
        return ps, pd.concat([S.rtdsm_parse(p) for p in ps], ignore_index=True)

    def spf_us():
        ps = [S.philly_download(f"{S.PHIL_SPF}/{f.lower()}.xlsx", RAW / "philly_spf", f"{f}.xlsx") for f in C.SPF_US]
        return ps, pd.concat([S.spf_parse(p) for p in ps], ignore_index=True)

    def french():
        ps = [S.french_download(f, RAW / "french") for f in C.FRENCH]
        return ps, pd.concat([S.french_parse(p) for p in ps], ignore_index=True)

    def gsw():
        p = S.gsw_download(RAW / "fedboard")
        return [p], S.gsw_parse(p)

    j.update(rtdsm=rtdsm, spf_us=spf_us, french=french, gsw_curve=gsw)
    return j


def main(only: list[str]):
    TIDY.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    man_path = ROOT / "data" / "manifest_raw.csv"
    manifest = pd.read_csv(man_path) if man_path.exists() else pd.DataFrame()
    rows, failed = [], []
    for name, job in jobs().items():
        if only and name not in only:
            continue
        print(f"[{name}]", flush=True)
        try:
            paths, tidy = job()
        except Exception:
            traceback.print_exc(limit=2)
            failed.append(name)
            continue
        tidy.to_parquet(TIDY / f"{name}.parquet", index=False)
        print(f"  {len(paths)} raw file(s), {tidy['series'].nunique()} series, {len(tidy):,} rows")
        for p in paths:
            b = p.read_bytes()
            rows.append(dict(dataset=name, file=str(p.relative_to(ROOT)), bytes=len(b),
                             sha256=hashlib.sha256(b).hexdigest(), downloaded_utc=now))
    new = pd.DataFrame(rows)
    if len(manifest):
        manifest = manifest[~manifest["file"].isin(new["file"])] if len(new) else manifest
    pd.concat([manifest, new], ignore_index=True).sort_values(["dataset", "file"]).to_csv(man_path, index=False)
    print(f"\ndone; failed: {failed or 'none'}")
    return failed


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
