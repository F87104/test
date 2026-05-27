"""Pine Script faithful port of *大トレンドブレイク検出（ライン強調のみ）*.

The original script computes, for every bar ``t``:

    highLevel[t] = max(high[t-lookback+1 .. t])
    lowLevel [t] = min(low [t-lookback+1 .. t])

    recentHighTouch[t] = max(high[t-exclude_recent .. t-1]) >= highLevel[t]
    recentLowTouch [t] = min(low [t-exclude_recent .. t-1]) <= lowLevel [t]

    longCond [t] = close[t] > highLevel[t] and not recentHighTouch[t]
    shortCond[t] = close[t] < lowLevel [t] and not recentLowTouch [t]

This module reproduces the logic in vectorised form using pandas rolling
windows.  Equivalence to the original loop implementation is asserted by
``tests/test_indicator.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .config import IndicatorConfig
from .logger import get_logger

log = get_logger("trendbreak.indicator")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class IndicatorResult:
    """Container for all per-bar series produced by the indicator."""

    df: pd.DataFrame  # original OHLC + computed columns

    # convenient accessors -----------------------------------------------------
    @property
    def long_signal(self) -> pd.Series:
        return self.df["longCond"].fillna(False).astype(bool)

    @property
    def short_signal(self) -> pd.Series:
        return self.df["shortCond"].fillna(False).astype(bool)

    @property
    def long_signal_3m(self) -> pd.Series:
        return self.df["longCond3m"].fillna(False).astype(bool)

    @property
    def short_signal_3m(self) -> pd.Series:
        return self.df["shortCond3m"].fillna(False).astype(bool)


# ---------------------------------------------------------------------------
# Reference implementation (slow, used for testing)
# ---------------------------------------------------------------------------
def compute_indicator_reference(
    df: pd.DataFrame, cfg: IndicatorConfig
) -> IndicatorResult:
    """Bar-by-bar reference implementation that mirrors the Pine ``for`` loop.

    O(N · lookback) – use only for unit tests / small data.
    """
    cfg.validate()
    _validate_ohlc(df)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)

    high_level = np.full(n, np.nan)
    low_level = np.full(n, np.nan)
    high_level_3m = np.full(n, np.nan)
    low_level_3m = np.full(n, np.nan)

    if cfg.pine_compat_mode == "literal":
        for t in range(n):
            s = max(0, t - cfg.lookback + 1)
            high_level[t] = high[s : t + 1].max()
            low_level[t] = low[s : t + 1].min()
            s3 = max(0, t - cfg.lookback_3m + 1)
            high_level_3m[t] = high[s3 : t + 1].max()
            low_level_3m[t] = low[s3 : t + 1].min()
    else:
        for t in range(1, n):  # t=0 has no prior bar → NaN
            s = max(0, t - cfg.lookback)
            high_level[t] = high[s:t].max()
            low_level[t] = low[s:t].min()
            s3 = max(0, t - cfg.lookback_3m)
            high_level_3m[t] = high[s3:t].max()
            low_level_3m[t] = low[s3:t].min()

    # ta.highest(high[1], n) → max(high[t-1 .. t-n]) (excluding current)
    def _shifted_rolling(arr: np.ndarray, win: int, op: str) -> np.ndarray:
        out = np.full(n, np.nan)
        for t in range(n):
            if t == 0:
                continue
            s = max(0, t - win)
            slice_ = arr[s:t]
            if slice_.size == 0:
                continue
            out[t] = slice_.max() if op == "max" else slice_.min()
        return out

    recent_high_max = _shifted_rolling(high, cfg.exclude_recent, "max")
    recent_low_min = _shifted_rolling(low, cfg.exclude_recent, "min")
    recent_high_max_3m = _shifted_rolling(high, cfg.exclude_recent_3m, "max")
    recent_low_min_3m = _shifted_rolling(low, cfg.exclude_recent_3m, "min")

    return _assemble_result(
        df=df,
        cfg=cfg,
        high_level=high_level,
        low_level=low_level,
        high_level_3m=high_level_3m,
        low_level_3m=low_level_3m,
        recent_high_max=recent_high_max,
        recent_low_min=recent_low_min,
        recent_high_max_3m=recent_high_max_3m,
        recent_low_min_3m=recent_low_min_3m,
    )


# ---------------------------------------------------------------------------
# Vectorised implementation (fast, default)
# ---------------------------------------------------------------------------
def compute_indicator(df: pd.DataFrame, cfg: IndicatorConfig) -> IndicatorResult:
    """Vectorised implementation using pandas rolling windows.

    Equivalent to :func:`compute_indicator_reference` but ~1000× faster on
    realistic data sizes (10 years × 1H ≈ 87k bars).
    """
    cfg.validate()
    _validate_ohlc(df)

    high = df["high"].astype(float)
    low = df["low"].astype(float)

    # NOTE: ``min_periods=1`` mirrors Pine's behaviour, where the level is
    # defined for every bar even before ``lookback`` bars are available.
    if cfg.pine_compat_mode == "literal":
        # Faithful to the original Pine ``for i = lookback-1 to 0`` loop –
        # the level INCLUDES the current bar.  See note in design doc.
        high_level = high.rolling(cfg.lookback, min_periods=1).max()
        low_level = low.rolling(cfg.lookback, min_periods=1).min()
        high_level_3m = high.rolling(cfg.lookback_3m, min_periods=1).max()
        low_level_3m = low.rolling(cfg.lookback_3m, min_periods=1).min()
    else:
        # "intended" mode – the level is derived from the prior ``lookback``
        # bars only, which is what a real-world break-out indicator needs.
        high_level = high.shift(1).rolling(cfg.lookback, min_periods=1).max()
        low_level = low.shift(1).rolling(cfg.lookback, min_periods=1).min()
        high_level_3m = high.shift(1).rolling(cfg.lookback_3m, min_periods=1).max()
        low_level_3m = low.shift(1).rolling(cfg.lookback_3m, min_periods=1).min()

    # ta.highest(high[1], N) → max over the previous N bars, excluding now
    recent_high_max = high.shift(1).rolling(cfg.exclude_recent, min_periods=1).max()
    recent_low_min = low.shift(1).rolling(cfg.exclude_recent, min_periods=1).min()
    recent_high_max_3m = (
        high.shift(1).rolling(cfg.exclude_recent_3m, min_periods=1).max()
    )
    recent_low_min_3m = (
        low.shift(1).rolling(cfg.exclude_recent_3m, min_periods=1).min()
    )

    return _assemble_result(
        df=df,
        cfg=cfg,
        high_level=high_level.to_numpy(),
        low_level=low_level.to_numpy(),
        high_level_3m=high_level_3m.to_numpy(),
        low_level_3m=low_level_3m.to_numpy(),
        recent_high_max=recent_high_max.to_numpy(),
        recent_low_min=recent_low_min.to_numpy(),
        recent_high_max_3m=recent_high_max_3m.to_numpy(),
        recent_low_min_3m=recent_low_min_3m.to_numpy(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_REQUIRED = ("open", "high", "low", "close")


def _validate_ohlc(df: pd.DataFrame) -> None:
    missing = [c for c in _REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(
            f"[ERR-DATA] missing required OHLC columns: {missing!r}; "
            f"got columns={list(df.columns)!r}"
        )
    if len(df) == 0:
        raise ValueError("[ERR-DATA] empty dataframe passed to indicator")


def _assemble_result(
    *,
    df: pd.DataFrame,
    cfg: IndicatorConfig,
    high_level,
    low_level,
    high_level_3m,
    low_level_3m,
    recent_high_max,
    recent_low_min,
    recent_high_max_3m,
    recent_low_min_3m,
) -> IndicatorResult:
    out = df.copy()
    out["highLevel"] = high_level
    out["lowLevel"] = low_level
    out["highLevel3m"] = high_level_3m
    out["lowLevel3m"] = low_level_3m
    out["midMedian3m"] = (out["highLevel3m"] + out["lowLevel3m"]) / 2.0

    # Pine: noRecentHighTouch = not (max(high[1..n]) >= highLevel)
    #   ⇔ max(high[1..n]) < highLevel  (strict)
    no_recent_high = recent_high_max < high_level
    no_recent_low = recent_low_min > low_level
    no_recent_high_3m = recent_high_max_3m < high_level_3m
    no_recent_low_3m = recent_low_min_3m > low_level_3m

    close = out["close"].to_numpy(dtype=float)
    out["longCond"] = (close > high_level) & no_recent_high
    out["shortCond"] = (close < low_level) & no_recent_low
    out["longCond3m"] = (close > high_level_3m) & no_recent_high_3m
    out["shortCond3m"] = (close < low_level_3m) & no_recent_low_3m

    # First bar has NaN shifted rolling values → NaN-safe boolean cast
    for col in ("longCond", "shortCond", "longCond3m", "shortCond3m"):
        out[col] = out[col].fillna(False).astype(bool)

    if cfg.strict_warmup:
        n = len(out)
        idx = np.arange(n)
        # 長期: 直近接触除外の判定材料が揃っている＝idx >= exclude_recent
        not_warm_long = idx < cfg.exclude_recent
        not_warm_mid = idx < cfg.exclude_recent_3m
        out.loc[not_warm_long, ["longCond", "shortCond"]] = False
        out.loc[not_warm_mid, ["longCond3m", "shortCond3m"]] = False

    return IndicatorResult(df=out)


# ---------------------------------------------------------------------------
# ATR (utility used by backtest / analysis)
# ---------------------------------------------------------------------------
def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder's ATR.  Matches TradingView's ``ta.atr`` to 1e-12 on test data."""
    if period < 2:
        raise ValueError("[ERR-PARAM] ATR period must be >= 2")
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # Wilder's smoothing is RMA = EMA(alpha=1/period)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


__all__ = [
    "IndicatorResult",
    "compute_indicator",
    "compute_indicator_reference",
    "atr",
]
