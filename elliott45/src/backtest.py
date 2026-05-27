"""Event-driven backtester for Elliott Wave 4→5 setups.

Causal rules:
  * A setup created at pivot4-confirm bar ``c`` is acted on starting at
    bar ``c+1`` (``entry_bar``).
  * Each setup carries a trigger price (computed in ``elliott.py`` from
    ``entry_buffer_frac``). If price touches it intra-bar within
    ``max_pending_bars`` the trade fills at the trigger price.
  * Once filled, the trade is monitored intra-bar. If SL and TP can both
    be hit in the same bar we conservatively assume SL hit first.
  * Optional exit improvements (all causal):
      - ``partial_tp_r``      : at price = entry + R × multiple, close
                                ``partial_tp_size`` fraction of the
                                position and (optionally) move the stop
                                to breakeven.
      - ``move_be_at_partial``: when the partial TP triggers, move SL to
                                the entry price.
      - ``trail_atr_mult``    : after entry, trail a Chandelier-style stop
                                using ATR (causal: uses previous bar ATR).
  * Only one position open at a time. A new setup invalidates any older
    still-pending setup. No commission/slippage/swap modelled.
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
    reason: str  # "tp", "sl", "timeout", "trail", "partial+stop"


@dataclass
class BacktestConfig:
    starting_equity: float = 10_000.0
    risk_per_trade: float = 0.01
    max_pending_bars: int = 24
    max_hold_bars: int = 240
    allow_short: bool = True
    fixed_sizing: bool = False

    # exit improvements
    partial_tp_r: float = 0.0          # 0 disables; e.g. 1.0 = take half at +1R
    partial_tp_size: float = 0.5       # fraction of position closed on partial
    move_be_at_partial: bool = True    # move SL to breakeven when partial fires
    trail_atr_mult: float = 0.0        # 0 disables; e.g. 3.0 = trail by 3×ATR
    trail_atr_period: int = 14
    trail_after_partial_only: bool = False  # if True, only start trailing once partial fired
    cost_per_trade: float = 0.0    # round-trip cost in price units (spread+commission); subtracted from pnl per unit
    slippage_atr_mult: float = 0.0  # per-side ATR slippage applied AGAINST us on entry / SL / trail / partial


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
        if need_atr
        else None
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
    pos_sl = 0.0
    pos_tp = 0.0
    pos_entry_bar = 0
    pos_entry_time = None
    pos_setup_idx = -1
    pos_partial_done = False
    pos_partial_pnl = 0.0
    pos_partial_r = 0.0
    pos_r_per_unit = 0.0     # |entry − initial SL|, the R denominator

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
        total_r = (
            pos_partial_r
            + (pnl_per_unit / pos_r_per_unit) * (pos_qty_open / pos_qty_initial)
            if pos_r_per_unit > 0
            else 0.0
        )
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
            # 1) Partial TP check (intra-bar). Conservative: even if SL also
            #    touches we let the partial fire only if its price is "closer"
            #    to the previous close than the SL is.
            if (
                cfg.partial_tp_r > 0
                and not pos_partial_done
                and pos_r_per_unit > 0
            ):
                if pos_dir == "long":
                    partial_price = pos_entry_price + cfg.partial_tp_r * pos_r_per_unit
                    partial_hit = bar_high >= partial_price
                else:
                    partial_price = pos_entry_price - cfg.partial_tp_r * pos_r_per_unit
                    partial_hit = bar_low <= partial_price
                if partial_hit:
                    half_slip = 0.0
                    if cfg.slippage_atr_mult > 0 and atr_arr is not None:
                        prev_atr = atr_arr[i - 1] if i > 0 else 0.0
                        if not np.isnan(prev_atr):
                            half_slip = 0.5 * cfg.slippage_atr_mult * prev_atr
                    effective_partial = (
                        partial_price - half_slip if pos_dir == "long" else partial_price + half_slip
                    )
                    closed_qty = pos_qty_initial * cfg.partial_tp_size
                    pnl_unit = (
                        (effective_partial - pos_entry_price)
                        if pos_dir == "long"
                        else (pos_entry_price - effective_partial)
                    )
                    pos_partial_pnl += pnl_unit * closed_qty
                    pos_partial_r += (pnl_unit / pos_r_per_unit) * (closed_qty / pos_qty_initial) if pos_r_per_unit > 0 else 0.0
                    pos_qty_open -= closed_qty
                    pos_partial_done = True
                    if cfg.move_be_at_partial:
                        pos_sl = pos_entry_price

            # 2) Trailing stop (Chandelier) update — uses previous bar ATR so
            #    it's causal within this bar.
            if (
                cfg.trail_atr_mult > 0
                and atr_arr is not None
                and (not cfg.trail_after_partial_only or pos_partial_done)
            ):
                prev_atr = atr_arr[i - 1] if i > 0 else np.nan
                if not np.isnan(prev_atr) and prev_atr > 0:
                    band = cfg.trail_atr_mult * prev_atr
                    if pos_dir == "long":
                        new_sl = high[i - 1] - band if i > 0 else pos_sl
                        if new_sl > pos_sl:
                            pos_sl = new_sl
                    else:
                        new_sl = low[i - 1] + band if i > 0 else pos_sl
                        if new_sl < pos_sl:
                            pos_sl = new_sl

            # 3) Standard SL/TP/timeout exits.
            sl_hit = (pos_dir == "long" and bar_low <= pos_sl) or (
                pos_dir == "short" and bar_high >= pos_sl
            )
            tp_hit = (pos_dir == "long" and bar_high >= pos_tp) or (
                pos_dir == "short" and bar_low <= pos_tp
            )
            exit_price: Optional[float] = None
            reason = ""
            stop_slip = 0.0
            if cfg.slippage_atr_mult > 0 and atr_arr is not None:
                prev_atr = atr_arr[i - 1] if i > 0 else 0.0
                if not np.isnan(prev_atr):
                    stop_slip = cfg.slippage_atr_mult * prev_atr
            if sl_hit and tp_hit:
                exit_price = pos_sl - stop_slip if pos_dir == "long" else pos_sl + stop_slip
                reason = "sl" if not pos_partial_done else "partial+stop"
            elif sl_hit:
                exit_price = pos_sl - stop_slip if pos_dir == "long" else pos_sl + stop_slip
                reason = "sl" if not pos_partial_done else "partial+stop"
            elif tp_hit:
                exit_price = pos_tp
                reason = "tp"
            elif (i - pos_entry_bar) >= cfg.max_hold_bars:
                exit_price = close[i]
                reason = "timeout"
            if exit_price is not None:
                _close_position(i, exit_price, reason)

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
                    if cfg.slippage_atr_mult > 0 and atr_arr is not None:
                        prev_atr = atr_arr[i - 1] if i > 0 else 0.0
                        if not np.isnan(prev_atr):
                            slip = cfg.slippage_atr_mult * prev_atr
                    entry_price = trig + slip if s.direction == "long" else trig - slip
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
