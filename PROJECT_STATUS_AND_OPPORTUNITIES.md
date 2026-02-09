# Portfolio Dashboard: Status & Improvement Opportunities

*Analysis Date: February 8, 2026*

This document consolidates findings from previous analyses and evaluates the current implementation against industry standards for retail investor dashboards.

---

## Executive Summary

The dashboard has evolved into a capable tool for self-directed investors monitoring Robinhood portfolios with technical analysis overlays. The Portfolio Spotlight alert system and Research page technical indicators are genuinely useful for swing trading. However, several gaps remain between the current implementation and what retail investors expect from platforms like Robinhood, Fidelity, and Schwab.

The most critical gaps are: missing watchlist functionality, no dividend tracking, and incomplete performance attribution. The good news is that the technical foundation is solid, with efficient batch data fetching, intelligent caching, and clean state management that will support future enhancements.

---

## Current Implementation Status

### Completed Features

**Market Page**
- Market indices header (S&P 500, Nasdaq, Dow Jones, VIX) with daily changes
- 30-day momentum trend chart comparing major indices
- Portfolio Spotlight with 5 signal tabs:
  - Price Gaps (gap up/down with 1.5x volume confirmation)
  - Near Key Levels (within 5% of 50d/200d MA)
  - Below 200d MA (downtrend detection)
  - Near 52-Week High (proximity to resistance)
  - Trend Signals (MA breakouts, Golden Cross, Death Cross)

**Portfolio Page**
- Multi-account support with tab switching
- Daily P/L with S&P 500 benchmark comparison
- Treemap visualization with P/L-based color gradients
- Stock holdings table (sortable by symbol, price, shares, value, P/L, allocation)
- Options holdings table (sortable by DTE, strike, delta, P/L)
- Separate views for index funds vs individual positions
- Privacy mode for screen sharing

**Research Page**
- Stock ticker search with period selector (1mo to 2y)
- Technical indicators: RSI (14-day with zone classification), MACD, 50/200-day MAs, volatility
- Fundamental indicators: P/E ratio, revenue growth, profit margin, ROE, debt-to-equity
- 52-week range position (0-100%)
- Interactive candlestick chart with volume and MA overlays

**Infrastructure**
- Parallel async data fetching with asyncio.gather
- Intelligent caching (1-5 minute TTLs)
- Session persistence via pickle
- MFA-enabled login flow

### Partially Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Benchmark comparison | Daily only | Missing historical comparison, TWR/MWR calculations |
| Options analytics | Per-ticker delta exposure | Portfolio-level Greeks aggregation available per ticker |

### Not Yet Implemented

| Feature | Priority | Rationale |
|---------|----------|-----------|
| Watchlist | High | Cannot track stocks not owned; limits research utility |
| Dividend tracking | High | Essential for income-focused investors |
| Historical performance charts | Medium | Users want to see how portfolio performed over time |
| Tax-loss harvesting identification | Low | Nice-to-have for tax-aware investors |
| Portfolio-level Greeks | Low | Advanced feature for options-heavy portfolios |

### Recently Completed (February 2026)

| Feature | Implementation Notes |
|---------|---------------------|
| Per-Ticker Delta Exposure | New tab in allocation card showing aggregate delta per symbol combining stocks (delta=1/share) and options; filtered to tickers with open options positions only; separated by index funds vs individual stocks; visual bar chart with bullish/bearish color coding |
| Sector Exposure Breakdown | Donut chart with Morningstar-inspired color scheme; shows top 6 sectors + "Other"; excludes index funds |
| Enhanced RSI/MACD Display | 4-row subplot chart (price 50%, volume 15%, RSI 17.5%, MACD 17.5%) with reference lines |
| Cost Basis Tooltips | Info icon with popover explaining why cost basis may be unavailable |
| 52-Week Range Column | Visual progress bar in holdings table with color coding (green >70%, blue 30-70%, red <30%) |

---

## Calculation Accuracy Review

### Verified Correct

**RSI (14-day)**: Implementation uses rolling average method for gain/loss calculations. Zone thresholds (30/50/70) align with industry conventions. Note: This is a simplified approach; true Wilder's smoothing uses exponential weighting, but the difference is minimal for most practical purposes.

