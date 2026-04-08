"""
Confluence – checks multiple lower-timeframe confluences before allowing
a trade entry.  At least ``config.MIN_CONFLUENCES`` must be met.
"""

import logging

import pandas as pd

import config
import market_analysis as ma

logger = logging.getLogger(__name__)


def check_confluences(
    ltf_df: pd.DataFrame, bias: str
) -> tuple[bool, list[str]]:
    """
    Evaluate lower-timeframe confluences for the given *bias*
    ('bullish' or 'bearish').

    Returns
    -------
    (signal, reasons)
        signal  – True if confluences >= MIN_CONFLUENCES
        reasons – list of human-readable confluence descriptions that matched
    """
    reasons: list[str] = []

    # 1. Market Structure (BOS / CHoCH on LTF aligns with bias)
    if config.USE_STRUCTURE_CONFLUENCE:
        bos = ma.detect_bos_choch(ltf_df)
        if bos["direction"] == bias and bos["type"] in ("BOS", "CHoCH"):
            reasons.append(f"LTF {bos['type']} {bos['direction']}")

    # 2. EMA alignment
    if config.USE_EMA_CONFLUENCE:
        df = ma.add_indicators(ltf_df)
        if len(df) > 0 and not df["ema_fast"].isna().iloc[-1]:
            ema_fast = df["ema_fast"].iloc[-1]
            ema_slow = df["ema_slow"].iloc[-1]
            close = df["close"].iloc[-1]
            if bias == "bullish" and ema_fast > ema_slow and close > ema_fast:
                reasons.append("EMA bullish alignment")
            elif bias == "bearish" and ema_fast < ema_slow and close < ema_fast:
                reasons.append("EMA bearish alignment")

    # 3. RSI
    if config.USE_RSI_CONFLUENCE:
        df = ma.add_indicators(ltf_df) if "rsi" not in ltf_df.columns else ltf_df
        if len(df) > 0 and not pd.isna(df["rsi"].iloc[-1]):
            rsi_val = df["rsi"].iloc[-1]
            if bias == "bullish" and rsi_val < config.RSI_OVERSOLD:
                reasons.append(f"RSI oversold ({rsi_val:.1f})")
            elif bias == "bearish" and rsi_val > config.RSI_OVERBOUGHT:
                reasons.append(f"RSI overbought ({rsi_val:.1f})")

    # 4. Engulfing pattern
    if config.USE_ENGULFING_CONFLUENCE:
        eng = ma.detect_engulfing(ltf_df)
        if eng == bias:
            reasons.append(f"{bias.title()} engulfing candle")

    # 5. Fair Value Gap
    if config.USE_FVG_CONFLUENCE:
        fvgs = ma.detect_fvg(ltf_df)
        # Check if there's a recent FVG aligned with bias (last 10 candles)
        recent_fvgs = [f for f in fvgs if f["index"] >= len(ltf_df) - 10]
        matching = [f for f in recent_fvgs if f["type"] == bias]
        if matching:
            reasons.append(f"{bias.title()} FVG detected")

    signal = len(reasons) >= config.MIN_CONFLUENCES
    logger.info(
        "Confluence check (%s): %d/%d met – %s → %s",
        bias,
        len(reasons),
        config.MIN_CONFLUENCES,
        reasons,
        "PASS" if signal else "FAIL",
    )
    return signal, reasons
