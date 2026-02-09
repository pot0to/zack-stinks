import reflex as rx
import asyncio
from datetime import datetime
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from .base import BaseState
from ..utils.cache import get_cached, set_cached, PORTFOLIO_TTL, MARKET_DATA_TTL
from ..utils.technical import batch_fetch_earnings, batch_fetch_history
from ..styles.constants import PL_GREEN_BASE, PL_GREEN_DEEP, PL_RED_BASE, PL_RED_DEEP, PL_NEUTRAL

SHARES_PER_CONTRACT = 100

# Broad market index funds and sector ETFs that should be displayed separately
# from individual stock positions. These represent diversified exposure rather
# than single-company bets.
INDEX_FUND_SYMBOLS = frozenset({
    # S&P 500 trackers
    "VOO", "SPY", "IVV", "SPLG",
    # Total market
    "VTI", "ITOT", "SPTM",
    # Nasdaq / tech-heavy
    "QQQ", "QQQM", "VGT", "XLK",
    # Growth / Value
    "VUG", "VTV", "IWF", "IWD",
    # Small cap
    "IWM", "VB", "SCHA",
    # Mid cap
    "VO", "IJH", "SCHM",
    # Dow Jones
    "DIA",
    # Sector ETFs
    "SMH", "SOXX",  # Semiconductors
    "XLF", "VFH",   # Financials
    "XLE", "VDE",   # Energy
    "XLV", "VHT",   # Healthcare
    "XLI", "VIS",   # Industrials
    "XLB", "VAW",   # Materials
    "XLU", "VPU",   # Utilities
    "XLP", "VDC",   # Consumer staples
    "XLY", "VCR",   # Consumer discretionary
    "XLRE", "VNQ",  # Real estate
    "XLC",          # Communication services
    # International
    "VEA", "IEFA", "EFA",   # Developed markets
    "VWO", "IEMG", "EEM",   # Emerging markets
    "VXUS",                  # Total international
    # Bonds (if held)
    "BND", "AGG", "TLT", "IEF", "SHY",
    # Thematic / ARK
    "ARKK", "ARKW", "ARKF", "ARKG", "ARKQ",
    # Thematic / Other
    "FINX",  # Global FinTech
    "SPMO",  # S&P 500 Momentum
    "SHLD",  # Global X Defense Tech
    # Leveraged (common ones)
    "TQQQ", "SQQQ", "SPXL", "SPXS", "UPRO",
})


def is_index_fund(symbol: str) -> bool:
    """Check if a symbol is a broad market index fund or sector ETF."""
    return symbol.upper() in INDEX_FUND_SYMBOLS


def _sort_key_for_column(x: dict, sort_col: str):
    """Generic sort key function for table sorting.
    
    Handles None values (sorts to bottom), string columns (case-insensitive),
    and numeric columns.
    """
    val = x.get(sort_col)
    if val is None:
        return (1, 0)  # None items sort last
    if isinstance(val, str):
        return (0, val.lower())
    return (0, val)


def _pl_to_color(pl_pct: float | None) -> str:
    """Convert P/L percentage to RGB color string.
    
    Uses gradient interpolation: green for gains, red for losses, gray for N/A.
    Intensity scales with magnitude (clamped to +/-100%).
    """
    if pl_pct is None:
        return f"rgb({PL_NEUTRAL[0]}, {PL_NEUTRAL[1]}, {PL_NEUTRAL[2]})"
    
    clamped = max(-100, min(100, pl_pct))
    intensity = abs(clamped) / 100
    
    if pl_pct >= 0:
        base, deep = PL_GREEN_BASE, PL_GREEN_DEEP
    else:
        base, deep = PL_RED_BASE, PL_RED_DEEP
    
    r = int(base[0] - (base[0] - deep[0]) * intensity)
    g = int(base[1] - (base[1] - deep[1]) * intensity)
    b = int(base[2] - (base[2] - deep[2]) * intensity)
    
    return f"rgb({r}, {g}, {b})"


def _toggle_sort(current_col: str, current_asc: bool, new_col: str) -> tuple[str, bool]:
    """Generic sort toggle: flip direction if same column, else start ascending."""
    if current_col == new_col:
        return current_col, not current_asc
    return new_col, True


