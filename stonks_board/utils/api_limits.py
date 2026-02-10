"""
Third-Party API Rate Limits and Best Practices
===============================================

This module documents the rate limits and throttling behavior for all external
APIs used by this dashboard. These limits are critical to understand when
considering changes to data granularity or refresh frequency.

IMPORTANT: Neither Yahoo Finance nor Robinhood publish official rate limits.
The values documented here are based on community observation and may change
without notice. Always implement defensive caching and exponential backoff.


YAHOO FINANCE (yfinance library)
--------------------------------
yfinance is an UNOFFICIAL wrapper around Yahoo Finance's web endpoints.
There is no official API or documented rate limits.

Observed Limits:
    - No official TPS limit published
    - Community consensus: 0.5 TPS (1 request every 2 seconds) is safe
    - Aggressive usage: 1 TPS may work but risks temporary IP blocks
    - Heavy usage can result in HTTP 429 errors or temporary IP bans

Endpoint Risk Levels:
    - yf.download() for price history: LOWER RISK
      * Supports batch requests (multiple tickers in one call)
      * Uses efficient JSON API endpoint
      * ALWAYS prefer batch downloads over individual ticker.history() calls
    
    - ticker.info: HIGHER RISK
      * Requires multiple internal requests (JSON + HTML scraping)
      * Add 2-3 second delays between individual .info calls
      * Cache aggressively (data changes infrequently)
    
    - ticker.financials, ticker.earnings: HIGHER RISK
      * HTML scraping endpoints
      * More prone to rate limiting
    
    - ticker.calendar, ticker.earnings_dates: MODERATE RISK
      * Used for earnings date detection
      * Cache for 24+ hours (EARNINGS_TTL)

Rate Limit Responses:
    - HTTP 429 "Too Many Requests"
    - HTTP 503 "Service Unavailable"
    - YFRateLimitError exception (yfinance 0.2.54+)
    - Temporary IP bans (minutes to hours)

Best Practices:
    1. BATCH PRICE FETCHES: Use yf.download(['AAPL', 'MSFT', ...], ...)
       instead of individual ticker.history() calls
    2. CACHE EVERYTHING: Historical data doesn't change; cache locally
    3. THROTTLE .info CALLS: Add 2-3 second delays between calls
    4. IMPLEMENT EXPONENTIAL BACKOFF: Handle 429 errors gracefully
    5. USE RANDOMIZED DELAYS: Avoid predictable request patterns

Current Implementation Compliance:
    - batch_fetch_history() uses yf.download() for efficient batch fetching ✓
    - batch_fetch_info() caches results per-symbol ✓
    - MARKET_DATA_TTL (60s) prevents excessive refreshes ✓
    - EARNINGS_TTL (24 hours) for infrequently-changing data ✓
    - batch_fetch_earnings_async() limits concurrency to 10 ✓


ROBINHOOD (robin_stocks library)
--------------------------------
robin_stocks uses Robinhood's private, undocumented API. Rate limits are
not published and are determined through community observation.

Observed Limits:
    - Order endpoints: ~8 requests before throttle, 14-second recovery
    - Quote/data endpoints: More permissive, supports batch requests
    - Authentication endpoints: VERY restrictive, can cause lockouts

Throttle Response Format:
    {'detail': 'Request was throttled. Expected available in X seconds.'}

Endpoint Categories:
    - Orders/Trading: MOST RESTRICTIVE
      * ~8 requests before throttle
      * 14-second recovery window
      * Add 2-3 second delays between order operations
    
    - Quotes/Market Data: PERMISSIVE
      * Supports batch requests (up to ~400 symbols)
      * Polling every few seconds is generally safe
      * ALWAYS use batch methods: rs.stocks.get_quotes([symbols])
    
    - Account/Profile: MODERATE
      * Less frequently called
      * 30-60 second refresh interval is safe
    
    - Authentication: VERY RESTRICTIVE
      * Excessive attempts cause extended lockouts
      * Use session persistence (pickle file)
      * Handle auth failures gracefully

Safe Refresh Intervals:
    - Portfolio/account data: 30-60 seconds (PORTFOLIO_TTL = 120s is safe)
    - Quote data: 5-10 seconds if using batch requests
    - Order operations: 2-3 seconds between operations

Session Management:
    - Use store_session=True to persist auth tokens
    - Session tokens may expire before configured time (server-side)
    - Device token changes may trigger security checks
    - Handle re-authentication gracefully, don't retry automatically

Best Practices:
    1. BATCH ALL QUOTE REQUESTS: Use rs.stocks.get_quotes([symbols])
    2. CACHE SESSION TOKENS: Use pickle file persistence
    3. ADD DELAYS FOR SEQUENTIAL CALLS: 2 seconds between operations
    4. IMPLEMENT EXPONENTIAL BACKOFF: Parse "Expected available in X seconds"
    5. REFRESH ACCOUNT DATA SPARINGLY: 30-60 second intervals

Current Implementation Compliance:
    - Session persistence via pickle file ✓
    - PORTFOLIO_TTL (120s) prevents excessive refreshes ✓
    - Async calls via asyncio.to_thread() prevent blocking ✓


RATE LIMIT CONSTANTS
--------------------
These constants are defined in cache.py and should be respected when
making any changes to data fetching logic.
"""

