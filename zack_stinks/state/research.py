"""State management for the Stock Research page."""
import reflex as rx
import asyncio
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from .base import BaseState
from ..utils.technical import calculate_ma_proximity, calculate_ma_series
from ..utils.cache import get_cached, set_cached, DEFAULT_TTL


class ResearchState(BaseState):
    """Manages stock research data and calculations."""
    ticker: str = "AAPL"
    period: str = "6mo"
    active_tab: str = "technical"  # "technical" or "fundamentals"
    
    # Stock statistics
    current_price: str = "--"
    price_change_pct: str = "--"
    price_change_positive: bool = True  # For color coding
    high_52w: str = "--"
    rsi_14: str = "--"
    rsi_zone: str = "--"  # Oversold/Weak/Bullish/Overbought
    volatility: str = "--"
    volatility_zone: str = "--"  # Low/Normal/High relative to stock's own history
    volatility_vs_spy: str = "--"  # SPY volatility for market benchmark
    ma_50_pct: str = "--"
    ma_200_pct: str = "--"
    macd_signal: str = "--"
    range_52w: str = "--"  # Position in 52-week range (0-100%)
    
    # RSI and MACD series for subplot charting
    _rsi_series: list = []
    _macd_line: list = []
    _macd_signal_line: list = []
    _macd_histogram: list = []
    _indicator_dates: list = []
    
    # Fundamental indicators
    has_fundamentals: bool = True  # False for ETFs
    pe_ratio: str = "--"
    pe_zone: str = "--"  # Value/Fair/Premium
    revenue_growth: str = "--"
    revenue_growth_zone: str = "--"  # Accelerating/Stable/Declining
    profit_margin: str = "--"
    profit_margin_zone: str = "--"  # Strong/Average/Weak
    roe: str = "--"
    roe_zone: str = "--"  # Strong/Average/Weak
    debt_to_equity: str = "--"
    debt_to_equity_zone: str = "--"  # Conservative/Moderate/Aggressive
    
    # Chart figure
    price_chart: go.Figure = go.Figure()

    def set_ticker(self, value: str):
        self.ticker = value.upper()

    def set_period(self, value: str):
        self.period = value

    def set_active_tab(self, value: str):
        self.active_tab = value

    async def fetch_stock_data(self):
        """Fetch stock data and calculate all statistics.
        
        Optimized: fetches extended history once and slices for display period.
        """
        if not self.ticker.strip():
            yield rx.toast.error("Please enter a ticker symbol")
            return
            
        self.is_loading = True
        yield

        try:
            ticker_obj = yf.Ticker(self.ticker)
            
            # Map display periods to days for slicing
            period_days = {
                "1mo": 22,
                "3mo": 66, 
                "6mo": 126,
                "1y": 252,
                "2y": 504,
            }
            display_days = period_days.get(self.period, 252)
            
            # Check cache for extended history
            cache_key = f"stock_history:{self.ticker}"
            full_hist = get_cached(cache_key)
            
            if full_hist is None:
                # Fetch 5 years of data once (covers all display periods + MA calculations)
                full_hist = await asyncio.to_thread(
                    ticker_obj.history, period="5y"
                )
                if not full_hist.empty:
                    set_cached(cache_key, full_hist, DEFAULT_TTL)
            
            if full_hist is None or full_hist.empty:
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
            self.price_change_positive = bool(change_pct >= 0)

            # 52-week high and low for range calculation
            high_52 = stats_hist['High'].max()
            low_52 = stats_hist['Low'].min()
            self.high_52w = f"${high_52:.2f}"
            
            # 52-week range position: where price sits in the range (0-100%)
            if high_52 > low_52:
                range_position = ((current - low_52) / (high_52 - low_52)) * 100
                self.range_52w = f"{range_position:.0f}%"
            else:
                self.range_52w = "N/A"

            # RSI (14-day) with zone classification
            rsi_value = self._calculate_rsi(full_hist['Close'], 14)
            self.rsi_14 = f"{rsi_value:.1f}"
            
            # RSI zones for buy/sell signal context
            if rsi_value < 30:
                self.rsi_zone = "Oversold"  # Potential buy signal
            elif rsi_value < 50:
                self.rsi_zone = "Weak"  # Bearish momentum, caution
            elif rsi_value <= 70:
                self.rsi_zone = "Bullish"  # Healthy uptrend
            else:
                self.rsi_zone = "Overbought"  # Potential sell signal

            # Volatility calculation with dual context (industry standard approach):
            # 1. Current volatility: 30-day HV (standard retail display)
            # 2. Historical baseline: 52-week rolling average for zone comparison
            # 3. SPY benchmark: 30-day HV for market comparison
            
            # Guard against very new stocks with insufficient history
            if len(full_hist) < 30:
                self.volatility = "N/A"
                self.volatility_zone = "--"
                self.volatility_vs_spy = "SPY: N/A"
            else:
                # Current 30-day historical volatility (HV30) - industry standard
                recent_returns = full_hist['Close'].tail(30).pct_change().dropna()
                current_vol = recent_returns.std() * (252 ** 0.5) * 100
                self.volatility = f"{current_vol:.1f}%"
                
                # Calculate stock's 52-week average volatility for baseline comparison
                if len(full_hist) >= 252:  # Need 1 year of data
                    hist_1y = full_hist.tail(252)
                    rolling_vol = hist_1y['Close'].pct_change().rolling(30).std() * (252 ** 0.5) * 100
                    hist_avg_vol = rolling_vol.dropna().mean()
                else:
                    # Fall back to full history average if less than 1 year
                    all_returns = full_hist['Close'].pct_change().dropna()
                    hist_avg_vol = all_returns.std() * (252 ** 0.5) * 100
                
                # Zone based on stock's own historical behavior
                vol_ratio = current_vol / hist_avg_vol if hist_avg_vol > 0 else 1.0
                if vol_ratio < 0.7:
                    self.volatility_zone = "Low"  # Unusually calm for this stock
                elif vol_ratio <= 1.3:
                    self.volatility_zone = "Normal"  # Typical for this stock
                else:
                    self.volatility_zone = "High"  # Elevated for this stock
                
                # Fetch SPY 30-day volatility for market benchmark comparison
                spy_cache_key = "stock_history:SPY"
                spy_hist = get_cached(spy_cache_key)
                if spy_hist is None:
                    spy_ticker = yf.Ticker("SPY")
                    spy_hist = await asyncio.to_thread(spy_ticker.history, period="1y")
                    if spy_hist is not None and not spy_hist.empty:
                        set_cached(spy_cache_key, spy_hist, DEFAULT_TTL)
                
                if spy_hist is not None and not spy_hist.empty:
                    spy_returns = spy_hist['Close'].tail(30).pct_change().dropna()
                    spy_vol = spy_returns.std() * (252 ** 0.5) * 100
                    self.volatility_vs_spy = f"SPY: {spy_vol:.1f}%"
                else:
                    self.volatility_vs_spy = "SPY: N/A"

            # 50-day and 200-day moving average comparisons
            ma_50_val, pct_from_50 = calculate_ma_proximity(full_hist['Close'], 50)
            self.ma_50_pct = f"{pct_from_50:+.1f}%" if pct_from_50 is not None else "N/A"

            ma_200_val, pct_from_200 = calculate_ma_proximity(full_hist['Close'], 200)
            self.ma_200_pct = f"{pct_from_200:+.1f}%" if pct_from_200 is not None else "N/A"

            # MACD
            macd_value = self._calculate_macd(full_hist['Close'])
            self.macd_signal = "Positive" if macd_value > 0 else "Negative"

            # Calculate MA series from full history for charting
            ma_50_series = calculate_ma_series(full_hist['Close'], 50)
            ma_200_series = calculate_ma_series(full_hist['Close'], 200)

            # Slice chart data from full history (no second fetch!)
            chart_hist = full_hist.tail(display_days)
            
            # Filter MA series to match chart date range
            chart_start = chart_hist.index.min()
            ma_50_filtered = ma_50_series[ma_50_series.index >= chart_start] if ma_50_series is not None else None
            ma_200_filtered = ma_200_series[ma_200_series.index >= chart_start] if ma_200_series is not None else None
            
            # Calculate RSI and MACD series for subplot charting
            rsi_series = self._calculate_rsi_series(full_hist['Close'], 14)
            macd_line, signal_line, histogram = self._calculate_macd_series(full_hist['Close'])
            
            # Filter indicator series to match chart date range
            rsi_filtered = rsi_series[rsi_series.index >= chart_start] if rsi_series is not None else None
            macd_line_filtered = macd_line[macd_line.index >= chart_start] if macd_line is not None else None
            signal_line_filtered = signal_line[signal_line.index >= chart_start] if signal_line is not None else None
            histogram_filtered = histogram[histogram.index >= chart_start] if histogram is not None else None
            
            # Use weekly candles for periods > 1 year to reduce clutter
            use_weekly = self.period in ["2y"]
            
            self.price_chart = self._build_candlestick_chart(
                chart_hist, ma_50_filtered, ma_200_filtered, use_weekly,
                rsi_filtered, macd_line_filtered, signal_line_filtered, histogram_filtered
            )

            # Fetch fundamental data from ticker info
            await self._fetch_fundamentals(ticker_obj)

            yield rx.toast.success(f"Loaded {self.ticker}")

        except Exception as e:
            yield rx.toast.error(f"Error: {str(e)}")
        finally:
            self.is_loading = False

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate the Relative Strength Index (current value only)."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 0

    def _calculate_rsi_series(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI as a full series for charting."""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series) -> float:
        """Calculate MACD (12-day EMA minus 26-day EMA) current value."""
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        return macd_line.iloc[-1]

    def _calculate_macd_series(self, prices: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD line, signal line, and histogram as series for charting."""
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def _build_candlestick_chart(
        self, 
        hist: pd.DataFrame, 
        ma_50: pd.Series = None, 
        ma_200: pd.Series = None,
        use_weekly: bool = False,
        rsi_series: pd.Series = None,
        macd_line: pd.Series = None,
        signal_line: pd.Series = None,
        histogram: pd.Series = None,
    ) -> go.Figure:
        """Build a candlestick chart with volume, RSI, and MACD subplots.
        
        Layout: 55% price, 15% volume, 15% RSI, 15% MACD
        RSI includes overbought (70) and oversold (30) reference lines.
        MACD shows line, signal, and histogram with color-coded bars.
        """
        
        # Resample to weekly if requested
        if use_weekly and len(hist) > 0:
            hist = hist.resample('W').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            # Resample indicator series to weekly as well
            if rsi_series is not None:
                rsi_series = rsi_series.resample('W').last().dropna()
            if macd_line is not None:
                macd_line = macd_line.resample('W').last().dropna()
            if signal_line is not None:
                signal_line = signal_line.resample('W').last().dropna()
            if histogram is not None:
                histogram = histogram.resample('W').last().dropna()
        
        # Create 4-row subplot with more space for price chart
        # Increased vertical_spacing for clearer separation between panels
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=[0.55, 0.15, 0.15, 0.15],
        )

        # Row 1: Candlestick chart
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

        # 50-day moving average
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

        # 200-day moving average
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

        # Row 2: Volume bars
        colors = ['rgb(34, 197, 94)' if c >= o else 'rgb(239, 68, 68)' 
                  for c, o in zip(hist['Close'], hist['Open'])]
        fig.add_trace(
            go.Bar(
                x=hist.index,
                y=hist['Volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
                showlegend=False,
            ),
            row=2, col=1
        )

        # Row 3: RSI with overbought/oversold lines
        if rsi_series is not None and not rsi_series.dropna().empty:
            fig.add_trace(
                go.Scatter(
                    x=rsi_series.index,
                    y=rsi_series,
                    name="RSI",
                    line=dict(color='rgb(168, 85, 247)', width=1.5),
                    showlegend=False,
                ),
                row=3, col=1
            )
            # Overbought line (70)
            fig.add_hline(y=70, line_dash="dot", line_color="rgba(239, 68, 68, 0.5)", row=3, col=1)
            # Oversold line (30)
            fig.add_hline(y=30, line_dash="dot", line_color="rgba(34, 197, 94, 0.5)", row=3, col=1)
            # Centerline (50)
            fig.add_hline(y=50, line_dash="dot", line_color="rgba(255, 255, 255, 0.2)", row=3, col=1)

        # Row 4: MACD with histogram
        if macd_line is not None and not macd_line.dropna().empty:
            # MACD line
            fig.add_trace(
                go.Scatter(
                    x=macd_line.index,
                    y=macd_line,
                    name="MACD",
                    line=dict(color='rgb(59, 130, 246)', width=1.5),
                    showlegend=False,
                ),
                row=4, col=1
            )
        
        if signal_line is not None and not signal_line.dropna().empty:
            # Signal line
            fig.add_trace(
                go.Scatter(
                    x=signal_line.index,
                    y=signal_line,
                    name="Signal",
                    line=dict(color='rgb(249, 115, 22)', width=1.5),
                    showlegend=False,
                ),
                row=4, col=1
            )
        
        if histogram is not None and not histogram.dropna().empty:
            # Histogram bars: green when positive, red when negative
            hist_colors = ['rgb(34, 197, 94)' if v >= 0 else 'rgb(239, 68, 68)' 
                          for v in histogram]
            fig.add_trace(
                go.Bar(
                    x=histogram.index,
                    y=histogram,
                    name="Histogram",
                    marker_color=hist_colors,
                    opacity=0.6,
                    showlegend=False,
                ),
                row=4, col=1
            )
            # Zero line for MACD
            fig.add_hline(y=0, line_dash="dot", line_color="rgba(255, 255, 255, 0.3)", row=4, col=1)

        title_suffix = " (Weekly)" if use_weekly else ""
        fig.update_layout(
            title=f"{self.ticker} Price Action{title_suffix}",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=700,
            margin=dict(t=40, l=60, r=20, b=20),
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
        
        # Add y-axis titles for each subplot panel
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Vol", row=2, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)')

        return fig

    async def _fetch_fundamentals(self, ticker_obj):
        """Fetch and process fundamental indicators from ticker info.
        
        Retrieves P/E ratio, revenue growth, profit margin, ROE, and debt-to-equity
        from yfinance info dictionary. Classifies each metric into zones for
        color-coded badge display.
        """
        try:
            info = await asyncio.to_thread(lambda: ticker_obj.info)
            
            # Check if this is an ETF (no fundamental data available)
            quote_type = info.get('quoteType', '')
            if quote_type in ('ETF', 'MUTUALFUND', 'INDEX'):
                self.has_fundamentals = False
                self._reset_fundamentals()
                return
            
            self.has_fundamentals = True
            
            # P/E Ratio with zone classification
            pe = info.get('trailingPE') or info.get('forwardPE')
            if pe is not None:
                if pe < 0:
                    # Negative P/E indicates unprofitable company
                    self.pe_ratio = "Negative"
                    self.pe_zone = "Unprofitable"
                elif pe > 0:
                    self.pe_ratio = f"{pe:.1f}"
                    # Zone based on absolute thresholds (sector-agnostic baseline)
                    if pe < 15:
                        self.pe_zone = "Value"
                    elif pe <= 25:
                        self.pe_zone = "Fair"
                    else:
                        self.pe_zone = "Premium"
                else:
                    self.pe_ratio = "N/A"
                    self.pe_zone = "--"
            else:
                self.pe_ratio = "N/A"
                self.pe_zone = "--"
            
            # Revenue Growth (YoY) with zone classification
            rev_growth = info.get('revenueGrowth')
            if rev_growth is not None:
                self.revenue_growth = f"{rev_growth * 100:+.1f}%"
                if rev_growth > 0.10:
                    self.revenue_growth_zone = "Accelerating"
                elif rev_growth >= 0:
                    self.revenue_growth_zone = "Stable"
                else:
                    self.revenue_growth_zone = "Declining"
            else:
                self.revenue_growth = "N/A"
                self.revenue_growth_zone = "--"
            
            # Profit Margin (Net) with zone classification
            margin = info.get('profitMargins')
            if margin is not None:
                self.profit_margin = f"{margin * 100:.1f}%"
                if margin > 0.15:
                    self.profit_margin_zone = "Strong"
                elif margin >= 0.05:
                    self.profit_margin_zone = "Average"
                else:
                    self.profit_margin_zone = "Weak"
            else:
                self.profit_margin = "N/A"
                self.profit_margin_zone = "--"
            
            # ROE (Return on Equity) with zone classification
            roe_val = info.get('returnOnEquity')
            if roe_val is not None:
                self.roe = f"{roe_val * 100:.1f}%"
                if roe_val > 0.15:
                    self.roe_zone = "Strong"
                elif roe_val >= 0.08:
                    self.roe_zone = "Average"
                else:
                    self.roe_zone = "Weak"
            else:
                self.roe = "N/A"
                self.roe_zone = "--"
            
            # Debt-to-Equity with zone classification
            de_ratio = info.get('debtToEquity')
            if de_ratio is not None:
                # yfinance returns this as a percentage (e.g., 150 = 1.5 ratio)
                de_normalized = de_ratio / 100 if de_ratio > 10 else de_ratio
                self.debt_to_equity = f"{de_normalized:.2f}"
                if de_normalized < 0.5:
                    self.debt_to_equity_zone = "Conservative"
                elif de_normalized <= 1.5:
                    self.debt_to_equity_zone = "Moderate"
                else:
                    self.debt_to_equity_zone = "Aggressive"
            else:
                self.debt_to_equity = "N/A"
                self.debt_to_equity_zone = "--"
                
        except Exception:
            # Gracefully handle any API errors
            self._reset_fundamentals()
    
    def _reset_fundamentals(self):
        """Reset all fundamental indicators to default values."""
        self.pe_ratio = "N/A"
        self.pe_zone = "--"
        self.revenue_growth = "N/A"
        self.revenue_growth_zone = "--"
        self.profit_margin = "N/A"
        self.profit_margin_zone = "--"
        self.roe = "N/A"
        self.roe_zone = "--"
        self.debt_to_equity = "N/A"
        self.debt_to_equity_zone = "--"
