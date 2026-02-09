"""Shared technical analysis utilities.

RATE LIMIT CONSIDERATIONS (see api_limits.py for full documentation):
- yfinance has no official rate limits but community consensus is 0.5 TPS safe
- Always prefer batch_fetch_history() over individual ticker.history() calls
- ticker.info calls are higher risk; add 2-3s delays between sequential calls
- All results are cached to minimize API calls
- HTTP 429 errors indicate rate limiting; implement exponential backoff
"""
import asyncio
import pandas as pd
import yfinance as yf
from datetime import datetime, date
from typing import Optional
from .cache import get_cached, set_cached, MARKET_DATA_TTL, DEFAULT_TTL


def normalize_symbol_for_yfinance(symbol: str) -> str:
    """
    Convert broker symbol format to yfinance-compatible format.
    
    Robinhood uses formats like "$BRK.B" but yfinance expects "BRK-B".
    """
    # Remove leading $ if present
    s = symbol.lstrip("$")
    # Replace dots with hyphens for share class notation (BRK.B -> BRK-B)
    s = s.replace(".", "-")
    return s


def calculate_ma(prices: pd.Series, window: int) -> Optional[float]:
    """
    Calculate a simple moving average for the given window.
    Returns None if insufficient data or calculation produces NaN.
    """
    if len(prices) < window:
        return None
    ma_value = prices.rolling(window=window).mean().iloc[-1]
    if pd.notna(ma_value) and ma_value > 0:
        return float(ma_value)  # Convert numpy float to Python float
    return None


def calculate_ma_proximity(prices: pd.Series, window: int) -> tuple[Optional[float], Optional[float]]:
    """
    Calculate MA value and percentage offset from current price.
    
    Returns:
        (ma_value, pct_offset) or (None, None) if insufficient data.
    """
    ma_value = calculate_ma(prices, window)
    if ma_value is None:
        return None, None
    
    current_price = float(prices.iloc[-1])  # Convert numpy float to Python float
    pct_offset = ((current_price - ma_value) / ma_value) * 100
    return ma_value, pct_offset


def calculate_ma_series(prices: pd.Series, window: int) -> Optional[pd.Series]:
    """
    Calculate a full MA series for charting purposes.
    Returns None if insufficient data.
    """
    if len(prices) < window:
        return None
    return prices.rolling(window=window).mean()


def get_stock_ma_data(symbol: str, period: str = "1y") -> dict:
    """
    Fetch stock data and calculate MA values for a single symbol.
    Results are cached per-symbol to avoid redundant API calls.
    
    Returns dict with current_price, ma_50, ma_200, pct_from_50, pct_from_200.
    Values are None if unavailable. All numeric values are Python floats.
    """
    cache_key = f"ma_data:{symbol}:{period}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    result = {
        "current_price": None,
        "ma_50": None,
        "ma_200": None,
        "pct_from_50": None,
        "pct_from_200": None,
    }
    
    try:
        yf_symbol = normalize_symbol_for_yfinance(symbol)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period)
        
        if df.empty:
            set_cached(cache_key, result, MARKET_DATA_TTL)
            return result
        
        prices = df["Close"]
        result["current_price"] = float(prices.iloc[-1])
        
        ma_50, pct_50 = calculate_ma_proximity(prices, 50)
        result["ma_50"] = ma_50
        result["pct_from_50"] = pct_50
        
        ma_200, pct_200 = calculate_ma_proximity(prices, 200)
        result["ma_200"] = ma_200
        result["pct_from_200"] = pct_200
        
    except Exception as e:
        print(f"Error fetching MA data for {symbol}: {e}")
    
    set_cached(cache_key, result, MARKET_DATA_TTL)
    return result


