from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass(frozen=True)
class VixSnapshot:
    value: float | None
    interpretation: str


def get_vix_snapshot() -> VixSnapshot:
    try:
        history = yf.Ticker("^VIX").history(period="5d", interval="1d")
    except Exception:
        return VixSnapshot(value=None, interpretation="VIX could not be retrieved.")

    if history.empty:
        return VixSnapshot(value=None, interpretation="VIX data is unavailable.")

    closes = history["Close"].dropna()
    if closes.empty:
        return VixSnapshot(None, "VIX data is unavailable.")
    value = float(closes.iloc[-1])
    return VixSnapshot(value=value, interpretation=f"Latest available daily reading ({closes.index[-1].date()}): {_interpret_vix(value)}")


def _interpret_vix(value: float) -> str:
    if value < 15:
        return "Expected market volatility is relatively low."
    if value < 20:
        return "Expected market volatility is moderate."
    if value < 30:
        return "Expected market volatility is elevated."
    return "Expected market volatility is high."