**MACD**: Standard 12/26 EMA calculation. Displays positive/negative signal correctly.

**Moving Averages**: Simple moving average calculations are correct. The 50-day and 200-day periods are industry standard.

**Volume Confirmation Thresholds**: 1.5x for 50-day MA breakouts and 2.0x for 200-day MA breakouts align with IBD (Investor's Business Daily) methodology.

**P/L Calculations**: Cost basis tracking with reliability detection handles edge cases where Robinhood returns unreliable data.

**Daily P/L**: Uses Robinhood's `extended_hours_equity` and `adjusted_equity_previous_close` for accurate daily change calculation.

### Potential Issues

**Volatility Calculation**: The implementation calculates 30-day historical volatility (HV30) annualized, which is correct. However, the zone classification compares current volatility to the stock's own 52-week average. This is a reasonable approach but differs from some platforms that compare to absolute thresholds or sector averages. Consider adding a tooltip explaining the methodology.

**P/E Ratio Zones**: The thresholds (Value <15, Fair 15-25, Premium >25) are sector-agnostic. This works as a baseline but may mislead users analyzing high-growth tech stocks (where P/E >30 is common) or utilities (where P/E >20 is expensive). Consider adding sector context or a note that these are general guidelines.

**52-Week High Detection**: Uses `fiftyTwoWeekHigh` from yfinance info, which may not update intraday. For stocks making new 52-week highs during the trading day, the alert may not trigger until the next day. Note: This tracks 52-week highs, not all-time highs.

### Missing Calculations

**Time-Weighted Return (TWR)**: Industry standard for comparing investment strategy performance independent of cash flows. Formula: `[(1 + R1) × (1 + R2) × ... × (1 + Rn)] - 1`. Not currently implemented.

**Sharpe Ratio**: Measures risk-adjusted returns. Formula: `(Portfolio Return - Risk-Free Rate) / Standard Deviation`. Essential for understanding if returns justify the risk taken.

**Maximum Drawdown**: Worst peak-to-trough decline. Critical for understanding downside risk. A 50% drawdown requires a 100% gain to recover.

---

## UX Evaluation

### What Works Well

**Progressive Disclosure**: The tabbed interface in Portfolio Spotlight and Research page keeps the UI clean while providing depth on demand.

**Visual Hierarchy**: The treemap provides immediate visual feedback on position sizing and P/L status. Color gradients (green for gains, red for losses) follow universal conventions.

**Privacy Mode**: Thoughtful feature for screen sharing scenarios. Fixed-width mask strings prevent layout shift.

**Index Fund Separation**: The UI separates index funds and sector ETFs from individual stock positions throughout the portfolio and market pages. This helps users distinguish between diversified exposure and single-company bets.

**Responsive Design**: Sidebar collapse and grid breakpoints handle different screen sizes.

### Areas for Improvement

**No Watchlist**: Users cannot track stocks they don't own. This significantly limits the Research page's utility for prospecting new positions. A watchlist is considered a "must-have" feature in retail platforms.

**No Historical Performance View**: Users want to see how their portfolio performed over time, not just today's change. A simple line chart showing portfolio value over 1M/3M/6M/1Y would address this.

**Benchmark Comparison Limited to Daily**: The S&P 500 comparison only shows today's relative performance. Users want to know if they're beating the market over longer periods.

---

## Industry Standards Comparison

### Must-Have Features (Retail Platforms)

| Feature | Robinhood | Fidelity | Schwab | This Dashboard |
|---------|-----------|----------|--------|----------------|
| Portfolio value & daily change | ✅ | ✅ | ✅ | ✅ |
| Holdings list with P/L | ✅ | ✅ | ✅ | ✅ |
| Cost basis tracking | ✅ | ✅ | ✅ | ✅ |
| Watchlist | ✅ | ✅ | ✅ | ❌ |
| Price charts | ✅ | ✅ | ✅ | ✅ |
| Basic technical indicators | ✅ | ✅ | ✅ | ✅ |
| Dividend tracking | ✅ | ✅ | ✅ | ❌ |
| Sector allocation | ❌ | ✅ | ✅ | ✅ |
| Historical performance | ✅ | ✅ | ✅ | ❌ |

### Nice-to-Have Features

| Feature | Status | Notes |
|---------|--------|-------|
| Advanced technical indicators | ✅ | RSI, MACD, MAs implemented |
| Fundamental data | ✅ | P/E, revenue growth, margins, ROE, D/E |
| Options analytics | Partial | Individual delta shown, no portfolio Greeks |
| Risk metrics (Sharpe, drawdown) | ❌ | Would require historical data storage |
| Tax optimization | ❌ | Complex; requires tax lot tracking |
| News integration | ❌ | Would require additional API |

---

## Recommended Improvements

### High Priority

1. **Add Watchlist Functionality**
   - Allow users to add tickers to a watchlist
   - Show watchlist on Research page or as a new tab
   - Include basic price alerts (price crosses threshold)
   - Estimated effort: Medium

2. **Add Dividend Tracking**
   - Show dividend income received (from Robinhood API)
   - Display upcoming ex-dividend dates for holdings
   - Calculate yield on cost for each position
   - Estimated effort: Medium

3. **Add Historical Performance Chart**
   - Line chart showing portfolio value over time
   - Period selector (1M, 3M, 6M, YTD, 1Y)
   - Overlay S&P 500 for benchmark comparison
   - Note: Requires storing historical snapshots or using Robinhood's historical data
   - Estimated effort: High (data storage challenge)

### Medium Priority (Completed February 2026)

4. **Sector Exposure Breakdown** ✅
   - Donut chart with Morningstar-inspired color scheme (cyclical=orange, sensitive=blue, defensive=green)
   - Shows top 6 sectors plus "Other" grouping; excludes index funds for accurate single-stock exposure
   - Includes info popover explaining why index funds are excluded

5. **Enhanced RSI/MACD Display** ✅
   - 4-row subplot chart: price (50%), volume (15%), RSI (17.5%), MACD (17.5%)
   - RSI includes overbought (70), oversold (30), and centerline (50) reference lines
   - MACD shows line, signal, and color-coded histogram (green positive, red negative)

6. **Cost Basis Tooltips** ✅
   - Info icon with popover in P/L column when cost basis is unavailable
   - Explains common causes: transferred positions, corporate actions, pre-2011 shares

7. **52-Week Range Column** ✅
   - Visual progress bar in holdings table showing position within 52-week range
   - Color coding: green (>70% = strong momentum), blue (30-70% = neutral), red (<30% = weakness)

### Low Priority

8. **Add Risk Metrics**
   - Sharpe ratio (requires historical returns)
   - Maximum drawdown
   - Portfolio beta vs S&P 500
   - Estimated effort: High (requires historical data)

9. **Portfolio-Level Greeks**
   - ~~Aggregate delta, gamma, theta, vega across all options~~
   - Per-ticker delta exposure now implemented ✅
   - Gamma, theta, vega aggregation still available as enhancement
   - Estimated effort: Low (delta done, other Greeks similar pattern)

10. **Tax-Loss Harvesting Identification**
    - Flag positions with unrealized losses
    - Warn about wash sale rules
    - Estimated effort: Medium

---

## Technical Debt & Performance Notes

**Caching Strategy**: Current TTLs are appropriate (1-5 minutes for volatile data, 24 hours for static data). No changes needed.

**Batch Fetching**: The `batch_fetch_history()` and `detect_all_signals()` patterns are efficient. Single API call for multiple symbols.

**State Management**: Clean separation between BaseState, MarketState, PortfolioState, and ResearchState. No circular dependencies.

**Potential Performance Issue**: The Research page fetches 5 years of history for every ticker search to support MA calculations. This is cached, but initial loads for new tickers may feel slow. Consider showing a loading skeleton while data fetches.

---

## Conclusion

The dashboard is well-architected and provides genuine value for swing traders monitoring Robinhood portfolios. The Portfolio Spotlight alerts and technical analysis tools are the standout features. To reach parity with mainstream retail platforms, the highest-impact additions would be watchlist functionality, dividend tracking, and historical performance visualization. The existing codebase is well-structured to support these enhancements.