def batch_fetch_history(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """
    Batch fetch historical data for multiple symbols using yfinance's download().
    Returns a dict mapping symbol -> DataFrame with OHLCV data.
    
    RATE LIMIT NOTE: This is the PREFERRED method for fetching price history.
    yf.download() fetches all symbols in a single API call, which is far more
    efficient than individual ticker.history() calls and reduces rate limit risk.
    
    For 50 symbols:
    - Individual calls: 50 API requests (high rate limit risk)
    - Batch download: 1 API request (minimal rate limit risk)
    
    Args:
        symbols: List of stock symbols to fetch
        period: History period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    
    Returns:
        Dict mapping original symbol -> DataFrame with OHLCV columns
    """
    if not symbols:
        return {}
    
    # Normalize symbols for yfinance
    yf_symbols = [normalize_symbol_for_yfinance(s) for s in symbols]
    symbol_map = dict(zip(yf_symbols, symbols))  # Map back to original symbols
    
    try:
        # yf.download with group_by="ticker" returns multi-level columns for multiple symbols
        data = yf.download(yf_symbols, period=period, group_by="ticker", threads=True, progress=False)
        
        if data.empty:
            return {}
        
        result = {}
        
        # Handle single vs multiple symbols (yfinance returns different structures)
        if len(yf_symbols) == 1:
            # Single symbol: columns are just OHLCV
            original_symbol = symbol_map[yf_symbols[0]]
            result[original_symbol] = data
        else:
            # Multiple symbols: columns are (symbol, OHLCV)
            for yf_sym in yf_symbols:
                if yf_sym in data.columns.get_level_values(0):
                    original_symbol = symbol_map[yf_sym]
                    symbol_df = data[yf_sym].dropna(how="all")
                    if not symbol_df.empty:
                        result[original_symbol] = symbol_df
        
        return result
        
    except Exception as e:
        print(f"Error in batch fetch: {e}")
        return {}


def batch_fetch_info(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch ticker.info for multiple symbols.
    Returns a dict mapping symbol -> info dict.
    
    RATE LIMIT WARNING: ticker.info is a HIGH-RISK endpoint that makes multiple
    internal requests (JSON + HTML scraping). Unlike batch_fetch_history(),
    there is no true batch API for .info data.
    
    Current implementation:
    - Fetches sequentially (no parallel calls to reduce rate limit risk)
    - Caches results per-symbol (MARKET_DATA_TTL = 60s)
    - No delay between calls (relies on caching to reduce total calls)
    
    If rate limiting becomes an issue, consider:
    - Adding time.sleep(2) between uncached fetches
    - Increasing MARKET_DATA_TTL for .info data specifically
    - Implementing exponential backoff on HTTP 429 errors
    
    Args:
        symbols: List of stock symbols to fetch info for
    
    Returns:
        Dict mapping symbol -> info dict (empty dict for failed fetches)
    """
    result = {}
    
    for symbol in symbols:
        cache_key = f"ticker_info:{symbol}"
        cached = get_cached(cache_key)
        if cached is not None:
            result[symbol] = cached
            continue
        
        try:
            yf_symbol = normalize_symbol_for_yfinance(symbol)
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            result[symbol] = info
            set_cached(cache_key, info, MARKET_DATA_TTL)
        except Exception as e:
            print(f"Error fetching info for {symbol}: {e}")
            result[symbol] = {}
    
    return result


def calculate_ma_data_from_df(df: pd.DataFrame) -> dict:
    """
    Calculate MA data from a pre-fetched DataFrame.
    Used with batch_fetch_history() to avoid redundant API calls.
    """
    result = {
        "current_price": None,
        "ma_50": None,
        "ma_200": None,
        "pct_from_50": None,
        "pct_from_200": None,
    }
    
    if df is None or df.empty:
        return result
    
    prices = df["Close"]
    if prices.empty:
        return result
    
    result["current_price"] = float(prices.iloc[-1])
    
    ma_50, pct_50 = calculate_ma_proximity(prices, 50)
    result["ma_50"] = ma_50
    result["pct_from_50"] = pct_50
    
    ma_200, pct_200 = calculate_ma_proximity(prices, 200)
    result["ma_200"] = ma_200
    result["pct_from_200"] = pct_200
    
    return result


# Earnings date TTL: 6 hours since earnings dates don't change frequently
EARNINGS_TTL = 21600


def _is_warrant_or_unit(symbol: str) -> bool:
    """Check if symbol appears to be a warrant, unit, or rights offering.
    
    These securities don't have earnings dates. We detect them by:
    - Explicit warrant suffixes: .WS, -WS, /WS
    - Known warrant patterns from user's portfolio (OPENW, OPENZ, OPENL)
    
    We intentionally avoid single-letter suffix heuristics as they cause
    false positives on normal tickers (AAPL, GOOGL, UBER, etc.).
    """
    upper = symbol.upper()
    
    # Check for explicit warrant suffixes
    if upper.endswith('.WS') or upper.endswith('-WS') or upper.endswith('/WS'):
        return True
    
    # Known warrant patterns from user's portfolio
    # These are SPAC-related warrants where base ticker + suffix
    known_warrant_bases = {'OPEN'}  # Opendoor warrants: OPENW, OPENZ, OPENL
    
    if len(symbol) >= 5:
        base = symbol[:-1].upper()
        suffix = symbol[-1].upper()
        if base in known_warrant_bases and suffix in ('W', 'Z', 'L', 'U', 'R'):
            return True
    
    return False


def get_earnings_date(symbol: str) -> dict:
    """
    Fetch next earnings date for a symbol from yfinance.
    
    Returns dict with:
        - earnings_date: datetime or None
        - earnings_date_str: formatted string (e.g., "Feb 15, 2026") or None
        - days_until: int or None (negative if earnings already passed)
        - timing: "BMO", "AMC", or None (before market open / after market close)
    
    Results are cached for 6 hours since earnings dates rarely change.
    ETFs, index funds, warrants, and units are skipped since they don't have earnings.
    """
    cache_key = f"earnings:{symbol}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    
    result = {
        "earnings_date": None,
        "earnings_date_str": None,
        "days_until": None,
        "timing": None,
    }
    
    # Skip known ETFs/index funds - they don't have earnings dates
    from .symbols import is_index_fund
    if is_index_fund(symbol):
        set_cached(cache_key, result, EARNINGS_TTL)
        return result
    
    # Skip warrants, units, and rights - they don't have earnings dates
    if _is_warrant_or_unit(symbol):
        set_cached(cache_key, result, EARNINGS_TTL)
        return result
    
    try:
        yf_symbol = normalize_symbol_for_yfinance(symbol)
        ticker = yf.Ticker(yf_symbol)
        
        # yfinance provides earnings dates via the calendar property
        # Note: yfinance 0.2.x+ returns a dict, older versions return DataFrame
        calendar = ticker.calendar
        earnings_date = None
        
        if calendar is not None:
            if isinstance(calendar, dict):
                # New yfinance format: calendar is a dict with 'Earnings Date' as a list
                earnings_list = calendar.get('Earnings Date')
                if earnings_list and len(earnings_list) > 0:
                    # Take the first date from the list
                    earnings_date = pd.to_datetime(earnings_list[0])
            elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
                # Legacy DataFrame format (for backwards compatibility)
                if 'Earnings Date' in calendar.index:
                    val = calendar.loc['Earnings Date'].iloc[0]
                    if pd.notna(val):
                        earnings_date = pd.to_datetime(val)
                elif len(calendar.columns) > 0:
                    first_col = calendar.iloc[:, 0]
                    if len(first_col) > 0 and pd.notna(first_col.iloc[0]):
                        try:
                            earnings_date = pd.to_datetime(first_col.iloc[0])
                        except Exception:
                            pass
        
        if earnings_date is not None:
            result["earnings_date"] = earnings_date.to_pydatetime()
            result["earnings_date_str"] = earnings_date.strftime("%b %d, %Y")
            
            # Calculate days until earnings
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            earnings_dt = earnings_date.replace(hour=0, minute=0, second=0, microsecond=0)
            delta = (earnings_dt - today).days
            result["days_until"] = delta
        
        # Try to get timing (BMO/AMC) from earnings_dates if available
        # Note: This requires lxml to be installed
        try:
            earnings_dates = ticker.earnings_dates
            if earnings_dates is not None and not earnings_dates.empty:
                # Find the next upcoming earnings date
                # Use timezone-aware timestamp to match earnings_dates index
                now = pd.Timestamp.now(tz='America/New_York')
                future_dates = earnings_dates[earnings_dates.index >= now]
                if not future_dates.empty:
                    next_earnings = future_dates.index[0]
                    # Update with more accurate date if available
                    result["earnings_date"] = next_earnings.to_pydatetime()
                    result["earnings_date_str"] = next_earnings.strftime("%b %d, %Y")
                    
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    earnings_dt = next_earnings.replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
                    result["days_until"] = (earnings_dt - today).days
                    
                    # Check time of day for BMO/AMC
                    hour = next_earnings.hour
                    if hour < 12:
                        result["timing"] = "BMO"
                    elif hour >= 16:
                        result["timing"] = "AMC"
        except ImportError:
            pass  # lxml not installed, skip BMO/AMC detection
        except Exception:
            pass  # earnings_dates not available for all tickers
                
    except Exception:
        pass  # Silently handle errors - ETFs and some tickers don't have earnings
    
    set_cached(cache_key, result, EARNINGS_TTL)
    return result


def batch_fetch_earnings(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch earnings dates for multiple symbols (synchronous version).
    Returns dict mapping symbol -> earnings data dict.
    
    Note: This is the legacy synchronous version. Prefer batch_fetch_earnings_async()
    for better performance when called from async context.
    """
    result = {}
    for symbol in symbols:
        result[symbol] = get_earnings_date(symbol)
    return result


async def batch_fetch_earnings_async(
    symbols: list[str], 
    max_concurrent: int = 10
) -> dict[str, dict]:
    """
    Fetch earnings dates for multiple symbols in parallel.
    
    RATE LIMIT NOTE: Each get_earnings_date() call may hit ticker.calendar
    and ticker.earnings_dates endpoints. The semaphore limits concurrency
    to prevent overwhelming Yahoo Finance's servers.
    
    The default max_concurrent=10 is conservative. If rate limiting occurs:
    - Reduce to 5 for safer operation
    - Results are cached for 6 hours (EARNINGS_TTL), so subsequent calls are free
    - Consider adding a small delay in fetch_one() if 429 errors persist
    
    Args:
        symbols: List of stock symbols to fetch earnings for
        max_concurrent: Maximum concurrent API calls (default 10)
    
    Returns:
        Dict mapping symbol -> earnings data dict (empty dict for failed fetches)
    """
    if not symbols:
        return {}
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_one(symbol: str) -> tuple[str, dict]:
        async with semaphore:
            try:
                return symbol, await asyncio.to_thread(get_earnings_date, symbol)
            except Exception as e:
                print(f"Error fetching earnings for {symbol}: {e}")
                return symbol, {}
    
    results = await asyncio.gather(*[fetch_one(s) for s in symbols])
    return dict(results)