class PortfolioState(BaseState):
    # Map account names to their internal Robinhood account numbers
    account_map: dict[str, str] = {}
    loading_accounts: set[str] = set()
    selected_account: str = ""

    all_stock_holdings: dict[str, list[dict]] = {}
    all_options_holdings: dict[str, list[dict]] = {}
    metric_data: dict[str, dict[str, str | float]] = {}
    
    # Sector exposure data: maps account_number -> {sector: value}
    sector_data: dict[str, dict[str, float]] = {}
    
    # 52-week range data: maps symbol -> range_pct (0-100)
    range_52w_data: dict[str, float] = {}
    
    # Earnings data: maps symbol -> {days_until, earnings_date_str, timing}
    earnings_data: dict[str, dict] = {}
    
    # S&P 500 benchmark data for comparison
    sp500_daily_change_pct: float = 0.0

    cash_balance: str = "$0.00"
    buying_power: str = "$0.00"
    
    # Sorting state for stock holdings table
    # Default: sort by allocation descending
    stock_sort_column: str = "allocation_raw"
    stock_sort_ascending: bool = False
    
    # Sorting state for options holdings table
    # Default: sort by DTE ascending
    options_sort_column: str = "dte_raw"
    options_sort_ascending: bool = True
    
    def set_stock_sort(self, column: str):
        """Toggle sort direction if same column, otherwise set new column ascending."""
        self.stock_sort_column, self.stock_sort_ascending = _toggle_sort(
            self.stock_sort_column, self.stock_sort_ascending, column
        )
    
    def set_options_sort(self, column: str):
        """Toggle sort direction if same column, otherwise set new column ascending."""
        self.options_sort_column, self.options_sort_ascending = _toggle_sort(
            self.options_sort_column, self.options_sort_ascending, column
        )

    @rx.var
    def account_names(self) -> list[str]:
        return list(self.account_map.keys())
    
    def change_tab(self, new_name: str):
        self.selected_account = new_name
        # Update metrics instantly from storage when tab changes
        acc_num = self.account_map.get(new_name)
        if acc_num and acc_num in self.metric_data:
            self.cash_balance = self.metric_data[acc_num]["cash"]
            self.buying_power = self.metric_data[acc_num]["bp"]
    
    @rx.var
    def selected_account_stock_holdings(self) -> list[dict]:
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num: return []
        
        raw_data = self.all_stock_holdings.get(acc_num, [])
        total_equity = sum(float(item.get("raw_equity", 0)) for item in raw_data)
        
        formatted = []
        for item in raw_data:
            val = float(item.get("raw_equity", 0))
            shares = float(item.get("shares", 0))
            price = float(item.get("price", 0))
            avg_buy_price = float(item.get("average_buy_price", 0))
            cost_basis = float(item.get("cost_basis", 0))
            pl = float(item.get("pl", 0))
            cost_basis_reliable = item.get("cost_basis_reliable", True)
            
            # P/L percentage = (current - cost) / cost * 100
            pl_pct = (pl / cost_basis * 100) if cost_basis > 0 and cost_basis_reliable else 0
            allocation = (val / total_equity * 100) if total_equity > 0 else 0
            
            # 52-week range position from cached data
            symbol = item.get("symbol", "???")
            range_52w = self.range_52w_data.get(symbol)
            
            # Earnings data for badge display (only show if within 7 days)
            earnings_info = self.earnings_data.get(symbol, {})
            days_until_earnings = earnings_info.get("days_until")
            has_upcoming_earnings = days_until_earnings is not None and 0 <= days_until_earnings <= 7
            
            # Earnings badge urgency: imminent (0-3 days) or soon (4-7 days)
            earnings_urgency = None
            if has_upcoming_earnings:
                earnings_urgency = "imminent" if days_until_earnings <= 3 else "soon"
            
            # Build earnings tooltip text
            earnings_tooltip = ""
            if has_upcoming_earnings:
                date_str = earnings_info.get("earnings_date_str", "")
                timing = earnings_info.get("timing", "")
                timing_str = f" ({timing})" if timing else ""
                days_str = f"in {days_until_earnings} day{'s' if days_until_earnings != 1 else ''}"
                earnings_tooltip = f"Earnings {date_str}{timing_str} - {days_str}"
            
            formatted.append({
                "symbol": symbol,
                "price_raw": price,
                "price": f"${price:,.2f}",
                "shares_raw": shares,
                "shares": f"{shares:.4f}",
                "value_raw": val,
                "value": f"${val:,.2f}",
                "avg_cost_raw": avg_buy_price if cost_basis_reliable else None,
                "avg_cost": f"${avg_buy_price:,.2f}" if cost_basis_reliable else "N/A",
                "pl_raw": pl if cost_basis_reliable else None,
                "pl": pl,
                "pl_formatted": (f"${abs(pl):,.2f}" if pl >= 0 else f"-${abs(pl):,.2f}") if cost_basis_reliable else "N/A",
                "pl_pct_raw": pl_pct if cost_basis_reliable else None,
                "pl_pct_formatted": (f"{abs(pl_pct):.2f}%" if pl_pct >= 0 else f"-{abs(pl_pct):.2f}%") if cost_basis_reliable else "N/A",
                "pl_positive": pl >= 0,
                "cost_basis_reliable": cost_basis_reliable,
                "allocation": f"{allocation:.2f}%",
                "allocation_raw": allocation,
                "raw_equity": val,
                "range_52w_raw": range_52w,
                "range_52w": f"{range_52w:.0f}%" if range_52w is not None else "N/A",
                # Earnings badge data
                "has_upcoming_earnings": has_upcoming_earnings,
                "earnings_urgency": earnings_urgency,
                "earnings_tooltip": earnings_tooltip,
            })
        
        # Dynamic sorting based on state
        sort_col = self.stock_sort_column
        ascending = self.stock_sort_ascending
        
        formatted.sort(key=lambda x: _sort_key_for_column(x, sort_col), reverse=not ascending)
        return formatted
    
    @rx.var
    def selected_account_option_holdings(self) -> list[dict]:
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num: return []
        
        # 1. Get raw data from storage
        raw_options = self.all_options_holdings.get(acc_num, [])
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        
        # 2. Calculate total ABSOLUTE exposure for weight calculation
        stock_exposure = sum(abs(float(s.get("raw_equity", 0))) for s in raw_stocks)
        option_exposure = sum(abs(float(o.get("raw_equity", 0))) for o in raw_options)
        total_exposure = stock_exposure + option_exposure
        
        formatted = []
        for item in raw_options:
            val = float(item.get("raw_equity", 0))
            contracts = float(item.get("shares", 0))
            is_short = item.get("is_short", False)
            position_type = item.get("position_type", "long")
            
            # Weight = absolute value / total absolute exposure
            weight = (abs(val) / total_exposure * 100) if total_exposure > 0 else 0
            
            # Extract new fields
            strike = float(item.get("strike_price", 0))
            option_type = item.get("option_type", "")
            dte = int(item.get("dte", 0))
            delta = float(item.get("delta", 0))
            underlying = float(item.get("underlying_price", 0))
            cost_basis = float(item.get("cost_basis", 0))
            current_value = float(item.get("current_value", 0))
            pl = float(item.get("pl", 0))
            
            # P/L percentage = pl / cost_basis * 100
            pl_pct = (pl / cost_basis * 100) if cost_basis > 0 else 0
            
            # Determine if option is in-the-money (ITM)
            # Call: ITM when underlying > strike, Put: ITM when underlying < strike
            is_itm = (option_type == "Call" and underlying > strike) or \
                     (option_type == "Put" and underlying < strike)
            
            formatted.append({
                "symbol": item.get("symbol", "???"),
                "strike_raw": strike,
                "strike": f"${strike:,.2f}",
                "option_type": option_type,
                "side": "Short" if is_short else "Long",
                "dte": str(dte),
                "dte_raw": dte,
                "underlying_raw": underlying,
                "underlying": f"${underlying:,.2f}",
                "delta_raw": delta,
                "delta": f"{delta:.3f}",
                "cost_basis_raw": cost_basis,
                "cost_basis": f"${cost_basis:,.2f}",
                "current_value_raw": current_value,
                "current_value": f"${current_value:,.2f}",
                "pl": pl,
                "pl_raw": pl,
                "pl_formatted": f"${abs(pl):,.2f}" if pl >= 0 else f"-${abs(pl):,.2f}",
                "pl_pct_raw": pl_pct,
                "pl_pct_formatted": f"{abs(pl_pct):.2f}%" if pl_pct >= 0 else f"-{abs(pl_pct):.2f}%",
                "pl_positive": pl >= 0,
                "weight_raw": weight,
                "weight": f"{weight:.2f}%",
                "is_short": is_short,
                "is_itm": is_itm,
                "raw_equity": val,
            })
        
        # Dynamic sorting based on state
        sort_col = self.options_sort_column
        ascending = self.options_sort_ascending
        
        formatted.sort(key=lambda x: _sort_key_for_column(x, sort_col), reverse=not ascending)
        return formatted
    
    # Filtered views: separate index funds/ETFs from individual positions
    
    @rx.var
    def selected_account_index_fund_holdings(self) -> list[dict]:
        """Stock holdings filtered to only index funds and sector ETFs."""
        return [h for h in self.selected_account_stock_holdings if is_index_fund(h["symbol"])]
    
    @rx.var
    def selected_account_individual_stock_holdings(self) -> list[dict]:
        """Stock holdings filtered to exclude index funds and sector ETFs."""
        return [h for h in self.selected_account_stock_holdings if not is_index_fund(h["symbol"])]
    
    @rx.var
    def selected_account_index_fund_options(self) -> list[dict]:
        """Options holdings filtered to only index funds and sector ETFs."""
        return [h for h in self.selected_account_option_holdings if is_index_fund(h["symbol"])]
    
    @rx.var
    def selected_account_individual_options(self) -> list[dict]:
        """Options holdings filtered to exclude index funds and sector ETFs."""
        return [h for h in self.selected_account_option_holdings if not is_index_fund(h["symbol"])]
    
    @rx.var
    def selected_account_delta_exposure(self) -> list[dict]:
        """Per-ticker aggregate delta exposure for tickers with open options positions.
        
        Only shows tickers that have options positions, since stock-only positions
        are already visible in the treemap. This keeps the view focused on how
        options modify directional exposure.
        
        Stock delta = shares × 1.0 (stocks have delta of 1 per share)
        Options delta = contracts × 100 × option_delta
        Net delta = stock_delta + options_delta
        
        Returns list sorted by absolute net delta (largest exposure first).
        """
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return []
        
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        raw_options = self.all_options_holdings.get(acc_num, [])
        
        # First, identify which symbols have options positions
        symbols_with_options = set()
        for option in raw_options:
            symbol = option.get("symbol", "")
            if symbol:
                symbols_with_options.add(symbol)
        
        # Only process tickers that have options positions
        if not symbols_with_options:
            return []
        
        # Aggregate by symbol (only for tickers with options)
        delta_by_symbol: dict[str, dict] = {}
        
        # Add stock deltas (delta = 1.0 per share for long positions)
        # Only for symbols that also have options
        for stock in raw_stocks:
            symbol = stock.get("symbol", "")
            if not symbol or symbol not in symbols_with_options:
                continue
            shares = float(stock.get("shares", 0))
            stock_delta = shares  # Delta = 1.0 per share
            
            if symbol not in delta_by_symbol:
                delta_by_symbol[symbol] = {"stock_delta": 0.0, "options_delta": 0.0}
            delta_by_symbol[symbol]["stock_delta"] += stock_delta
        
        # Add options deltas (delta = contracts × 100 × option_delta)
        for option in raw_options:
            symbol = option.get("symbol", "")
            if not symbol:
                continue
            contracts = float(option.get("shares", 0))  # 'shares' field holds contract count
            option_delta = float(option.get("delta", 0))
            is_short = option.get("is_short", False)
            
            # Position delta = contracts × 100 × delta
            # API returns raw option delta (calls positive, puts negative).
            # For short positions, we flip the sign since selling reverses directional exposure.
            position_delta = contracts * SHARES_PER_CONTRACT * option_delta
            if is_short:
                position_delta = -position_delta
            
            if symbol not in delta_by_symbol:
                delta_by_symbol[symbol] = {"stock_delta": 0.0, "options_delta": 0.0}
            delta_by_symbol[symbol]["options_delta"] += position_delta
        
        # Build formatted list
        result = []
        max_abs_delta = 0.0
        
        for symbol, deltas in delta_by_symbol.items():
            stock_d = deltas["stock_delta"]
            options_d = deltas["options_delta"]
            net_d = stock_d + options_d
            max_abs_delta = max(max_abs_delta, abs(net_d))
            
            result.append({
                "symbol": symbol,
                "stock_delta_raw": stock_d,
                "stock_delta": f"{stock_d:+,.0f}" if stock_d != 0 else "0",
                "options_delta_raw": options_d,
                "options_delta": f"{options_d:+,.0f}" if options_d != 0 else "0",
                "net_delta_raw": net_d,
                "net_delta": f"{net_d:+,.0f}",
                "is_bullish": net_d >= 0,
                "is_index_fund": is_index_fund(symbol),
            })
        
        # Add relative bar width (percentage of max)
        for item in result:
            if max_abs_delta > 0:
                bar_pct = (abs(item["net_delta_raw"]) / max_abs_delta) * 100
            else:
                bar_pct = 0
            item["bar_width"] = f"{bar_pct:.0f}%"
        
        # Sort by absolute net delta descending
        result.sort(key=lambda x: abs(x["net_delta_raw"]), reverse=True)
        return result
    
    @rx.var
    def selected_account_individual_delta_exposure(self) -> list[dict]:
        """Delta exposure filtered to individual stocks only."""
        return [d for d in self.selected_account_delta_exposure if not d["is_index_fund"]]
    
    @rx.var
    def selected_account_index_fund_delta_exposure(self) -> list[dict]:
        """Delta exposure filtered to index funds and ETFs only."""
        return [d for d in self.selected_account_delta_exposure if d["is_index_fund"]]
    
    @rx.var
    def selected_account_balance(self) -> str:
        # Sum both stocks and options
        stock_total = sum(item["raw_equity"] for item in self.selected_account_stock_holdings)
        
        # We need a computed var for current options too!
        option_total = sum(float(item.get("raw_equity", 0)) for item in self.selected_account_option_holdings)
        
        total = stock_total + option_total
        return f"${total:,.2f}"

    @rx.var
    def selected_account_change(self) -> str:
        """Daily P/L from Robinhood's portfolio profile (includes extended hours)."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return "+$0.00 (0.00%)"
        
        metrics = self.metric_data.get(acc_num, {})
        equity = metrics.get("equity", 0)
        prev_close = metrics.get("equity_prev_close", 0)
        
        if prev_close <= 0:
            return "+$0.00 (0.00%)"
        
        daily_change = equity - prev_close
        daily_change_pct = (daily_change / prev_close) * 100
        
        if daily_change >= 0:
            return f"+${daily_change:,.2f} (+{daily_change_pct:.2f}%)"
        else:
            return f"-${abs(daily_change):,.2f} ({daily_change_pct:.2f}%)"

    @rx.var
    def selected_account_daily_pct(self) -> float:
        """Portfolio daily change as a percentage (for benchmark comparison)."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return 0.0
        
        metrics = self.metric_data.get(acc_num, {})
        equity = metrics.get("equity", 0)
        prev_close = metrics.get("equity_prev_close", 0)
        
        if prev_close <= 0:
            return 0.0
        
        return float(((equity - prev_close) / prev_close) * 100)

    @rx.var
    def benchmark_comparison(self) -> str:
        """Relative performance vs S&P 500 (portfolio daily % minus S&P daily %)."""
        alpha = self.selected_account_daily_pct - self.sp500_daily_change_pct
        if alpha >= 0:
            return f"+{alpha:.2f}% vs S&P"
        else:
            return f"{alpha:.2f}% vs S&P"

    @rx.var
    def beating_benchmark(self) -> bool:
        """True if portfolio is outperforming S&P 500 today."""
        return bool(self.selected_account_daily_pct >= self.sp500_daily_change_pct)

    @rx.var
    def portfolio_treemap(self) -> go.Figure:
        """Treemap showing all positions (stocks + options) sized by absolute exposure.
        Color indicates P/L: green gradient for gains, red gradient for losses, gray for N/A."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return go.Figure()
        
        # Get raw data for both stocks and options
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        raw_options = self.all_options_holdings.get(acc_num, [])
        
        if not raw_stocks and not raw_options:
            return go.Figure()
        
        # Build combined lists for treemap
        labels = []
        values = []
        colors = []
        hover_texts = []
        
        # Add stocks with P/L-based coloring
        for s in raw_stocks:
            labels.append(s.get("symbol", "???"))
            value = abs(float(s.get("raw_equity", 0)))
            values.append(value)
            
            # Calculate P/L percentage for color
            cost_basis = float(s.get("cost_basis", 0))
            pl = float(s.get("pl", 0))
            cost_basis_reliable = s.get("cost_basis_reliable", True)
            
            if cost_basis_reliable and cost_basis > 0:
                pl_pct = (pl / cost_basis) * 100
                pl_pct_str = f"{pl_pct:+.2f}%"
                pl_dollar_str = f"+${pl:,.2f}" if pl >= 0 else f"-${abs(pl):,.2f}"
            else:
                pl_pct = None
                pl_pct_str = "N/A"
                pl_dollar_str = "N/A"
            
            colors.append(_pl_to_color(pl_pct))
            if self.hide_portfolio_values:
                hover_texts.append("*****<br>P/L: *****")
            else:
                hover_texts.append(f"${value:,.2f}<br>P/L: {pl_dollar_str} ({pl_pct_str})")
        
        # Add options aggregated by ticker symbol
        options_by_symbol: dict[str, dict] = {}
        for o in raw_options:
            symbol = o.get("symbol", "???")
            value = abs(float(o.get("raw_equity", 0)))
            cost_basis = float(o.get("cost_basis", 0))
            pl = float(o.get("pl", 0))
            
            if symbol not in options_by_symbol:
                options_by_symbol[symbol] = {"value": 0, "cost_basis": 0, "pl": 0}
            
            options_by_symbol[symbol]["value"] += value
            options_by_symbol[symbol]["cost_basis"] += cost_basis
            options_by_symbol[symbol]["pl"] += pl
        
        for symbol, data in options_by_symbol.items():
            labels.append(f"{symbol} (Opt)")
            values.append(data["value"])
            
            # Calculate combined P/L percentage
            if data["cost_basis"] > 0:
                pl_pct = (data["pl"] / data["cost_basis"]) * 100
                pl_pct_str = f"{pl_pct:+.2f}%"
                pl_dollar_str = f"+${data['pl']:,.2f}" if data["pl"] >= 0 else f"-${abs(data['pl']):,.2f}"
            else:
                pl_pct = None
                pl_pct_str = "N/A"
                pl_dollar_str = "N/A"
            
            colors.append(_pl_to_color(pl_pct))
            if self.hide_portfolio_values:
                hover_texts.append("*****<br>P/L: *****")
            else:
                hover_texts.append(f"${data['value']:,.2f}<br>P/L: {pl_dollar_str} ({pl_pct_str})")

        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=[""] * len(labels),
            values=values,
            textinfo="label+percent parent",
            marker=dict(colors=colors),
            textfont=dict(color="black"),
            hovertemplate="<b>%{label}</b><br>%{customdata}<extra></extra>",
            customdata=hover_texts,
        ))
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), template="plotly_dark", height=300)
        return fig

    @rx.var
    def sector_exposure_chart(self) -> go.Figure:
        """Donut chart showing sector allocation for individual stocks.
        
        Uses Morningstar-inspired color scheme:
        - Cyclical sectors (Consumer Discretionary, Financials, Real Estate): Orange tones
        - Sensitive sectors (Communication, Energy, Industrials, Technology): Blue tones
        - Defensive sectors (Consumer Staples, Healthcare, Utilities): Green tones
        
        Shows top 6 sectors, groups remainder as "Other" for readability.
        """
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num or acc_num not in self.sector_data:
            return go.Figure()
        
        sector_values = self.sector_data.get(acc_num, {})
        if not sector_values:
            return go.Figure()
        
        # Sort by value descending
        sorted_sectors = sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
        
        # Take top 6, group rest as "Other"
        top_sectors = sorted_sectors[:6]
        other_value = sum(v for _, v in sorted_sectors[6:])
        
        labels = [s[0] for s in top_sectors]
        values = [s[1] for s in top_sectors]
        
        if other_value > 0:
            labels.append("Other")
            values.append(other_value)
        
        # Morningstar-inspired sector color mapping
        sector_colors = {
            # Cyclical - Orange tones
            "Consumer Cyclical": "#EF7622",
            "Consumer Discretionary": "#EF7622",
            "Financial Services": "#F59E0B",
            "Financials": "#F59E0B",
            "Real Estate": "#D97706",
            "Basic Materials": "#B45309",
            "Materials": "#B45309",
            # Sensitive - Blue tones
            "Technology": "#1F55A5",
            "Information Technology": "#1F55A5",
            "Communication Services": "#3B82F6",
            "Energy": "#0EA5E9",
            "Industrials": "#6366F1",
            # Defensive - Green tones
            "Healthcare": "#518428",
            "Consumer Defensive": "#22C55E",
            "Consumer Staples": "#22C55E",
            "Utilities": "#10B981",
            # Fallback
            "Other": "#6B7280",
        }
        
        colors = [sector_colors.get(label, "#6B7280") for label in labels]
        
        # Calculate total for center text
        total = sum(values)
        
        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            marker=dict(colors=colors),
            textinfo="label+percent",
            textposition="outside",
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        ))
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=280,
            margin=dict(t=20, l=20, r=20, b=20),
            showlegend=False,
            annotations=[
                dict(
                    text=f"${total:,.0f}" if not self.hide_portfolio_values else "*****",
                    x=0.5, y=0.5,
                    font_size=16,
                    font_color="white",
                    showarrow=False,
                )
            ],
        )
        
        return fig
    
    async def setup_portfolio_page(self):
        """Setup portfolio page - validate session and fetch data if logged in."""
        await self.validate_existing_session()
        if self.is_logged_in:
            yield PortfolioState.fetch_all_portfolio_data
    
    async def _process_single_account(self, name: str, acc_num: str) -> dict:
        """Process a single account's data. Returns dict with all account data."""
        # Fetch account profile, portfolio profile, stocks, and options in parallel
        account_profile_task = asyncio.to_thread(rs.profiles.load_account_profile, account_number=acc_num)
        portfolio_profile_task = asyncio.to_thread(rs.profiles.load_portfolio_profile, account_number=acc_num)
        stocks_task = asyncio.to_thread(rs.account.get_open_stock_positions, account_number=acc_num)
        options_task = asyncio.to_thread(rs.options.get_open_option_positions, account_number=acc_num)
        
        account_profile, portfolio_profile, stock_positions, option_positions = await asyncio.gather(
            account_profile_task, portfolio_profile_task, stocks_task, options_task
        )
        
        c_str = f"${float(account_profile.get('cash', 0)):,.2f}"
        b_str = f"${float(account_profile.get('buying_power', 0)):,.2f}"
        
        # Extract equity values for daily P/L calculation
        # Use extended hours equity by default for most current value
        # TODO: Consider adding UX toggle for "trading day" vs "extended hours" view
        equity = float(portfolio_profile.get('extended_hours_equity') or portfolio_profile.get('equity') or 0)
        equity_prev_close = float(portfolio_profile.get('adjusted_equity_previous_close') or portfolio_profile.get('equity_previous_close') or 0)
        
        # Process stocks
        acc_stocks = await self._process_stock_positions(stock_positions)
        
        # Process options
        acc_options = await self._process_option_positions(option_positions)
        
        return {
            "name": name,
            "acc_num": acc_num,
            "stocks": acc_stocks,
            "options": acc_options,
            "cash": c_str,
            "buying_power": b_str,
            "equity": equity,
            "equity_prev_close": equity_prev_close,
        }
    
    async def _process_stock_positions(self, stock_positions: list) -> list[dict]:
        """Process stock positions with parallel symbol lookups."""
        if not stock_positions:
            return []
        
        # Fetch all symbols in parallel
        symbol_tasks = [
            asyncio.to_thread(rs.get_symbol_by_url, p['instrument']) 
            for p in stock_positions
        ]
        stock_symbols = await asyncio.gather(*symbol_tasks)
        
        # Fetch all prices in one batch call
        prices = await asyncio.to_thread(rs.stocks.get_latest_price, stock_symbols)
        
        acc_stocks = []
        for i, p in enumerate(stock_positions):
            price = float(prices[i]) if prices[i] else 0.0
            qty = float(p['quantity'])
            
            avg_buy_price_raw = p.get('average_buy_price') or p.get('pending_average_buy_price') or 0
            avg_buy_price = float(avg_buy_price_raw) if avg_buy_price_raw else 0.0
            
            cost_basis_reliable = avg_buy_price > 0 and (price == 0 or avg_buy_price > price * 0.01)
            cost_basis = qty * avg_buy_price
            market_value = qty * price
            pl = market_value - cost_basis if cost_basis_reliable else 0
            
            acc_stocks.append({
                "symbol": stock_symbols[i],
                "shares": qty,
                "price": price,
                "raw_equity": market_value,
                "average_buy_price": avg_buy_price,
                "cost_basis": cost_basis,
                "cost_basis_reliable": cost_basis_reliable,
                "pl": pl,
                "type": "Stock"
            })
        
        return acc_stocks
    
    async def _process_option_positions(self, option_positions: list) -> list[dict]:
        """Process option positions with parallel data fetches."""
        if not option_positions:
            return []
        
        option_ids = [p['option_id'] for p in option_positions]
        
        # Fetch market data and instrument data in parallel for all options
        async def fetch_market_data(oid):
            return await asyncio.to_thread(rs.options.get_option_market_data_by_id, oid)
        
        async def fetch_instrument_data(oid):
            return await asyncio.to_thread(rs.options.get_option_instrument_data_by_id, oid)
        
        market_tasks = [fetch_market_data(oid) for oid in option_ids]
        instrument_tasks = [fetch_instrument_data(oid) for oid in option_ids]
        
        # Get unique underlying symbols
        underlying_symbols = list(set(p["chain_symbol"] for p in option_positions))
        underlying_task = asyncio.to_thread(rs.stocks.get_latest_price, underlying_symbols)
        
        # Run all fetches in parallel
        results = await asyncio.gather(
            asyncio.gather(*market_tasks),
            asyncio.gather(*instrument_tasks),
            underlying_task
        )
        
        market_data = results[0]
        instrument_data = results[1]
        underlying_prices_raw = results[2]
        
        underlying_price_map = {
            sym: float(underlying_prices_raw[i] or 0) 
            for i, sym in enumerate(underlying_symbols)
        }
        
        acc_options = []
        for i, p in enumerate(option_positions):
            m_data = market_data[i] if (market_data and i < len(market_data)) else None
            i_data = instrument_data[i] if (instrument_data and i < len(instrument_data)) else None

            mark = 0.0
            delta = 0.0
            
            if m_data and isinstance(m_data, list) and len(m_data) > 0:
                option_data = m_data[0]
                mark = float(option_data.get('adjusted_mark_price') or option_data.get('mark_price') or 0)
                delta = float(option_data.get('delta') or 0)
            elif m_data and isinstance(m_data, dict):
                mark = float(m_data.get('adjusted_mark_price') or m_data.get('mark_price') or 0)
                delta = float(m_data.get('delta') or 0)
            
            strike_price = float(i_data.get('strike_price', 0)) if i_data else 0
            expiration_date = i_data.get('expiration_date', '') if i_data else ''
            option_type = (i_data.get('type', '') if i_data else '').capitalize()
            
            dte = 0
            if expiration_date:
                try:
                    exp_dt = datetime.strptime(expiration_date, '%Y-%m-%d')
                    dte = (exp_dt - datetime.now()).days
                    if dte < 0:
                        dte = 0
                except ValueError:
                    pass
        
            qty = float(p['quantity'])
            position_type = p.get('type', 'long')
            is_short = position_type == 'short'
            
            avg_price = abs(float(p.get('average_price', 0)))
            cost_basis = avg_price * qty
            current_value = qty * mark * SHARES_PER_CONTRACT
            
            if is_short:
                pl = cost_basis - current_value
            else:
                pl = current_value - cost_basis
            
            signed_value = -current_value if is_short else current_value
            underlying_price = underlying_price_map.get(p["chain_symbol"], 0)
            
            acc_options.append({
                "symbol": p["chain_symbol"],
                "shares": qty,
                "raw_equity": signed_value,
                "position_type": position_type,
                "is_short": is_short,
                "strike_price": strike_price,
                "option_type": option_type,
                "expiration_date": expiration_date,
                "dte": dte,
                "delta": delta,
                "underlying_price": underlying_price,
                "cost_basis": cost_basis,
                "current_value": current_value,
                "pl": pl,
            })
        
        return acc_options

    async def _fetch_sp500_daily_change(self) -> float:
        """Fetch S&P 500 daily percentage change for benchmark comparison."""
        cache_key = "sp500_daily_pct"
        cached = get_cached(cache_key)
        if cached is not None:
            return float(cached)
        
        try:
            ticker = yf.Ticker("^GSPC")
            df = await asyncio.to_thread(lambda: ticker.history(period="5d"))
            
            if df is None or df.empty or len(df) < 2:
                return 0.0
            
            current = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            pct_change = float(((current - prev) / prev) * 100)
            
            set_cached(cache_key, pct_change, MARKET_DATA_TTL)
            return pct_change
        except Exception as e:
            print(f"Error fetching S&P 500 data: {e}")
            return 0.0

    async def _fetch_sector_and_range_data(self, all_stocks: dict) -> tuple[dict, dict, dict]:
        """Fetch sector, 52-week range, and earnings data for all stock holdings.
        
        Returns (sector_data, range_52w_data, earnings_data) where:
        - sector_data: {account_num: {sector: total_value}}
        - range_52w_data: {symbol: range_pct}
        - earnings_data: {symbol: {days_until, earnings_date_str, timing}}
        
        Sector data is only fetched for individual stocks (excludes index funds/ETFs).
        52-week range data is fetched for ALL symbols (stocks and ETFs).
        Earnings data is fetched for individual stocks only.
        """
        # Collect unique symbols across all accounts
        all_symbols = set()
        individual_symbols = set()
        etf_symbols = set()
        for acc_stocks in all_stocks.values():
            for stock in acc_stocks:
                symbol = stock.get("symbol", "")
                if symbol:
                    all_symbols.add(symbol)
                    if is_index_fund(symbol):
                        etf_symbols.add(symbol)
                    else:
                        individual_symbols.add(symbol)
        
        if not all_symbols:
            return {}, {}, {}
        
        # Check cache
        cache_key = f"sector_range_earnings_data:{','.join(sorted(all_symbols))}"
        cached = get_cached(cache_key)
        if cached:
            return cached["sector_data"], cached["range_data"], cached.get("earnings_data", {})
        
        # Fetch ticker info for individual symbols in parallel (for sector/range)
        symbol_info = {}
        
        async def fetch_info(symbol: str):
            try:
                ticker = yf.Ticker(symbol)
                info = await asyncio.to_thread(lambda: ticker.info)
                return symbol, info
            except Exception as e:
                print(f"Error fetching info for {symbol}: {e}")
                return symbol, {}
        
        tasks = [fetch_info(s) for s in individual_symbols]
        results = await asyncio.gather(*tasks)
        
        for symbol, info in results:
            symbol_info[symbol] = info
        
        # Build range_52w_data from fetched info (individual stocks)
        range_52w_data = {}
        symbols_missing_range = []
        
        for symbol, info in symbol_info.items():
            current = info.get("currentPrice") or info.get("regularMarketPrice")
            high_52 = info.get("fiftyTwoWeekHigh")
            low_52 = info.get("fiftyTwoWeekLow")
            
            if current and high_52 and low_52 and high_52 > low_52:
                range_pct = ((current - low_52) / (high_52 - low_52)) * 100
                range_52w_data[symbol] = float(range_pct)
            else:
                # Track symbols missing 52-week data for fallback calculation
                symbols_missing_range.append(symbol)
        
        # Fallback: calculate 52-week range from historical data for symbols
        # where ticker.info didn't provide it (common for ETFs and some stocks)
        # Also include all ETFs since they rarely have reliable ticker.info data
        symbols_needing_history = list(set(symbols_missing_range) | etf_symbols)
        
        if symbols_needing_history:
            history_data = await asyncio.to_thread(
                batch_fetch_history, symbols_needing_history, "1y"
            )
            for symbol in symbols_needing_history:
                df = history_data.get(symbol)
                if df is not None and not df.empty and "High" in df.columns and "Low" in df.columns:
                    high_52 = df["High"].max()
                    low_52 = df["Low"].min()
                    current = df["Close"].iloc[-1] if "Close" in df.columns else None
                    
                    if current and high_52 and low_52 and high_52 > low_52:
                        range_pct = ((current - low_52) / (high_52 - low_52)) * 100
                        range_52w_data[symbol] = float(range_pct)
        
        # Build sector_data per account
        sector_data = {}
        for acc_num, acc_stocks in all_stocks.items():
            acc_sectors = {}
            for stock in acc_stocks:
                symbol = stock.get("symbol", "")
                if not symbol or is_index_fund(symbol):
                    continue
                
                info = symbol_info.get(symbol, {})
                sector = info.get("sector", "Unknown")
                value = float(stock.get("raw_equity", 0))
                
                if sector not in acc_sectors:
                    acc_sectors[sector] = 0
                acc_sectors[sector] += value
            
            sector_data[acc_num] = acc_sectors
        
        # Fetch earnings data for individual stocks (not index funds)
        earnings_data = {}
        if individual_symbols:
            earnings_data = await asyncio.to_thread(
                batch_fetch_earnings, list(individual_symbols)
            )
        
        # Cache results
        set_cached(cache_key, {
            "sector_data": sector_data, 
            "range_data": range_52w_data,
            "earnings_data": earnings_data,
        }, MARKET_DATA_TTL)
        
        return sector_data, range_52w_data, earnings_data

    @rx.event(background=True)
    async def fetch_all_portfolio_data(self):
        async with self:
            self.is_loading = True

        try:
            # Check cache first
            cached_data = get_cached("portfolio_data")
            if cached_data:
                async with self:
                    self.account_map = cached_data["account_map"]
                    self.all_stock_holdings = cached_data["all_stock_holdings"]
                    self.all_options_holdings = cached_data["all_options_holdings"]
                    self.metric_data = cached_data["metric_data"]
                    self.sp500_daily_change_pct = cached_data.get("sp500_daily_pct", 0.0)
                    self.sector_data = cached_data.get("sector_data", {})
                    self.range_52w_data = cached_data.get("range_52w_data", {})
                    self.earnings_data = cached_data.get("earnings_data", {})
                    if not self.selected_account and self.account_names:
                        self.selected_account = self.account_names[0]
                    if self.selected_account:
                        acc_num = self.account_map.get(self.selected_account)
                        if acc_num and acc_num in self.metric_data:
                            self.cash_balance = self.metric_data[acc_num]["cash"]
                            self.buying_power = self.metric_data[acc_num]["bp"]
                    self.is_loading = False
                return rx.toast.success("Portfolio loaded from cache")

            # Fetch all accounts
            url = "https://api.robinhood.com/accounts/?default_to_all_accounts=true&include_managed=true&include_multiple_individual=true"
            res = await asyncio.to_thread(rs.request_get, url, "regular")
            
            if res is None:
                # Session expired - reset login state, UI will show login placeholder
                async with self:
                    self.is_logged_in = False
                    self.account_name = "User"
                    self.is_loading = False
                return rx.toast.info("Session expired. Please sign in to view portfolio.")
            
            temp_map = {}
            for acc in res.get('results', []):
                if acc["state"] == "active":
                    nickname = (acc['nickname'] or acc['brokerage_account_type'].replace('_', ' ')).title()
                    acc_num = acc['account_number']
                    temp_map[f"{nickname}*{acc_num[-4:]}"] = acc_num

            async with self:
                self.account_map = temp_map
                if not self.selected_account and self.account_names:
                    self.selected_account = self.account_names[0]
                current_accounts = list(self.account_map.items())
                for name, _ in current_accounts:
                    self.loading_accounts.add(name)

            # Process ALL accounts in parallel, also fetch S&P 500 for benchmark
            account_tasks = [
                self._process_single_account(name, acc_num) 
                for name, acc_num in current_accounts
            ]
            sp500_task = self._fetch_sp500_daily_change()
            
            all_results = await asyncio.gather(
                asyncio.gather(*account_tasks, return_exceptions=True),
                sp500_task
            )
            account_results = all_results[0]
            sp500_pct = all_results[1]

            # Aggregate results
            all_stocks = {}
            all_options = {}
            all_metrics = {}
            
            for result in account_results:
                if isinstance(result, Exception):
                    print(f"Error processing account: {result}")
                    continue
                    
                acc_num = result["acc_num"]
                all_stocks[acc_num] = result["stocks"]
                all_options[acc_num] = result["options"]
                all_metrics[acc_num] = {
                    "cash": result["cash"],
                    "bp": result["buying_power"],
                    "equity": result["equity"],
                    "equity_prev_close": result["equity_prev_close"],
                }

            # Fetch sector and 52-week range data for individual stocks
            sector_data, range_52w_data, earnings_data = await self._fetch_sector_and_range_data(all_stocks)

            # Update state once with all data
            async with self:
                self.all_stock_holdings = all_stocks
                self.all_options_holdings = all_options
                self.metric_data = all_metrics
                self.sp500_daily_change_pct = sp500_pct
                self.sector_data = sector_data
                self.range_52w_data = range_52w_data
                self.earnings_data = earnings_data
                
                if self.selected_account:
                    acc_num = self.account_map.get(self.selected_account)
                    if acc_num and acc_num in self.metric_data:
                        self.cash_balance = self.metric_data[acc_num]["cash"]
                        self.buying_power = self.metric_data[acc_num]["bp"]
                
                self.loading_accounts = set()

            # Cache the results
            set_cached("portfolio_data", {
                "account_map": temp_map,
                "all_stock_holdings": all_stocks,
                "all_options_holdings": all_options,
                "metric_data": all_metrics,
                "sp500_daily_pct": sp500_pct,
                "sector_data": sector_data,
                "range_52w_data": range_52w_data,
                "earnings_data": earnings_data,
            }, PORTFOLIO_TTL)

            return rx.toast.success("Portfolio Updated")
        except Exception as e:
            error_str = str(e)
            # Check for 401 Unauthorized errors
            if "401" in error_str or "Unauthorized" in error_str:
                async with self:
                    self.is_logged_in = False
                    self.account_name = "User"
                    self.is_loading = False
                return rx.toast.info("Session expired. Please sign in to view portfolio.")
            return rx.toast.error(f"Sync failed: {error_str}")
        finally:
            async with self:
                self.is_loading = False