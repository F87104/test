"""CSV data loader for MT4/MT5 style OHLCV files in this repository.

All CSVs share the header
    <TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>
where TIME is HHMM. Per-symbol files may live both at the repo root and
under a sub-directory such as ``USDJPY2014-2024/``.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

# Canonical symbol -> list of glob patterns (relative to repo root).
SYMBOL_PATTERNS: dict[str, list[str]] = {
    "USDJPY": [
        "USDJPY_H1_*.csv",
        "USDJPY2014-2024/USDJPY_H1_*.csv",
    ],
    "EURJPY": [
        "EURJPY2014-2024/EURJPY_H1_*.csv",
        "AUDJPY2014-2024/EURJPY_H1_*.csv",  # 2025/2026 happen to live here
    ],
    "AUDJPY": [
        "AUDJPY H1 *.csv",
        "AUDJPY2014-2024/AUDJPY H1 *.csv",
    ],
    "CHFJPY": [
        "CHFJPY_H1_*.csv",
        "CHFJPY2014-2024/CHFJPY_H1_*.csv",
        "AUDJPY2014-2024/CHFJPY_H1_*.csv",
    ],
    "GBPJPY": [
        "GBYJPY2014-2024/GBYJPY H1/GBY JPY H1 *.csv",
        "AUDJPY2014-2024/GBY JPY H1 *.csv",
    ],
    "XAUUSD": [
        "XAUUSD_H1_*.csv",
        "XAUUSD2014-2024/XAUUSD_H1_*.csv",
    ],
    "XAGUSD": [
        "SILVER_H1_*.csv",
        "SILVER2014-2024/SILVER_H1_*.csv",
    ],
    "NAS100": [
        "NAS100_H1_*.csv",
    ],
    "SPX500": [
        "SPX500 2014-2026/SPX500_H1_*.csv",
    ],
}


@dataclass
class LoadResult:
    symbol: str
    df: pd.DataFrame
    sources: list[str]


def _resample_to_h1(df: pd.DataFrame) -> pd.DataFrame:
    """Force a 1-hour OHLCV frame. Sub-hour bars get aggregated, native H1
    bars survive unchanged. Empty hours are dropped."""
    if df.empty:
        return df
    indexed = df.set_index("datetime").sort_index()
    agg = indexed.resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    agg = agg.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return agg


def _resolve(repo_root: str, patterns: Iterable[str]) -> list[str]:
    out: list[str] = []
    for p in patterns:
        out.extend(sorted(glob.glob(os.path.join(repo_root, p))))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for path in out:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _read_one(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalise columns: strip angle brackets, upper-case.
    df.columns = [re.sub(r"[<>]", "", c).strip().upper() for c in df.columns]
    required = {"DTYYYYMMDD", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    time_str = df["TIME"].astype(int).astype(str).str.zfill(4)
    dt = pd.to_datetime(
        df["DTYYYYMMDD"].astype(str) + time_str,
        format="%Y%m%d%H%M",
        utc=True,
        errors="coerce",
    )
    out = pd.DataFrame(
        {
            "datetime": dt,
            "open": df["OPEN"].astype(float),
            "high": df["HIGH"].astype(float),
            "low": df["LOW"].astype(float),
            "close": df["CLOSE"].astype(float),
            "volume": df["VOL"].astype(float) if "VOL" in df.columns else 0.0,
        }
    )
    out = out.dropna(subset=["datetime"]).sort_values("datetime")
    return out


def load_symbol(symbol: str, repo_root: str) -> LoadResult:
    if symbol not in SYMBOL_PATTERNS:
        raise KeyError(f"Unknown symbol: {symbol}")
    paths = _resolve(repo_root, SYMBOL_PATTERNS[symbol])
    if not paths:
        raise FileNotFoundError(f"No CSVs found for {symbol} under {repo_root}")
    frames = [_read_one(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime")
    df = _resample_to_h1(df)
    df = df.reset_index(drop=True)
    return LoadResult(symbol=symbol, df=df, sources=paths)


def available_symbols() -> list[str]:
    return list(SYMBOL_PATTERNS.keys())
