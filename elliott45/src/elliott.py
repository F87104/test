"""Elliott Wave 4 → 5 setup detector.

We look at the last 5 confirmed ZigZag pivots and check whether they
plausibly form waves 0 → 1 → 2 → 3 → 4 of an Elliott impulse.

Strict rules enforced (Elliott, 5-wave impulse):
  R1. Wave 2 does not retrace beyond the start of wave 1 (point 0).
  R2. Wave 4 does not enter wave 1 territory:
        - bull: low(W4) > high(end of W1)  → P4 > P1
        - bear: high(W4) < low(end of W1)  → P4 < P1
  R3. Wave 3 is not the shortest of waves 1 and 3 (wave 5 is unknown):
        len(W3) > len(W1)
  R4. Wave 3 makes a higher (or lower) extreme than wave 1 end.

Soft rules (configurable):
  S1. Wave 2 retrace fraction of wave 1 in [r2_min, r2_max].
  S2. Wave 4 retrace fraction of wave 3 in [r4_min, r4_max].
  S3. Wave 4 must be a clean correction: shorter in price than wave 3.

The setup is "confirmed" only at the bar where pivot 4 is confirmed by
the ZigZag detector — that is when we are allowed to act.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .zigzag import Pivot, find_pivots


@dataclass
class Setup:
    direction: str             # "long" or "short"
    p0: Pivot
    p1: Pivot
    p2: Pivot
    p3: Pivot
    p4: Pivot
    w1_len: float
    w3_len: float
    w2_retrace: float
    w4_retrace: float
    entry_bar: int             # bar at which we may submit the order (next bar after p4 confirmation)
    entry_ref_price: float     # reference price = pivot4 price (we trigger when price reclaims this with buffer)
    trigger_price: float       # the actual stop-entry price we wait for
    stop_price: float
    target_price: float


@dataclass
class WaveParams:
    r2_min: float = 0.236
    r2_max: float = 0.886
    r4_min: float = 0.118
    r4_max: float = 0.618
    require_w3_longer_than_w1: bool = True
    # Wave 5 target as Fibonacci extension of wave 1 measured from end of wave 4.
    target_w1_mult: float = 1.000
    # Stop placed beyond pivot 4 by this fraction of wave 4 length.
    # 0.5 keeps the SL comfortably below the swing low without being absurd.
    stop_buffer_frac: float = 0.50
    # Confirmation: price must move past pivot 4 by this fraction of wave 4 length
    # (in the direction of wave 5) before we enter. Keeps us causal.
    entry_buffer_frac: float = 0.20


def _classify(p0: Pivot, p1: Pivot, p2: Pivot, p3: Pivot, p4: Pivot) -> Optional[str]:
    seq_bull = ("L", "H", "L", "H", "L")
    seq_bear = ("H", "L", "H", "L", "H")
    kinds = (p0.kind, p1.kind, p2.kind, p3.kind, p4.kind)
    if kinds == seq_bull:
        return "long"
    if kinds == seq_bear:
        return "short"
    return None


def _validate(direction: str, p0, p1, p2, p3, p4, params: WaveParams) -> Optional[Setup]:
    if direction == "long":
        # Monotonic constraints implied by classification, but be defensive.
        if not (p1.price > p0.price and p2.price < p1.price and p3.price > p2.price and p4.price < p3.price):
            return None
        # R1: wave 2 does not break wave 1 start.
        if p2.price <= p0.price:
            return None
        # R2: wave 4 does not enter wave 1 price territory.
        if p4.price <= p1.price:
            return None
        w1 = p1.price - p0.price
        w3 = p3.price - p2.price
        if w1 <= 0 or w3 <= 0:
            return None
        if params.require_w3_longer_than_w1 and w3 <= w1:
            return None
        w2_retr = (p1.price - p2.price) / w1
        w4_retr = (p3.price - p4.price) / w3
        if not (params.r2_min <= w2_retr <= params.r2_max):
            return None
        if not (params.r4_min <= w4_retr <= params.r4_max):
            return None
        w4_len = p3.price - p4.price
        stop = p4.price - params.stop_buffer_frac * w4_len
        trigger = p4.price + params.entry_buffer_frac * w4_len
        target = p4.price + params.target_w1_mult * w1
        entry_ref = p4.price
        return Setup(
            direction="long",
            p0=p0, p1=p1, p2=p2, p3=p3, p4=p4,
            w1_len=w1, w3_len=w3, w2_retrace=w2_retr, w4_retrace=w4_retr,
            entry_bar=p4.confirm_idx + 1,
            entry_ref_price=entry_ref,
            trigger_price=trigger,
            stop_price=stop,
            target_price=target,
        )
    else:  # short
        if not (p1.price < p0.price and p2.price > p1.price and p3.price < p2.price and p4.price > p3.price):
            return None
        if p2.price >= p0.price:
            return None
        if p4.price >= p1.price:
            return None
        w1 = p0.price - p1.price
        w3 = p2.price - p3.price
        if w1 <= 0 or w3 <= 0:
            return None
        if params.require_w3_longer_than_w1 and w3 <= w1:
            return None
        w2_retr = (p2.price - p1.price) / w1
        w4_retr = (p4.price - p3.price) / w3
        if not (params.r2_min <= w2_retr <= params.r2_max):
            return None
        if not (params.r4_min <= w4_retr <= params.r4_max):
            return None
        w4_len = p4.price - p3.price
        stop = p4.price + params.stop_buffer_frac * w4_len
        trigger = p4.price - params.entry_buffer_frac * w4_len
        target = p4.price - params.target_w1_mult * w1
        entry_ref = p4.price
        return Setup(
            direction="short",
            p0=p0, p1=p1, p2=p2, p3=p3, p4=p4,
            w1_len=w1, w3_len=w3, w2_retrace=w2_retr, w4_retrace=w4_retr,
            entry_bar=p4.confirm_idx + 1,
            entry_ref_price=entry_ref,
            trigger_price=trigger,
            stop_price=stop,
            target_price=target,
        )


def detect_setups(
    df: pd.DataFrame,
    *,
    threshold_atr: float = 3.0,
    atr_period: int = 14,
    params: Optional[WaveParams] = None,
) -> list[Setup]:
    """Return all confirmed Wave-4→5 setups, in chronological order."""

    params = params or WaveParams()
    pivots = find_pivots(df, threshold_atr=threshold_atr, atr_period=atr_period)
    setups: list[Setup] = []
    for i in range(4, len(pivots)):
        p0, p1, p2, p3, p4 = pivots[i - 4:i + 1]
        direction = _classify(p0, p1, p2, p3, p4)
        if direction is None:
            continue
        setup = _validate(direction, p0, p1, p2, p3, p4, params)
        if setup is None:
            continue
        if setup.entry_bar >= len(df):
            continue
        setups.append(setup)
    return setups
