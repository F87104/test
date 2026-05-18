"""CSV → :class:`pandas.DataFrame` loader with automatic datetime detection.

Accepts the canonical ``datetime,open,high,low,close,volume`` schema as well
as common aliases (``time``, ``timestamp``, ``Date``, ``<DATE>``…).  Datetime
values may be ISO-8601 strings, ``YYYY/MM/DD HH:MM:SS``, or unix epoch
seconds/milliseconds — all detected automatically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from .logger import get_logger

log = get_logger("trendbreak.data_loader")


# ---------------------------------------------------------------------------
DATETIME_CANDIDATES = (
    "datetime",
    "date_time",
    "timestamp",
    "time",
    "date",
    "<date>",
    "<time>",
    "Date",
    "Time",
    "Timestamp",
)
PRICE_ALIASES: Mapping[str, str] = {
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
    "vol": "volume",
    "<open>": "open",
    "<high>": "high",
    "<low>": "low",
    "<close>": "close",
    "<vol>": "volume",
}


@dataclass
class LoadReport:
    rows_in: int
    rows_out: int
    rows_dropped_invalid_ohlc: int
    rows_dropped_duplicate: int
    inferred_datetime_format: str
    timezone: str


# ---------------------------------------------------------------------------
def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=cols)
    df = df.rename(columns={k: v for k, v in PRICE_ALIASES.items() if k in df.columns})
    if "datetime" not in df.columns:
        for cand in DATETIME_CANDIDATES:
            cand_l = cand.lower()
            if cand_l in df.columns:
                df = df.rename(columns={cand_l: "datetime"})
                break
        else:
            # Fallback: combine separate <DATE>/<TIME> columns if present
            if "<date>" in df.columns and "<time>" in df.columns:
                df["datetime"] = df["<date>"].astype(str) + " " + df["<time>"].astype(str)
                df = df.drop(columns=["<date>", "<time>"])
    return df


def _parse_datetime(series: pd.Series) -> tuple[pd.Series, str]:
    """Try multiple parsing strategies; return (parsed_series, format_label)."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series, "already_datetime"

    raw = series.dropna()
    if raw.empty:
        raise ValueError("[ERR-DATETIME] datetime column is entirely empty")

    sample = str(raw.iloc[0]).strip()

    # Numeric → unix epoch (seconds vs milliseconds heuristic)
    if pd.api.types.is_numeric_dtype(series) or sample.isdigit():
        as_num = pd.to_numeric(series, errors="coerce")
        max_val = as_num.dropna().max()
        if max_val is np.nan or max_val is None:
            raise ValueError("[ERR-DATETIME] could not coerce datetime to number")
        if max_val > 1e14:  # nanoseconds
            return pd.to_datetime(as_num, unit="ns", errors="coerce"), "unix_ns"
        if max_val > 1e11:  # milliseconds
            return pd.to_datetime(as_num, unit="ms", errors="coerce"), "unix_ms"
        return pd.to_datetime(as_num, unit="s", errors="coerce"), "unix_s"

    # String formats
    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    if parsed.notna().mean() < 0.99:  # try common explicit formats
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y%m%d %H%M%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ):
            attempt = pd.to_datetime(series, format=fmt, errors="coerce")
            if attempt.notna().mean() > parsed.notna().mean():
                parsed = attempt
                if parsed.notna().mean() > 0.99:
                    return parsed, fmt
    if parsed.notna().mean() < 0.5:
        raise ValueError(
            "[ERR-DATETIME] failed to parse the datetime column; first sample="
            f"{sample!r}.  Use a recognised format such as 'YYYY-MM-DD HH:MM:SS'."
        )
    return parsed, "auto"


