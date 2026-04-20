"""State management for the Watchlist page.

Manages watchlist tickers, alert evaluation, and conviction scoring.
Persists ticker list and alert configuration via SQLite (watchlist_db).
"""
import reflex as rx
import asyncio
import pandas as pd
from typing import Optional, Callable
from .base import BaseState
from ..utils import watchlist_db
from ..utils.technical import (
    calculate_ma, calculate_rsi, calculate_macd, calculate_ema,
    batch_fetch_history,
)
from ..utils.price_db import batch_get_history as db_batch_get_history

# ---------------------------------------------------------------------------
# Alert type registry
# ---------------------------------------------------------------------------

# Each alert: (type_key, display_name, direction, persistence)
ALERT_DEFINITIONS: list[tuple[str, str, str, str]] = [
    ("sma_50_above",    "Price > 50d SMA",       "bullish",  "state"),
    ("sma_50_below",    "Price < 50d SMA",        "bearish",  "state"),
    ("sma_200_above",   "Price > 200d SMA",       "bullish",  "state"),
    ("sma_200_below",   "Price < 200d SMA",        "bearish",  "state"),
    ("sma_50_above_200","50d SMA > 200d SMA",     "bullish",  "state"),
    ("sma_50_below_200","50d SMA < 200d SMA",     "bearish",  "state"),
    ("golden_cross",    "Golden Cross",            "bullish",  "point"),
    ("death_cross",     "Death Cross",             "bearish",  "point"),
    ("macd_positive",   "MACD Positive",           "bullish",  "state"),
    ("macd_negative",   "MACD Negative",           "bearish",  "state"),
    ("rsi_oversold",    "RSI Oversold (<30)",      "bullish",  "state"),
    ("rsi_overbought",  "RSI Overbought (>70)",    "bearish",  "state"),
    ("ema_ribbon_bull", "EMA Ribbon Bullish",      "bullish",  "state"),
    ("ema_ribbon_bear", "EMA Ribbon Bearish",      "bearish",  "state"),
    ("gap_up",          "Gap Up",                  "bullish",  "point"),
    ("gap_down",        "Gap Down",                "bearish",  "point"),
]

ALL_ALERT_TYPES = [a[0] for a in ALERT_DEFINITIONS]

ALERT_META: dict[str, dict] = {
    a[0]: {"name": a[1], "direction": a[2], "persistence": a[3]}
    for a in ALERT_DEFINITIONS
}


# ---------------------------------------------------------------------------
# Alert evaluators -- each takes a DataFrame (OHLCV) and returns (triggered, value_str)
# ---------------------------------------------------------------------------

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yf.download single-ticker results."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel("Ticker", axis=1) if "Ticker" in df.columns.names else df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    return df


def _eval_sma_cross(df: pd.DataFrame, window: int, above: bool) -> tuple[bool, str]:
    """Price vs SMA relationship."""
    prices = df["Close"]
    ma = calculate_ma(prices, window)
    if ma is None:
        return False, "N/A"
    current = float(prices.iloc[-1])
    triggered = current > ma if above else current < ma
    pct = ((current - ma) / ma) * 100
    return triggered, f"{pct:+.1f}% from {window}d"


def _eval_sma_50_vs_200(df: pd.DataFrame, above: bool) -> tuple[bool, str]:
    """50d SMA vs 200d SMA relationship."""
    prices = df["Close"]
    ma50 = calculate_ma(prices, 50)
    ma200 = calculate_ma(prices, 200)
    if ma50 is None or ma200 is None:
        return False, "N/A"
    triggered = ma50 > ma200 if above else ma50 < ma200
    spread = ((ma50 - ma200) / ma200) * 100
    return triggered, f"Spread: {spread:+.1f}%"


