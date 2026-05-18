"""Configuration dataclasses for the trend-break backtester.

All parameters mirror the Pine Script definition where applicable so that
results are bit-for-bit reproducible.  Anything that is *not* in Pine Script
(stop-loss style, take-profit, slippage…) is collected in
:class:`BacktestConfig` so the user can experiment freely without affecting
indicator semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional
import json


# ---------------------------------------------------------------------------
# Indicator parameters
# ---------------------------------------------------------------------------
@dataclass
class IndicatorConfig:
    """Pine Script equivalent inputs."""

    # 長期ライン
    lookback: int = 5000
    exclude_recent: int = 760
    # 中期ライン
    lookback_3m: int = 480
    exclude_recent_3m: int = 120
    # 完全等価モード: lookback 本に満たないバーではシグナルを出さない
    strict_warmup: bool = True
    # ----------------------------------------------------------------
    # Pine 互換モード:
    #   "literal"  → 原 Pine をそのまま再現。`for i = lookback-1 to 0` が
    #                i=0（現在バー）を含むため、highLevel は現在バー高値を
    #                含む。結果として close > highLevel は実務上ほぼ発火
    #                しない（参考: docs/design_document.md §1.2 注記）。
    #   "intended" → 「直近 N 本の旧高値を実体ブレイク」の意図に沿って
    #                level は **現在バーを除く過去 lookback 本** から計算。
    #                バックテストではこちらが既定。
    # ----------------------------------------------------------------
    pine_compat_mode: str = "intended"  # "literal" | "intended"

    def validate(self) -> None:
        for name in ("lookback", "exclude_recent", "lookback_3m", "exclude_recent_3m"):
            v = getattr(self, name)
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"[ERR-PARAM] '{name}' must be a positive int, got {v!r}")
        if self.exclude_recent >= self.lookback:
            raise ValueError(
                "[ERR-PARAM] exclude_recent must be < lookback "
                f"(got exclude_recent={self.exclude_recent}, lookback={self.lookback})"
            )
        if self.exclude_recent_3m >= self.lookback_3m:
            raise ValueError(
                "[ERR-PARAM] exclude_recent_3m must be < lookback_3m "
                f"(got exclude_recent_3m={self.exclude_recent_3m}, "
                f"lookback_3m={self.lookback_3m})"
            )
        if self.pine_compat_mode not in {"literal", "intended"}:
            raise ValueError(
                "[ERR-PARAM] pine_compat_mode must be 'literal' or 'intended', "
                f"got {self.pine_compat_mode!r}"
            )


# ---------------------------------------------------------------------------
# Backtest parameters
# ---------------------------------------------------------------------------
EntryFill = Literal["next_open", "signal_close"]
LevelKind = Literal["long", "mid", "confluence"]
SLMode = Literal["atr", "fixed_pct", "signal_bar"]
TPMode = Literal["rr", "atr", "none"]
Direction = Literal["long_only", "short_only", "both"]


@dataclass
class BacktestConfig:
    direction: Direction = "both"
    level_kind: LevelKind = "long"

    entry_fill: EntryFill = "next_open"
    one_position_only: bool = True

    sl_mode: SLMode = "atr"
    sl_atr_mult: float = 2.0
    sl_fixed_pct: float = 0.01  # 1 % of entry price
    tp_mode: TPMode = "rr"
    tp_rr: float = 2.0
    tp_atr_mult: float = 4.0

    atr_period: int = 14
    time_exit_bars: int = 0
    cost_pips: float = 0.0
    slippage_pips: float = 0.0
    pip_size: float = 0.0001  # auto-detected per symbol when None upstream

    initial_equity: float = 10_000.0
    risk_per_trade_pct: float = 1.0  # % of equity risked on each trade

    # ------------------------------------------------------------------
    # Optional strategy enhancements (disabled by default = "vanilla")
    # ------------------------------------------------------------------
    # Session filter: only trade when entry bar's UTC hour falls in one of
    # the listed sessions.  None / empty = no filter.
    session_filter: Optional[tuple[str, ...]] = None  # e.g. ("asia","ny")

    # Breakout-strength pre-filter: require the signal bar's close to clear
    # the broken level by at least this many ATRs.  0.0 disables.
    min_breakout_margin_atr: float = 0.0

    # Body-strength pre-filter: require |close-open| / (high-low) >= ratio.
    # 0.0 disables.
    min_body_strength: float = 0.0

    # Volatility regime filter: skip trades whose ATR percentile (across the
    # full series) is outside [low, high].  None = no filter.
    atr_pct_band: Optional[tuple[float, float]] = None  # e.g. (0.0, 0.66)

    # Move stop-loss to break-even when price has travelled this many R in
    # favour.  0.0 disables.
    breakeven_at_r: float = 0.0

    # ATR trailing stop: after entry, dynamically trail SL by N × ATR from
    # the most favourable price.  0.0 disables.  When trailing is active and
    # ``tp_mode == 'none'`` you'll let winners run until the trail is hit.
    trailing_atr_mult: float = 0.0

    def validate(self) -> None:
        if self.sl_atr_mult <= 0:
            raise ValueError("[ERR-PARAM] sl_atr_mult must be > 0")
        if self.atr_period < 2:
            raise ValueError("[ERR-PARAM] atr_period must be >= 2")
        if self.tp_mode == "rr" and self.tp_rr <= 0:
            raise ValueError("[ERR-PARAM] tp_rr must be > 0 when tp_mode='rr'")
        if self.initial_equity <= 0:
            raise ValueError("[ERR-PARAM] initial_equity must be > 0")
        if self.risk_per_trade_pct <= 0 or self.risk_per_trade_pct > 100:
            raise ValueError("[ERR-PARAM] risk_per_trade_pct must be in (0,100]")


# ---------------------------------------------------------------------------
# Run / IO parameters
# ---------------------------------------------------------------------------
@dataclass
class RunConfig:
    symbol: str = "UNKNOWN"
    timezone: Optional[str] = None  # e.g. "UTC", "Asia/Tokyo"
    save_chart: bool = True
    save_trades_csv: bool = True
    save_equity_csv: bool = True
    output_dir: str = "results"
    log_dir: str = "logs"
    chart_max_bars: int = 6000  # avoid huge images on long histories


# ---------------------------------------------------------------------------
@dataclass
class FullConfig:
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    run: RunConfig = field(default_factory=RunConfig)

    def validate(self) -> None:
        self.indicator.validate()
        self.backtest.validate()

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "FullConfig":
        return cls(
            indicator=IndicatorConfig(**data.get("indicator", {})),
            backtest=BacktestConfig(**data.get("backtest", {})),
            run=RunConfig(**data.get("run", {})),
        )


__all__ = [
    "IndicatorConfig",
    "BacktestConfig",
    "RunConfig",
    "FullConfig",
]
