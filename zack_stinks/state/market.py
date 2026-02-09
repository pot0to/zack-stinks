from .base import BaseState
from ..utils.symbols import is_index_fund
import reflex as rx
import asyncio
import plotly.graph_objects as go
import yfinance as yf
from ..analyzer import StockAnalyzer
from ..utils.cache import get_cached, set_cached, MARKET_DATA_TTL, DEFAULT_TTL
from ..utils.technical import batch_fetch_earnings_async

class MarketState(BaseState):
    market_data: dict[str, dict[str, str]] = {}
    trend_fig: go.Figure = go.Figure()
    gap_events: list[dict] = []
    ma_proximity_events: list[dict] = []
    below_ma_200_events: list[dict] = []
    near_ath_events: list[dict] = []
    ma_breakout_events: list[dict] = []
    upcoming_earnings_events: list[dict] = []  # Holdings with earnings within 7 days
    # Track portfolio spotlight loading state
    portfolio_signals_loading: bool = False
    portfolio_data_available: bool = False

    # Filtered views: separate index funds/ETFs from individual positions
    @rx.var
    def index_fund_gap_events(self) -> list[dict]:
        return [e for e in self.gap_events if is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def individual_gap_events(self) -> list[dict]:
        return [e for e in self.gap_events if not is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def index_fund_ma_proximity_events(self) -> list[dict]:
        return [e for e in self.ma_proximity_events if is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def individual_ma_proximity_events(self) -> list[dict]:
        return [e for e in self.ma_proximity_events if not is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def index_fund_below_ma_200_events(self) -> list[dict]:
        return [e for e in self.below_ma_200_events if is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def individual_below_ma_200_events(self) -> list[dict]:
        return [e for e in self.below_ma_200_events if not is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def index_fund_near_ath_events(self) -> list[dict]:
        return [e for e in self.near_ath_events if is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def individual_near_ath_events(self) -> list[dict]:
        return [e for e in self.near_ath_events if not is_index_fund(e.get("symbol", ""))]

    @rx.var
    def index_fund_ma_breakout_events(self) -> list[dict]:
        return [e for e in self.ma_breakout_events if is_index_fund(e.get("symbol", ""))]
    
    @rx.var
    def individual_ma_breakout_events(self) -> list[dict]:
        return [e for e in self.ma_breakout_events if not is_index_fund(e.get("symbol", ""))]

    async def setup_market_page(self):
        """Setup market page - validate session and fetch data.
        
        Market data is public and always fetched. Portfolio signals
        require authentication and auto-load portfolio data if needed.
        """
        # Try to restore session from pickle if available
        await self.validate_existing_session()
        
        # Fetch public market data regardless of login status
        yield MarketState.fetch_market_data
        yield MarketState.fetch_trend_data
        
        # Portfolio signals require authentication
        if self.is_logged_in:
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
        
        Auto-loads portfolio data from cache if not already in memory,
        allowing the Market page to show Portfolio Spotlight without
        requiring a visit to the Portfolio page first.
        
        Uses read-only access to portfolio state to avoid blocking tab switching.
        """
        from .portfolio import PortfolioState
        
        self.portfolio_signals_loading = True
        yield
        
        portfolio_state = await self.get_state(PortfolioState)
        
        # Read portfolio data - prefer in-memory state, fall back to cache
        # We read without holding a lock to avoid blocking UI interactions
        all_stock_holdings = portfolio_state.all_stock_holdings
        all_options_holdings = portfolio_state.all_options_holdings
        account_map = portfolio_state.account_map
        
        if not all_stock_holdings:
            cached_portfolio = get_cached("portfolio_data")
            if cached_portfolio:
                # Use cached data for signal analysis without modifying portfolio state
                # This avoids blocking the portfolio page's tab switching
                all_stock_holdings = cached_portfolio["all_stock_holdings"]
                all_options_holdings = cached_portfolio["all_options_holdings"]
                account_map = cached_portfolio["account_map"]
                # Note: We intentionally do NOT update PortfolioState here.
                # The portfolio page will load its own data from cache when visited.
                # Acquiring a lock on PortfolioState would block tab switching.
            else:
                # No cached data available - user needs to visit Portfolio page
                self.gap_events = []
                self.ma_proximity_events = []
                self.below_ma_200_events = []
                self.near_ath_events = []
                self.ma_breakout_events = []
                self.upcoming_earnings_events = []
                self.portfolio_data_available = False
                self.portfolio_signals_loading = False
                return
        
        self.portfolio_data_available = True
        
        # Collect unique symbols from local data (not holding any locks)
        symbol_list, symbol_accounts = self._collect_portfolio_symbols_from_data(
            all_stock_holdings, all_options_holdings, account_map
        )
        
        if symbol_list:
            # Check cache
            cache_key = f"portfolio_signals:{','.join(sorted(symbol_list))}"
            cached = get_cached(cache_key)
            if cached:
                self.gap_events = cached["gap_events"]
                self.ma_proximity_events = cached["ma_proximity_events"]
                self.below_ma_200_events = cached.get("below_ma_200_events", [])
                self.near_ath_events = cached.get("near_ath_events", [])
                self.ma_breakout_events = cached.get("ma_breakout_events", [])
                self.upcoming_earnings_events = cached.get("upcoming_earnings_events", [])
                self.portfolio_signals_loading = False
                return
            
            # Fetch all signals in a single batch operation
            analyzer = StockAnalyzer()
            results = await asyncio.to_thread(
                analyzer.detect_all_signals, symbol_list, symbol_accounts
            )
            
            # Fetch earnings data for all symbols (parallel async fetch)
            earnings_data = await batch_fetch_earnings_async(symbol_list)
            upcoming_earnings = self._process_earnings_events(earnings_data, symbol_accounts)
            
            self.gap_events = results["gap_events"]
            self.ma_proximity_events = results["ma_proximity_events"]
            self.below_ma_200_events = results["below_ma_200_events"]
            self.near_ath_events = results["near_ath_events"]
            self.ma_breakout_events = results["ma_breakout_events"]
            self.upcoming_earnings_events = upcoming_earnings
            
            # Cache results (include earnings)
            results["upcoming_earnings_events"] = upcoming_earnings
            set_cached(cache_key, results, DEFAULT_TTL)
        else:
            self.gap_events = []
            self.ma_proximity_events = []
            self.below_ma_200_events = []
            self.near_ath_events = []
            self.ma_breakout_events = []
            self.upcoming_earnings_events = []
        
        self.portfolio_signals_loading = False
    
    def _process_earnings_events(
        self, 
        earnings_data: dict[str, dict], 
        symbol_accounts: dict[str, list[str]]
    ) -> list[dict]:
        """Process earnings data into events for holdings with earnings within 7 days.
        
        Returns list of dicts sorted by days_until (soonest first).
        """
        events = []
        
        for symbol, data in earnings_data.items():
            days_until = data.get("days_until")
            
            # Only include if earnings within 7 days (and not in the past)
            if days_until is not None and 0 <= days_until <= 7:
                accounts = symbol_accounts.get(symbol, [])
                accounts_str = ", ".join(accounts) if accounts else "Unknown"
                
                # Determine urgency level for color coding
                if days_until <= 3:
                    urgency = "imminent"  # Red badge
                else:
                    urgency = "soon"  # Yellow badge
                
                events.append({
                    "symbol": symbol,
                    "earnings_date": data.get("earnings_date_str", "Unknown"),
                    "days_until": days_until,
                    "days_until_str": f"in {days_until} day{'s' if days_until != 1 else ''}",
                    "timing": data.get("timing"),  # BMO, AMC, or None
                    "timing_str": f" ({data['timing']})" if data.get("timing") else "",
                    "urgency": urgency,
                    "accounts": accounts_str,
                })
        
        # Sort by days_until (soonest first)
        events.sort(key=lambda x: x["days_until"])
        return events
    
    def _collect_portfolio_symbols_from_data(
        self,
        all_stock_holdings: dict,
        all_options_holdings: dict,
        account_map: dict
    ) -> tuple[list[str], dict[str, list[str]]]:
        """Extract unique symbols and their account ownership from portfolio data.
        
        This version works with raw data dicts instead of state objects,
        allowing signal analysis without holding state locks.
        
        Returns (symbol_list, symbol_accounts) where symbol_accounts maps each symbol
        to the list of account display names that hold it.
        """
        symbols = set()
        symbol_accounts: dict[str, list[str]] = {}
        
        # Build reverse map: account_number -> display_name
        acc_num_to_name = {v: k for k, v in account_map.items()}
        
        # Process both stock and option holdings
        for holdings_dict in [all_stock_holdings, all_options_holdings]:
            for acc_num, acc_holdings in holdings_dict.items():
                acc_name = acc_num_to_name.get(acc_num, acc_num)
                for holding in acc_holdings:
                    symbol = holding.get("symbol", "")
                    if symbol:
                        symbols.add(symbol)
                        if symbol not in symbol_accounts:
                            symbol_accounts[symbol] = []
                        if acc_name not in symbol_accounts[symbol]:
                            symbol_accounts[symbol].append(acc_name)
        
        return list(symbols), symbol_accounts

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
            hoverlabel=dict(
                bgcolor="rgba(30, 30, 30, 0.95)",
                font_color="white",
                bordercolor="rgba(255, 255, 255, 0.2)",
            ),
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