def _eval_golden_death_cross(df: pd.DataFrame, golden: bool) -> tuple[bool, str]:
    """Detect 50d/200d SMA crossover in the last 5 trading days."""
    prices = df["Close"]
    if len(prices) < 201:
        return False, "N/A"
    ma50_series = prices.rolling(50).mean()
    ma200_series = prices.rolling(200).mean()
    # Check last 5 days for a crossover
    for i in range(-5, 0):
        if i - 1 < -len(ma50_series):
            continue
        prev_50, curr_50 = float(ma50_series.iloc[i - 1]), float(ma50_series.iloc[i])
        prev_200, curr_200 = float(ma200_series.iloc[i - 1]), float(ma200_series.iloc[i])
        if pd.isna(prev_50) or pd.isna(curr_50) or pd.isna(prev_200) or pd.isna(curr_200):
            continue
        if golden and prev_50 <= prev_200 and curr_50 > curr_200:
            return True, f"Day {5 + i + 1} ago"
        if not golden and prev_50 >= prev_200 and curr_50 < curr_200:
            return True, f"Day {5 + i + 1} ago"
    return False, ""


def _eval_macd(df: pd.DataFrame, positive: bool) -> tuple[bool, str]:
    """MACD line vs signal line."""
    result = calculate_macd(df["Close"])
    if result is None:
        return False, "N/A"
    triggered = result["histogram"] > 0 if positive else result["histogram"] < 0
    return triggered, f"MACD: {result['macd']:.2f}"


def _eval_rsi(df: pd.DataFrame, overbought: bool) -> tuple[bool, str]:
    """RSI threshold check."""
    val = calculate_rsi(df["Close"], 14)
    if val is None:
        return False, "N/A"
    triggered = val > 70 if overbought else val < 30
    return triggered, f"RSI: {val:.1f}"


def _eval_ema_ribbon(df: pd.DataFrame, bullish: bool) -> tuple[bool, str]:
    """8, 13, 21 EMA all above (or below) 55 EMA."""
    prices = df["Close"]
    ema_55 = calculate_ema(prices, 55)
    if ema_55 is None:
        return False, "N/A"
    ema_55_val = float(ema_55.iloc[-1])
    short_spans = [8, 13, 21]
    vals = []
    for span in short_spans:
        e = calculate_ema(prices, span)
        if e is None:
            return False, "N/A"
        vals.append(float(e.iloc[-1]))
    if bullish:
        triggered = all(v > ema_55_val for v in vals)
    else:
        triggered = all(v < ema_55_val for v in vals)
    return triggered, f"EMA55: {ema_55_val:.2f}"


def _eval_gap(df: pd.DataFrame, up: bool) -> tuple[bool, str]:
    """Gap up/down detection on the most recent completed day."""
    if len(df) < 2 or not all(c in df.columns for c in ("Open", "High", "Low")):
        return False, "N/A"
    today_open = float(df["Open"].iloc[-1])
    prev_high = float(df["High"].iloc[-2])
    prev_low = float(df["Low"].iloc[-2])
    if up:
        gap_pct = ((today_open - prev_high) / prev_high) * 100 if prev_high > 0 else 0
        triggered = gap_pct > 1.0
    else:
        gap_pct = ((prev_low - today_open) / prev_low) * 100 if prev_low > 0 else 0
        triggered = gap_pct > 1.0
    return triggered, f"Gap: {abs(gap_pct):.1f}%" if triggered else ""


# Evaluator dispatch table
_EVALUATORS: dict[str, Callable] = {
    "sma_50_above":     lambda df: _eval_sma_cross(df, 50, above=True),
    "sma_50_below":     lambda df: _eval_sma_cross(df, 50, above=False),
    "sma_200_above":    lambda df: _eval_sma_cross(df, 200, above=True),
    "sma_200_below":    lambda df: _eval_sma_cross(df, 200, above=False),
    "sma_50_above_200": lambda df: _eval_sma_50_vs_200(df, above=True),
    "sma_50_below_200": lambda df: _eval_sma_50_vs_200(df, above=False),
    "golden_cross":     lambda df: _eval_golden_death_cross(df, golden=True),
    "death_cross":      lambda df: _eval_golden_death_cross(df, golden=False),
    "macd_positive":    lambda df: _eval_macd(df, positive=True),
    "macd_negative":    lambda df: _eval_macd(df, positive=False),
    "rsi_oversold":     lambda df: _eval_rsi(df, overbought=False),
    "rsi_overbought":   lambda df: _eval_rsi(df, overbought=True),
    "ema_ribbon_bull":  lambda df: _eval_ema_ribbon(df, bullish=True),
    "ema_ribbon_bear":  lambda df: _eval_ema_ribbon(df, bullish=False),
    "gap_up":           lambda df: _eval_gap(df, up=True),
    "gap_down":         lambda df: _eval_gap(df, up=False),
}


