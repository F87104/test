"""ATR-aware ZigZag pivot detector.

Pivots alternate strictly between ``high`` and ``low``. A new pivot is
confirmed only after price moves against the running extreme by at least
``threshold * ATR(atr_period)`` measured at the candidate pivot bar.

The detector is fully causal: pivot ``i`` is confirmed at the bar where
the reversal threshold is crossed, never before. This is what we use to
gate entries so the backtest cannot peek ahead.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Pivot:
    idx: int          # bar index of the extreme high/low
    confirm_idx: int  # bar index where the reversal threshold was crossed
    price: float
    kind: str         # "H" or "L"


def true_range(df: pd.DataFrame) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.rolling(period, min_periods=period).mean()


def find_pivots(
    df: pd.DataFrame,
    threshold_atr: float = 3.0,
    atr_period: int = 14,
) -> list[Pivot]:
    """Causal ATR-based ZigZag.

    Parameters
    ----------
    threshold_atr
        Reversal amount expressed as ATR multiples. Larger values yield
        fewer, more meaningful pivots.
    """

    if len(df) < atr_period + 2:
        return []

    atr_series = atr(df, atr_period).to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()

    pivots: list[Pivot] = []

    # Seed: start by assuming the first valid bar is both extreme candidates.
    start = atr_period
    direction = 0  # 0 unknown, +1 looking for next high (last pivot was low), -1 vice versa
    ext_idx = start
    ext_price = high[start]
    ext_kind = "H"

    # Track the opposite extreme candidate while we wait for confirmation.
    alt_idx = start
    alt_price = low[start]

    for i in range(start + 1, len(df)):
        a = atr_series[i] if not np.isnan(atr_series[i]) else atr_series[atr_period]
        if np.isnan(a) or a <= 0:
            continue
        thr = threshold_atr * a

        if ext_kind == "H":
            # Update running high.
            if high[i] > ext_price:
                ext_price = high[i]
                ext_idx = i
                alt_price = low[i]
                alt_idx = i
            else:
                # Track lowest low since the running high.
                if low[i] < alt_price:
                    alt_price = low[i]
                    alt_idx = i
                # Confirm reversal once we have dropped enough from the high.
                if ext_price - low[i] >= thr:
                    pivots.append(
                        Pivot(
                            idx=ext_idx,
                            confirm_idx=i,
                            price=ext_price,
                            kind="H",
                        )
                    )
                    ext_kind = "L"
                    ext_price = alt_price
                    ext_idx = alt_idx
                    alt_price = high[i]
                    alt_idx = i
        else:  # ext_kind == "L"
            if low[i] < ext_price:
                ext_price = low[i]
                ext_idx = i
                alt_price = high[i]
                alt_idx = i
            else:
                if high[i] > alt_price:
                    alt_price = high[i]
                    alt_idx = i
                if high[i] - ext_price >= thr:
                    pivots.append(
                        Pivot(
                            idx=ext_idx,
                            confirm_idx=i,
                            price=ext_price,
                            kind="L",
                        )
                    )
                    ext_kind = "H"
                    ext_price = alt_price
                    ext_idx = alt_idx
                    alt_price = low[i]
                    alt_idx = i

    return pivots
