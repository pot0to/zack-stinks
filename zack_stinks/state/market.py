from .base import BaseState
import reflex as rx
import asyncio
import plotly.graph_objects as go
import yfinance as yf
from ..analyzer import StockAnalyzer
from ..utils.cache import get_cached, set_cached, MARKET_DATA_TTL, DEFAULT_TTL

class MarketState(BaseState):
    market_data: dict[str, dict[str, str]] = {}
    trend_fig: go.Figure = go.Figure()
    gap_events: list[dict] = []
    ma_proximity_events: list[dict] = []
    # Track portfolio spotlight loading state
    portfolio_signals_loading: bool = False
    portfolio_data_available: bool = False

    async def setup_market_page(self):
        """Setup market page - check login status and fetch data."""
        # If not logged in, redirect to login page
        if not self.is_logged_in:
            yield rx.redirect("/login")
            return
        # Fetch market data and trend chart in parallel (don't wait for portfolio)
        yield MarketState.fetch_market_data
        yield MarketState.fetch_trend_data
        # Portfolio signals are fetched separately, non-blocking
        yield MarketState.fetch_portfolio_signals_async

    async def fetch_market_data(self):
        self.is_loading = True
        yield
        
        # Check cache first
        cached = get_cached("market_indices")
        if cached:
            self.market_data = cached
            self.is_loading = False
            return
        
        # Fetch fresh data
        self.market_data = await asyncio.to_thread(StockAnalyzer().get_market_indices)
        set_cached("market_indices", self.market_data, MARKET_DATA_TTL)
        self.is_loading = False

    async def fetch_portfolio_signals_async(self):
        """Fetch gap events and MA proximity for portfolio holdings.
        
        This is now non-blocking: if portfolio isn't loaded, we skip rather than
        triggering a full portfolio sync. The user can refresh after visiting portfolio.
        """
        from .portfolio import PortfolioState
        
        self.portfolio_signals_loading = True
        yield
        
        portfolio_state = await self.get_state(PortfolioState)
        
        # If portfolio not loaded, skip signals (don't block market page)
        if not portfolio_state.all_stock_holdings:
            self.gap_events = []
            self.ma_proximity_events = []
            self.portfolio_data_available = False
            self.portfolio_signals_loading = False
            return
        
        self.portfolio_data_available = True
        
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
        
        if symbol_list:
            # Check cache
            cache_key = f"portfolio_signals:{','.join(sorted(symbol_list))}"
            cached = get_cached(cache_key)
            if cached:
                self.gap_events = cached["gap_events"]
                self.ma_proximity_events = cached["ma_proximity_events"]
                self.portfolio_signals_loading = False
                return
            
            # Fetch signals in parallel
            analyzer = StockAnalyzer()
            gap_task = asyncio.to_thread(analyzer.detect_gap_events, symbol_list)
            ma_task = asyncio.to_thread(analyzer.detect_ma_proximity, symbol_list)
            
            self.gap_events, self.ma_proximity_events = await asyncio.gather(gap_task, ma_task)
            
            # Cache results
            set_cached(cache_key, {
                "gap_events": self.gap_events,
                "ma_proximity_events": self.ma_proximity_events,
            }, DEFAULT_TTL)
        else:
            self.gap_events = []
            self.ma_proximity_events = []
        
        self.portfolio_signals_loading = False

    async def fetch_trend_data(self):
        """Fetches historical data and builds the normalized comparison chart.
        Now async with parallel ticker fetches."""
        
        # Check cache first
        cached = get_cached("trend_chart")
        if cached:
            self.trend_fig = cached
            return
        
        analyzer = StockAnalyzer()
        tickers = analyzer.ticker_map 
        
        # Fetch all tickers in parallel
        async def fetch_ticker_data(name: str, symbol: str):
            if name == "VIX":
                return None
            try:
                df = await asyncio.to_thread(
                    lambda: yf.Ticker(symbol).history(period="1mo").reset_index()
                )
                if df.empty:
                    return None
                
                start_price = df["Close"].iloc[0]
                relative_growth = (((df["Close"] / start_price) - 1) * 100).round(2).tolist()
                dates = df["Date"].dt.strftime("%b %d").tolist()
                
                return {
                    "name": name,
                    "dates": dates,
                    "growth": relative_growth,
                }
            except Exception as e:
                print(f"Error loading trend for {name} ({symbol}): {e}")
                return None
        
        # Parallel fetch all tickers
        tasks = [fetch_ticker_data(name, symbol) for name, symbol in tickers.items()]
        results = await asyncio.gather(*tasks)
        
        fig = go.Figure()
        
        for result in results:
            if result is None:
                continue
            fig.add_trace(
                go.Scatter(
                    x=result["dates"],
                    y=result["growth"],
                    name=result["name"],
                    mode="lines",
                    hovertemplate=f"<b>{result['name']}</b>: %{{y}}%<extra></extra>"
                )
            )

        # Modern Financial Dashboard Styling
        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=10, r=10, t=60, b=20),
            xaxis=dict(
                showgrid=False,
                dtick="M1",
                tickformat="%b %Y",
                tickangle=-45, 
            ),
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
        set_cached("trend_chart", fig, MARKET_DATA_TTL)