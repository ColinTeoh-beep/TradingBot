"""
Bot – main orchestrator that ties together analysis, confluence,
planning, risk management, and trade management in a continuous loop.
"""

import logging
import sys
import time

import config
import confluence
import market_analysis as ma
import mt5_connector as mt5c
import risk_management as rm
import trade_manager as tm
import trading_plan as tp

# ─── Logging setup ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading_bot.log"),
    ],
)
logger = logging.getLogger("bot")


def analyse_and_trade(symbol: str):
    """
    Single iteration:
    1. Fetch HTF data → determine structure & zones.
    2. Decide bias (buy zone or sell zone).
    3. Fetch LTF data → check confluences.
    4. If ≥ MIN_CONFLUENCES met → build plan → execute.
    5. Manage open positions (break-even / trailing stop).
    """

    # ── Step 1: Higher-timeframe analysis ──────────────────────────
    htf_df = mt5c.get_candles(symbol, config.HIGHER_TIMEFRAME, config.HTF_CANDLE_COUNT)
    if htf_df.empty:
        logger.warning("No HTF data – skipping iteration.")
        return

    structure = ma.determine_market_structure(htf_df)
    logger.info("HTF structure: %s", structure)

    demand_zones = ma.detect_demand_zones(htf_df)
    supply_zones = ma.detect_supply_zones(htf_df)
    logger.info("Demand zones: %d | Supply zones: %d", len(demand_zones), len(supply_zones))

    # ── Step 2: Determine bias from HTF ────────────────────────────
    tick = mt5c.get_tick(symbol)
    if tick is None:
        return

    current_price = (tick.ask + tick.bid) / 2
    bias = None
    chosen_zone = None

    if structure in ("bullish", "ranging"):
        # Look for price near a demand zone → buy bias
        for z in sorted(demand_zones, key=lambda z: z["high"], reverse=True):
            if z["low"] <= current_price <= z["high"] * config.ZONE_PROXIMITY_TOLERANCE:
                bias = "bullish"
                chosen_zone = z
                break

    if bias is None and structure in ("bearish", "ranging"):
        # Look for price near a supply zone → sell bias
        for z in sorted(supply_zones, key=lambda z: z["low"]):
            if z["low"] * (2 - config.ZONE_PROXIMITY_TOLERANCE) <= current_price <= z["high"]:
                bias = "bearish"
                chosen_zone = z
                break

    if bias is None:
        logger.info("No actionable zone near current price (%.5f). Waiting…", current_price)
        return

    logger.info(
        "Bias: %s | Zone: %.5f–%.5f | Price: %.5f",
        bias,
        chosen_zone["low"],
        chosen_zone["high"],
        current_price,
    )

    # ── Step 3: Lower-timeframe confluence check ───────────────────
    ltf_df = mt5c.get_candles(symbol, config.LOWER_TIMEFRAME, config.LTF_CANDLE_COUNT)
    if ltf_df.empty:
        logger.warning("No LTF data – skipping iteration.")
        return

    signal, reasons = confluence.check_confluences(ltf_df, bias)
    if not signal:
        logger.info("Insufficient confluences – no trade this iteration.")
        return

    # ── Step 4: Build plan & execute ───────────────────────────────
    if not rm.can_open_trade(symbol):
        return

    plan = tp.build_plan(symbol, bias, chosen_zone)
    if plan is None:
        return

    tickets = tm.execute_trade(symbol, plan)
    if tickets:
        logger.info("Trade(s) opened: %s", tickets)
    else:
        logger.info("No trades were opened this iteration.")


def manage_open_positions(symbol: str):
    """Run break-even and trailing-stop logic on existing positions."""
    tm.manage_breakeven(symbol)
    tm.manage_trailing_stop(symbol)


# ═══════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════
def main():
    logger.info("=" * 60)
    logger.info("MT5 Auto-Trading Bot starting…")
    logger.info("Symbol: %s | HTF: %s | LTF: %s", config.SYMBOL, config.HIGHER_TIMEFRAME, config.LOWER_TIMEFRAME)
    logger.info("Risk: %.1f%% | RR: 1:%.1f | Layers: %s", config.RISK_PERCENT, config.RR_RATIO, config.MAX_LAYERS if config.LAYERING_ENABLED else "off")
    logger.info("=" * 60)

    if not mt5c.connect():
        logger.critical("Cannot connect to MT5. Exiting.")
        sys.exit(1)

    try:
        while True:
            try:
                analyse_and_trade(config.SYMBOL)
                manage_open_positions(config.SYMBOL)
            except Exception:
                logger.exception("Error in main loop iteration")
            time.sleep(config.BOT_LOOP_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        mt5c.disconnect()


if __name__ == "__main__":
    main()
