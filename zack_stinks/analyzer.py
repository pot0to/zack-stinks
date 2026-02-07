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
        Returns a dict: {"Index Name": {"price": str, "change": str}}
        """
        market_results = {}
        
        for name, ticker_symbol in self.ticker_map.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                # Fetching the last 2 days of data to calculate change
                df = ticker.history(period="2d")
                
                if not df.empty:
                    current_val = df['Close'].iloc[-1]
                    
                    if len(df) >= 2:
                        prev_val = df['Close'].iloc[-2]
                    else:
                        # Fallback if only 1 day of data exists
                        prev_val = df['Open'].iloc[-1]
                    
                    price_diff = current_val - prev_val
                    
                    # We format to 2 decimal places as strings here to avoid 
                    # Reflex compilation errors with Var.format()
                    market_results[name] = {
                        "price": f"{float(current_val):,.2f}",
                        "change": f"{float(price_diff):+.2f}" # Adds + or - sign
                    }
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                market_results[name] = {"price": "0.00", "change": "0.00"}
                
        return market_results

    def find_buy_opportunities(self, threshold=-3.0):
        return []