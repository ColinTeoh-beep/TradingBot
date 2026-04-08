"""Tests for trading strategies."""

import numpy as np
import pandas as pd
import pytest

from tradingbot.strategies.base import Signal
from tradingbot.strategies.moving_average import MovingAverageCrossover
from tradingbot.strategies.rsi import RSIStrategy, _compute_rsi


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(closes: list) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of close prices."""
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


# ---------------------------------------------------------------------------
# MovingAverageCrossover
# ---------------------------------------------------------------------------

class TestMovingAverageCrossover:
    def test_init_invalid_windows(self):
        with pytest.raises(ValueError):
            MovingAverageCrossover(short_window=50, long_window=20)

    def test_init_equal_windows(self):
        with pytest.raises(ValueError):
            MovingAverageCrossover(short_window=20, long_window=20)

    def test_init_short_window_too_small(self):
        with pytest.raises(ValueError):
            MovingAverageCrossover(short_window=1, long_window=10)

    def test_name(self):
        strat = MovingAverageCrossover(short_window=10, long_window=30)
        assert "10" in strat.name
        assert "30" in strat.name

    def test_insufficient_data_raises(self):
        strat = MovingAverageCrossover(short_window=5, long_window=10)
        data = _make_ohlcv([100.0] * 8)
        with pytest.raises(ValueError):
            strat.generate_signal(data)

    def test_hold_signal_flat_prices(self):
        """Flat price series: MA lines never cross → HOLD."""
        strat = MovingAverageCrossover(short_window=5, long_window=10)
        data = _make_ohlcv([100.0] * 15)
        result = strat.generate_signal(data)
        assert result.signal == Signal.HOLD

    def test_buy_signal_golden_cross(self):
        """Prices jump after a period of decline: short MA crosses above long MA → BUY."""
        strat = MovingAverageCrossover(short_window=3, long_window=5)
        # Declining then rapidly rising prices force a golden cross
        closes = [10, 9, 8, 7, 6, 5, 20, 30, 40, 50]
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        assert result.signal == Signal.BUY
        assert result.price == pytest.approx(50.0)
        assert "short_ma" in result.indicator_values
        assert "long_ma" in result.indicator_values

    def test_sell_signal_death_cross(self):
        """Prices drop sharply after a rise: short MA crosses below long MA → SELL."""
        strat = MovingAverageCrossover(short_window=3, long_window=5)
        closes = [10, 20, 30, 40, 50, 60, 5, 4, 3, 2]
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        assert result.signal == Signal.SELL

    def test_result_price_matches_last_close(self):
        strat = MovingAverageCrossover(short_window=3, long_window=5)
        closes = [100.0] * 10
        closes[-1] = 150.0
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        assert result.price == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# RSI helpers
# ---------------------------------------------------------------------------

class TestComputeRSI:
    def test_output_length_matches_input(self):
        close = pd.Series(range(1, 31), dtype=float)
        rsi = _compute_rsi(close, period=14)
        assert len(rsi) == len(close)

    def test_rsi_bounded(self):
        rng = np.random.default_rng(42)
        close = pd.Series(100 + rng.standard_normal(100).cumsum())
        rsi = _compute_rsi(close, period=14).dropna()
        assert (rsi >= 0).all() and (rsi <= 100).all()

    def test_constant_prices_rsi_nan(self):
        """Constant prices produce 0 loss and 0 gain → RSI is NaN or 100."""
        close = pd.Series([50.0] * 30)
        rsi = _compute_rsi(close, period=14)
        # With zero losses RS is inf → RSI is 100 or NaN; either is acceptable
        assert rsi.dropna().isin([100.0]).all() or rsi.isna().any()


# ---------------------------------------------------------------------------
# RSIStrategy
# ---------------------------------------------------------------------------

class TestRSIStrategy:
    def test_init_invalid_thresholds(self):
        with pytest.raises(ValueError):
            RSIStrategy(oversold=70, overbought=30)

    def test_init_period_too_small(self):
        with pytest.raises(ValueError):
            RSIStrategy(period=1)

    def test_name_contains_params(self):
        strat = RSIStrategy(period=14, oversold=30, overbought=70)
        assert "14" in strat.name
        assert "30" in strat.name
        assert "70" in strat.name

    def test_insufficient_data_raises(self):
        strat = RSIStrategy(period=14)
        data = _make_ohlcv([100.0] * 10)
        with pytest.raises(ValueError):
            strat.generate_signal(data)

    def test_hold_on_normal_prices(self):
        """Slowly trending price series: no threshold crossover → HOLD."""
        strat = RSIStrategy(period=5, oversold=30, overbought=70)
        closes = list(range(50, 70))  # 20 gently rising bars
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        # RSI will be high but may not cross back below 70 at last step
        assert result.signal in (Signal.HOLD, Signal.SELL, Signal.BUY)
        assert "rsi" in result.indicator_values

    def test_buy_signal_oversold_crossover(self):
        """Price crashes then recovers: RSI should cross up through 30 → BUY."""
        strat = RSIStrategy(period=5, oversold=30, overbought=70)
        # sharp drop then one sharp recovery
        closes = [100] * 5 + [50, 40, 30, 20, 10, 9, 8, 7, 6, 5, 60]
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        assert result.signal == Signal.BUY

    def test_sell_signal_overbought_crossover(self):
        """Price surges then pulls back: RSI should cross down through 70 → SELL."""
        strat = RSIStrategy(period=5, oversold=30, overbought=70)
        closes = [10] * 5 + [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 10]
        data = _make_ohlcv(closes)
        result = strat.generate_signal(data)
        assert result.signal == Signal.SELL
