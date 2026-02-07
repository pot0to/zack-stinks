from .base import BaseState
import reflex as rx
import plotly.graph_objects as go
import yfinance as yf
from ..analyzer import StockAnalyzer

class MarketState(BaseState):
    market_data: dict[str, dict[str, str]] = {}
    trend_fig: go.Figure = go.Figure()
    gap_events: list[dict] = []
    ma_proximity_events: list[dict] = []
    # Store portfolio symbols for analysis
    _portfolio_symbols: list[str] = []

    async def setup_market_page(self):
        yield MarketState.fetch_market_data
        yield MarketState.fetch_trend_data
        yield MarketState.fetch_portfolio_signals

    async def fetch_market_data(self):
        self.is_loading = True
        yield
        self.market_data = StockAnalyzer().get_market_indices()
        self.is_loading = False

    async def fetch_portfolio_signals(self):
        """Fetch gap events and MA proximity for portfolio holdings."""
        from .portfolio import PortfolioState
        
        portfolio_state = await self.get_state(PortfolioState)
        
        print(f"DEBUG: is_logged_in = {portfolio_state.is_logged_in}")
        print(f"DEBUG: all_stock_holdings keys = {list(portfolio_state.all_stock_holdings.keys())}")
        
        # Ensure portfolio data is loaded (login and fetch if needed)
        if not portfolio_state.all_stock_holdings and not portfolio_state.is_logged_in:
            print("DEBUG: Triggering portfolio login and fetch...")
            # Trigger portfolio login and data fetch
            async for _ in portfolio_state.login_to_robinhood():
                pass
            async for _ in portfolio_state.fetch_all_portfolio_data():
                pass
            # Re-fetch state after loading
            portfolio_state = await self.get_state(PortfolioState)
            print(f"DEBUG: After fetch - all_stock_holdings keys = {list(portfolio_state.all_stock_holdings.keys())}")
        
        # Collect unique symbols from portfolio
        symbols = set()
        for acc_holdings in portfolio_state.all_stock_holdings.values():
            for holding in acc_holdings:
                symbol = holding.get("symbol", "")
                if symbol:
                    symbols.add(symbol)
        for acc_holdings in portfolio_state.all_options_holdings.values():
            for holding in acc_holdings:
                symbol = holding.get("symbol", "")
                if symbol:
                    symbols.add(symbol)
        
        symbol_list = list(symbols)
        print(f"DEBUG: Collected symbols = {symbol_list}")
        
        if symbol_list:
            analyzer = StockAnalyzer()
            self.gap_events = analyzer.detect_gap_events(symbol_list)
            print(f"DEBUG: gap_events count = {len(self.gap_events)}")
            self.ma_proximity_events = analyzer.detect_ma_proximity(symbol_list)
            print(f"DEBUG: ma_proximity_events count = {len(self.ma_proximity_events)}")
            print(f"DEBUG: ma_proximity_events = {self.ma_proximity_events}")
        else:
            print("DEBUG: No symbols found, setting empty lists")
            self.gap_events = []
            self.ma_proximity_events = []

    def fetch_trend_data(self):
        """Fetches historical data and builds the normalized comparison chart."""
        analyzer = StockAnalyzer()
        # Use the raw symbols defined in your analyzer's ticker_map
        tickers = analyzer.ticker_map 
        
        fig = go.Figure()

        for name, symbol in tickers.items():
            # Skip VIX for the momentum chart (it remains in header cards)
            if name == "VIX":
                continue
            try:
                # Get 1 month of price history
                df = yf.Ticker(symbol).history(period="1mo").reset_index()
                if df.empty:
                    continue

                # Percent change from start: ((Current / Start) - 1) * 100, centered at 0%
                start_price = df["Close"].iloc[0]
                relative_growth = (((df["Close"] / start_price) - 1) * 100).round(2).tolist()
                dates = df["Date"].dt.strftime("%b %d").tolist()

                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=relative_growth,
                        name=name,
                        mode="lines",
                        hovertemplate=f"<b>{name}</b>: %{{y}}%<extra></extra>"
                    )
                )
            except Exception as e:
                print(f"Error loading trend for {name} ({symbol}): {e}")

        # Modern Financial Dashboard Styling
        fig.update_layout(
            template="plotly_dark",
            # title=dict(text="Market Momentum", font=dict(size=16)),
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=10, r=10, t=60, b=20),
            
            # X-AXIS: Month and Year only
            xaxis=dict(
                showgrid=False,
                # 'dtick' controls the frequency (M1 = every 1 month)
                dtick="M1",
                # 'tickformat' defines the display ( %b = Short Month, %Y = 4-digit Year)
                tickformat="%b %Y",
                # Ensures labels don't overlap if you have many months
                tickangle=-45, 
            ),
            
            # Y-AXIS: Named "% Change"
            yaxis=dict(
                title="30-Day % Change",
                ticksuffix="%", 
                gridcolor="rgba(255,255,255,0.05)",
                side="right"
            ),
            
            legend=dict(
                orientation="h", 
                yanchor="bottom", y=1.02, 
                xanchor="right", x=1
            )
        )

        self.trend_fig = fig