def evaluate_alerts(df: pd.DataFrame, enabled_alerts: list[str]) -> list[dict]:
    """Evaluate all enabled alerts for a single ticker's price data.

    Returns a list of dicts: {type, name, direction, triggered, value, enabled}.
    """
    results = []
    for alert_type in ALL_ALERT_TYPES:
        meta = ALERT_META[alert_type]
        enabled = alert_type in enabled_alerts
        if enabled and alert_type in _EVALUATORS:
            triggered, value = _EVALUATORS[alert_type](df)
        else:
            triggered, value = False, ""
        results.append({
            "type": alert_type,
            "name": meta["name"],
            "direction": meta["direction"],
            "triggered": triggered,
            "value": value,
            "enabled": enabled,
        })
    return results


# ---------------------------------------------------------------------------
# Reflex state
# ---------------------------------------------------------------------------

class WatchlistState(BaseState):
    """Manages watchlist tickers, alert evaluation, and conviction display."""

    # Ticker list (loaded from DB)
    watchlist_tickers: list[str] = []

    # Per-ticker evaluated data: {symbol: {price, change_pct, alerts, bullish_triggered,
    #   bullish_total, bearish_triggered, bearish_total, total_triggered, error}}
    ticker_data: dict[str, dict] = {}

    # UI state
    add_ticker_input: str = ""
    expanded_ticker: str = ""
    is_validating_ticker: bool = False

    # Two-phase loading
    phase1_complete: bool = False
    phase2_complete: bool = False

    # Last refresh timestamp
    last_refresh_at: str = ""

    def set_add_ticker_input(self, value: str):
        self.add_ticker_input = value.upper().strip()

    def toggle_expanded(self, symbol: str):
        """Expand/collapse a ticker's detail row."""
        self.expanded_ticker = "" if self.expanded_ticker == symbol else symbol

    async def load_watchlist(self):
        """on_load handler: Phase 1 loads tickers, Phase 2 evaluates alerts."""
        self.phase1_complete = False
        self.phase2_complete = False
        self.is_loading = True
        yield

        # Phase 1: load tickers from DB
        tickers = await asyncio.to_thread(watchlist_db.get_all_tickers)
        self.watchlist_tickers = tickers
        self.phase1_complete = True
        yield

        if not tickers:
            self.is_loading = False
            return

        # Phase 2: fetch prices and evaluate alerts
        await self._evaluate_all_alerts()
        self.phase2_complete = True
        self.is_loading = False

    async def add_ticker(self):
        """Validate a ticker via price fetch, add to DB with default alerts."""
        symbol = self.add_ticker_input.strip().upper()
        if not symbol:
            return

        if watchlist_db.ticker_exists(symbol):
            yield rx.toast.warning(f"{symbol} is already in your watchlist")
            return

        self.is_validating_ticker = True
        yield

        # Validate by attempting a price fetch
        try:
            history = await asyncio.to_thread(
                db_batch_get_history, [symbol], "6mo"
            )
            df = history.get(symbol)
            if df is None or df.empty or len(df) < 10:
                self.is_validating_ticker = False
                yield rx.toast.error(f"Invalid ticker: {symbol}")
                return
        except Exception:
            self.is_validating_ticker = False
            yield rx.toast.error(f"Could not validate ticker: {symbol}")
            return

        # Add to DB with all alerts enabled by default
        await asyncio.to_thread(watchlist_db.add_ticker, symbol)
        await asyncio.to_thread(watchlist_db.ensure_default_alerts, symbol, ALL_ALERT_TYPES)

        self.watchlist_tickers = [symbol] + self.watchlist_tickers
        self.add_ticker_input = ""
        self.is_validating_ticker = False
        yield rx.toast.success(f"Added {symbol} to watchlist")

        # Evaluate alerts for the new ticker
        await self._evaluate_single_ticker(symbol)

    async def remove_ticker(self, symbol: str):
        """Remove a ticker and its alerts."""
        await asyncio.to_thread(watchlist_db.remove_ticker, symbol)
        self.watchlist_tickers = [t for t in self.watchlist_tickers if t != symbol]
        self.ticker_data = {k: v for k, v in self.ticker_data.items() if k != symbol}
        if self.expanded_ticker == symbol:
            self.expanded_ticker = ""
        yield rx.toast.info(f"Removed {symbol}")

    async def toggle_alert(self, symbol: str, alert_type: str):
        """Toggle a single alert and re-evaluate."""
        await asyncio.to_thread(watchlist_db.toggle_alert, symbol, alert_type)
        await self._evaluate_single_ticker(symbol)

    async def toggle_all_alerts(self, symbol: str):
        """Bulk toggle: if any enabled, disable all; otherwise enable all."""
        data = self.ticker_data.get(symbol, {})
        alerts = data.get("alerts", [])
        any_enabled = any(a.get("enabled") for a in alerts)
        await asyncio.to_thread(watchlist_db.set_all_alerts_for_ticker, symbol, not any_enabled)
        await self._evaluate_single_ticker(symbol)

    async def refresh_alerts(self):
        """Manual refresh of all alerts."""
        self.phase2_complete = False
        self.is_loading = True
        yield
        await self._evaluate_all_alerts()
        self.phase2_complete = True
        self.is_loading = False

    async def _evaluate_all_alerts(self):
        """Fetch prices and evaluate alerts for all watchlist tickers."""
        if not self.watchlist_tickers:
            return

        from datetime import datetime
        self.last_refresh_at = datetime.now().strftime("%I:%M %p")

        # Batch fetch price data
        history = await asyncio.to_thread(
            db_batch_get_history, self.watchlist_tickers, "6mo"
        )

        # Load all alert configs from DB
        all_alerts = await asyncio.to_thread(watchlist_db.get_all_alerts)

        # Evaluate each ticker
        new_data = {}
        for symbol in self.watchlist_tickers:
            df = history.get(symbol)
            if df is None or df.empty:
                new_data[symbol] = {
                    "price": "N/A", "change_pct": "N/A", "change_positive": True,
                    "alerts": [], "bullish_triggered": 0, "bullish_total": 0,
                    "bearish_triggered": 0, "bearish_total": 0, "total_triggered": 0,
                    "error": "No data",
                }
                continue

            df = _flatten_columns(df)

            # Price and daily change
            current_price = float(df["Close"].iloc[-1])
            if len(df) >= 2:
                prev_close = float(df["Close"].iloc[-2])
                change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            else:
                change_pct = 0

            # Get enabled alert types for this ticker
            alert_configs = all_alerts.get(symbol, [])
            enabled_types = [a["alert_type"] for a in alert_configs if a["enabled"]]

            # Evaluate
            alerts = await asyncio.to_thread(evaluate_alerts, df, enabled_types)

            # Count triggered by direction
            bullish_alerts = [a for a in alerts if a["direction"] == "bullish" and a["enabled"]]
            bearish_alerts = [a for a in alerts if a["direction"] == "bearish" and a["enabled"]]

            new_data[symbol] = {
                "price": f"${current_price:.2f}",
                "change_pct": f"{change_pct:+.1f}%",
                "change_positive": change_pct >= 0,
                "alerts": alerts,
                "bullish_triggered": sum(1 for a in bullish_alerts if a["triggered"]),
                "bullish_total": len(bullish_alerts),
                "bearish_triggered": sum(1 for a in bearish_alerts if a["triggered"]),
                "bearish_total": len(bearish_alerts),
                "total_triggered": sum(1 for a in alerts if a["triggered"] and a["enabled"]),
                "error": None,
            }

        self.ticker_data = new_data

    async def _evaluate_single_ticker(self, symbol: str):
        """Evaluate alerts for a single ticker (after add or toggle)."""
        history = await asyncio.to_thread(db_batch_get_history, [symbol], "6mo")
        alert_configs = await asyncio.to_thread(watchlist_db.get_alerts, symbol)
        enabled_types = [a["alert_type"] for a in alert_configs if a["enabled"]]

        df = history.get(symbol)
        if df is None or df.empty:
            return

        df = _flatten_columns(df)

        current_price = float(df["Close"].iloc[-1])
        prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0

        alerts = await asyncio.to_thread(evaluate_alerts, df, enabled_types)
        bullish_alerts = [a for a in alerts if a["direction"] == "bullish" and a["enabled"]]
        bearish_alerts = [a for a in alerts if a["direction"] == "bearish" and a["enabled"]]

        updated = dict(self.ticker_data)
        updated[symbol] = {
            "price": f"${current_price:.2f}",
            "change_pct": f"{change_pct:+.1f}%",
            "change_positive": change_pct >= 0,
            "alerts": alerts,
            "bullish_triggered": sum(1 for a in bullish_alerts if a["triggered"]),
            "bullish_total": len(bullish_alerts),
            "bearish_triggered": sum(1 for a in bearish_alerts if a["triggered"]),
            "bearish_total": len(bearish_alerts),
            "total_triggered": sum(1 for a in alerts if a["triggered"] and a["enabled"]),
            "error": None,
        }
        self.ticker_data = updated

    # -- Computed vars for UI --

    @rx.var
    def sorted_tickers(self) -> list[dict]:
        """Tickers sorted by total triggered signals descending, then alphabetical."""
        items = []
        for symbol in self.watchlist_tickers:
            data = self.ticker_data.get(symbol, {})
            alerts = data.get("alerts", [])
            bullish_names = [a["name"] for a in alerts if a["triggered"] and a["enabled"] and a["direction"] == "bullish"]
            bearish_names = [a["name"] for a in alerts if a["triggered"] and a["enabled"] and a["direction"] == "bearish"]
            items.append({
                "symbol": symbol,
                "price": data.get("price", "--"),
                "change_pct": data.get("change_pct", "--"),
                "change_positive": data.get("change_positive", True),
                "bullish_triggered": data.get("bullish_triggered", 0),
                "bearish_triggered": data.get("bearish_triggered", 0),
                "total_triggered": data.get("total_triggered", 0),
                "bullish_signals": " · ".join(bullish_names) if bullish_names else "",
                "bearish_signals": " · ".join(bearish_names) if bearish_names else "",
                "has_error": bool(data.get("error")),
            })
        items.sort(key=lambda x: (-x["total_triggered"], x["symbol"]))
        return items

    @rx.var
    def expanded_alerts(self) -> list[dict]:
        """Alert details for the currently expanded ticker."""
        if not self.expanded_ticker:
            return []
        data = self.ticker_data.get(self.expanded_ticker, {})
        return data.get("alerts", [])

    @rx.var
    def has_tickers(self) -> bool:
        return len(self.watchlist_tickers) > 0

    @rx.var
    def summary_total(self) -> int:
        return len(self.watchlist_tickers)

    @rx.var
    def summary_alerts_firing(self) -> int:
        return sum(d.get("total_triggered", 0) for d in self.ticker_data.values())

    @rx.var
    def summary_strong_bullish(self) -> int:
        """Count of tickers with 4+ bullish signals triggered."""
        return sum(1 for d in self.ticker_data.values() if d.get("bullish_triggered", 0) >= 4)

    @rx.var
    def summary_strong_bearish(self) -> int:
        """Count of tickers with 4+ bearish signals triggered."""
        return sum(1 for d in self.ticker_data.values() if d.get("bearish_triggered", 0) >= 4)
