"""
Elliott 5-Wave Targeting Strategy - Python Backtester
=====================================================

Faithful Python reproduction of the trading method described in
F87104/sai : エリオット波動.pdf (Chapter 4) + 手法.pdf (§55, §56).

Same logic as ``elliott_5wave_saido.pine`` so that Pine and Python results
should be directly comparable.

Designed to run on the CSV files already in the repository
(``AUDJPY_H1_2025.csv`` etc.).

Usage
-----
    python elliott_5wave_backtest.py PATH/TO/FILE.csv [--symbol AUDJPY] [--tp ...]

Or to scan many files / parameter sets:
    python elliott_5wave_backtest.py --scan ../../  --out results/scan.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable, List, Optional


# =============================================================================
# Config
# =============================================================================
@dataclass
class Config:
    # Ichimoku
    tenkan: int = 9
    kijun: int = 26
    senkou_b: int = 52
    displacement: int = 26

    # Strict Elliott rules
    rule_w3_not_shortest: bool = True
    rule_w2_no_break: bool = True
    rule_w4_no_break: bool = True

    # Fibonacci retrace filter
    use_fib_filter: bool = True
    w2_min_pct: float = 38.2
    w2_max_pct: float = 90.0
    w4_min_pct: float = 20.0
    w4_max_pct: float = 70.0

    # Entry trigger
    require_swing_break: bool = False
    swing_lookback: int = 5

    # Higher timeframe filter (we approximate by aggregating same CSV)
    use_htf_filter: bool = True
    htf_multiplier: int = 4   # e.g. H1 chart -> H4 long TF
    htf_kind: str = "Cloud"   # "Cloud" or "EMA_slope"
    htf_ema_len: int = 50

    # Risk / exit
    sl_mode: str = "Wave2"     # "Wave2" or "Wave1Start"
    sl_buffer_atr: float = 0.2
    atr_len: int = 14
    tp_mode: str = "Hybrid"    # "Fib_61_8" "Fib_161_8" "Trail_ATR" "Hybrid"
    trail_atr_mult: float = 2.0
    max_bars_in_trade: int = 200

    # Direction
    direction: str = "Both"    # "Long" "Short" "Both"

    # Costs (per round-trip, fraction of price)
    commission_pct: float = 0.00002     # 0.2 bps each side ~ retail FX-ish
    slippage_pct: float = 0.00005

    # Initial capital
    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01        # 1% risk per trade

    # Backtest window
    start_year: Optional[int] = None
    end_year: Optional[int] = None


# =============================================================================
# Data loading
# =============================================================================
@dataclass
class Bar:
    t: str          # timestamp string, original
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


def load_csv(path: str) -> List[Bar]:
    bars: List[Bar] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        # Try to detect headers
        sniff = f.read(4096)
        f.seek(0)
        has_header = any(k in sniff.lower() for k in ("time", "date", "open"))
        reader = csv.reader(f)
        if has_header:
            header = next(reader)
            # Normalize column names: strip <> brackets and lowercase
            def norm(s):
                return s.strip().strip("<>").lower()
            cols = {norm(h): i for i, h in enumerate(header)}
            def col(*names):
                for n in names:
                    if n in cols:
                        return cols[n]
                return None
            # If both date and time exist as separate columns, prefer date+time
            i_date = col("dtyyyymmdd", "date")
            i_time_only = col("time") if i_date is not None else None
            if i_date is not None:
                i_t = i_date
                i_t2 = i_time_only
            else:
                i_t = col("datetime", "timestamp", "time")
                i_t2 = None
            i_o   = col("open", "o")
            i_h   = col("high", "h")
            i_l   = col("low",  "l")
            i_c   = col("close", "c")
            i_v   = col("volume", "vol", "v")
            if i_o is None or i_h is None or i_l is None or i_c is None:
                # Fallback to positional: skip header anyway
                pass
            for row in reader:
                try:
                    if i_o is None:
                        continue
                    ts = ""
                    if i_t is not None:
                        ts = row[i_t]
                        if i_t2 is not None:
                            ts = f"{row[i_t]} {row[i_t2]}"
                    bars.append(Bar(
                        t=ts,
                        o=float(row[i_o]),
                        h=float(row[i_h]),
                        l=float(row[i_l]),
                        c=float(row[i_c]),
                        v=float(row[i_v]) if i_v is not None and row[i_v] else 0.0,
                    ))
                except (ValueError, IndexError):
                    continue
        else:
            for row in reader:
                # Common headerless format: YYYY.MM.DD HH:MM,O,H,L,C,V
                try:
                    if len(row) >= 6:
                        bars.append(Bar(t=str(row[0]), o=float(row[1]), h=float(row[2]),
                                        l=float(row[3]), c=float(row[4]),
                                        v=float(row[5]) if row[5] else 0.0))
                    elif len(row) >= 5:
                        # date,time,o,h,l,c
                        bars.append(Bar(t=f"{row[0]} {row[1]}", o=float(row[2]),
                                        h=float(row[3]), l=float(row[4]), c=float(row[5])))
                except (ValueError, IndexError):
                    continue
    return bars


def extract_year(ts: str) -> Optional[int]:
    """Extract year from common formats: YYYYMMDD, YYYY-MM-DD, YYYY.MM.DD HH:MM, etc."""
    if not ts:
        return None
    s = ts.strip()
    try:
        return int(s[:4])
    except (ValueError, TypeError):
        return None


# =============================================================================
# Indicators
# =============================================================================
def donchian_mid(bars: List[Bar], length: int) -> List[float]:
    n = len(bars)
    out = [math.nan] * n
    for i in range(n):
        if i + 1 < length:
            continue
        hi = max(b.h for b in bars[i + 1 - length : i + 1])
        lo = min(b.l for b in bars[i + 1 - length : i + 1])
        out[i] = (hi + lo) / 2.0
    return out


def true_range(bars: List[Bar]) -> List[float]:
    n = len(bars)
    out = [math.nan] * n
    for i in range(n):
        if i == 0:
            out[i] = bars[i].h - bars[i].l
        else:
            pc = bars[i - 1].c
            out[i] = max(bars[i].h - bars[i].l,
                         abs(bars[i].h - pc),
                         abs(bars[i].l - pc))
    return out


def rolling_mean(x: List[float], length: int) -> List[float]:
    n = len(x)
    out = [math.nan] * n
    s = 0.0
    q: List[float] = []
    for i, v in enumerate(x):
        if math.isnan(v):
            v = 0.0
        q.append(v)
        s += v
        if len(q) > length:
            s -= q.pop(0)
        if len(q) == length:
            out[i] = s / length
    return out


def ema(x: List[float], length: int) -> List[float]:
    n = len(x)
    out = [math.nan] * n
    k = 2.0 / (length + 1.0)
    seeded = False
    for i, v in enumerate(x):
        if math.isnan(v):
            continue
        if not seeded:
            out[i] = v
            seeded = True
        else:
            out[i] = v * k + out[i - 1] * (1 - k)
    return out


def aggregate(bars: List[Bar], factor: int) -> List[Bar]:
    """Aggregate consecutive `factor` bars into one (e.g. H1 -> H4 with factor=4).

    The aggregation here is *index-based* rather than calendar-aware, which is a
    simplification but adequate for relative trend filtering.
    """
    out: List[Bar] = []
    i = 0
    n = len(bars)
    while i < n:
        chunk = bars[i : i + factor]
        if not chunk:
            break
        out.append(Bar(
            t=chunk[0].t,
            o=chunk[0].o,
            h=max(b.h for b in chunk),
            l=min(b.l for b in chunk),
            c=chunk[-1].c,
            v=sum(b.v for b in chunk),
        ))
        i += factor
    return out


# =============================================================================
# Strategy state
# =============================================================================
@dataclass
class WaveState:
    direction: int           # +1 long, -1 short
    state: int = 0           # 0 idle, 1..4 inside wave N
    w0_price: float = math.nan   # wave 1 start (low for long, high for short)
    w0_bar:   int   = -1
    w1_price: float = math.nan
    w1_bar:   int   = -1
    w2_price: float = math.nan
    w2_bar:   int   = -1
    w3_price: float = math.nan
    w3_bar:   int   = -1
    w4_price: float = math.nan
    w4_bar:   int   = -1


@dataclass
class Trade:
    direction: int
    entry_bar: int
    entry_time: str
    entry_price: float
    sl: float
    tp: float
    qty: float
    exit_bar: int = -1
    exit_time: str = ""
    exit_price: float = math.nan
    exit_reason: str = ""
    pnl: float = 0.0


# =============================================================================
# Core backtest
# =============================================================================
def backtest(bars: List[Bar], cfg: Config) -> dict:
    n = len(bars)
    if n < cfg.senkou_b + cfg.displacement + 50:
        return {"error": "not enough bars", "n": n, "trades": [], "equity_curve": []}

    # Ichimoku cloud (Senkou values plotted at +displacement, but for "cloud at now"
    # we use Senkou values from `displacement` bars ago)
    tenkan   = donchian_mid(bars, cfg.tenkan)
    kijun    = donchian_mid(bars, cfg.kijun)
    senkouA  = [(t + k) / 2.0 if not (math.isnan(t) or math.isnan(k)) else math.nan
                for t, k in zip(tenkan, kijun)]
    senkouB  = donchian_mid(bars, cfg.senkou_b)

    def cloud_at_now(i: int):
        idx = i - cfg.displacement
        if idx < 0:
            return (math.nan, math.nan)
        a, b = senkouA[idx], senkouB[idx]
        if math.isnan(a) or math.isnan(b):
            return (math.nan, math.nan)
        return (max(a, b), min(a, b))

    # ATR
    tr   = true_range(bars)
    atr  = rolling_mean(tr, cfg.atr_len)

    # Higher TF for trend filter
    htf_bars = aggregate(bars, cfg.htf_multiplier) if cfg.use_htf_filter else []
    htf_tenkan  = donchian_mid(htf_bars, cfg.tenkan)
    htf_kijun   = donchian_mid(htf_bars, cfg.kijun)
    htf_senkA   = [(t + k) / 2.0 if not (math.isnan(t) or math.isnan(k)) else math.nan
                   for t, k in zip(htf_tenkan, htf_kijun)]
    htf_senkB   = donchian_mid(htf_bars, cfg.senkou_b)
    htf_ema     = ema([b.c for b in htf_bars], cfg.htf_ema_len) if htf_bars else []

    def htf_idx(i: int) -> int:
        return i // cfg.htf_multiplier

    def htf_ok(i: int, direction: int) -> bool:
        if not cfg.use_htf_filter:
            return True
        hi = htf_idx(i)
        if hi >= len(htf_bars):
            return True
        if cfg.htf_kind == "Cloud":
            ai = hi - cfg.displacement
            if ai < 0:
                return True
            a, b = htf_senkA[ai], htf_senkB[ai]
            if math.isnan(a) or math.isnan(b):
                return True
            top = max(a, b); bot = min(a, b)
            c = htf_bars[hi].c
            return (c > top) if direction > 0 else (c < bot)
        elif cfg.htf_kind == "EMA_slope":
            if hi == 0:
                return True
            e_now = htf_ema[hi]
            e_prev = htf_ema[hi - 1]
            if math.isnan(e_now) or math.isnan(e_prev):
                return True
            c = htf_bars[hi].c
            if direction > 0:
                return (e_now > e_prev) and (c > e_now)
            else:
                return (e_now < e_prev) and (c < e_now)
        return True

    # Backtest variables
    cash = cfg.initial_capital
    equity_curve: List[float] = []
    trades: List[Trade] = []
    open_trade: Optional[Trade] = None
    L = WaveState(direction=+1)
    S = WaveState(direction=-1)

    # Cloud state buffer
    prev_above = False
    prev_below = False

    # Hybrid TP tracking
    half_done = False
    trail = math.nan

    allow_long  = cfg.direction in ("Long",  "Both")
    allow_short = cfg.direction in ("Short", "Both")

    for i in range(n):
        b = bars[i]
        top, bot = cloud_at_now(i)
        if math.isnan(top):
            equity_curve.append(cash)
            continue

        above = b.c > top
        below = b.c < bot
        inside = (not above) and (not below)
        cross_up   = above and not prev_above
        cross_down = below and not prev_below

        # ---------- Manage open trade FIRST (intrabar) ----------
        if open_trade is not None:
            t = open_trade
            exit_now = False
            exit_price = math.nan
            exit_reason = ""

            if t.direction > 0:
                # Check SL hit (low <= SL)
                if b.l <= t.sl:
                    exit_now = True
                    exit_price = t.sl
                    exit_reason = "SL"
                # Check fixed TP hit (high >= TP)
                elif not math.isnan(t.tp) and b.h >= t.tp:
                    exit_now = True
                    exit_price = t.tp
                    exit_reason = "TP_Fib"
            else:
                if b.h >= t.sl:
                    exit_now = True
                    exit_price = t.sl
                    exit_reason = "SL"
                elif not math.isnan(t.tp) and b.l <= t.tp:
                    exit_now = True
                    exit_price = t.tp
                    exit_reason = "TP_Fib"

            # Trailing (only if not yet exited)
            if not exit_now and cfg.tp_mode in ("Trail_ATR", "Hybrid"):
                a = atr[i]
                if not math.isnan(a):
                    dist = cfg.trail_atr_mult * a
                    if t.direction > 0:
                        new_trail = b.c - dist
                        trail = new_trail if math.isnan(trail) else max(trail, new_trail)
                        if b.l <= trail:
                            exit_now = True
                            exit_price = trail
                            exit_reason = "Trail"
                    else:
                        new_trail = b.c + dist
                        trail = new_trail if math.isnan(trail) else min(trail, new_trail)
                        if b.h >= trail:
                            exit_now = True
                            exit_price = trail
                            exit_reason = "Trail"

            # Cloud-break exit (book's "5波中に雲を割ったら手仕舞い")
            if not exit_now:
                if t.direction > 0 and below and not prev_below:
                    exit_now = True
                    exit_price = b.c
                    exit_reason = "CloudFlip"
                elif t.direction < 0 and above and not prev_above:
                    exit_now = True
                    exit_price = b.c
                    exit_reason = "CloudFlip"

            # Max bars in trade
            if not exit_now and (i - t.entry_bar) > cfg.max_bars_in_trade:
                exit_now = True
                exit_price = b.c
                exit_reason = "MaxBars"

            if exit_now:
                # Apply slippage and commission
                slip = exit_price * cfg.slippage_pct * (-1 if t.direction > 0 else +1)
                exit_price_actual = exit_price + slip
                pnl_per_unit = (exit_price_actual - t.entry_price) * t.direction
                pnl = pnl_per_unit * t.qty
                pnl -= (abs(t.entry_price) + abs(exit_price_actual)) * cfg.commission_pct * t.qty
                cash += pnl
                t.exit_bar = i
                t.exit_time = b.t
                t.exit_price = exit_price_actual
                t.exit_reason = exit_reason
                t.pnl = pnl
                trades.append(t)
                open_trade = None
                trail = math.nan
                half_done = False

        # ---------- Wave state updates (only when no open trade or always?) ----------
        # We keep waves running always; only entry is blocked when in position.
        def update_long():
            nonlocal L
            if L.state == 0:
                if cross_up:
                    # Wave 1 start = lowest low of last `kijun` bars
                    start = max(0, i + 1 - cfg.kijun)
                    L.w0_price = min(bars[j].l for j in range(start, i + 1))
                    L.w0_bar = start
                    L.w1_price = b.h
                    L.w1_bar = i
                    L.state = 1
            elif L.state == 1:
                if b.h > L.w1_price:
                    L.w1_price = b.h
                    L.w1_bar = i
                if cross_down or inside:
                    L.w2_price = b.l
                    L.w2_bar = i
                    L.state = 2
            elif L.state == 2:
                if b.l < L.w2_price:
                    L.w2_price = b.l
                    L.w2_bar = i
                if cfg.rule_w2_no_break and L.w2_price <= L.w0_price:
                    L.state = 0
                elif cross_up:
                    L.w3_price = b.h
                    L.w3_bar = i
                    L.state = 3
            elif L.state == 3:
                if b.h > L.w3_price:
                    L.w3_price = b.h
                    L.w3_bar = i
                if cross_down or inside:
                    L.w4_price = b.l
                    L.w4_bar = i
                    L.state = 4
            elif L.state == 4:
                if b.l < L.w4_price:
                    L.w4_price = b.l
                    L.w4_bar = i
                if cfg.rule_w4_no_break and L.w4_price <= L.w1_price:
                    L.state = 0
                elif cross_up:
                    return True   # Wave-5 confirmed!
            return False

        def update_short():
            nonlocal S
            if S.state == 0:
                if cross_down:
                    start = max(0, i + 1 - cfg.kijun)
                    S.w0_price = max(bars[j].h for j in range(start, i + 1))
                    S.w0_bar = start
                    S.w1_price = b.l
                    S.w1_bar = i
                    S.state = 1
            elif S.state == 1:
                if b.l < S.w1_price:
                    S.w1_price = b.l
                    S.w1_bar = i
                if cross_up or inside:
                    S.w2_price = b.h
                    S.w2_bar = i
                    S.state = 2
            elif S.state == 2:
                if b.h > S.w2_price:
                    S.w2_price = b.h
                    S.w2_bar = i
                if cfg.rule_w2_no_break and S.w2_price >= S.w0_price:
                    S.state = 0
                elif cross_down:
                    S.w3_price = b.l
                    S.w3_bar = i
                    S.state = 3
            elif S.state == 3:
                if b.l < S.w3_price:
                    S.w3_price = b.l
                    S.w3_bar = i
                if cross_up or inside:
                    S.w4_price = b.h
                    S.w4_bar = i
                    S.state = 4
            elif S.state == 4:
                if b.h > S.w4_price:
                    S.w4_price = b.h
                    S.w4_bar = i
                if cfg.rule_w4_no_break and S.w4_price >= S.w1_price:
                    S.state = 0
                elif cross_down:
                    return True
            return False

        long_sig = update_long()
        short_sig = update_short()

        # Match Pine behavior: state ALWAYS resets after a wave-5 attempt
        # (regardless of whether an open trade prevents entry).
        if long_sig:
            L.state = 0
        if short_sig:
            S.state = 0

        # ---------- Entry decisions ----------
        if open_trade is None:
            # Window filter
            yr = extract_year(b.t)
            in_window = True
            if cfg.start_year is not None and yr is not None and yr < cfg.start_year:
                in_window = False
            if cfg.end_year is not None and yr is not None and yr > cfg.end_year:
                in_window = False

            if long_sig and allow_long and in_window:
                # Validate strict rules
                ok = True
                w1_len = L.w1_price - L.w0_price
                w3_len = L.w3_price - L.w2_price
                if cfg.rule_w3_not_shortest and w3_len < w1_len:
                    ok = False
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2_pct = 100.0 * (L.w1_price - L.w2_price) / w1_len
                    w4_pct = 100.0 * (L.w3_price - L.w4_price) / w3_len
                    if not (cfg.w2_min_pct <= w2_pct <= cfg.w2_max_pct):
                        ok = False
                    if not (cfg.w4_min_pct <= w4_pct <= cfg.w4_max_pct):
                        ok = False
                if cfg.require_swing_break:
                    # need close > highest high of last N bars (excluding current)
                    start = max(0, i - cfg.swing_lookback)
                    recent_hi = max(bars[j].h for j in range(start, i))
                    if b.c <= recent_hi:
                        ok = False
                if ok and htf_ok(i, +1):
                    a = atr[i] if not math.isnan(atr[i]) else 0.0
                    sl_base = L.w2_price if cfg.sl_mode == "Wave2" else L.w0_price
                    sl = sl_base - cfg.sl_buffer_atr * a
                    fib1 = L.w1_price - L.w0_price
                    if cfg.tp_mode == "Fib_61_8":
                        tp = L.w4_price + fib1 * 0.618
                    elif cfg.tp_mode == "Fib_161_8":
                        tp = L.w4_price + fib1 * 1.618
                    else:
                        tp = math.nan
                    entry = b.c + b.c * cfg.slippage_pct
                    risk_per_unit = entry - sl
                    if risk_per_unit > 0:
                        qty = (cash * cfg.risk_per_trade) / risk_per_unit
                        open_trade = Trade(direction=+1, entry_bar=i, entry_time=b.t,
                                           entry_price=entry, sl=sl, tp=tp, qty=qty)
                        trail = math.nan
                        half_done = False

            elif short_sig and allow_short and in_window:
                ok = True
                w1_len = S.w0_price - S.w1_price
                w3_len = S.w2_price - S.w3_price
                if cfg.rule_w3_not_shortest and w3_len < w1_len:
                    ok = False
                if cfg.use_fib_filter and w1_len > 0 and w3_len > 0:
                    w2_pct = 100.0 * (S.w2_price - S.w1_price) / w1_len
                    w4_pct = 100.0 * (S.w4_price - S.w3_price) / w3_len
                    if not (cfg.w2_min_pct <= w2_pct <= cfg.w2_max_pct):
                        ok = False
                    if not (cfg.w4_min_pct <= w4_pct <= cfg.w4_max_pct):
                        ok = False
                if cfg.require_swing_break:
                    start = max(0, i - cfg.swing_lookback)
                    recent_lo = min(bars[j].l for j in range(start, i))
                    if b.c >= recent_lo:
                        ok = False
                if ok and htf_ok(i, -1):
                    a = atr[i] if not math.isnan(atr[i]) else 0.0
                    sl_base = S.w2_price if cfg.sl_mode == "Wave2" else S.w0_price
                    sl = sl_base + cfg.sl_buffer_atr * a
                    fib1 = S.w0_price - S.w1_price
                    if cfg.tp_mode == "Fib_61_8":
                        tp = S.w4_price - fib1 * 0.618
                    elif cfg.tp_mode == "Fib_161_8":
                        tp = S.w4_price - fib1 * 1.618
                    else:
                        tp = math.nan
                    entry = b.c - b.c * cfg.slippage_pct
                    risk_per_unit = sl - entry
                    if risk_per_unit > 0:
                        qty = (cash * cfg.risk_per_trade) / risk_per_unit
                        open_trade = Trade(direction=-1, entry_bar=i, entry_time=b.t,
                                           entry_price=entry, sl=sl, tp=tp, qty=qty)
                        trail = math.nan
                        half_done = False

        prev_above = above
        prev_below = below
        equity_curve.append(cash + (
            (b.c - open_trade.entry_price) * open_trade.qty * open_trade.direction
            if open_trade else 0.0))

    # =============================================================================
    # Metrics
    # =============================================================================
    n_trades = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    win_rate = (len(wins) / n_trades) if n_trades else 0.0
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)
    pf = (gross_profit / gross_loss) if gross_loss > 0 else math.inf if gross_profit > 0 else 0.0
    total_pnl = cash - cfg.initial_capital
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (-gross_loss / len(losses)) if losses else 0.0
    expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    # Max drawdown
    peak = equity_curve[0] if equity_curve else cfg.initial_capital
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (v - peak) / peak if peak else 0.0
        if dd < max_dd:
            max_dd = dd

    return dict(
        n_bars=n,
        n_trades=n_trades,
        win_rate=win_rate,
        profit_factor=pf,
        total_pnl=total_pnl,
        total_return_pct=100.0 * total_pnl / cfg.initial_capital,
        max_drawdown_pct=100.0 * max_dd,
        avg_win=avg_win,
        avg_loss=avg_loss,
        expectancy=expectancy,
        final_equity=cash,
        trades=trades,
        equity_curve=equity_curve,
    )


# =============================================================================
# CLI
# =============================================================================
def fmt_pct(x: float) -> str:
    return f"{x:+.2f}%"


def summarize(result: dict, label: str = "") -> str:
    if "error" in result:
        return f"[{label}] ERROR: {result['error']} (n={result.get('n')})"
    return (f"[{label}] bars={result['n_bars']:>6} | trades={result['n_trades']:>4} | "
            f"win={result['win_rate']*100:5.1f}% | PF={result['profit_factor']:5.2f} | "
            f"ret={fmt_pct(result['total_return_pct']):>8} | "
            f"DD={fmt_pct(result['max_drawdown_pct']):>8} | "
            f"E[trade]={result['expectancy']:+.2f}")


def main(argv: List[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", nargs="?", help="CSV file to backtest")
    p.add_argument("--scan", help="Directory to glob CSVs from")
    p.add_argument("--pattern", default="*H1*.csv", help="Glob pattern when scanning")
    p.add_argument("--out", help="Output summary CSV file")
    p.add_argument("--tp", default="Hybrid",
                   choices=["Fib_61_8", "Fib_161_8", "Trail_ATR", "Hybrid"])
    p.add_argument("--no-htf",  action="store_true", help="Disable HTF filter")
    p.add_argument("--no-fib",  action="store_true", help="Disable Fib retrace filter")
    p.add_argument("--no-w3",   action="store_true", help="Disable w3-not-shortest rule")
    p.add_argument("--start",   type=int)
    p.add_argument("--end",     type=int)
    p.add_argument("--direction", default="Both", choices=["Long", "Short", "Both"])
    p.add_argument("--trades-out", help="Path to dump trades CSV")
    args = p.parse_args(argv)

    cfg = Config()
    cfg.tp_mode = args.tp
    cfg.use_htf_filter = not args.no_htf
    cfg.use_fib_filter = not args.no_fib
    cfg.rule_w3_not_shortest = not args.no_w3
    cfg.start_year = args.start
    cfg.end_year = args.end
    cfg.direction = args.direction

    rows = []
    paths = []
    if args.scan:
        paths = sorted(glob.glob(os.path.join(args.scan, "**", args.pattern), recursive=True))
    elif args.path:
        paths = [args.path]
    else:
        p.print_help()
        return 1

    if not paths:
        print("No CSV files matched.", file=sys.stderr)
        return 1

    all_trades = []
    for path in paths:
        bars = load_csv(path)
        if not bars:
            print(f"[{path}] no bars parsed", file=sys.stderr)
            continue
        r = backtest(bars, cfg)
        label = os.path.basename(path)
        print(summarize(r, label))
        rows.append([label, len(bars), r.get("n_trades", 0),
                     f"{r.get('win_rate', 0) * 100:.2f}",
                     f"{r.get('profit_factor', 0):.2f}",
                     f"{r.get('total_return_pct', 0):.2f}",
                     f"{r.get('max_drawdown_pct', 0):.2f}",
                     f"{r.get('expectancy', 0):.4f}"])
        if args.trades_out:
            for t in r.get("trades", []):
                all_trades.append([label, t.direction,
                                   t.entry_time, t.entry_price,
                                   t.exit_time, t.exit_price,
                                   t.sl, t.tp, t.exit_reason, t.pnl])

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True) if os.path.dirname(args.out) else None
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "bars", "trades", "win_pct", "pf",
                        "ret_pct", "max_dd_pct", "expectancy"])
            w.writerows(rows)
        print(f"\nWrote summary to {args.out}")

    if args.trades_out and all_trades:
        with open(args.trades_out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "dir", "entry_time", "entry_price",
                        "exit_time", "exit_price", "sl", "tp",
                        "reason", "pnl"])
            w.writerows(all_trades)
        print(f"Wrote trades to {args.trades_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
