"""Vectorized single-asset backtester that is free of look-ahead bias by construction.

Convention: ``signals[t]`` is the target position decided using information available at the
close of period ``t``. It is applied to the return of period ``t + lag`` (``lag >= 1``), so a
signal can never earn the return that was used to produce it.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from app.quant.metrics import (
    alpha_beta,
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    cost_bps: float = 1.0  # commission/fees per unit of turnover, in basis points
    slippage_bps: float = 2.0  # assumed adverse fill per unit of turnover, in basis points
    lag: int = 1  # periods between signal and execution; must be >= 1
    max_leverage: float = 1.0  # signals are clipped to [-max_leverage, max_leverage]
    periods_per_year: int = 252
    risk_free_rate: float = 0.0

    def __post_init__(self) -> None:
        if self.lag < 1:
            raise ValueError("lag must be >= 1 to avoid look-ahead bias")
        if self.cost_bps < 0 or self.slippage_bps < 0:
            raise ValueError("costs must be non-negative")
        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")
        if self.periods_per_year < 1:
            raise ValueError("periods_per_year must be >= 1")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    positions: FloatArray
    gross_returns: FloatArray
    costs: FloatArray
    net_returns: FloatArray
    turnover: float  # average absolute position change per period
    metrics: dict[str, float]


def run_backtest(
    asset_returns: FloatArray,
    signals: FloatArray,
    config: BacktestConfig | None = None,
    benchmark_returns: FloatArray | None = None,
) -> BacktestResult:
    cfg = config or BacktestConfig()
    returns = np.asarray(asset_returns, dtype=np.float64)
    raw = np.asarray(signals, dtype=np.float64)
    if returns.ndim != 1 or raw.ndim != 1:
        raise ValueError("asset_returns and signals must be one-dimensional")
    if returns.shape != raw.shape:
        raise ValueError("asset_returns and signals must have the same length")
    if not (np.all(np.isfinite(returns)) and np.all(np.isfinite(raw))):
        raise ValueError("inputs must be finite")
    if np.any(returns <= -1.0):
        raise ValueError("asset returns must be greater than -100%")

    target = np.clip(raw, -cfg.max_leverage, cfg.max_leverage)
    positions = np.zeros_like(target)
    positions[cfg.lag :] = target[: target.size - cfg.lag]

    previous = np.concatenate(([0.0], positions[:-1])) if positions.size else positions
    traded = np.abs(positions - previous)
    costs = traded * (cfg.cost_bps + cfg.slippage_bps) / 1e4
    gross = positions * returns
    net = gross - costs

    metrics = {
        "annualized_return": annualized_return(net, cfg.periods_per_year),
        "annualized_volatility": annualized_volatility(net, cfg.periods_per_year),
        "sharpe": sharpe_ratio(net, cfg.risk_free_rate, cfg.periods_per_year),
        "sortino": sortino_ratio(net, cfg.risk_free_rate, cfg.periods_per_year),
        "max_drawdown": max_drawdown(net),
        "total_cost": float(np.sum(costs)),
    }
    if benchmark_returns is not None:
        bench = np.asarray(benchmark_returns, dtype=np.float64)
        alpha, beta = alpha_beta(net, bench, cfg.periods_per_year)
        metrics.update(
            alpha=alpha,
            beta=beta,
            benchmark_sharpe=sharpe_ratio(bench, cfg.risk_free_rate, cfg.periods_per_year),
            benchmark_annualized_return=annualized_return(bench, cfg.periods_per_year),
        )
    return BacktestResult(
        positions=positions,
        gross_returns=gross,
        costs=costs,
        net_returns=net,
        turnover=float(np.mean(traded)) if traded.size else 0.0,
        metrics=metrics,
    )
