"""Event-driven backtester for Elliott Wave 4→5 setups.

Causal rules (audited 2026-05):
  * A setup created at pivot4-confirm bar ``c`` is acted on starting at
    bar ``c+1`` (``entry_bar``).
  * Each setup carries a trigger price. If price touches it intra-bar
    within ``max_pending_bars`` the trade fills at the trigger price
    (+slippage when configured).
  * Intra-bar ordering on subsequent bars (CONSERVATIVE):
      1. Apply the trailing stop update from the PRIOR bar (so the SL
         level in force at bar open is correctly raised).
      2. Snapshot ``sl_at_open`` and check it against bar high/low FIRST.
         If touched, exit at that level — partial TP cannot fire on the
         same bar (we don't know intra-bar order between an upper partial
         and a lower SL, so we default to the SL).
      3. Only if the SL didn't hit, look for partial TP on this bar.
         A partial fire books the partial profit and moves SL to break-
         even, but the new BE level only becomes effective on the NEXT
         bar (mirroring the trail's bar-open semantics).
      4. After partial handling, check TP against bar high/low. If it
         hit, exit the remaining size at TP. (Partial < TP for longs by
         construction, so the natural intra-bar order partial→TP is
         physically plausible.)
      5. Otherwise check the bar-count timeout and exit at close.
  * Exits on the trade's own entry bar are NOT checked (we don't know
    intra-bar order between trigger fill and subsequent SL/TP touches).
    This bias is roughly symmetric.
  * Only one position is open at a time. A new setup invalidates any
    older still-pending setup. No swap is modelled; ``cost_per_trade``
    and ``slippage_atr_mult`` cover spread + commission + execution slip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .elliott import Setup
from .zigzag import atr as atr_series_fn


@dataclass
class Trade:
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    qty: float
    pnl: float
    r_multiple: float
    bars_held: int
    setup_w1: float
    setup_w3: float
    reason: str


@dataclass
class BacktestConfig:
    starting_equity: float = 10_000.0
    risk_per_trade: float = 0.01
    max_pending_bars: int = 24
    max_hold_bars: int = 240
    allow_short: bool = True
    fixed_sizing: bool = False

    # exit improvements
    partial_tp_r: float = 0.0
    partial_tp_size: float = 0.5
    move_be_at_partial: bool = True
    trail_atr_mult: float = 0.0
    trail_atr_period: int = 14
    trail_after_partial_only: bool = False

    # frictions
    cost_per_trade: float = 0.0
    slippage_atr_mult: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity: pd.Series


def run_backtest(
    df: pd.DataFrame,
    setups: list[Setup],
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    cfg = config or BacktestConfig()
    n = len(df)
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    times = df["datetime"].to_numpy()

    need_atr = cfg.trail_atr_mult > 0 or cfg.slippage_atr_mult > 0
    atr_arr = (
        atr_series_fn(df, cfg.trail_atr_period).to_numpy()
        if need_atr else None
    )

    triggers: list[float] = [s.trigger_price for s in setups]
    expiries: list[int] = [s.entry_bar + cfg.max_pending_bars for s in setups]

    order = sorted(range(len(setups)), key=lambda i: setups[i].entry_bar)
    setup_ptr = 0
    pending: list[int] = []

    equity = cfg.starting_equity
    equity_curve = np.full(n, np.nan)
    trades: list[Trade] = []

    in_pos = False
    pos_dir = ""
    pos_entry_price = 0.0
    pos_qty_initial = 0.0
    pos_qty_open = 0.0
    pos_sl = 0.0       # SL level effective at bar open (updated by trail at top of each bar)
    pos_tp = 0.0
    pos_entry_bar = 0
    pos_entry_time = None
    pos_setup_idx = -1
    pos_partial_done = False
    pos_partial_pnl = 0.0
    pos_partial_r = 0.0
    pos_r_per_unit = 0.0

    def _close_position(i: int, exit_price: float, reason: str) -> None:
        nonlocal in_pos, equity
        pnl_per_unit = (
            (exit_price - pos_entry_price)
            if pos_dir == "long"
            else (pos_entry_price - exit_price)
        )
        pnl_remaining = pnl_per_unit * pos_qty_open
        total_pnl = pos_partial_pnl + pnl_remaining
        if cfg.cost_per_trade > 0:
            total_pnl -= cfg.cost_per_trade * pos_qty_initial
        total_r = pos_partial_r
        if pos_r_per_unit > 0:
            total_r += (pnl_per_unit / pos_r_per_unit) * (pos_qty_open / pos_qty_initial)
            if cfg.cost_per_trade > 0:
                total_r -= cfg.cost_per_trade / pos_r_per_unit
        s = setups[pos_setup_idx]
        trades.append(
            Trade(
                direction=pos_dir,
                entry_time=pd.Timestamp(pos_entry_time),
                entry_price=pos_entry_price,
                exit_time=pd.Timestamp(times[i]),
                exit_price=float(exit_price),
                qty=pos_qty_initial,
                pnl=float(total_pnl),
                r_multiple=float(total_r),
                bars_held=int(i - pos_entry_bar),
                setup_w1=float(s.w1_len),
                setup_w3=float(s.w3_len),
                reason=reason,
            )
        )
        equity += total_pnl
        in_pos = False

    for i in range(n):
        while setup_ptr < len(order) and setups[order[setup_ptr]].entry_bar <= i:
            pending.append(order[setup_ptr])
            setup_ptr += 1
        pending = [k for k in pending if expiries[k] >= i]

        bar_high = high[i]
        bar_low = low[i]

        if in_pos:
            # ---- Step 1: trailing stop update from PRIOR bar ----
            # The trail level depends on bar i-1 close + ATR, so it is the
            # level you would have placed before bar i opens.
            if (
                cfg.trail_atr_mult > 0
                and atr_arr is not None
                and (not cfg.trail_after_partial_only or pos_partial_done)
                and i > 0
            ):
                prev_atr = atr_arr[i - 1]
                if not np.isnan(prev_atr) and prev_atr > 0:
                    band = cfg.trail_atr_mult * prev_atr
                    if pos_dir == "long":
                        new_sl = high[i - 1] - band
                        if new_sl > pos_sl:
                            pos_sl = new_sl
                    else:
                        new_sl = low[i - 1] + band
                        if new_sl < pos_sl:
                            pos_sl = new_sl

            # Slippage (applied AGAINST us on a stop fill).
            stop_slip = 0.0
            half_slip = 0.0
            if cfg.slippage_atr_mult > 0 and atr_arr is not None and i > 0:
                prev_atr = atr_arr[i - 1]
                if not np.isnan(prev_atr):
                    stop_slip = cfg.slippage_atr_mult * prev_atr
                    half_slip = 0.5 * cfg.slippage_atr_mult * prev_atr

            # ---- Step 2: SL check FIRST against bar-open SL (conservative) ----
            sl_at_open = pos_sl
            sl_hit = (
                (pos_dir == "long" and bar_low <= sl_at_open)
                or (pos_dir == "short" and bar_high >= sl_at_open)
            )
            if sl_hit:
                exit_price = (
                    sl_at_open - stop_slip if pos_dir == "long"
                    else sl_at_open + stop_slip
                )
                reason = "sl" if not pos_partial_done else "partial+stop"
                _close_position(i, exit_price, reason)

            # ---- Step 3: partial TP (only if SL did not hit) ----
            if in_pos and cfg.partial_tp_r > 0 and not pos_partial_done and pos_r_per_unit > 0:
                if pos_dir == "long":
                    partial_price = pos_entry_price + cfg.partial_tp_r * pos_r_per_unit
                    partial_hit = bar_high >= partial_price
                else:
                    partial_price = pos_entry_price - cfg.partial_tp_r * pos_r_per_unit
                    partial_hit = bar_low <= partial_price
                if partial_hit:
                    eff_partial = (
                        partial_price - half_slip if pos_dir == "long"
                        else partial_price + half_slip
                    )
                    closed_qty = pos_qty_initial * cfg.partial_tp_size
                    pnl_unit = (
                        (eff_partial - pos_entry_price)
                        if pos_dir == "long"
                        else (pos_entry_price - eff_partial)
                    )
                    pos_partial_pnl += pnl_unit * closed_qty
                    if pos_r_per_unit > 0:
                        pos_partial_r += (pnl_unit / pos_r_per_unit) * (closed_qty / pos_qty_initial)
                    pos_qty_open -= closed_qty
                    pos_partial_done = True
                    if cfg.move_be_at_partial:
                        # BE applies from NEXT bar, mirroring trail semantics.
                        pos_sl = pos_entry_price

            # ---- Step 4: TP check ----
            if in_pos:
                tp_hit = (
                    (pos_dir == "long" and bar_high >= pos_tp)
                    or (pos_dir == "short" and bar_low <= pos_tp)
                )
                if tp_hit:
                    _close_position(i, pos_tp, "tp")

            # ---- Step 5: timeout ----
            if in_pos and (i - pos_entry_bar) >= cfg.max_hold_bars:
                _close_position(i, close[i], "timeout")

        # Entry handling (after exits on the same bar — entries do NOT
        # check exits on their own bar).
        if not in_pos and pending:
            pending.sort(key=lambda k: setups[k].entry_bar)
            candidate_idx = pending[-1]
            s = setups[candidate_idx]
            if not cfg.allow_short and s.direction == "short":
                pending.remove(candidate_idx)
            else:
                trig = triggers[candidate_idx]
                triggered = (
                    (s.direction == "long" and bar_high >= trig)
                    or (s.direction == "short" and bar_low <= trig)
                )
                if triggered:
                    slip = 0.0
                    if cfg.slippage_atr_mult > 0 and atr_arr is not None and i > 0:
                        prev_atr = atr_arr[i - 1]
                        if not np.isnan(prev_atr):
                            slip = cfg.slippage_atr_mult * prev_atr
                    entry_price = (
                        trig + slip if s.direction == "long" else trig - slip
                    )
                    risk = abs(entry_price - s.stop_price)
                    if risk > 0:
                        sizing_equity = cfg.starting_equity if cfg.fixed_sizing else equity
                        qty = (sizing_equity * cfg.risk_per_trade) / risk
                        in_pos = True
                        pos_dir = s.direction
                        pos_entry_price = entry_price
                        pos_qty_initial = qty
                        pos_qty_open = qty
                        pos_sl = s.stop_price
                        pos_tp = s.target_price
                        pos_entry_bar = i
                        pos_entry_time = times[i]
                        pos_setup_idx = candidate_idx
                        pos_partial_done = False
                        pos_partial_pnl = 0.0
                        pos_partial_r = 0.0
                        pos_r_per_unit = risk
                    pending = []

        equity_curve[i] = equity

    return BacktestResult(
        trades=trades,
        equity=pd.Series(equity_curve, index=pd.DatetimeIndex(times)),
    )
