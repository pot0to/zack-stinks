"""
Stock analysis utilities for detecting trading signals.

Uses batch data fetching for performance: a single yf.download() call
retrieves history for all symbols, then each detection method processes
the pre-fetched data without additional API calls.
"""
import yfinance as yf
from .utils.technical import (
    normalize_symbol_for_yfinance,
    batch_fetch_history,
    batch_fetch_info,
    calculate_ma_data_from_df,
)


class StockAnalyzer:
    def __init__(self):
        self.ticker_map = {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "Dow Jones": "^DJI",
            "VIX": "^VIX"
        }

    def get_market_indices(self) -> dict:
        """
        Fetch major indices for the header cards.
        Returns a dict with price, daily change, 1-month high/low, and currency flag.
        """
        market_results = {}
        
        for name, ticker_symbol in self.ticker_map.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                df = ticker.history(period="1mo")
                
                if not df.empty:
                    current_val = df['Close'].iloc[-1]
                    high_val = df['High'].max()
                    low_val = df['Low'].min()
                    
                    if len(df) >= 2:
                        prev_val = df['Close'].iloc[-2]
                    else:
                        prev_val = df['Open'].iloc[-1]
                    
                    price_diff = current_val - prev_val
                    pct_change = (price_diff / prev_val) * 100
                    is_currency = name != "VIX"
                    
                    sign = "+" if price_diff >= 0 else "-"
                    abs_diff = abs(price_diff)
                    if is_currency:
                        change_str = f"{sign}${abs_diff:,.2f} ({pct_change:+.2f}%)"
                    else:
                        change_str = f"{price_diff:+.2f} ({pct_change:+.2f}%)"
                    
                    market_results[name] = {
                        "price": f"{float(current_val):,.2f}",
                        "change": change_str,
                        "change_val": float(price_diff),
                        "high": f"{float(high_val):,.2f}",
                        "low": f"{float(low_val):,.2f}",
                        "is_currency": str(is_currency)
                    }
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                market_results[name] = {
                    "price": "0.00", "change": "+$0.00 (+0.00%)",
                    "change_val": 0.0,
                    "high": "0.00", "low": "0.00", "is_currency": "True"
                }
                
        return market_results

    def detect_all_signals(
        self,
        symbols: list[str],
        symbol_accounts: dict[str, list[str]],
        ma_proximity_threshold: float = 5.0,
        near_high_threshold: float = 5.0,
        volume_threshold: float = 1.5,
    ) -> dict[str, list[dict]]:
        """
        Detect all portfolio signals in a single pass using batch data fetching.
        
        This consolidates gap detection, MA proximity, below-MA-200, and near-52-week-high
        detection into one method that fetches data once and processes it for all signals.
        
        Returns dict with keys: gap_events, ma_proximity_events, below_ma_200_events, near_ath_events
        """
        if not symbols:
            return {
                "gap_events": [],
                "ma_proximity_events": [],
                "below_ma_200_events": [],
                "near_ath_events": [],
            }
        
        # Batch fetch all historical data (1 year covers all needs including 5-day for gaps)
        history_data = batch_fetch_history(symbols, period="1y")
        
        # Batch fetch ticker info for 52-week high data
        info_data = batch_fetch_info(symbols)
        
        # Process all signals from the pre-fetched data
        gap_events = []
        ma_proximity_events = []
        below_ma_200_events = []
        near_ath_events = []
        
        for symbol in symbols:
            df = history_data.get(symbol)
            info = info_data.get(symbol, {})
            accounts = symbol_accounts.get(symbol, [])
            accounts_str = ", ".join(accounts) if accounts else "Unknown"
            
            # Process gap events (needs last 2 days of data)
            gap_event = self._process_gap_event(symbol, df, volume_threshold)
            if gap_event:
                gap_events.append(gap_event)
            
            # Process MA-based signals (proximity and below-200)
            ma_data = calculate_ma_data_from_df(df)
            current_price = ma_data["current_price"]
            
            if current_price is not None:
                # MA proximity events (50-day and 200-day)
                ma_proximity_events.extend(
                    self._process_ma_proximity(symbol, ma_data, current_price, ma_proximity_threshold)
                )
                
                # Below 200-day MA events
                below_event = self._process_below_ma_200(symbol, ma_data, current_price, accounts_str)
                if below_event:
                    below_ma_200_events.append(below_event)
            
            # Process near 52-week high events
            near_high_event = self._process_near_high(symbol, info, near_high_threshold, accounts_str)
            if near_high_event:
                near_ath_events.append(near_high_event)
        
        # Sort results
        gap_events.sort(key=lambda x: x["pct_change_val"], reverse=True)
        ma_proximity_events.sort(key=lambda x: x["abs_offset"])
        below_ma_200_events.sort(key=lambda x: x["pct_below_val"])
        near_ath_events.sort(key=lambda x: x["abs_from_ath"])
        
        return {
            "gap_events": gap_events,
            "ma_proximity_events": ma_proximity_events,
            "below_ma_200_events": below_ma_200_events,
            "near_ath_events": near_ath_events,
        }
    
    def _process_gap_event(self, symbol: str, df, volume_threshold: float) -> dict | None:
        """Process gap detection for a single symbol from pre-fetched data."""
        if df is None or len(df) < 2:
            return None
        
        try:
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            
            today_high = today["High"]
            today_low = today["Low"]
            today_close = today["Close"]
            today_volume = today["Volume"]
            
            yesterday_high = yesterday["High"]
            yesterday_low = yesterday["Low"]
            yesterday_close = yesterday["Close"]
            
            # Detect gap type
            gap_type = None
            if today_low > yesterday_high:
                gap_type = "Gap Up"
            elif today_high < yesterday_low:
                gap_type = "Gap Down"
            
            if not gap_type:
                return None
            
            pct_change = ((today_close - yesterday_close) / yesterday_close) * 100
            
            # Use 50-day average volume (industry standard, aligns with IBD methodology)
            # Fall back to available data if less than 50 days
            volume_window = min(50, len(df) - 1)
            if volume_window > 0:
                avg_volume = df["Volume"].iloc[-volume_window-1:-1].mean()
            else:
                avg_volume = 0
            
            volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0
            is_high_volume = volume_ratio >= volume_threshold
            
            return {
                "symbol": symbol,
                "gap_type": gap_type,
                "pct_change": f"{pct_change:.2f}",
                "pct_change_val": pct_change,
                "volume_ratio": f"{volume_ratio:.2f}",
                "is_high_volume": str(is_high_volume)
            }
        except Exception as e:
            print(f"Error processing gap for {symbol}: {e}")
            return None
    
    def _process_ma_proximity(
        self, symbol: str, ma_data: dict, current_price: float, threshold_pct: float
    ) -> list[dict]:
        """Process MA proximity events for a single symbol from pre-calculated MA data."""
        events = []
        
        # Check 50-day MA proximity
        if ma_data["ma_50"] is not None and ma_data["pct_from_50"] is not None:
            pct_offset = float(ma_data["pct_from_50"])
            if abs(pct_offset) <= threshold_pct:
                events.append({
                    "symbol": symbol,
                    "price": f"${current_price:,.2f}",
                    "ma_type": "50-day MA",
                    "ma_value": f"${ma_data['ma_50']:,.2f}",
                    "pct_offset": f"{pct_offset:+.2f}",
                    "pct_offset_val": pct_offset,
                    "abs_offset": abs(pct_offset)
                })
        
        # Check 200-day MA proximity
        if ma_data["ma_200"] is not None and ma_data["pct_from_200"] is not None:
            pct_offset = float(ma_data["pct_from_200"])
            if abs(pct_offset) <= threshold_pct:
                events.append({
                    "symbol": symbol,
                    "price": f"${current_price:,.2f}",
                    "ma_type": "200-day MA",
                    "ma_value": f"${ma_data['ma_200']:,.2f}",
                    "pct_offset": f"{pct_offset:+.2f}",
                    "pct_offset_val": pct_offset,
                    "abs_offset": abs(pct_offset)
                })
        
        return events
    
    def _process_below_ma_200(
        self, symbol: str, ma_data: dict, current_price: float, accounts_str: str
    ) -> dict | None:
        """Process below-200-day-MA detection for a single symbol."""
        if ma_data["ma_200"] is None or ma_data["pct_from_200"] is None:
            return None
        
        pct_from_200 = ma_data["pct_from_200"]
        if pct_from_200 >= 0:
            return None
        
        return {
            "symbol": symbol,
            "price": f"${current_price:,.2f}",
            "ma_200_value": f"${ma_data['ma_200']:,.2f}",
            "pct_below": f"{pct_from_200:.2f}",
            "pct_below_val": pct_from_200,
            "accounts": accounts_str,
        }
    
    def _process_near_high(
        self, symbol: str, info: dict, threshold_pct: float, accounts_str: str
    ) -> dict | None:
        """Process near-52-week-high detection for a single symbol."""
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        fifty_two_week_high = info.get("fiftyTwoWeekHigh")
        
        if not current_price or not fifty_two_week_high or fifty_two_week_high <= 0:
            return None
        
        pct_from_high = ((current_price - fifty_two_week_high) / fifty_two_week_high) * 100
        
        if abs(pct_from_high) > threshold_pct:
            return None
        
        return {
            "symbol": symbol,
            "price": f"${current_price:,.2f}",
            "all_time_high": f"${fifty_two_week_high:,.2f}",
            "pct_from_ath": f"{pct_from_high:.2f}",
            "pct_from_ath_val": pct_from_high,
            "abs_from_ath": abs(pct_from_high),
            "accounts": accounts_str,
        }

    # Legacy methods kept for backward compatibility (used by other parts of the app)
    def detect_gap_events(self, symbols: list[str], volume_threshold: float = 1.5) -> list[dict]:
        """Legacy method - prefer detect_all_signals() for batch processing."""
        results = self.detect_all_signals(symbols, {}, volume_threshold=volume_threshold)
        return results["gap_events"]

    def detect_ma_proximity(self, symbols: list[str], threshold_pct: float = 5.0) -> list[dict]:
        """Legacy method - prefer detect_all_signals() for batch processing."""
        results = self.detect_all_signals(symbols, {}, ma_proximity_threshold=threshold_pct)
        return results["ma_proximity_events"]

    def detect_below_ma_200(self, symbols: list[str], symbol_accounts: dict[str, list[str]]) -> list[dict]:
        """Legacy method - prefer detect_all_signals() for batch processing."""
        results = self.detect_all_signals(symbols, symbol_accounts)
        return results["below_ma_200_events"]

    def detect_near_all_time_highs(
        self, symbols: list[str], symbol_accounts: dict[str, list[str]], threshold_pct: float = 5.0
    ) -> list[dict]:
        """Legacy method - prefer detect_all_signals() for batch processing."""
        results = self.detect_all_signals(symbols, symbol_accounts, near_high_threshold=threshold_pct)
        return results["near_ath_events"]
