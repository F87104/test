"""Parameter search (grid + random) with parallel execution.

The optimiser only varies *indicator* parameters by default — backtest
behaviour (SL/TP/sizing) is held fixed so we are tuning the *signal*, not
the exit logic.  Power users can also pass a ``backtest_grid`` to vary
strategy params.

Robustness measures:

* trades < ``min_trades`` → score = -inf
* default score is ``profit_factor + 0.5*win_rate − 0.5*|max_dd_pct|``
* result is ranked, top-K saved as CSV
"""
from __future__ import annotations

import itertools
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .config import BacktestConfig, IndicatorConfig
from .logger import get_logger
from .metrics import Metrics, compute_metrics

log = get_logger("trendbreak.optimizer")


# ---------------------------------------------------------------------------
@dataclass
class OptimisationResult:
    params: dict
    metrics: dict
    score: float


def _default_score(m: Metrics) -> float:
    if m.n_trades < 1:
        return -math.inf
    pf = m.profit_factor if math.isfinite(m.profit_factor) else 5.0
    return float(pf + 0.5 * m.win_rate - 0.5 * abs(m.max_drawdown_pct))


# Top-level worker so it can be pickled by ProcessPoolExecutor
def _evaluate(args) -> OptimisationResult:
    df_dict, params, bcfg_dict, symbol, pip_size, min_trades = args
    df = pd.DataFrame(df_dict["data"], index=pd.DatetimeIndex(df_dict["index"]))
    icfg = IndicatorConfig(**params)
    bcfg = BacktestConfig(**bcfg_dict)
    res = run_backtest(
        df,
        indicator_cfg=icfg,
        backtest_cfg=bcfg,
        symbol=symbol,
        pip_size=pip_size,
    )
    m = compute_metrics(
        res.trades_df, res.equity_curve, initial_equity=bcfg.initial_equity
    )
    score = _default_score(m) if m.n_trades >= min_trades else -math.inf
    return OptimisationResult(params=params, metrics=m.to_dict(), score=score)


# ---------------------------------------------------------------------------
def _df_to_dict(df: pd.DataFrame) -> dict:
    return {
        "data": {c: df[c].to_numpy() for c in df.columns},
        "index": df.index,
    }


# ---------------------------------------------------------------------------
def grid_search(
    df: pd.DataFrame,
    *,
    grid: Mapping[str, Iterable[int]],
    backtest_cfg: BacktestConfig,
    base_indicator_cfg: Optional[IndicatorConfig] = None,
    symbol: str = "UNKNOWN",
    pip_size: float = 0.0001,
    min_trades: int = 5,
    workers: Optional[int] = None,
    score_fn: Callable[[Metrics], float] = _default_score,  # noqa: ARG001
) -> pd.DataFrame:
    """Full Cartesian-product grid search.

    Returns a dataframe ranked by score (descending).  Combinations that
    violate ``exclude_recent < lookback`` are skipped automatically.
    """
    base = base_indicator_cfg or IndicatorConfig()
    base_dict = asdict(base)
    keys = list(grid.keys())
    values = [list(grid[k]) for k in keys]

    combos = []
    for combo in itertools.product(*values):
        params = dict(base_dict)
        params.update({k: v for k, v in zip(keys, combo)})
        try:
            IndicatorConfig(**params).validate()
        except Exception:
            continue
        combos.append(params)
    log.info("grid search: %d valid combos × workers=%s", len(combos), workers)

    if not combos:
        return pd.DataFrame()

    df_payload = _df_to_dict(df)
    bcfg_dict = asdict(backtest_cfg)
    work_items = [
        (df_payload, params, bcfg_dict, symbol, pip_size, min_trades)
        for params in combos
    ]

    results: list[OptimisationResult] = []
    if workers and workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_evaluate, w) for w in work_items]
            for fut in as_completed(futures):
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    log.warning("worker failed: %s", exc)
    else:
        for w in work_items:
            try:
                results.append(_evaluate(w))
            except Exception as exc:  # noqa: BLE001
                log.warning("eval failed: %s", exc)

    if not results:
        return pd.DataFrame()

    rows = []
    for r in results:
        row = dict(r.params)
        row.update({f"m_{k}": v for k, v in r.metrics.items()})
        row["score"] = r.score
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
def random_search(
    df: pd.DataFrame,
    *,
    space: Mapping[str, tuple[int, int]],
    n_iter: int,
    backtest_cfg: BacktestConfig,
    base_indicator_cfg: Optional[IndicatorConfig] = None,
    symbol: str = "UNKNOWN",
    pip_size: float = 0.0001,
    min_trades: int = 5,
    workers: Optional[int] = None,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    base = base_indicator_cfg or IndicatorConfig()
    base_dict = asdict(base)
    combos = []
    tries = 0
    while len(combos) < n_iter and tries < n_iter * 20:
        tries += 1
        params = dict(base_dict)
        for k, (lo, hi) in space.items():
            params[k] = int(rng.integers(lo, hi + 1))
        try:
            IndicatorConfig(**params).validate()
        except Exception:
            continue
        combos.append(params)

    log.info("random search: %d combos sampled", len(combos))
    if not combos:
        return pd.DataFrame()

    df_payload = _df_to_dict(df)
    bcfg_dict = asdict(backtest_cfg)
    work_items = [
        (df_payload, params, bcfg_dict, symbol, pip_size, min_trades) for params in combos
    ]

    results: list[OptimisationResult] = []
    if workers and workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(_evaluate, work_items):
                results.append(r)
    else:
        for w in work_items:
            try:
                results.append(_evaluate(w))
            except Exception as exc:  # noqa: BLE001
                log.warning("eval failed: %s", exc)

    rows = []
    for r in results:
        row = dict(r.params)
        row.update({f"m_{k}": v for k, v in r.metrics.items()})
        row["score"] = r.score
        rows.append(row)
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


__all__ = ["grid_search", "random_search", "OptimisationResult"]
