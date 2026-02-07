"""State management for the Stock Research page."""
import reflex as rx
import asyncio
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import BaseState


class ResearchState(BaseState):
    """Manages stock research data and calculations."""
    ticker: str = "AAPL"
    period: str = "6mo"
    
    # Stock statistics
    current_price: str = "--"
    price_change_pct: str = "--"
    high_52w: str = "--"
    rsi_14: str = "--"
    volatility: str = "--"
    ma_50_pct: str = "--"
    ma_200_pct: str = "--"
    macd_signal: str = "--"
    
    # Chart figure
    price_chart: go.Figure = go.Figure()

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    def set_period(self, value: str):
        self.period = value

    async def fetch_stock_data(self):
        """Fetch stock data and calculate all statistics."""
        if not self.ticker.strip():
            yield rx.toast.error("Please enter a ticker symbol")
            return
            
        self.is_loading = True
        yield

        try:
            ticker_obj = yf.Ticker(self.ticker)
            
            # Determine how much history we need: display period + 200 days for MA calculation
            # Map periods to approximate fetch periods that ensure full MA coverage
            extended_periods = {
                "1mo": "1y",
                "3mo": "1y", 
                "6mo": "2y",
                "1y": "3y",
                "2y": "5y",
            }
            fetch_period = extended_periods.get(self.period, "5y")
            
            # Fetch extended historical data for MA calculations
            full_hist = await asyncio.to_thread(
                ticker_obj.history, period=fetch_period
            )
            
            if full_hist.empty:
                yield rx.toast.error(f"No data found for {self.ticker}")
                self.is_loading = False
                return

            # Use most recent 1 year for stats calculations
            stats_hist = full_hist.tail(252) if len(full_hist) > 252 else full_hist

            # Current price and daily change
            current = full_hist['Close'].iloc[-1]
            prev_close = full_hist['Close'].iloc[-2] if len(full_hist) > 1 else current
            change_pct = ((current - prev_close) / prev_close) * 100
            
            self.current_price = f"${current:.2f}"
            self.price_change_pct = f"{change_pct:+.2f}%"

            # 52-week high
            high_52 = stats_hist['High'].max()
            self.high_52w = f"${high_52:.2f}"

            # RSI (14-day)
            self.rsi_14 = f"{self._calculate_rsi(full_hist['Close'], 14):.1f}"

            # Volatility (annualized standard deviation of returns)
            returns = stats_hist['Close'].pct_change().dropna()
            vol = returns.std() * (252 ** 0.5) * 100
            self.volatility = f"{vol:.1f}%"

            # 50-day and 200-day moving average comparisons
            if len(full_hist) >= 50:
                ma_50_current = full_hist['Close'].rolling(window=50).mean().iloc[-1]
                pct_from_50 = ((current - ma_50_current) / ma_50_current) * 100
                self.ma_50_pct = f"{pct_from_50:+.1f}%"
            else:
                self.ma_50_pct = "N/A"

            if len(full_hist) >= 200:
                ma_200_current = full_hist['Close'].rolling(window=200).mean().iloc[-1]
                pct_from_200 = ((current - ma_200_current) / ma_200_current) * 100
                self.ma_200_pct = f"{pct_from_200:+.1f}%"
            else:
                self.ma_200_pct = "N/A"

            # MACD
            macd_value = self._calculate_macd(full_hist['Close'])
            self.macd_signal = "Positive" if macd_value > 0 else "Negative"

            # Calculate MAs from full history
            ma_50_series = full_hist['Close'].rolling(window=50).mean() if len(full_hist) >= 50 else None
            ma_200_series = full_hist['Close'].rolling(window=200).mean() if len(full_hist) >= 200 else None

            # Get chart data for the selected display period
            chart_hist = await asyncio.to_thread(
                ticker_obj.history, period=self.period
            )
            
            # Filter MA series to match chart date range
            chart_start = chart_hist.index.min()
            ma_50_filtered = ma_50_series[ma_50_series.index >= chart_start] if ma_50_series is not None else None
            ma_200_filtered = ma_200_series[ma_200_series.index >= chart_start] if ma_200_series is not None else None
            
            # Use weekly candles for periods > 1 year to reduce clutter
            use_weekly = self.period in ["2y"]
            
            self.price_chart = self._build_candlestick_chart(
                chart_hist, ma_50_filtered, ma_200_filtered, use_weekly
            )

            yield rx.toast.success(f"Loaded {self.ticker}")

        except Exception as e:
            yield rx.toast.error(f"Error: {str(e)}")
        finally:
            self.is_loading = False

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate the Relative Strength Index."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 0

    def _calculate_macd(self, prices: pd.Series) -> float:
        """Calculate MACD (12-day EMA minus 26-day EMA)."""
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        return macd_line.iloc[-1]

    def _build_candlestick_chart(
        self, 
        hist: pd.DataFrame, 
        ma_50: pd.Series = None, 
        ma_200: pd.Series = None,
        use_weekly: bool = False
    ) -> go.Figure:
        """Build a candlestick chart with volume subplot and moving averages."""
        
        # Resample to weekly if requested
        if use_weekly and len(hist) > 0:
            hist = hist.resample('W').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.8, 0.2]
        )

        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name="Price",
                increasing_line_color='rgb(34, 197, 94)',
                decreasing_line_color='rgb(239, 68, 68)',
            ),
            row=1, col=1
        )

        # 50-day moving average (pre-calculated from full history)
        if ma_50 is not None and not ma_50.dropna().empty:
            fig.add_trace(
                go.Scatter(
                    x=ma_50.index,
                    y=ma_50,
                    name="50 MA",
                    line=dict(color='rgb(59, 130, 246)', width=1.5),
                ),
                row=1, col=1
            )

        # 200-day moving average (pre-calculated from full history)
        if ma_200 is not None and not ma_200.dropna().empty:
            fig.add_trace(
                go.Scatter(
                    x=ma_200.index,
                    y=ma_200,
                    name="200 MA",
                    line=dict(color='rgb(249, 115, 22)', width=1.5),
                ),
                row=1, col=1
            )

        # Volume bars
        colors = ['rgb(34, 197, 94)' if c >= o else 'rgb(239, 68, 68)' 
                  for c, o in zip(hist['Close'], hist['Open'])]
        fig.add_trace(
            go.Bar(
                x=hist.index,
                y=hist['Volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
            ),
            row=2, col=1
        )

        title_suffix = " (Weekly)" if use_weekly else ""
        fig.update_layout(
            title=f"{self.ticker} Price Action{title_suffix}",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=450,
            margin=dict(t=40, l=50, r=20, b=20),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10),
            ),
            xaxis_rangeslider_visible=False,
        )
        
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)')

        return fig
