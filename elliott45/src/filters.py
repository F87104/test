"""Quality filters applied on top of detected Elliott Wave 4→5 setups.

The detector in ``elliott.py`` enforces the *Elliott rules* themselves.
Everything in this file is an *optional quality gate* that uses
information available at, or before, the entry bar so the backtest stays
causal.

Each filter takes ``df`` (the full OHLCV frame) and a list of setups and
returns the subset that survives. All filters can be combined.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .elliott import Setup
from .zigzag import atr


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


@dataclass
class FilterConfig:
    # --- trend alignment ---
    use_trend: bool = False
    trend_ema_period: int = 200

    # --- volatility regime: skip setups when ATR is in a noisy tail ---
    use_atr_regime: bool = False
    atr_regime_period: int = 14
    atr_regime_window: int = 1000      # rolling sample to compute percentile
    atr_low_pct: float = 0.20          # skip below this percentile (dead market)
    atr_high_pct: float = 0.97         # skip above this percentile (gap/spike)

    # --- wave-3 strength: filter weak impulses ---
    use_w3_strength: bool = False
    w3_min_ratio: float = 1.272        # W3 / W1

    # --- alternation principle: W2 and W4 should differ in character ---
    use_alternation: bool = False
    alternation_min_diff: float = 0.20  # |w2_retrace − w4_retrace|

    # --- minimum reward / risk at entry ---
    use_min_rr: bool = False
    min_rr: float = 1.50               # (target − trigger) / (trigger − stop)


def _entry_bar_value(series: np.ndarray, idx: int) -> float:
    if idx < 0 or idx >= len(series):
        return np.nan
    return float(series[idx])


def apply_filters(
    df: pd.DataFrame,
    setups: list[Setup],
    cfg: FilterConfig,
) -> list[Setup]:
    if not setups:
        return setups

    ema_arr: np.ndarray | None = None
    if cfg.use_trend:
        ema_arr = _ema(df["close"], cfg.trend_ema_period).to_numpy()

    atr_pct_arr: np.ndarray | None = None
    if cfg.use_atr_regime:
        atr_series = atr(df, cfg.atr_regime_period)
        atr_pct_arr = (
            atr_series.rolling(cfg.atr_regime_window, min_periods=cfg.atr_regime_window // 5)
            .rank(pct=True)
            .to_numpy()
        )

    close_arr = df["close"].to_numpy()
    out: list[Setup] = []
    for s in setups:
        # Use the confirmation bar (last bar with information) rather than the
        # entry bar, so the gate uses past-only state.
        eval_idx = max(s.p4.confirm_idx, 0)

        if cfg.use_trend and ema_arr is not None:
            ema_v = _entry_bar_value(ema_arr, eval_idx)
            if np.isnan(ema_v):
                continue
            close_v = _entry_bar_value(close_arr, eval_idx)
            if s.direction == "long" and not (close_v > ema_v):
                continue
            if s.direction == "short" and not (close_v < ema_v):
                continue

        if cfg.use_atr_regime and atr_pct_arr is not None:
            pct = _entry_bar_value(atr_pct_arr, eval_idx)
            if np.isnan(pct):
                continue
            if not (cfg.atr_low_pct <= pct <= cfg.atr_high_pct):
                continue

        if cfg.use_w3_strength:
            if s.w1_len <= 0:
                continue
            if (s.w3_len / s.w1_len) < cfg.w3_min_ratio:
                continue

        if cfg.use_alternation:
            if abs(s.w2_retrace - s.w4_retrace) < cfg.alternation_min_diff:
                continue

        if cfg.use_min_rr:
            risk = abs(s.trigger_price - s.stop_price)
            reward = abs(s.target_price - s.trigger_price)
            if risk <= 0 or (reward / risk) < cfg.min_rr:
                continue

        out.append(s)

    return out
