"""Simple TTL cache for market data to avoid redundant API calls.

Supports Stale-While-Revalidate (SWR) pattern for improved perceived performance:
data is served immediately from cache (even if stale), while fresh data is fetched
in the background.

RATE LIMIT CONTEXT (see api_limits.py for full documentation):
The TTL values below are calibrated to stay well within API rate limits:
- MARKET_DATA_TTL (60s): Prevents excessive yfinance calls for real-time data
- PORTFOLIO_TTL (120s): Conservative refresh for Robinhood API
- DEFAULT_TTL (300s): General data that changes infrequently

These values assume a single user. If multiple users share a server instance,
consider increasing TTLs or implementing per-user rate limiting.
"""
import time
from typing import Any, Callable
from functools import wraps
import asyncio

# Global cache storage: key -> (value, expiry_time, stale_time)
# expiry_time: when data is considered stale
# stale_time: when stale data should no longer be served (hard expiry)
_cache: dict[str, tuple[Any, float, float]] = {}

# Track in-flight refresh operations to prevent duplicate fetches
_refresh_in_progress: set[str] = set()

# Default TTL values (in seconds)
DEFAULT_TTL = 300  # 5 minutes for most data
MARKET_DATA_TTL = 60  # 1 minute for real-time market data
PORTFOLIO_TTL = 120  # 2 minutes for portfolio data
STALE_GRACE_PERIOD = 60  # Serve stale data for up to 60s while refreshing

# Tiered TTLs for data with different volatility characteristics
# These reduce yfinance API calls by caching slow-changing data longer
SECTOR_TTL = 604800  # 7 days - sectors rarely change unless major business pivot
RANGE_52W_TTL = 86400  # 24 hours - 52-week bounds shift daily but meaningful change is weekly
EARNINGS_TTL = 86400  # 24 hours - earnings dates announced weeks in advance


def get_cached(key: str) -> Any | None:
    """Get a value from cache if it exists and hasn't expired.
    
    This is the strict version that only returns fresh data.
    For SWR behavior, use get_cached_with_stale() instead.
    """
    if key in _cache:
        value, expiry, stale_expiry = _cache[key]
        if time.time() < expiry:
            return value
        del _cache[key]
    return None


def get_cached_with_stale(key: str) -> tuple[Any | None, bool]:
    """Get cached value, returning stale data if within grace period.
    
    Returns:
        Tuple of (value, is_stale) where:
        - value: The cached data, or None if not found/expired
        - is_stale: True if data is past expiry but within grace period
    
    Use this for SWR pattern: if is_stale is True, trigger a background
    refresh while displaying the stale data to the user.
    """
    if key in _cache:
        value, expiry, stale_expiry = _cache[key]
        now = time.time()
        
        if now < expiry:
            # Fresh data
            return value, False
        elif now < stale_expiry:
            # Stale but still usable
            return value, True
        else:
            # Past stale window, remove from cache
            del _cache[key]
    
    return None, False


def set_cached(key: str, value: Any, ttl: float = DEFAULT_TTL, stale_ttl: float = None) -> None:
    """Store a value in cache with TTL and optional stale grace period.
    
    Args:
        key: Cache key
        value: Data to cache
        ttl: Time-to-live in seconds (data considered fresh)
        stale_ttl: Additional time to serve stale data (defaults to STALE_GRACE_PERIOD)
    """
    if stale_ttl is None:
        stale_ttl = STALE_GRACE_PERIOD
    
    now = time.time()
    _cache[key] = (value, now + ttl, now + ttl + stale_ttl)
    
    # Clear refresh flag if this was a background refresh
    _refresh_in_progress.discard(key)


def clear_cache(prefix: str = None) -> None:
    """Clear cache entries. If prefix provided, only clear matching keys."""
    global _cache, _refresh_in_progress
    if prefix:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(prefix)}
        _refresh_in_progress = {k for k in _refresh_in_progress if not k.startswith(prefix)}
    else:
        _cache = {}
        _refresh_in_progress = set()


def is_refresh_in_progress(key: str) -> bool:
    """Check if a background refresh is already running for this key."""
    return key in _refresh_in_progress


def mark_refresh_started(key: str) -> bool:
    """Mark that a refresh has started. Returns False if already in progress.
    
    Use this to prevent duplicate refresh operations:
        if mark_refresh_started(key):
            # Start refresh
        else:
            # Refresh already running, skip
    """
    if key in _refresh_in_progress:
        return False
    _refresh_in_progress.add(key)
    return True


def mark_refresh_complete(key: str) -> None:
    """Mark that a refresh has completed (success or failure)."""
    _refresh_in_progress.discard(key)


def cached(ttl: float = DEFAULT_TTL, key_prefix: str = ""):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{args}:{kwargs}"
            cached_value = get_cached(cache_key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            set_cached(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def async_cached(ttl: float = DEFAULT_TTL, key_prefix: str = ""):
    """Decorator for caching async function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{args}:{kwargs}"
            cached_value = get_cached(cache_key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            set_cached(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def async_cached_swr(ttl: float = DEFAULT_TTL, key_prefix: str = "", on_refresh: Callable = None):
    """Decorator for caching with Stale-While-Revalidate pattern.
    
    Returns cached data immediately (even if stale), while triggering a
    background refresh. This provides instant perceived performance while
    keeping data fresh.
    
    Args:
        ttl: Time-to-live for fresh data
        key_prefix: Prefix for cache keys
        on_refresh: Optional callback when fresh data arrives (for UI updates)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{key_prefix}{func.__name__}:{args}:{kwargs}"
            cached_value, is_stale = get_cached_with_stale(cache_key)
            
            if cached_value is not None:
                if is_stale and mark_refresh_started(cache_key):
                    # Spawn background refresh without blocking
                    async def background_refresh():
                        try:
                            result = await func(*args, **kwargs)
                            # set_cached clears the refresh flag on success
                            set_cached(cache_key, result, ttl)
                            if on_refresh:
                                on_refresh(result)
                        except Exception as e:
                            # Log but don't propagate -- stale data is still being served
                            import logging
                            logging.warning(f"SWR background refresh failed for {cache_key}: {e}")
                            mark_refresh_complete(cache_key)
                    
                    asyncio.create_task(background_refresh())
                
                return cached_value
            
            # No cached data, fetch synchronously
            result = await func(*args, **kwargs)
            set_cached(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
