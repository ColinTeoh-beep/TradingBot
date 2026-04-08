"""Risk management: position sizing, stop-loss, and take-profit logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tradingbot.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PositionSizeResult:
    """Output from position sizing calculation.

    Attributes:
        shares: Number of shares to trade.
        position_value: Total capital committed to the position.
        stop_loss_price: Price at which to cut the loss.
        take_profit_price: Price at which to lock in profit.
    """

    shares: int
    position_value: float
    stop_loss_price: float
    take_profit_price: float


class RiskManager:
    """Calculates position sizes and manages trade risk parameters.

    Args:
        max_position_pct: Maximum fraction of portfolio for a single position (0-1].
        stop_loss_pct: Fraction below entry price for the stop-loss order.
        take_profit_pct: Fraction above entry price for the take-profit order.
        max_open_positions: Hard limit on simultaneous open trades.
    """

    def __init__(
        self,
        max_position_pct: float = 0.10,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15,
        max_open_positions: int = 5,
    ) -> None:
        if not 0 < max_position_pct <= 1:
            raise ValueError("max_position_pct must be in (0, 1].")
        if stop_loss_pct <= 0 or stop_loss_pct >= 1:
            raise ValueError("stop_loss_pct must be in (0, 1).")
        if take_profit_pct <= 0:
            raise ValueError("take_profit_pct must be positive.")
        if max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")

        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_open_positions = max_open_positions

    def calculate_position_size(
        self,
        portfolio_value: float,
        entry_price: float,
        open_positions: int = 0,
    ) -> Optional[PositionSizeResult]:
        """Determine how many shares to buy given portfolio constraints.

        Args:
            portfolio_value: Current total portfolio value in USD.
            entry_price: Price at which the trade will be entered.
            open_positions: Number of currently open positions.

        Returns:
            PositionSizeResult if a trade is allowed, else None.
        """
        if open_positions >= self.max_open_positions:
            logger.info(
                "Max open positions (%d) reached; skipping.", self.max_open_positions
            )
            return None
        if entry_price <= 0:
            logger.warning("Invalid entry price %.4f; skipping.", entry_price)
            return None
        if portfolio_value <= 0:
            logger.warning("Portfolio value %.2f is not positive; skipping.", portfolio_value)
            return None

        max_dollars = portfolio_value * self.max_position_pct
        shares = int(max_dollars // entry_price)
        if shares < 1:
            logger.info(
                "Not enough capital (%.2f) to buy at least one share (%.4f).",
                portfolio_value,
                entry_price,
            )
            return None

        position_value = shares * entry_price
        stop_loss_price = round(entry_price * (1 - self.stop_loss_pct), 4)
        take_profit_price = round(entry_price * (1 + self.take_profit_pct), 4)

        return PositionSizeResult(
            shares=shares,
            position_value=position_value,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        )

    def should_stop_loss(self, entry_price: float, current_price: float) -> bool:
        """Return True if the current price triggers a stop-loss.

        Args:
            entry_price: Price at which the position was opened.
            current_price: Latest market price.
        """
        return current_price <= entry_price * (1 - self.stop_loss_pct)

    def should_take_profit(self, entry_price: float, current_price: float) -> bool:
        """Return True if the current price triggers a take-profit.

        Args:
            entry_price: Price at which the position was opened.
            current_price: Latest market price.
        """
        return current_price >= entry_price * (1 + self.take_profit_pct)
