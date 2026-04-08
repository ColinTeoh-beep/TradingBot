"""Event-driven backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from tradingbot.logger import get_logger
from tradingbot.risk_manager import RiskManager, PositionSizeResult
from tradingbot.strategies.base import BaseStrategy, Signal

logger = get_logger(__name__)


@dataclass
class Trade:
    """Record of a completed round-trip trade."""

    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    exit_reason: str  # "signal", "stop_loss", "take_profit", "end_of_data"


@dataclass
class BacktestResult:
    """Summary of a backtest run."""

    initial_capital: float
    final_capital: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trades: List[Trade] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=== Backtest Results ===",
            f"  Initial capital  : ${self.initial_capital:>12,.2f}",
            f"  Final capital    : ${self.final_capital:>12,.2f}",
            f"  Total return     : {self.total_return_pct:>8.2f}%",
            f"  Total trades     : {self.total_trades}",
            f"  Win rate         : {self.win_rate * 100:.1f}%",
            f"  Max drawdown     : {self.max_drawdown_pct:.2f}%",
            f"  Sharpe ratio     : {self.sharpe_ratio:.3f}",
        ]
        return "\n".join(lines)


@dataclass
class _OpenPosition:
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    stop_loss_price: float
    take_profit_price: float


class Backtester:
    """Walk-forward backtesting engine.

    Iterates bar-by-bar over historical data, applies strategy signals,
    and tracks portfolio performance with risk management.

    Args:
        strategy: Strategy instance to evaluate.
        risk_manager: RiskManager controlling position sizing and exits.
        initial_capital: Starting portfolio value in USD.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        initial_capital: float = 100_000.0,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive.")
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.initial_capital = initial_capital

    def run(self, symbol: str, data: pd.DataFrame) -> BacktestResult:
        """Run the backtest on a single symbol.

        Args:
            symbol: Ticker symbol (used for labelling trades).
            data: OHLCV DataFrame sorted ascending by time.

        Returns:
            BacktestResult with full trade log and performance metrics.
        """
        capital = self.initial_capital
        open_position: Optional[_OpenPosition] = None
        completed_trades: List[Trade] = []
        portfolio_values: List[float] = [capital]

        min_bars = max(
            getattr(self.strategy, "_long_window", 0),
            getattr(self.strategy, "_period", 0),
        ) + 2

        for i in range(min_bars, len(data)):
            window = data.iloc[: i + 1]
            bar = data.iloc[i]
            current_price = float(bar["Close"])
            current_date = data.index[i]

            # ---- Check open position exits first ----
            if open_position is not None:
                exit_reason: Optional[str] = None

                if self.risk_manager.should_stop_loss(open_position.entry_price, current_price):
                    exit_reason = "stop_loss"
                elif self.risk_manager.should_take_profit(open_position.entry_price, current_price):
                    exit_reason = "take_profit"
                else:
                    try:
                        result = self.strategy.generate_signal(window)
                        if result.signal == Signal.SELL:
                            exit_reason = "signal"
                    except ValueError:
                        pass

                if exit_reason:
                    trade = self._close_position(
                        open_position, current_price, current_date, exit_reason
                    )
                    completed_trades.append(trade)
                    capital += trade.pnl + open_position.shares * open_position.entry_price
                    open_position = None
                    logger.debug(
                        "Closed %s @ %.4f (%s) | PnL=%.2f",
                        symbol, current_price, exit_reason, trade.pnl,
                    )

            # ---- Check for new entry ----
            if open_position is None:
                try:
                    result = self.strategy.generate_signal(window)
                except ValueError:
                    portfolio_values.append(capital)
                    continue

                if result.signal == Signal.BUY:
                    ps: Optional[PositionSizeResult] = self.risk_manager.calculate_position_size(
                        portfolio_value=capital,
                        entry_price=current_price,
                        open_positions=0,
                    )
                    if ps is not None:
                        capital -= ps.position_value
                        open_position = _OpenPosition(
                            symbol=symbol,
                            entry_date=current_date,
                            entry_price=current_price,
                            shares=ps.shares,
                            stop_loss_price=ps.stop_loss_price,
                            take_profit_price=ps.take_profit_price,
                        )
                        logger.debug(
                            "Opened %s @ %.4f x%d shares", symbol, current_price, ps.shares
                        )

            # Track portfolio value (capital + open position mark-to-market)
            mtm = (open_position.shares * current_price) if open_position else 0.0
            portfolio_values.append(capital + mtm)

        # Close any remaining open position at last price
        if open_position is not None:
            last_price = float(data["Close"].iloc[-1])
            last_date = data.index[-1]
            trade = self._close_position(open_position, last_price, last_date, "end_of_data")
            completed_trades.append(trade)
            capital += trade.pnl + open_position.shares * open_position.entry_price

        final_capital = capital
        return self._compute_results(
            completed_trades, portfolio_values, self.initial_capital, final_capital
        )

    @staticmethod
    def _close_position(
        pos: _OpenPosition,
        exit_price: float,
        exit_date: pd.Timestamp,
        exit_reason: str,
    ) -> Trade:
        pnl = (exit_price - pos.entry_price) * pos.shares
        pnl_pct = (exit_price / pos.entry_price - 1) * 100
        return Trade(
            symbol=pos.symbol,
            entry_date=pos.entry_date,
            exit_date=exit_date,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            shares=pos.shares,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            exit_reason=exit_reason,
        )

    @staticmethod
    def _compute_results(
        trades: List[Trade],
        portfolio_values: List[float],
        initial_capital: float,
        final_capital: float,
    ) -> BacktestResult:
        total_return_pct = (final_capital / initial_capital - 1) * 100

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        win_rate = len(winning) / len(trades) if trades else 0.0

        # Max drawdown
        pv_series = pd.Series(portfolio_values)
        rolling_max = pv_series.cummax()
        drawdowns = (pv_series - rolling_max) / rolling_max * 100
        max_drawdown_pct = float(drawdowns.min())

        # Sharpe ratio (annualised, assuming daily bars, risk-free = 0)
        daily_returns = pv_series.pct_change().dropna()
        if daily_returns.std() > 0:
            sharpe = float(daily_returns.mean() / daily_returns.std() * (252 ** 0.5))
        else:
            sharpe = 0.0

        return BacktestResult(
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            total_return_pct=round(total_return_pct, 4),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=round(win_rate, 4),
            max_drawdown_pct=round(max_drawdown_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            trades=trades,
        )
