import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from app.quant import (
    BacktestConfig,
    alpha_beta,
    max_drawdown,
    run_backtest,
    sharpe_ratio,
    sortino_ratio,
    walk_forward_windows,
)

returns_strategy = arrays(
    np.float64, st.integers(3, 80), elements=st.floats(-0.2, 0.2, allow_nan=False)
)


def test_known_buy_and_hold_without_costs() -> None:
    r = np.array([0.01, 0.02, -0.01, 0.03])
    res = run_backtest(r, np.ones(4), BacktestConfig(cost_bps=0, slippage_bps=0))
    # lag=1: first period is flat, then fully invested
    assert res.net_returns.tolist() == pytest.approx([0.0, 0.02, -0.01, 0.03])


def test_costs_charged_on_turnover() -> None:
    cfg = BacktestConfig(cost_bps=10, slippage_bps=0)
    res = run_backtest(np.zeros(4), np.array([1.0, 1.0, -1.0, -1.0]), cfg)
    # positions: 0, 1, 1, -1 -> traded: 0, 1, 0, 2
    assert res.costs.tolist() == pytest.approx([0.0, 0.001, 0.0, 0.002])


def test_rejects_zero_lag_and_bad_input() -> None:
    with pytest.raises(ValueError):
        BacktestConfig(lag=0)
    with pytest.raises(ValueError):
        run_backtest(np.zeros(3), np.zeros(4))
    with pytest.raises(ValueError):
        run_backtest(np.array([0.0, np.nan]), np.zeros(2))


def test_max_drawdown_known_value() -> None:
    assert max_drawdown(np.array([0.1, -0.5, 0.2])) == pytest.approx(-0.5)


def test_alpha_beta_recovers_exact_relationship() -> None:
    rng = np.random.default_rng(0)
    bench = rng.normal(0, 0.01, 500)
    alpha, beta = alpha_beta(0.0002 + 1.5 * bench, bench)
    assert beta == pytest.approx(1.5)
    assert alpha == pytest.approx(0.0002 * 252)


def test_sortino_ignores_upside_volatility() -> None:
    assert sortino_ratio(np.array([0.01, 0.05, 0.02, 0.09])) == 0.0  # no downside at all
    assert sharpe_ratio(np.full(10, 0.01)) == 0.0  # zero vol handled


@settings(max_examples=100, deadline=None)
@given(returns_strategy, st.data())
def test_no_lookahead_future_returns_cannot_change_past_pnl(
    r: np.ndarray, data: st.DataObject
) -> None:
    n = r.size
    signals = data.draw(arrays(np.float64, n, elements=st.floats(-1, 1, allow_nan=False)))
    cut = data.draw(st.integers(1, n - 1))
    altered = r.copy()
    tail = arrays(np.float64, n - cut, elements=st.floats(-0.2, 0.2, allow_nan=False))
    altered[cut:] = data.draw(tail)
    a = run_backtest(r, signals).net_returns
    b = run_backtest(altered, signals).net_returns
    assert np.array_equal(a[:cut], b[:cut])


@settings(max_examples=100, deadline=None)
@given(returns_strategy, st.data())
def test_future_signals_cannot_change_past_positions(r: np.ndarray, data: st.DataObject) -> None:
    n = r.size
    signals = data.draw(arrays(np.float64, n, elements=st.floats(-1, 1, allow_nan=False)))
    cut = data.draw(st.integers(1, n - 1))
    altered = signals.copy()
    altered[cut:] = -signals[cut:]
    a = run_backtest(r, signals).positions
    b = run_backtest(r, altered).positions
    assert np.array_equal(a[: cut + 1], b[: cut + 1])


@settings(max_examples=100, deadline=None)
@given(returns_strategy, st.data())
def test_higher_costs_never_improve_results(r: np.ndarray, data: st.DataObject) -> None:
    signals = data.draw(arrays(np.float64, r.size, elements=st.floats(-1, 1, allow_nan=False)))
    cheap = run_backtest(r, signals, BacktestConfig(cost_bps=1, slippage_bps=1))
    pricey = run_backtest(r, signals, BacktestConfig(cost_bps=20, slippage_bps=20))
    assert pricey.net_returns.sum() <= cheap.net_returns.sum() + 1e-12


@settings(max_examples=100, deadline=None)
@given(returns_strategy)
def test_drawdown_bounds_and_flat_strategy(r: np.ndarray) -> None:
    assert -1.0 <= max_drawdown(r) <= 0.0
    flat = run_backtest(r, np.zeros(r.size))
    assert not flat.net_returns.any()
    assert flat.metrics["max_drawdown"] == 0.0


def test_walk_forward_windows_never_leak() -> None:
    windows = list(walk_forward_windows(100, train_size=40, test_size=10))
    assert len(windows) == 6
    for w in windows:
        assert w.train_end == w.test_start
        assert w.train_end - w.train_start == 40
    tests = [(w.test_start, w.test_end) for w in windows]
    assert all(a[1] <= b[0] for a, b in zip(tests, tests[1:], strict=False))
    expanding = list(walk_forward_windows(100, 40, 10, expanding=True))
    assert all(w.train_start == 0 for w in expanding)