def _validate_ohlc(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cols_needed = {"open", "high", "low", "close"}
    missing = cols_needed.difference(df.columns)
    if missing:
        raise ValueError(f"[ERR-DATA] missing OHLC columns: {sorted(missing)!r}")

    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    else:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)

    n0 = len(df)
    bad = (
        df[["open", "high", "low", "close"]].isna().any(axis=1)
        | (df["high"] < df["low"])
        | (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
        | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    )
    dropped = int(bad.sum())
    if dropped:
        log.warning(
            "dropping %d/%d rows with invalid OHLC (NaN, high<low, non-positive…)",
            dropped,
            n0,
        )
    return df.loc[~bad].copy(), dropped


# ---------------------------------------------------------------------------
def load_csv(
    path: str | Path,
    *,
    timezone: Optional[str] = None,
    drop_duplicates: bool = True,
    sort: bool = True,
) -> tuple[pd.DataFrame, LoadReport]:
    """Load and validate a CSV file with OHLCV bars.

    Returns ``(df, report)``.  The dataframe is indexed by ``datetime`` (UTC if
    no tz info is present, optionally converted via ``timezone``).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"[ERR-IO] CSV not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"[ERR-IO] CSV is empty: {path}")

    log.info("loading CSV: %s", path)
    df = pd.read_csv(path, low_memory=False)
    n0 = len(df)
    if n0 == 0:
        raise ValueError(f"[ERR-DATA] no rows in {path}")

    df = _normalise_columns(df)
    if "datetime" not in df.columns:
        raise ValueError(
            "[ERR-DATETIME] could not detect a datetime column; expected one of "
            f"{DATETIME_CANDIDATES} (case-insensitive)"
        )

    parsed, fmt_label = _parse_datetime(df["datetime"])
    df["datetime"] = parsed
    df = df.dropna(subset=["datetime"]).copy()

    if df["datetime"].dt.tz is None:
        df["datetime"] = df["datetime"].dt.tz_localize("UTC")
    if timezone:
        df["datetime"] = df["datetime"].dt.tz_convert(timezone)

    df, dropped_invalid = _validate_ohlc(df)

    dropped_dup = 0
    if drop_duplicates:
        before = len(df)
        df = df.drop_duplicates(subset=["datetime"], keep="last")
        dropped_dup = before - len(df)

    if sort:
        df = df.sort_values("datetime").reset_index(drop=True)
    df = df.set_index("datetime", drop=True)

    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep]

    report = LoadReport(
        rows_in=n0,
        rows_out=len(df),
        rows_dropped_invalid_ohlc=dropped_invalid,
        rows_dropped_duplicate=dropped_dup,
        inferred_datetime_format=fmt_label,
        timezone=str(df.index.tz) if df.index.tz else "naive",
    )
    log.info(
        "loaded %d rows (dropped %d invalid OHLC, %d duplicate, format=%s, tz=%s)",
        report.rows_out,
        report.rows_dropped_invalid_ohlc,
        report.rows_dropped_duplicate,
        report.inferred_datetime_format,
        report.timezone,
    )
    return df, report


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Symbol inference + normalisation
# ---------------------------------------------------------------------------
# Common aliases / known typos the user has in their archive ("GBY" instead
# of "GBP", "SILVER" for XAGUSD, "GOLD" for XAUUSD, MT4 micro suffixes…)
_SYMBOL_ALIASES: Mapping[str, str] = {
    "GBY": "GBP",
    "GBYJPY": "GBPJPY",
    "GBYNZD": "GBPNZD",
    "GBYUSD": "GBPUSD",
    "SILVER": "XAGUSD",
    "GOLD": "XAUUSD",
    "XBT": "BTCUSD",
    "XBTUSD": "BTCUSD",
    "NAS": "NAS100",
    "NDX": "NAS100",
    "US100": "NAS100",
    "USNAS100": "NAS100",
}

# Tokens that frequently appear in filenames but are not part of the symbol
_NOISE_TOKENS = {
    "DATA", "HISTORICAL", "HISTORY", "OHLC", "BARS",
    "TICK", "MINUTE", "HOURLY", "DAILY",
}

_TIMEFRAME_RE = re.compile(
    r"^(?:M1|M5|M15|M30|H1|H4|D1|W1|MN|1M|5M|15M|30M|60M|240M|1H|2H|4H|1D|1W|1MO|1MIN|5MIN|15MIN|30MIN|60MIN)$",
    re.IGNORECASE,
)


def _clean_symbol_token(token: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", token).upper()
    return _SYMBOL_ALIASES.get(s, s)


def infer_symbol(path: str | Path) -> str:
    """Best-effort symbol inference from a path.

    Handles the patterns observed in the user's Google Drive history dump:

    - ``EURJPY2014-2024/EURJPY_H1.csv``   → ``EURJPY``
    - ``SILVER2014-2024/silver_h4.csv``   → ``XAGUSD``   (SILVER alias)
    - ``GBY JPY H4 2024.csv``             → ``GBPJPY``   (typo + spaces + TF)
    - ``GBYNZD2014-2024.csv``             → ``GBPNZD``
    - ``XAUUSD_H1_2014-2024.csv``         → ``XAUUSD``
    - ``btc-1h.csv``                      → ``BTCUSD``
    """
    p = Path(path)
    parts = list(p.parents)[:3]  # check up to 3 parent folders for hints
    candidates: list[str] = []

    # 1) The stem itself
    stem = p.stem
    candidates.append(stem)

    # 2) Any parent folder that "looks like" a symbol folder
    for parent in parts:
        candidates.append(parent.name)

    for cand in candidates:
        sym = _symbol_from_token(cand)
        if sym and sym != "UNKNOWN":
            return sym
    return "UNKNOWN"


_YEAR_RANGE_RE = re.compile(r"(19|20)\d{2}\s*[-_]\s*(19|20)?\d{2}")
_SINGLE_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _symbol_from_token(token: str) -> str:
    if not token:
        return "UNKNOWN"
    # Strip year ranges & single years: "EURJPY2014-2024" → "EURJPY"
    t = _YEAR_RANGE_RE.sub(" ", token)
    t = _SINGLE_YEAR_RE.sub(" ", t)
    # Split on any non-alnum then drop noise / timeframe tokens
    raw_parts = re.split(r"[^A-Za-z0-9]+", t)
    parts = [
        x.upper() for x in raw_parts
        if x and x.upper() not in _NOISE_TOKENS and not _TIMEFRAME_RE.match(x)
    ]
    if not parts:
        return "UNKNOWN"

    joined = "".join(parts)
    # Try alias map on whole string first
    if joined in _SYMBOL_ALIASES:
        return _SYMBOL_ALIASES[joined]
    # "GBY JPY" → ["GBY", "JPY"] → "GBYJPY" → alias to "GBPJPY"
    if len(parts) >= 2:
        pair2 = (parts[0] + parts[1]).upper()
        if pair2 in _SYMBOL_ALIASES:
            return _SYMBOL_ALIASES[pair2]
        if len(pair2) in (6, 7, 8) and pair2.isalpha():
            return _clean_symbol_token(pair2)
    head = parts[0]
    if head in _SYMBOL_ALIASES:
        return _SYMBOL_ALIASES[head]
    return _clean_symbol_token(head)


def infer_pip_size(symbol: str) -> float:
    """Return a reasonable pip size for the symbol family."""
    s = _clean_symbol_token(symbol)
    if "JPY" in s:
        return 0.01
    if s.startswith(("XAU", "GOLD")):
        return 0.1
    if s.startswith(("XAG", "SILVER")):
        return 0.01
    if s in {"BTC", "BTCUSD", "BTCUSDT", "XBTUSD"}:
        return 1.0
    if s in {"ETH", "ETHUSD", "ETHUSDT"}:
        return 0.1
    if "NAS" in s or "NDX" in s or "SPX" in s or "DJI" in s or "US100" in s:
        return 1.0
    return 0.0001  # FX major


# ---------------------------------------------------------------------------
def synthesise_ohlcv(
    n: int = 5000,
    *,
    seed: int = 0,
    start: str = "2015-01-01",
    freq: str = "h",
    drift: float = 0.00005,
    vol: float = 0.005,
) -> pd.DataFrame:
    """Generate a synthetic OHLCV dataframe for tests / demos."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    open_ = np.r_[close[0], close[:-1]]
    body_max = np.maximum(open_, close)
    body_min = np.minimum(open_, close)
    high = body_max * (1 + np.abs(rng.normal(0, vol * 0.6, size=n)))
    low = body_min * (1 - np.abs(rng.normal(0, vol * 0.6, size=n)))
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1.0},
        index=idx,
    )


