"""Downloaders and parsers, one pair per data source.

Every downloader saves the bytes **exactly as the source served them** under `data/raw/<source>/`, so a
paper's numbers can always be traced back to an untouched file. Every parser turns a raw file into a
*tidy long* frame with columns

    series   str              source-specific id (FRED id, ECB key, Eurostat code, sheet/column, ...)
    date     datetime64       observation period (start of the period for monthly/quarterly data)
    value    float
    vintage  datetime64       only for real-time files: the date the data were published as seen

Nothing here transforms data (no logs, no differences, no seasonal adjustment). That lives in later
modules, so the raw→tidy step stays a pure re-formatting that can be audited by eye.
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

TIMEOUT = 120


# ---------------------------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------------------------

def http_get(url: str, params: dict | None = None, tries: int = 4, headers: dict | None = None) -> bytes:
    """GET with retries and exponential back-off. Raises on the last failure.

    Note: FRED refuses browser-like User-Agent strings, so the default `requests` UA is kept.
    """
    err = None
    for k in range(tries):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT, headers=headers)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            err = e
            time.sleep(2 ** k)
    raise RuntimeError(f"GET failed after {tries} tries: {url} {params or ''}: {err}")


def save(raw_dir: Path, name: str, content: bytes) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    p = raw_dir / name
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------------------------
# FRED (St. Louis Fed) — public fredgraph.csv endpoint, no key, <=10 ids per request
# ---------------------------------------------------------------------------------------------

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fred_download(ids: list[str], raw_dir: Path, chunk: int = 10) -> tuple[list[Path], list[str]]:
    """One CSV per id in raw_dir. Returns (paths, ids FRED could not serve)."""
    paths, failed = [], []

    def one_request(batch):
        txt = http_get(FRED_URL, {"id": ",".join(batch)}).decode()
        if not txt.lower().startswith(("observation_date", "date")):
            raise ValueError("not a CSV")  # unknown id -> FRED answers 200 with an HTML page
        return pd.read_csv(io.StringIO(txt), na_values=["."])

    for i in range(0, len(ids), chunk):
        batch = ids[i:i + chunk]
        try:
            frames = {None: one_request(batch)}
        except (ValueError, RuntimeError):
            frames = {}
            for s in batch:  # isolate the bad id
                try:
                    frames[s] = one_request([s])
                except (ValueError, RuntimeError):
                    failed.append(s)
        for df in frames.values():
            df = df.rename(columns={df.columns[0]: "date"})
            for s in df.columns[1:]:
                out = df[["date", s]].dropna()
                paths.append(save(raw_dir, f"{s}.csv", out.to_csv(index=False).encode()))
        time.sleep(0.3)
    return paths, failed


def fred_parse(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return pd.DataFrame({"series": df.columns[1], "date": df["date"], "value": df.iloc[:, 1].astype(float)})


# ---------------------------------------------------------------------------------------------
# ECB Data Portal — SDMX REST, csvdata format; '+' joins values within a key dimension
# ---------------------------------------------------------------------------------------------

ECB_URL = "https://data-api.ecb.europa.eu/service/data"


def ecb_download(flow: str, key: str, raw_dir: Path, name: str, history: bool = False) -> Path:
    """history=True asks for every revision of every observation (`includeHistory`); each row then
    carries VALID_FROM = when that value was published, which we keep as the vintage."""
    params = {"format": "csvdata"} | ({"includeHistory": "true"} if history else {})
    return save(raw_dir, f"{name}.csv", http_get(f"{ECB_URL}/{flow}/{key}", params))


def _period_to_date(p: pd.Series) -> pd.Series:
    """ECB/Eurostat periods: 2024-03-15 (daily), 2024-03 (monthly), 2024-Q1 (quarterly), 2024 (annual)."""
    p = p.astype(str)
    q = p.str.extract(r"^(\d{4})-?Q(\d)$")
    out = pd.to_datetime(p, errors="coerce", format="mixed")
    isq = q[0].notna()
    out[isq] = pd.to_datetime(q[0][isq] + "-" + ((q[1][isq].astype(int) - 1) * 3 + 1).astype(str) + "-01")
    return out


def ecb_parse(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"TIME_PERIOD": str}, low_memory=False)
    out = pd.DataFrame({"series": df["KEY"], "date": _period_to_date(df["TIME_PERIOD"]),
                        "value": pd.to_numeric(df["OBS_VALUE"], errors="coerce")})
    if "VALID_FROM" in df.columns:  # real-time history: vintage = publication day (local time dropped)
        out["vintage"] = pd.to_datetime(df["VALID_FROM"].str[:10])
        out = out.drop_duplicates(["series", "date", "vintage"], keep="last")
    return out.dropna(subset=["value"]).reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Eurostat — JSON-stat 2.0 dissemination API
# ---------------------------------------------------------------------------------------------

EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def eurostat_download(dataset: str, filters: dict, raw_dir: Path, name: str) -> Path:
    return save(raw_dir, f"{name}.json", http_get(f"{EUROSTAT_URL}/{dataset}", filters))


def eurostat_parse(path: Path) -> pd.DataFrame:
    """JSON-stat: values are a flat dict keyed by the row-major index over all dimensions."""
    import json
    import itertools
    js = json.loads(path.read_text())
    dims = js["id"]
    cats = [sorted(js["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in dims]
    labels = [[c for c, _ in cat] for cat in cats]
    rows = []
    for flat, combo in enumerate(itertools.product(*labels)):
        v = js["value"].get(str(flat))
        if v is None:
            continue
        d = dict(zip(dims, combo))
        series = ".".join(d[k] for k in dims if k not in ("time", "freq"))
        rows.append((f"{path.stem}:{series}", d["time"], float(v)))
    df = pd.DataFrame(rows, columns=["series", "period", "value"])
    df["date"] = _period_to_date(df.pop("period"))
    return df[["series", "date", "value"]]


# ---------------------------------------------------------------------------------------------
# Philadelphia Fed — Real-Time Data Set (RTDSM) and Survey of Professional Forecasters
# ---------------------------------------------------------------------------------------------

PHIL_RT = "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/real-time-data/data-files/xlsx"
PHIL_SPF = ("https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/"
            "survey-of-professional-forecasters/historical-data")


def philly_download(url: str, raw_dir: Path, name: str) -> Path:
    b = http_get(url)
    if not b.startswith(b"PK"):  # xlsx is a zip; the site answers 200 + HTML for a missing file
        raise RuntimeError(f"not an xlsx: {url}")
    return save(raw_dir, name, b)


def _xlsx_without_docprops(path: Path) -> io.BytesIO:
    """In-memory copy of an xlsx minus docProps/core.xml. iptMvMd.xlsx ships a malformed creation date
    there that makes openpyxl crash; the metadata carries no data. The raw file is left untouched."""
    src, buf = zipfile.ZipFile(path), io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename != "docProps/core.xml":
                dst.writestr(item, src.read(item.filename))
    buf.seek(0)
    return buf


def _yy(y: int) -> int:
    return 1900 + y if y >= 60 else 2000 + y


def rtdsm_parse(path: Path) -> pd.DataFrame:
    """Vintage matrix → long. Rows = observation dates ('1947:01' or '1947:Q1'), columns = vintages
    ('PCPI98M11' = Nov-1998 vintage, 'RUC98Q4' = 1998Q4 vintage, first month of the quarter)."""
    df = pd.read_excel(_xlsx_without_docprops(path))
    obs = df.columns[0]
    long = df.melt(id_vars=obs, var_name="vcode", value_name="value")
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"])
    m = long["vcode"].str.extract(r"^([A-Za-z]+)(\d{2})([MQ])(\d{1,2})$")
    month = m[3].astype(int).where(m[2] == "M", (m[3].astype(int) - 1) * 3 + 1)
    long["vintage"] = pd.to_datetime(dict(year=m[1].astype(int).map(_yy), month=month, day=1))
    o = long[obs].astype(str).str.extract(r"^(\d{4}):?([MQ]?)(\d{1,2})")
    omonth = o[2].astype(int).where(o[1] != "Q", (o[2].astype(int) - 1) * 3 + 1)
    long["date"] = pd.to_datetime(dict(year=o[0].astype(int), month=omonth, day=1))
    long["series"] = m[0].str.upper()
    return long[["series", "date", "vintage", "value"]].reset_index(drop=True)


def spf_parse(path: Path) -> pd.DataFrame:
    """SPF median file: one sheet per variable; rows = survey (YEAR, QUARTER); columns = horizons
    (e.g. UNEMP1 = quarter before the survey, UNEMP2 = survey quarter, ... UNEMPA = annual)."""
    out = []
    for sheet, df in pd.read_excel(path, sheet_name=None).items():
        if not {"YEAR", "QUARTER"} <= set(df.columns):
            continue
        df = df.dropna(subset=["YEAR", "QUARTER"])
        date = pd.to_datetime(dict(year=df["YEAR"].astype(int), month=(df["QUARTER"].astype(int) - 1) * 3 + 1, day=1))
        for c in df.columns.drop(["YEAR", "QUARTER"]):
            v = pd.to_numeric(df[c], errors="coerce")
            out.append(pd.DataFrame({"series": f"{path.stem}:{sheet}:{c}", "date": date, "value": v}).dropna())
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------------------------
# Kenneth French data library — zipped CSVs with several titled sections
# ---------------------------------------------------------------------------------------------

FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"


def french_download(name: str, raw_dir: Path) -> Path:
    return save(raw_dir, f"{name}.zip", http_get(f"{FRENCH_URL}/{name}.zip"))


def french_parse(path: Path) -> pd.DataFrame:
    """Each section = optional title lines, a header row starting with ',', then rows whose first
    field is a date (YYYYMMDD daily, YYYYMM monthly, YYYY annual). Values are percent; -99.99 = missing.
    Series name = '<file>:<section title>:<column>'."""
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    out, title, header, rows = [], "", None, []

    def flush():
        if header and rows:
            d = pd.DataFrame(rows, columns=["d"] + header)
            n = d["d"].str.len().iloc[0]
            fmt = {8: "%Y%m%d", 6: "%Y%m", 4: "%Y"}[n]
            date = pd.to_datetime(d["d"], format=fmt)
            sec = (title or "main") + ("" if n != 4 else " [annual]")
            for c in header:
                v = pd.to_numeric(d[c], errors="coerce").where(lambda x: x > -99.99 + 1e-9)
                out.append(pd.DataFrame({"series": f"{path.stem}:{sec}:{c}", "date": date, "value": v}).dropna())

    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        if re.fullmatch(r"\d{4}(\d{2}){0,2}", f[0]) and header:
            rows.append(f[:len(header) + 1])
        elif line.startswith(",") or (f[0] == "" and len(f) > 1):
            flush(); header, rows = f[1:], []
        elif line.strip():
            if rows:
                flush(); header, rows = None, []
            t = line.strip().strip(",")
            # short lines are section titles; long ones are the file's description paragraph
            title = t if len(t) <= 80 and not t.startswith("Missing data") else (title if rows or header else "")
    flush()
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------------------------
# Federal Reserve Board — Gürkaynak–Sack–Wright daily nominal zero-coupon curve (feds200628)
# ---------------------------------------------------------------------------------------------

GSW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"


def gsw_download(raw_dir: Path) -> Path:
    return save(raw_dir, "feds200628.csv", http_get(GSW_URL))


def gsw_parse(path: Path) -> pd.DataFrame:
    lines = path.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Date"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), na_values=["NA"], parse_dates=["Date"])
    long = df.melt(id_vars="Date", var_name="series", value_name="value").dropna()
    return long.rename(columns={"Date": "date"})[["series", "date", "value"]]
