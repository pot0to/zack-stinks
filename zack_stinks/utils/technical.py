"""Shared technical analysis utilities."""
import pandas as pd
import yfinance as yf
from typing import Optional
from .cache import get_cached, set_cached, MARKET_DATA_TTL


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
    
    This is significantly faster than individual ticker.history() calls
    because yfinance uses threading internally for batch downloads.
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
    
    Note: yfinance doesn't support true batch info fetching, but we cache
    results to avoid redundant calls within the same analysis run.
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
