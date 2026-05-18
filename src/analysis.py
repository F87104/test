"""Analysis breakdowns: per-symbol / fakeout / time-of-day / volatility.

Each function consumes a trade dataframe (as produced by
:meth:`BacktestResult.trades_df`) and returns a tidy summary dataframe.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from .metrics import compute_metrics


# ---------------------------------------------------------------------------
def _aggregate(group: pd.DataFrame) -> pd.Series:
    """Compute summary metrics for a group of trades (no equity curve)."""
    pnl = group["pnl_money"].to_numpy()
    r = group["r_multiple"].to_numpy()
    n = len(group)
    wins = pnl > 0
    profits = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    pf = float(profits / losses) if losses > 0 else (float("inf") if profits > 0 else 0.0)
    return pd.Series(
        {
            "n_trades": int(n),
            "win_rate": float(wins.mean()) if n else 0.0,
            "profit_factor": pf,
            "expectancy_r": float(r.mean()) if n else 0.0,
            "expectancy_money": float(pnl.mean()) if n else 0.0,
            "avg_win_r": float(r[r > 0].mean()) if (r > 0).any() else 0.0,
            "avg_loss_r": float(r[r < 0].mean()) if (r < 0).any() else 0.0,
            "total_pnl_money": float(pnl.sum()),
            "fakeout_rate": float(group["is_fakeout"].mean())
            if "is_fakeout" in group
            else 0.0,
            "avg_bars_held": float(group["bars_held"].mean()) if n else 0.0,
        }
    )


# ---------------------------------------------------------------------------
def per_symbol(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("symbol", group_keys=False).apply(_aggregate)


def per_direction(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("direction", group_keys=False).apply(_aggregate)


def per_session(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("session", group_keys=False).apply(_aggregate)


def per_weekday(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("weekday", group_keys=False).apply(_aggregate)


def per_hour(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("hour_utc", group_keys=False).apply(_aggregate)


def per_year(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    yr = trades["entry_time"].dt.year.rename("year")
    return trades.groupby(yr, group_keys=False).apply(_aggregate)


# ---------------------------------------------------------------------------
def per_volatility_bucket(
    trades: pd.DataFrame, *, n_bins: int = 3
) -> pd.DataFrame:
    """Bucket trades by ATR-at-entry quantiles ('low'/'mid'/'high' by default)."""
    if trades.empty:
        return pd.DataFrame()
    vals = trades["atr_at_entry"].astype(float)
    if vals.nunique() < n_bins:
        bucket = pd.Series(["all"] * len(trades), index=trades.index, name="vol_bucket")
    else:
        labels = (
            ["low", "mid", "high"]
            if n_bins == 3
            else [f"q{i+1}" for i in range(n_bins)]
        )
        bucket = pd.qcut(vals, q=n_bins, labels=labels, duplicates="drop")
        bucket = bucket.rename("vol_bucket")
    aug = trades.assign(vol_bucket=bucket)
    return aug.groupby("vol_bucket", observed=False, group_keys=False).apply(_aggregate)


# ---------------------------------------------------------------------------
def fakeout_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    """How fakeouts (SL hit within 5 bars) compare with other trades."""
    if trades.empty:
        return pd.DataFrame()
    return trades.groupby("is_fakeout", group_keys=False).apply(_aggregate)


# ---------------------------------------------------------------------------
def per_lookback_combo(trades: pd.DataFrame) -> pd.DataFrame:
    """Drill into parameter sets — useful when several optimiser runs are
    aggregated into one trade ledger."""
    if trades.empty:
        return pd.DataFrame()
    keys = ["lookback", "exclude_recent", "lookback_3m", "exclude_recent_3m"]
    avail = [k for k in keys if k in trades.columns]
    if not avail:
        return pd.DataFrame()
    return trades.groupby(avail, group_keys=False).apply(_aggregate)


# ---------------------------------------------------------------------------
def full_breakdown(
    trades: pd.DataFrame,
    equity: pd.Series,
    *,
    initial_equity: float | None = None,
) -> dict[str, pd.DataFrame]:
    overall = compute_metrics(trades, equity, initial_equity=initial_equity)
    return {
        "overall": pd.DataFrame([overall.to_dict()]),
        "per_symbol": per_symbol(trades),
        "per_direction": per_direction(trades),
        "per_session": per_session(trades),
        "per_weekday": per_weekday(trades),
        "per_hour": per_hour(trades),
        "per_year": per_year(trades),
        "per_volatility": per_volatility_bucket(trades),
        "per_fakeout": fakeout_breakdown(trades),
        "per_params": per_lookback_combo(trades),
    }


__all__ = [
    "per_symbol",
    "per_direction",
    "per_session",
    "per_weekday",
    "per_hour",
    "per_year",
    "per_volatility_bucket",
    "fakeout_breakdown",
    "per_lookback_combo",
    "full_breakdown",
]
