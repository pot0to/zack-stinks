"""Simple TTL cache for market data to avoid redundant API calls.

RATE LIMIT CONTEXT (see api_limits.py for full documentation):
The TTL values below are calibrated to stay well within API rate limits:
- MARKET_DATA_TTL (60s): Prevents excessive yfinance calls for real-time data
- PORTFOLIO_TTL (120s): Conservative refresh for Robinhood API
- DEFAULT_TTL (300s): General data that changes infrequently

These values assume a single user. If multiple users share a server instance,
consider increasing TTLs or implementing per-user rate limiting.
"""
import time
from typing import Any

# Global cache storage: key -> (value, expiry_time)
_cache: dict[str, tuple[Any, float]] = {}

# Default TTL values (in seconds)
DEFAULT_TTL = 300  # 5 minutes for most data
MARKET_DATA_TTL = 60  # 1 minute for real-time market data
PORTFOLIO_TTL = 120  # 2 minutes for portfolio data

# Tiered TTLs for data with different volatility characteristics
# These reduce yfinance API calls by caching slow-changing data longer
SECTOR_TTL = 604800  # 7 days - sectors rarely change unless major business pivot
RANGE_52W_TTL = 86400  # 24 hours - 52-week bounds shift daily but meaningful change is weekly
EARNINGS_TTL = 86400  # 24 hours - earnings dates announced weeks in advance


def get_cached(key: str) -> Any | None:
    """Get a value from cache if it exists and hasn't expired."""
    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            return value
        del _cache[key]
    return None


def set_cached(key: str, value: Any, ttl: float = DEFAULT_TTL) -> None:
    """Store a value in cache with TTL."""
    _cache[key] = (value, time.time() + ttl)


def clear_cache(prefix: str = None) -> None:
    """Clear cache entries. If prefix provided, only clear matching keys."""
    global _cache
    if prefix:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(prefix)}
    else:
        _cache = {}
