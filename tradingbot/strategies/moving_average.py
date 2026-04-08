"""Moving Average Crossover strategy.

Generates a BUY signal when the short-term MA crosses above the long-term MA
(golden cross) and a SELL signal when it crosses below (death cross).
"""

from __future__ import annotations

import pandas as pd

from tradingbot.strategies.base import BaseStrategy, Signal, StrategyResult


class MovingAverageCrossover(BaseStrategy):
    """Dual Moving Average Crossover strategy.

    Args:
        short_window: Period for the fast (short-term) moving average.
        long_window: Period for the slow (long-term) moving average.
    """

    def __init__(self, short_window: int = 20, long_window: int = 50) -> None:
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window.")
        if short_window < 2:
            raise ValueError("short_window must be at least 2.")
        self._short_window = short_window
        self._long_window = long_window

    @property
    def name(self) -> str:
        return f"MA_Crossover({self._short_window},{self._long_window})"

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        """Generate a signal based on moving average crossover.

        Args:
            data: OHLCV DataFrame with at least 'Close' column, sorted ascending.

        Returns:
            StrategyResult with BUY, SELL, or HOLD signal.

        Raises:
            ValueError: If there is insufficient data to compute indicators.
        """
        if len(data) < self._long_window:
            raise ValueError(
                f"Need at least {self._long_window} bars; got {len(data)}."
            )

        close = data["Close"]
        short_ma = close.rolling(self._short_window).mean()
        long_ma = close.rolling(self._long_window).mean()

        current_short = short_ma.iloc[-1]
        current_long = long_ma.iloc[-1]
        prev_short = short_ma.iloc[-2]
        prev_long = long_ma.iloc[-2]

        price = float(close.iloc[-1])

        if prev_short <= prev_long and current_short > current_long:
            signal = Signal.BUY
        elif prev_short >= prev_long and current_short < current_long:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        return StrategyResult(
            signal=signal,
            price=price,
            indicator_values={
                "short_ma": round(float(current_short), 4),
                "long_ma": round(float(current_long), 4),
            },
        )
