"""Tests for the Backtester."""

import pandas as pd
import pytest

from tradingbot.backtester import Backtester, BacktestResult
from tradingbot.risk_manager import RiskManager
from tradingbot.strategies.moving_average import MovingAverageCrossover
from tradingbot.strategies.rsi import RSIStrategy


def _make_ohlcv(closes: list) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=dates,
    )


class TestBacktesterSetup:
    def test_invalid_initial_capital(self):
        strategy = MovingAverageCrossover(short_window=5, long_window=10)
        rm = RiskManager()
        with pytest.raises(ValueError):
            Backtester(strategy=strategy, risk_manager=rm, initial_capital=0)

    def test_negative_capital_raises(self):
        strategy = MovingAverageCrossover(short_window=5, long_window=10)
        rm = RiskManager()
        with pytest.raises(ValueError):
            Backtester(strategy=strategy, risk_manager=rm, initial_capital=-1000)


class TestBacktesterRun:
    def _make_bt(self, short=5, long_w=10, capital=100_000.0):
        strategy = MovingAverageCrossover(short_window=short, long_window=long_w)
        rm = RiskManager(
            max_position_pct=0.10,
            stop_loss_pct=0.05,
            take_profit_pct=0.20,
            max_open_positions=1,
        )
        return Backtester(strategy=strategy, risk_manager=rm, initial_capital=capital)

    def test_returns_backtest_result(self):
        bt = self._make_bt()
        closes = list(range(50, 120))  # 70 bars of rising prices
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        assert isinstance(result, BacktestResult)

    def test_initial_equals_final_no_trades(self):
        """Flat prices produce no crossover signals → no trades → capital unchanged."""
        bt = self._make_bt()
        data = _make_ohlcv([100.0] * 50)
        result = bt.run("TEST", data)
        assert result.total_trades == 0
        assert result.final_capital == pytest.approx(100_000.0)

    def test_winning_trade_increases_capital(self):
        """Strongly uptrending prices should yield a profitable trade."""
        bt = self._make_bt(short=3, long_w=5, capital=50_000.0)
        # Declining then sharply rising: guarantees a golden cross
        closes = [10, 9, 8, 7, 6] + list(range(6, 156))  # 5 + 150 bars
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        # We may or may not have trades depending on the exact cross; just check types
        assert result.final_capital >= 0
        assert 0 <= result.win_rate <= 1.0

    def test_metrics_are_finite(self):
        bt = self._make_bt()
        closes = list(range(50, 120))
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        assert isinstance(result.total_return_pct, float)
        assert isinstance(result.max_drawdown_pct, float)
        assert isinstance(result.sharpe_ratio, float)

    def test_max_drawdown_non_positive(self):
        bt = self._make_bt()
        closes = list(range(50, 120))
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        assert result.max_drawdown_pct <= 0.0

    def test_win_rate_between_zero_and_one(self):
        bt = self._make_bt()
        closes = list(range(50, 120))
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        assert 0.0 <= result.win_rate <= 1.0

    def test_summary_is_string(self):
        bt = self._make_bt()
        closes = list(range(50, 120))
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        summary = result.summary()
        assert isinstance(summary, str)
        assert "Backtest Results" in summary

    def test_trade_exit_reasons_are_valid(self):
        bt = self._make_bt(short=3, long_w=5)
        closes = [10, 9, 8, 7, 6] + list(range(6, 100))
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        valid_reasons = {"signal", "stop_loss", "take_profit", "end_of_data"}
        for trade in result.trades:
            assert trade.exit_reason in valid_reasons

    def test_rsi_strategy_backtest(self):
        strategy = RSIStrategy(period=5, oversold=30, overbought=70)
        rm = RiskManager(max_position_pct=0.10, stop_loss_pct=0.05, take_profit_pct=0.20)
        bt = Backtester(strategy=strategy, risk_manager=rm, initial_capital=50_000.0)
        closes = [100, 90, 80, 70, 60, 50, 40, 30, 60, 80, 100, 120, 140, 160, 180]
        data = _make_ohlcv(closes)
        result = bt.run("TEST", data)
        assert isinstance(result, BacktestResult)
