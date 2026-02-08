"""Simple TTL cache for market data to avoid redundant API calls."""
import time
from typing import Any
from functools import wraps
import asyncio

# Global cache storage
_cache: dict[str, tuple[Any, float]] = {}

# Default TTL values (in seconds)
DEFAULT_TTL = 300  # 5 minutes for most data
MARKET_DATA_TTL = 60  # 1 minute for real-time market data
PORTFOLIO_TTL = 120  # 2 minutes for portfolio data


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
