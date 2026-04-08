"""RSI (Relative Strength Index) strategy.

Generates a BUY signal when RSI crosses up through the oversold threshold
and a SELL signal when it crosses down through the overbought threshold.
"""

from __future__ import annotations

import pandas as pd

from tradingbot.strategies.base import BaseStrategy, Signal, StrategyResult


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """Compute RSI using Wilder's smoothed moving average.

    Args:
        close: Series of closing prices.
        period: Look-back period.

    Returns:
        RSI series (0–100).
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    return rsi


class RSIStrategy(BaseStrategy):
    """Momentum strategy based on the Relative Strength Index.

    Args:
        period: RSI calculation period (default 14).
        oversold: RSI level below which the asset is considered oversold (default 30).
        overbought: RSI level above which the asset is considered overbought (default 70).
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        if oversold >= overbought:
            raise ValueError("oversold threshold must be less than overbought threshold.")
        if period < 2:
            raise ValueError("RSI period must be at least 2.")
        self._period = period
        self._oversold = oversold
        self._overbought = overbought

    @property
    def name(self) -> str:
        return f"RSI({self._period},{self._oversold},{self._overbought})"

    def generate_signal(self, data: pd.DataFrame) -> StrategyResult:
        """Generate a signal based on RSI crossover of thresholds.

        Args:
            data: OHLCV DataFrame with at least 'Close' column, sorted ascending.

        Returns:
            StrategyResult with BUY, SELL, or HOLD signal.

        Raises:
            ValueError: If there is insufficient data.
        """
        min_bars = self._period + 1
        if len(data) < min_bars:
            raise ValueError(f"Need at least {min_bars} bars; got {len(data)}.")

        rsi = _compute_rsi(data["Close"], self._period)

        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        price = float(data["Close"].iloc[-1])

        if prev_rsi <= self._oversold and current_rsi > self._oversold:
            signal = Signal.BUY
        elif prev_rsi >= self._overbought and current_rsi < self._overbought:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        return StrategyResult(
            signal=signal,
            price=price,
            indicator_values={"rsi": round(float(current_rsi), 4)},
        )
