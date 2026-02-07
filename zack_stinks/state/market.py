from .base import BaseState
import plotly.graph_objects as go
import yfinance as yf
from ..analyzer import StockAnalyzer

class MarketState(BaseState):
    market_data: dict[str, dict[str, str]] = {}
    trend_fig: go.Figure = go.Figure()

    async def setup_market_page(self):
        yield MarketState.fetch_market_data
        yield MarketState.fetch_trend_data

    async def fetch_market_data(self):
        self.is_loading = True
        yield
        self.market_data = StockAnalyzer().get_market_indices()
        self.is_loading = False

    def fetch_trend_data(self):
        """Fetches historical data and builds the normalized comparison chart."""
        analyzer = StockAnalyzer()
        # Use the raw symbols defined in your analyzer's ticker_map
        tickers = analyzer.ticker_map 
        
        fig = go.Figure()

        for name, symbol in tickers.items():
            try:
                # Get 1 month of price history
                df = yf.Ticker(symbol).history(period="1mo").reset_index()
                if df.empty:
                    continue

                # Normalization: (Current Price / Starting Price) * 100
                # This allows us to compare VIX (~15) and S&P (~5000) on one scale.
                start_price = df["Close"].iloc[0]
                relative_growth = ((df["Close"] / start_price) * 100).round(2).tolist()
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