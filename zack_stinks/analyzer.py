import yfinance as yf

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
                # Fetch 1 month of data for high/low (matches momentum chart period)
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
                    
                    # Format change with sign before $ for currency: "+$12.34 (+0.25%)"
                    sign = "+" if price_diff >= 0 else "-"
                    abs_diff = abs(price_diff)
                    if is_currency:
                        change_str = f"{sign}${abs_diff:,.2f} ({pct_change:+.2f}%)"
                    else:
                        change_str = f"{price_diff:+.2f} ({pct_change:+.2f}%)"
                    
                    # Format values as strings to avoid Reflex Var.format() issues
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

    def find_buy_opportunities(self, threshold=-3.0):
        return []

    def detect_gap_events(self, symbols: list[str], volume_threshold: float = 1.5) -> list[dict]:
        """
        Detect gap up/down events for a list of ticker symbols.
        
        Gap Up: Today's low > Yesterday's high
        Gap Down: Today's high < Yesterday's low
        
        Returns list of events sorted by percentage change (highest first).
        """
        events = []
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                # Fetch 5 days to ensure we have at least 2 trading days
                df = ticker.history(period="5d")
                
                if len(df) < 2:
                    continue
                
                # Get today and yesterday's data
                today = df.iloc[-1]
                yesterday = df.iloc[-2]
                
                today_open = today["Open"]
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
                    continue
                
                # Calculate percentage change from yesterday's close
                pct_change = ((today_close - yesterday_close) / yesterday_close) * 100
                
                # Calculate average volume (excluding today)
                avg_volume = df["Volume"].iloc[:-1].mean()
                volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0
                is_high_volume = volume_ratio >= volume_threshold
                
                events.append({
                    "symbol": symbol,
                    "gap_type": gap_type,
                    "pct_change": f"{pct_change:.2f}",
                    "pct_change_val": pct_change,
                    "volume_ratio": f"{volume_ratio:.2f}",
                    "is_high_volume": str(is_high_volume)
                })
                
            except Exception as e:
                print(f"Error detecting gap for {symbol}: {e}")
                continue
        
        # Sort by percentage change descending (highest gains first)
        events.sort(key=lambda x: x["pct_change_val"], reverse=True)
        return events


    def detect_ma_proximity(self, symbols: list[str], threshold_pct: float = 5.0) -> list[dict]:
        """
        Detect stocks near their 50-day or 200-day moving averages.
        
        Uses the most recent available closing price and compares to MAs.
        Returns list of events where price is within threshold_pct of either MA,
        sorted by absolute proximity (closest to MA first).
        """
        from .utils.technical import get_stock_ma_data
        
        events = []
        
        for symbol in symbols:
            try:
                ma_data = get_stock_ma_data(symbol, period="1y")
                current_price = ma_data["current_price"]
                
                if current_price is None:
                    continue
                
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
                
            except Exception as e:
                print(f"Error detecting MA proximity for {symbol}: {e}")
                continue
        
        # Sort by absolute proximity (closest to MA first)
        events.sort(key=lambda x: x["abs_offset"])
        return events

    def detect_below_ma_200(self, symbols: list[str], symbol_accounts: dict[str, list[str]]) -> list[dict]:
        """
        Detect stocks trading below their 200-day moving average.
        
        Returns list of events with symbol, price, MA value, % below, and accounts holding.
        Sorted by percentage below MA (most underwater first).
        """
        from .utils.technical import get_stock_ma_data
        
        events = []
        
        for symbol in symbols:
            try:
                ma_data = get_stock_ma_data(symbol, period="1y")
                current_price = ma_data["current_price"]
                
                if current_price is None or ma_data["ma_200"] is None:
                    continue
                
                pct_from_200 = ma_data["pct_from_200"]
                if pct_from_200 is None or pct_from_200 >= 0:
                    continue
                
                accounts = symbol_accounts.get(symbol, [])
                
                events.append({
                    "symbol": symbol,
                    "price": f"${current_price:,.2f}",
                    "ma_200_value": f"${ma_data['ma_200']:,.2f}",
                    "pct_below": f"{pct_from_200:.2f}",
                    "pct_below_val": pct_from_200,
                    "accounts": ", ".join(accounts) if accounts else "Unknown",
                })
                
            except Exception as e:
                print(f"Error detecting below MA 200 for {symbol}: {e}")
                continue
        
        # Sort by percentage below (most underwater first)
        events.sort(key=lambda x: x["pct_below_val"])
        return events