def load_csvs(
    paths: Iterable[str | Path],
    *,
    timezone: Optional[str] = None,
) -> tuple[pd.DataFrame, list[LoadReport]]:
    """Load several CSV files and return one chronologically sorted dataframe.

    Useful for archives that split the same symbol into yearly files
    (e.g. ``SILVER_H1_2014.csv … SILVER_H1_2025.csv``).

    Returns ``(merged_df, per_file_reports)``.  Duplicate timestamps (same
    bar reported in two files) are deduplicated, keeping the **last** value.
    """
    frames: list[pd.DataFrame] = []
    reports: list[LoadReport] = []
    bad: list[tuple[str, Exception]] = []
    for p in paths:
        try:
            df, rpt = load_csv(p, timezone=timezone, sort=False, drop_duplicates=False)
            frames.append(df)
            reports.append(rpt)
        except Exception as exc:  # noqa: BLE001
            bad.append((str(p), exc))
            log.error("[ERR-IO] failed to load %s: %s", p, exc)
    if not frames:
        raise ValueError(
            f"[ERR-DATA] no usable CSVs out of {len(list(paths))}: " + "; ".join(
                f"{p}: {e}" for p, e in bad
            )
        )
    merged = pd.concat(frames, axis=0)
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    log.info(
        "merged %d file(s) → %d rows  range=[%s, %s]",
        len(frames),
        len(merged),
        merged.index[0],
        merged.index[-1],
    )
    return merged, reports


__all__ = [
    "LoadReport",
    "load_csv",
    "load_csvs",
    "infer_symbol",
    "infer_pip_size",
    "synthesise_ohlcv",
]