# Re-export cache TTL constants for convenience
from .cache import (
    DEFAULT_TTL,      # 300s (5 min) - general data
    MARKET_DATA_TTL,  # 60s (1 min) - real-time market data
    PORTFOLIO_TTL,    # 120s (2 min) - portfolio data from Robinhood
    EARNINGS_TTL,     # 86400s (24 hours) - earnings dates
    SECTOR_TTL,       # 604800s (7 days) - sector data
    RANGE_52W_TTL,    # 86400s (24 hours) - 52-week high/low bounds
)

# Recommended minimum delays between API calls (in seconds)
# These are conservative values to avoid rate limiting
YFINANCE_MIN_DELAY = 2.0      # Between individual ticker.info calls
ROBINHOOD_MIN_DELAY = 2.0     # Between sequential Robinhood API calls
ROBINHOOD_ORDER_DELAY = 3.0   # Between order operations (if implemented)

# Maximum concurrent API calls
# Used by batch_fetch_earnings_async() to prevent thread pool exhaustion
# and reduce rate limit risk
YFINANCE_MAX_CONCURRENT = 10  # Concurrent yfinance calls
ROBINHOOD_MAX_CONCURRENT = 5  # Concurrent Robinhood calls (more conservative)

# Batch size limits
# yfinance.download() handles batching internally, but these are useful
# for planning data fetches
YFINANCE_BATCH_SIZE = 100     # Symbols per yf.download() call (no hard limit)
ROBINHOOD_QUOTE_BATCH = 400   # Max symbols per rs.stocks.get_quotes() call


def get_rate_limit_summary() -> str:
    """Return a human-readable summary of rate limits for debugging."""
    return """
    API Rate Limit Summary
    ======================
    
    Yahoo Finance (yfinance):
    - Safe TPS: 0.5 (1 request every 2 seconds)
    - Batch downloads: Use yf.download() for multiple symbols
    - Cache TTL: 60s for market data, 6h for earnings
    - Risk: HTTP 429, temporary IP bans
    
    Robinhood (robin_stocks):
    - Quote batch limit: ~400 symbols
    - Order throttle: ~8 requests, 14s recovery
    - Cache TTL: 120s for portfolio data
    - Risk: Throttle response, auth lockouts
    
    Current TTL Settings:
    - MARKET_DATA_TTL: 60 seconds
    - PORTFOLIO_TTL: 120 seconds
    - DEFAULT_TTL: 300 seconds
    - EARNINGS_TTL: 86400 seconds (24 hours)
    - SECTOR_TTL: 604800 seconds (7 days)
    - RANGE_52W_TTL: 86400 seconds (24 hours)
    """
