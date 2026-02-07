"""Shared technical analysis utilities."""
import pandas as pd
import yfinance as yf
from typing import Optional


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
    
    Returns dict with current_price, ma_50, ma_200, pct_from_50, pct_from_200.
    Values are None if unavailable. All numeric values are Python floats.
    """
    result = {
        "current_price": None,
        "ma_50": None,
        "ma_200": None,
        "pct_from_50": None,
        "pct_from_200": None,
    }
    
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        
        if df.empty:
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
    
    return result
