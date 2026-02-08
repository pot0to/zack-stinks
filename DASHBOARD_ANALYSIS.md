# Investment Dashboard Analysis

*Analysis Date: February 8, 2026*

## Overview

This is a Reflex-based portfolio dashboard that integrates with Robinhood for holdings data and Yahoo Finance for market data. It targets self-directed investors who want to monitor their brokerage accounts with technical analysis overlays.

---

## What Works Well

The **Portfolio Spotlight alerts** are the standout feature. Gap detection with volume confirmation (1.5x average threshold) is a legitimate technical signal that active traders actually use. The 200-day MA breach alerts are particularly valuable since institutional money often uses this level as a trend-following trigger. The 50-day and 200-day MA proximity detection (within 5% of key levels) provides actionable heads-up before positions hit critical support/resistance.

The **multi-account view** with unified treemap visualization is practical. The P/L-based color gradient gives immediate visual feedback on which positions are working and which aren't. Options holdings include the essential fields: DTE, delta, ITM status, and underlying price. Both stock and options tables support sortable columns for flexible analysis.

The **privacy mode** is thoughtful for screen sharing scenarios.

The **technical implementation** is solid: parallel async data fetching with asyncio.gather patterns, intelligent caching (1-5 minute TTLs depending on data volatility), clean state management, and session persistence via pickle for user convenience. The MFA-enabled login flow handles two-factor authentication gracefully.

---

## What Could Be Clearer

**UI/UX Issues:**

The **RSI and MACD displays** show isolated snapshots ("Positive"/"Negative" for MACD, single number for RSI) rather than time series. Professionals want to see these indicators on charts to identify divergences and trend strength, not just current readings.

The **cost basis "N/A" indicators** may confuse users who don't understand why some positions show P/L and others don't. A brief tooltip explaining cost basis reliability would help.

**Data Gaps:**

The **account-level P/L** shows a placeholder value. Daily and period returns are the first thing investors check, so this gap is noticeable.

---

## What's Missing

**Risk Management**: No portfolio-level beta, Sharpe ratio, max drawdown, or Value at Risk. No correlation analysis between positions. No sector/industry exposure breakdown. These are fundamental to understanding whether a portfolio is actually diversified or just holding correlated positions.

**Performance Attribution**: No benchmark comparison against S&P 500 or relevant sector ETFs. No time-weighted or money-weighted return calculations. No historical performance charts showing how the portfolio has performed over time.

**Options Analytics**: Individual delta is shown, but no portfolio-level Greeks aggregation (total delta, gamma, theta, vega exposure). No implied volatility display or IV rank. No breakdown of options P/L by theta decay versus delta movement.

**Fundamental Data**: No P/E ratios, earnings dates, revenue growth, or other fundamental metrics. The research page is purely technical.

**Watchlist**: Cannot track stocks you don't own. This limits the research page's utility for prospecting new positions.

**Dividend Tracking**: Important for income-focused investors, entirely absent.

**Tax Awareness**: No tax lot selection visibility or tax-loss harvesting identification.

**Data Timeliness**: The 15-30 minute delay (per the disclaimer) is inadequate for active trading decisions. This is a limitation of the free data sources rather than the implementation.

---

## Bottom Line

This dashboard serves a **self-directed investor** who wants to monitor their Robinhood portfolio with technical overlays. The alert system for gap events and MA proximity is genuinely useful for swing trading. However, it lacks the risk analytics, performance attribution, and benchmark comparison that professional portfolio management requires. The implementation quality is high, but the feature scope reflects a personal project rather than institutional-grade tooling.

---

## Prioritized Feature Roadmap

### P0 - Critical Gaps
*Blocks core use case; should be addressed first*

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| 1 | Account-level P/L | Calculate and display daily/period returns for each account | Medium |
| 2 | Benchmark Comparison | Compare portfolio performance against S&P 500 baseline | Medium |

### P1 - High Value Additions
*Significantly improves utility for serious investors*

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| 3 | Portfolio Greeks | Aggregate delta, gamma, theta, vega across all options positions | Medium |
| 4 | Sector Exposure | Breakdown of portfolio by GICS sector/industry | Medium |
| 5 | Historical Performance | Chart showing portfolio value over time with benchmark overlay | High |
| 6 | RSI/MACD on Charts | Add technical indicators as overlays on price charts | Low |

### P2 - Nice to Have
*Useful additions that round out the feature set*

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| 7 | Watchlist | Track stocks not currently held for research purposes | Medium |
| 8 | Dividend Tracking | Display dividend income, yield, and ex-dates | Medium |
| 9 | Tax Lot Visibility | Show individual tax lots with gain/loss for tax planning | High |
| 10 | Fundamental Data | Add P/E, earnings dates, revenue growth to research page | Low |
| 11 | Cost Basis Tooltips | Explain why some positions show "N/A" for P/L | Low |

### P3 - Future Considerations
*Advanced features requiring significant effort or external dependencies*

| # | Feature | Description | Complexity |
|---|---------|-------------|------------|
| 12 | Real-time Data | Integrate paid data source for live quotes | High |
| 13 | Value at Risk | Calculate portfolio VaR using historical simulation | High |
| 14 | Correlation Matrix | Show correlation between positions for diversification analysis | Medium |
| 15 | IV Rank/Percentile | Display implied volatility context for options | Medium |

---

## Implementation Notes

**Data Sources:**
- Robinhood API (via robin_stocks): Portfolio holdings, options data, account info
- Yahoo Finance (via yfinance): Market indices, historical prices, technical calculations

**Caching Strategy:**
- Market data: 1 minute TTL
- Portfolio data: 2 minute TTL
- Stock history: 5 minute TTL

**Key Files:**
- `zack_stinks/state/portfolio.py` - Portfolio state management
- `zack_stinks/state/market.py` - Market overview state
- `zack_stinks/state/research.py` - Stock research state
- `zack_stinks/analyzer.py` - Technical analysis calculations
- `zack_stinks/utils/technical.py` - MA and indicator utilities
