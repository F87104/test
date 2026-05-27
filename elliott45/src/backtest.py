"""Event-driven backtester for Elliott Wave 4→5 setups.

Causal rules:
  * A setup created at pivot4-confirm bar ``c`` may be acted on starting
    at bar ``c+1`` (``entry_bar``).
  * Each setup has a *pending* window of ``max_pending_bars`` bars during
    which a trigger price (carried on the setup) must be touched intra-bar.
    The entry fills at the trigger price on the same bar.
  * Once filled, the trade is monitored intra-bar. If both SL and TP can
    be hit in the same bar we conservatively assume SL hit first.
  * A new setup invalidates any earlier still-pending setup.
  * Only one position open at a time.
  * Position size: fixed fractional risk per trade (``risk_per_trade``).
    If ``fixed_sizing`` is True the size is computed off the starting
    equity (no compounding), otherwise off the live equity.
  * No commission / slippage / leverage cap is modelled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .elliott import Setup


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
    reason: str  # "tp", "sl", "timeout"


@dataclass
class BacktestConfig:
    starting_equity: float = 10_000.0
    risk_per_trade: float = 0.01      # fraction of equity risked per trade
    max_pending_bars: int = 24        # how long an unfilled setup stays alive
    max_hold_bars: int = 240          # auto-exit at next close after this many bars
    allow_short: bool = True
    fixed_sizing: bool = False        # if True, position size based on starting equity (no compounding)


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity: pd.Series  # indexed by bar timestamp


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
    pos_qty = 0.0
    pos_sl = 0.0
    pos_tp = 0.0
    pos_entry_bar = 0
    pos_entry_time = None
    pos_setup_idx = -1

    for i in range(n):
        while setup_ptr < len(order) and setups[order[setup_ptr]].entry_bar <= i:
            pending.append(order[setup_ptr])
            setup_ptr += 1
        pending = [k for k in pending if expiries[k] >= i]

        bar_high = high[i]
        bar_low = low[i]

        if in_pos:
            sl_hit = (pos_dir == "long" and bar_low <= pos_sl) or (
                pos_dir == "short" and bar_high >= pos_sl
            )
            tp_hit = (pos_dir == "long" and bar_high >= pos_tp) or (
                pos_dir == "short" and bar_low <= pos_tp
            )
            exit_price: Optional[float] = None
            reason = ""
            if sl_hit and tp_hit:
                exit_price = pos_sl  # conservative: SL first
                reason = "sl"
            elif sl_hit:
                exit_price = pos_sl
                reason = "sl"
            elif tp_hit:
                exit_price = pos_tp
                reason = "tp"
            elif (i - pos_entry_bar) >= cfg.max_hold_bars:
                exit_price = close[i]
                reason = "timeout"
            if exit_price is not None:
                pnl_per_unit = (
                    (exit_price - pos_entry_price)
                    if pos_dir == "long"
                    else (pos_entry_price - exit_price)
                )
                pnl = pnl_per_unit * pos_qty
                risk_per_unit = abs(pos_entry_price - pos_sl)
                r_mult = pnl_per_unit / risk_per_unit if risk_per_unit > 0 else 0.0
                s = setups[pos_setup_idx]
                trades.append(
                    Trade(
                        direction=pos_dir,
                        entry_time=pd.Timestamp(pos_entry_time),
                        entry_price=pos_entry_price,
                        exit_time=pd.Timestamp(times[i]),
                        exit_price=float(exit_price),
                        qty=pos_qty,
                        pnl=float(pnl),
                        r_multiple=float(r_mult),
                        bars_held=int(i - pos_entry_bar),
                        setup_w1=float(s.w1_len),
                        setup_w3=float(s.w3_len),
                        reason=reason,
                    )
                )
                equity += pnl
                in_pos = False

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
                    entry_price = trig
                    risk = abs(entry_price - s.stop_price)
                    if risk > 0:
                        sizing_equity = cfg.starting_equity if cfg.fixed_sizing else equity
                        qty = (sizing_equity * cfg.risk_per_trade) / risk
                        in_pos = True
                        pos_dir = s.direction
                        pos_entry_price = entry_price
                        pos_qty = qty
                        pos_sl = s.stop_price
                        pos_tp = s.target_price
                        pos_entry_bar = i
                        pos_entry_time = times[i]
                        pos_setup_idx = candidate_idx
                    pending = []

        equity_curve[i] = equity

    return BacktestResult(
        trades=trades,
        equity=pd.Series(equity_curve, index=pd.DatetimeIndex(times)),
    )
