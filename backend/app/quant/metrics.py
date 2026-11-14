"""Performance metrics on periodic simple-return series."""

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def _as_returns(returns: FloatArray) -> FloatArray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("returns must be one-dimensional")
    if not np.all(np.isfinite(arr)):
        raise ValueError("returns must be finite")
    return arr


def annualized_return(returns: FloatArray, periods_per_year: int = 252) -> float:
    """Geometric (CAGR-style) annualized return."""
    arr = _as_returns(returns)
    if arr.size == 0:
        return 0.0
    growth = float(np.prod(1.0 + arr))
    if growth <= 0.0:
        return -1.0
    return float(growth ** (periods_per_year / arr.size) - 1.0)


def annualized_volatility(returns: FloatArray, periods_per_year: int = 252) -> float:
    arr = _as_returns(returns)
    if arr.size < 2:
        return 0.0
    return float(np.std(arr, ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: FloatArray, risk_free_rate: float = 0.0, periods_per_year: int = 252
) -> float:
    """Annualized Sharpe ratio; ``risk_free_rate`` is an annual rate. Returns 0.0 if vol is zero."""
    arr = _as_returns(returns)
    if arr.size < 2:
        return 0.0
    excess = arr - risk_free_rate / periods_per_year
    std = float(np.std(excess, ddof=1))
    if std < 1e-12:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: FloatArray, risk_free_rate: float = 0.0, periods_per_year: int = 252
) -> float:
    """Annualized Sortino ratio using downside deviation below the per-period risk-free rate."""
    arr = _as_returns(returns)
    if arr.size < 2:
        return 0.0
    excess = arr - risk_free_rate / periods_per_year
    downside = np.minimum(excess, 0.0)
    downside_dev = float(np.sqrt(np.mean(downside**2)))
    if downside_dev < 1e-12:
        return 0.0
    return float(np.mean(excess) / downside_dev * np.sqrt(periods_per_year))


def max_drawdown(returns: FloatArray) -> float:
    """Maximum peak-to-trough decline of the equity curve, as a value in [-1, 0]."""
    arr = _as_returns(returns)
    if arr.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + arr)
    peak = np.maximum.accumulate(np.concatenate(([1.0], equity)))[1:]
    drawdown = equity / peak - 1.0
    return float(min(0.0, np.min(drawdown)))


def alpha_beta(
    returns: FloatArray, benchmark: FloatArray, periods_per_year: int = 252
) -> tuple[float, float]:
    """OLS alpha (annualized, arithmetic) and beta of ``returns`` against ``benchmark``."""
    arr = _as_returns(returns)
    bench = _as_returns(benchmark)
    if arr.shape != bench.shape:
        raise ValueError("returns and benchmark must have the same length")
    if arr.size < 2:
        return 0.0, 0.0
    var = float(np.var(bench, ddof=1))
    if var < 1e-18:
        return float(np.mean(arr)) * periods_per_year, 0.0
    beta = float(np.cov(arr, bench, ddof=1)[0, 1] / var)
    alpha = (float(np.mean(arr)) - beta * float(np.mean(bench))) * periods_per_year
    return alpha, beta
