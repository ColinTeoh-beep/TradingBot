"""Tests for the RiskManager."""

import pytest

from tradingbot.risk_manager import RiskManager, PositionSizeResult


class TestRiskManagerInit:
    def test_valid_defaults(self):
        rm = RiskManager()
        assert rm.max_position_pct == 0.10
        assert rm.stop_loss_pct == 0.05
        assert rm.take_profit_pct == 0.15
        assert rm.max_open_positions == 5

    def test_invalid_max_position_pct_zero(self):
        with pytest.raises(ValueError):
            RiskManager(max_position_pct=0.0)

    def test_invalid_max_position_pct_gt_one(self):
        with pytest.raises(ValueError):
            RiskManager(max_position_pct=1.5)

    def test_invalid_stop_loss_pct_zero(self):
        with pytest.raises(ValueError):
            RiskManager(stop_loss_pct=0.0)

    def test_invalid_stop_loss_pct_one(self):
        with pytest.raises(ValueError):
            RiskManager(stop_loss_pct=1.0)

    def test_invalid_take_profit_pct(self):
        with pytest.raises(ValueError):
            RiskManager(take_profit_pct=0.0)

    def test_invalid_max_open_positions(self):
        with pytest.raises(ValueError):
            RiskManager(max_open_positions=0)


class TestCalculatePositionSize:
    def setup_method(self):
        self.rm = RiskManager(
            max_position_pct=0.10,
            stop_loss_pct=0.05,
            take_profit_pct=0.15,
            max_open_positions=3,
        )

    def test_basic_position(self):
        result = self.rm.calculate_position_size(
            portfolio_value=100_000.0, entry_price=100.0, open_positions=0
        )
        assert result is not None
        assert isinstance(result, PositionSizeResult)
        assert result.shares == 100  # 10% of 100k / 100 = 100 shares
        assert result.position_value == pytest.approx(10_000.0)
        assert result.stop_loss_price == pytest.approx(95.0, rel=1e-4)
        assert result.take_profit_price == pytest.approx(115.0, rel=1e-4)

    def test_max_positions_reached(self):
        result = self.rm.calculate_position_size(
            portfolio_value=100_000.0, entry_price=100.0, open_positions=3
        )
        assert result is None

    def test_invalid_price(self):
        result = self.rm.calculate_position_size(
            portfolio_value=100_000.0, entry_price=0.0, open_positions=0
        )
        assert result is None

    def test_insufficient_capital(self):
        # 10% of 50 = 5, can't buy one share at 100
        result = self.rm.calculate_position_size(
            portfolio_value=50.0, entry_price=100.0, open_positions=0
        )
        assert result is None

    def test_stop_loss_below_entry(self):
        result = self.rm.calculate_position_size(
            portfolio_value=10_000.0, entry_price=200.0, open_positions=0
        )
        assert result is not None
        assert result.stop_loss_price < 200.0

    def test_take_profit_above_entry(self):
        result = self.rm.calculate_position_size(
            portfolio_value=10_000.0, entry_price=200.0, open_positions=0
        )
        assert result is not None
        assert result.take_profit_price > 200.0

    def test_shares_are_whole_numbers(self):
        result = self.rm.calculate_position_size(
            portfolio_value=10_000.0, entry_price=37.5, open_positions=0
        )
        assert result is not None
        assert isinstance(result.shares, int)


class TestStopLossAndTakeProfit:
    def setup_method(self):
        self.rm = RiskManager(stop_loss_pct=0.05, take_profit_pct=0.15)

    def test_stop_loss_triggered(self):
        assert self.rm.should_stop_loss(entry_price=100.0, current_price=94.0) is True

    def test_stop_loss_not_triggered(self):
        assert self.rm.should_stop_loss(entry_price=100.0, current_price=96.0) is False

    def test_stop_loss_at_exact_threshold(self):
        assert self.rm.should_stop_loss(entry_price=100.0, current_price=95.0) is True

    def test_take_profit_triggered(self):
        assert self.rm.should_take_profit(entry_price=100.0, current_price=116.0) is True

    def test_take_profit_not_triggered(self):
        assert self.rm.should_take_profit(entry_price=100.0, current_price=114.0) is False

    def test_take_profit_at_exact_threshold(self):
        assert self.rm.should_take_profit(entry_price=100.0, current_price=115.0) is True
