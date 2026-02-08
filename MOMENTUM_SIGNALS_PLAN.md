# Momentum & Breakout Signal Detection Plan

This document captures the finalized plan for adding momentum detection and breakout signals to the trading dashboard.

## Current State

The Portfolio Spotlight section on the Market page shows signals for portfolio holdings, focused on notable movements for a particular trading day. Current tabs:

1. **Price Gaps** — Gap up/down detection with 1.5x volume confirmation
2. **Near Key Levels** — Positions within 5% of 50-day or 200-day MA
3. **Below 200d MA** — Positions trading below their 200-day MA
4. **Near 52-Week High** — Positions within 5% of their 52-week high

Technical indicators already implemented: RSI (14-day), MACD line (positive/negative), 50-day MA, 200-day MA, annualized volatility, volume analysis.

---

## Finalized Implementation Plan

### 1. Portfolio Spotlight: New "Breakouts" Tab

Add a fifth tab to Portfolio Spotlight that shows MA breakout events (both bullish and bearish) with volume confirmation. This captures discrete daily events where price crosses a key moving average on significant volume.

**Bullish Breakout (Buy Signal):**
- Price closes above 50-day or 200-day MA
- Previous day's close was at or below that MA
- Volume >= 1.5x average (50-day MA) or >= 2.0x average (200-day MA)

**Bearish Breakdown (Sell Signal):**
- Price closes below 50-day or 200-day MA
- Previous day's close was at or above that MA
- Volume >= 1.5x average (50-day MA) or >= 2.0x average (200-day MA)

**UI Design:**
- Single tab with both bullish and bearish signals
- Color-coded rows: green tint for bullish, red tint for bearish
- Direction badge column showing "Bullish" or "Bearish"
- Columns: Symbol, Direction, MA Type (50d/200d), Price, MA Value, Volume Ratio
- Sort bullish signals first by default

### 2. Research Page: Enhanced Momentum Metrics

Add new stat cards to the Research page for intrinsic momentum characteristics. These metrics describe what a stock "is" rather than what "happened today."

**New Stat Cards:**
- **52-Week Range Position** — Where price sits in 52-week range (0-100%), displayed with visual bar
- **RSI Zone** — Badge showing Oversold (<30), Weak (30-50), Bullish (50-70), or Overbought (>70)
- **Momentum Score** — Composite 0-100 score (future enhancement, lower priority)

### 3. Portfolio Page: Optional 52-Week Range Column

Add 52-week range position as an optional column on the holdings table. This is the most intuitive single metric to add without clutter.

**Implementation Options (choose one):**
- Option A: Add as a visible column by default (simple)
- Option B: Add column visibility toggle with 52-week range hidden by default (cleaner)

---

## Implementation Sequence

**Phase 1: Trend Signals Tab (Portfolio Spotlight)** ✅ COMPLETE
1. Added `_process_ma_breakout()` method to `StockAnalyzer` in `analyzer.py`
2. Extended `detect_all_signals()` to return `ma_breakout_events`
3. Added `ma_breakout_events` state variable to `MarketState`
4. Added "Trend Signals" tab UI to `market.py`
5. Includes Golden Cross and Death Cross detection

**Phase 2: Research Page Enhancements** ✅ COMPLETE
1. Added `range_52w` and `rsi_zone` state variables to `ResearchState`
2. Added 52-week range position calculation
3. Added RSI zone classification with color-coded badges
4. Updated Research page stats row with new metrics

**Phase 3: Portfolio Page Column (Optional)** — Not yet implemented
1. Add 52-week range calculation to portfolio data fetch
2. Add column to holdings table
3. (Optional) Implement column visibility toggle

---

## Key Thresholds

| Signal | Threshold |
|--------|-----------|
| Volume surge for 50d MA breakout | >= 1.5x 20-day average |
| Volume surge for 200d MA breakout | >= 2.0x 20-day average |
| RSI overbought | > 70 |
| RSI oversold | < 30 |
| Strong momentum (range position) | >= 70% of 52-week range |

---

## Technical Notes

- All new signals use existing `batch_fetch_history()` data (1-year history already fetched)
- Breakout detection requires comparing consecutive days, which the existing DataFrame provides
- Follow existing patterns in `analyzer.py` for signal processing methods
- Follow existing tab patterns in `market.py` for UI consistency
