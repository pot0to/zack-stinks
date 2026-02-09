import reflex as rx
import asyncio
from datetime import datetime
from enum import Enum
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from .base import BaseState
from ..utils.cache import get_cached, set_cached, PORTFOLIO_TTL, MARKET_DATA_TTL
from ..utils.technical import batch_fetch_earnings, batch_fetch_earnings_async, batch_fetch_history
from ..utils.symbols import is_index_fund, INDEX_FUND_SYMBOLS
from ..styles.constants import PL_GREEN_BASE, PL_GREEN_DEEP, PL_RED_BASE, PL_RED_DEEP, PL_NEUTRAL

SHARES_PER_CONTRACT = 100


class PortfolioLoadingPhase(str, Enum):
    """Loading phases for portfolio data fetch and analysis.
    
    Single source of truth for loading state, replacing the previous
    is_loading/is_analyzing/is_portfolio_busy boolean flags.
    
    Phases:
        IDLE: No loading in progress, UI fully interactive
        FETCHING: Phase 1 - Core data fetch (holdings, prices, P/L)
        ANALYZING: Phase 2 - Background analysis (sector, 52-week range, earnings)
        RETRYING: Background retry for failed Yahoo Finance fetches
    """
    IDLE = "idle"
    FETCHING = "fetching"
    ANALYZING = "analyzing"
    RETRYING = "retrying"


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
    
    # Loading phase enum - single source of truth for loading state
    # Replaces the previous is_loading/is_analyzing boolean flags
    loading_phase: PortfolioLoadingPhase = PortfolioLoadingPhase.IDLE
    
    # Combined loading state flag. Kept in sync with loading_phase via the
    # _set_loading_phase() helper method. True during any non-IDLE phase.
    # Note: UI blocking now uses is_fetching computed var instead, allowing
    # user interaction during ANALYZING phase while background analysis runs.
    is_portfolio_busy: bool = False
    
    # Retry tracking for Yahoo Finance failures (eventual consistency)
    # Reset when a fresh analysis starts; incremented on each retry attempt
    _retry_count: int = 0
    MAX_RETRIES: int = 5  # Stop retrying after this many attempts
    
    # Pre-computed formatted holdings per account (avoids O(n) recalculation on tab switch)
    # These are populated during data fetch/analysis and keyed by:
    # "{acc_num}:{sort_col}:{sort_asc}" for holdings (sort-dependent)
    # "{acc_num}" for delta exposure (not sortable)
    _cached_stock_holdings: dict[str, list[dict]] = {}
    _cached_option_holdings: dict[str, list[dict]] = {}
    _cached_delta_exposure: dict[str, list[dict]] = {}
    
    # Pre-built Plotly figures per account (expensive to generate)
    _cached_treemaps: dict[str, go.Figure] = {}
    _cached_sector_charts: dict[str, go.Figure] = {}
    
    # Sorting state for stock holdings table
    # Default: sort by allocation descending
    stock_sort_column: str = "allocation_raw"
    stock_sort_ascending: bool = False
    
    # Sorting state for options holdings table
    # Default: sort by DTE ascending
    options_sort_column: str = "dte_raw"
    options_sort_ascending: bool = True
    
    def set_stock_sort(self, column: str):
        """Toggle sort direction if same column, otherwise set new column ascending.
        
        Invalidates cached stock holdings to trigger re-sort on next access.
        """
        self.stock_sort_column, self.stock_sort_ascending = _toggle_sort(
            self.stock_sort_column, self.stock_sort_ascending, column
        )
        # Invalidate cache to force re-sort
        self._cached_stock_holdings = {}
    
    def set_options_sort(self, column: str):
        """Toggle sort direction if same column, otherwise set new column ascending.
        
        Invalidates cached option holdings to trigger re-sort on next access.
        """
        self.options_sort_column, self.options_sort_ascending = _toggle_sort(
            self.options_sort_column, self.options_sort_ascending, column
        )
        # Invalidate cache to force re-sort
        self._cached_option_holdings = {}
    
    def _set_loading_phase(self, phase: PortfolioLoadingPhase):
        """Set loading phase and sync is_portfolio_busy flag.
        
        Centralizes loading state transitions to ensure is_portfolio_busy
        stays in sync with loading_phase. This helper should be called
        instead of setting loading_phase directly.
        """
        self.loading_phase = phase
        self.is_portfolio_busy = (phase != PortfolioLoadingPhase.IDLE)
    
    @rx.var
    def is_fetching(self) -> bool:
        """True during Phase 1 (core data fetch)."""
        return self.loading_phase == PortfolioLoadingPhase.FETCHING
    
    @rx.var
    def is_analyzing(self) -> bool:
        """True during Phase 2 (background analysis or retry)."""
        return self.loading_phase in (
            PortfolioLoadingPhase.ANALYZING,
            PortfolioLoadingPhase.RETRYING
        )
    
    def toggle_hide_values(self):
        """Toggle privacy mode and invalidate caches that depend on it.
        
        Treemaps and sector charts include privacy state in their cache keys,
        so they must be invalidated when privacy mode changes.
        """
        super().toggle_hide_values()
        # Invalidate caches that depend on hide_portfolio_values
        self._cached_treemaps = {}
        self._cached_sector_charts = {}
    
    def _build_stock_cache_key(self, acc_num: str) -> str:
        """Build cache key for stock holdings including sort state."""
        return f"{acc_num}:{self.stock_sort_column}:{self.stock_sort_ascending}"
    
    def _build_option_cache_key(self, acc_num: str) -> str:
        """Build cache key for option holdings including sort state."""
        return f"{acc_num}:{self.options_sort_column}:{self.options_sort_ascending}"
    
    def _format_stock_holdings_for_account(self, acc_num: str) -> list[dict]:
        """Format stock holdings for a single account. Used for cache population."""
        raw_data = self.all_stock_holdings.get(acc_num, [])
        if not raw_data:
            return []
        
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
            
            pl_pct = (pl / cost_basis * 100) if cost_basis > 0 and cost_basis_reliable else 0
            allocation = (val / total_equity * 100) if total_equity > 0 else 0
            
            symbol = item.get("symbol", "???")
            range_52w = self.range_52w_data.get(symbol)
            
            earnings_info = self.earnings_data.get(symbol, {})
            days_until_earnings = earnings_info.get("days_until")
            has_upcoming_earnings = days_until_earnings is not None and 0 <= days_until_earnings <= 7
            
            earnings_urgency = None
            if has_upcoming_earnings:
                earnings_urgency = "imminent" if days_until_earnings <= 3 else "soon"
            
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
                "has_upcoming_earnings": has_upcoming_earnings,
                "earnings_urgency": earnings_urgency,
                "earnings_tooltip": earnings_tooltip,
            })
        
        sort_col = self.stock_sort_column
        ascending = self.stock_sort_ascending
        formatted.sort(key=lambda x: _sort_key_for_column(x, sort_col), reverse=not ascending)
        return formatted
    
    def _format_option_holdings_for_account(self, acc_num: str) -> list[dict]:
        """Format option holdings for a single account. Used for cache population."""
        raw_options = self.all_options_holdings.get(acc_num, [])
        if not raw_options:
            return []
        
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        stock_exposure = sum(abs(float(s.get("raw_equity", 0))) for s in raw_stocks)
        option_exposure = sum(abs(float(o.get("raw_equity", 0))) for o in raw_options)
        total_exposure = stock_exposure + option_exposure
        
        formatted = []
        for item in raw_options:
            val = float(item.get("raw_equity", 0))
            is_short = item.get("is_short", False)
            
            weight = (abs(val) / total_exposure * 100) if total_exposure > 0 else 0
            
            strike = float(item.get("strike_price", 0))
            option_type = item.get("option_type", "")
            dte = int(item.get("dte", 0))
            delta = float(item.get("delta", 0))
            underlying = float(item.get("underlying_price", 0))
            cost_basis = float(item.get("cost_basis", 0))
            current_value = float(item.get("current_value", 0))
            pl = float(item.get("pl", 0))
            
            pl_pct = (pl / cost_basis * 100) if cost_basis > 0 else 0
            
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
        
        sort_col = self.options_sort_column
        ascending = self.options_sort_ascending
        formatted.sort(key=lambda x: _sort_key_for_column(x, sort_col), reverse=not ascending)
        return formatted
    
    def _compute_delta_exposure_for_account(self, acc_num: str) -> list[dict]:
        """Compute delta exposure for a single account. Used for cache population."""
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        raw_options = self.all_options_holdings.get(acc_num, [])
        
        symbols_with_options = set()
        for option in raw_options:
            symbol = option.get("symbol", "")
            if symbol:
                symbols_with_options.add(symbol)
        
        if not symbols_with_options:
            return []
        
        delta_by_symbol: dict[str, dict] = {}
        
        for stock in raw_stocks:
            symbol = stock.get("symbol", "")
            if not symbol or symbol not in symbols_with_options:
                continue
            shares = float(stock.get("shares", 0))
            
            if symbol not in delta_by_symbol:
                delta_by_symbol[symbol] = {"stock_delta": 0.0, "options_delta": 0.0}
            delta_by_symbol[symbol]["stock_delta"] += shares
        
        for option in raw_options:
            symbol = option.get("symbol", "")
            if not symbol:
                continue
            contracts = float(option.get("shares", 0))
            option_delta = float(option.get("delta", 0))
            is_short = option.get("is_short", False)
            
            position_delta = contracts * SHARES_PER_CONTRACT * option_delta
            if is_short:
                position_delta = -position_delta
            
            if symbol not in delta_by_symbol:
                delta_by_symbol[symbol] = {"stock_delta": 0.0, "options_delta": 0.0}
            delta_by_symbol[symbol]["options_delta"] += position_delta
        
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
        
        for item in result:
            if max_abs_delta > 0:
                bar_pct = (abs(item["net_delta_raw"]) / max_abs_delta) * 100
            else:
                bar_pct = 0
            item["bar_width"] = f"{bar_pct:.0f}%"
        
        result.sort(key=lambda x: abs(x["net_delta_raw"]), reverse=True)
        return result
    
    def _build_treemap_cache_key(self, acc_num: str) -> str:
        """Build cache key for treemap including privacy state."""
        return f"{acc_num}:{self.hide_portfolio_values}"
    
    def _build_treemap_for_account(self, acc_num: str) -> go.Figure:
        """Build treemap figure for a single account. Used for cache population."""
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        raw_options = self.all_options_holdings.get(acc_num, [])
        
        if not raw_stocks and not raw_options:
            return go.Figure()
        
        labels = []
        values = []
        colors = []
        hover_texts = []
        
        for s in raw_stocks:
            labels.append(s.get("symbol", "???"))
            value = abs(float(s.get("raw_equity", 0)))
            values.append(value)
            
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
    
    def _build_sector_chart_for_account(self, acc_num: str) -> go.Figure:
        """Build sector exposure chart for a single account. Used for cache population."""
        if acc_num not in self.sector_data:
            return go.Figure()
        
        sector_values = self.sector_data.get(acc_num, {})
        if not sector_values:
            return go.Figure()
        
        sorted_sectors = sorted(sector_values.items(), key=lambda x: x[1], reverse=True)
        
        top_sectors = sorted_sectors[:6]
        other_value = sum(v for _, v in sorted_sectors[6:])
        
        labels = [s[0] for s in top_sectors]
        values = [s[1] for s in top_sectors]
        
        if other_value > 0:
            labels.append("Other")
            values.append(other_value)
        
        sector_colors = {
            "Consumer Cyclical": "#EF7622",
            "Consumer Discretionary": "#EF7622",
            "Financial Services": "#F59E0B",
            "Financials": "#F59E0B",
            "Real Estate": "#D97706",
            "Basic Materials": "#B45309",
            "Materials": "#B45309",
            "Technology": "#1F55A5",
            "Information Technology": "#1F55A5",
            "Communication Services": "#3B82F6",
            "Energy": "#0EA5E9",
            "Industrials": "#6366F1",
            "Healthcare": "#518428",
            "Consumer Defensive": "#22C55E",
            "Consumer Staples": "#22C55E",
            "Utilities": "#10B981",
            "Other": "#6B7280",
        }
        
        colors = [sector_colors.get(label, "#6B7280") for label in labels]
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

    @rx.var
    def account_names(self) -> list[str]:
        return list(self.account_map.keys())
    
    @rx.var
    def cash_balance(self) -> str:
        """Cash balance for the selected account, derived from metric_data.
        
        Computed var allows tab switching without state lock contention.
        """
        acc_num = self.account_map.get(self.selected_account)
        if acc_num and acc_num in self.metric_data:
            return str(self.metric_data[acc_num].get("cash", "$0.00"))
        return "$0.00"
    
    @rx.var
    def buying_power(self) -> str:
        """Buying power for the selected account, derived from metric_data.
        
        Computed var allows tab switching without state lock contention.
        """
        acc_num = self.account_map.get(self.selected_account)
        if acc_num and acc_num in self.metric_data:
            return str(self.metric_data[acc_num].get("bp", "$0.00"))
        return "$0.00"
    
    def change_tab(self, new_name: str):
        """Switch to a different account tab.
        
        Only sets selected_account; cash_balance and buying_power are
        computed vars that derive their values automatically. This keeps
        the event handler fast and avoids state lock contention during
        background data loading.
        
        Only blocks during FETCHING phase when core data isn't available.
        During ANALYZING phase, tab switching is allowed since holdings
        data is already loaded and cached.
        """
        if self.loading_phase == PortfolioLoadingPhase.FETCHING:
            return
        self.selected_account = new_name
    
    @rx.var
    def selected_account_stock_holdings(self) -> list[dict]:
        """Stock holdings for selected account. Uses cache for instant tab switching."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return []
        
        cache_key = self._build_stock_cache_key(acc_num)
        if cache_key in self._cached_stock_holdings:
            return self._cached_stock_holdings[cache_key]
        
        # Cache miss - compute and store
        formatted = self._format_stock_holdings_for_account(acc_num)
        self._cached_stock_holdings[cache_key] = formatted
        return formatted
    
    @rx.var
    def selected_account_option_holdings(self) -> list[dict]:
        """Option holdings for selected account. Uses cache for instant tab switching."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return []
        
        cache_key = self._build_option_cache_key(acc_num)
        if cache_key in self._cached_option_holdings:
            return self._cached_option_holdings[cache_key]
        
        # Cache miss - compute and store
        formatted = self._format_option_holdings_for_account(acc_num)
        self._cached_option_holdings[cache_key] = formatted
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
        """Delta exposure for selected account. Uses cache for instant tab switching."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return []
        
        if acc_num in self._cached_delta_exposure:
            return self._cached_delta_exposure[acc_num]
        
        # Cache miss - compute and store
        result = self._compute_delta_exposure_for_account(acc_num)
        self._cached_delta_exposure[acc_num] = result
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
        """Treemap for selected account. Uses cache for instant tab switching."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return go.Figure()
        
        cache_key = self._build_treemap_cache_key(acc_num)
        if cache_key in self._cached_treemaps:
            return self._cached_treemaps[cache_key]
        
        # Cache miss - compute and store
        fig = self._build_treemap_for_account(acc_num)
        self._cached_treemaps[cache_key] = fig
        return fig

    @rx.var
    def sector_exposure_chart(self) -> go.Figure:
        """Sector chart for selected account. Uses cache for instant tab switching."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num or acc_num not in self.sector_data:
            return go.Figure()
        
        # Cache key includes privacy state since it affects center text
        cache_key = f"{acc_num}:{self.hide_portfolio_values}"
        if cache_key in self._cached_sector_charts:
            return self._cached_sector_charts[cache_key]
        
        # Cache miss - compute and store
        fig = self._build_sector_chart_for_account(acc_num)
        self._cached_sector_charts[cache_key] = fig
        return fig
    
    @rx.event(background=True)
    async def setup_portfolio_page(self):
        """Setup portfolio page - validate session and fetch data if logged in.
        
        This is a background event handler to avoid blocking UI interactions
        (like tab switching) while validating the session. The state lock is
        only held briefly when updating state variables.
        """
        # Validate session with brief lock acquisitions
        is_valid = False
        try:
            user_profile = await asyncio.to_thread(rs.account.load_user_profile)
            if user_profile and user_profile.get("first_name"):
                async with self:
                    self.account_name = user_profile.get("first_name", "User")
                    self.is_logged_in = True
                is_valid = True
        except Exception:
            pass
        
        if not is_valid:
            async with self:
                self.is_logged_in = False
                self.account_name = "User"
            return
        
        # Trigger data fetch
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

    async def _fetch_sector_and_range_data(self, all_stocks: dict) -> tuple[dict, dict, dict, bool]:
        """Fetch sector, 52-week range, and earnings data for all stock holdings.
        
        Returns (sector_data, range_52w_data, earnings_data, has_failures) where:
        - sector_data: {account_num: {sector: total_value}}
        - range_52w_data: {symbol: range_pct}
        - earnings_data: {symbol: {days_until, earnings_date_str, timing}}
        
        Sector data is only fetched for individual stocks (excludes index funds/ETFs).
        52-week range data is fetched for ALL symbols (stocks and ETFs).
        Earnings data is fetched for individual stocks only.
        
        Performance: Earnings fetch runs in parallel with info/history fetches
        since it has no dependencies on their results.
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
            return {}, {}, {}, False
        
        # Check cache
        cache_key = f"sector_range_earnings_data:{','.join(sorted(all_symbols))}"
        cached = get_cached(cache_key)
        if cached:
            # Return cached data with its incomplete status
            return cached["sector_data"], cached["range_data"], cached.get("earnings_data", {}), cached.get("incomplete", False)
        
        # Start earnings fetch immediately (no dependency on info/history)
        # This runs in parallel with the info fetch below
        earnings_task = None
        if individual_symbols:
            earnings_task = batch_fetch_earnings_async(list(individual_symbols))
        
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
        
        info_tasks = [fetch_info(s) for s in individual_symbols]
        info_results = await asyncio.gather(*info_tasks)
        
        for symbol, info in info_results:
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
        
        # Run history fetch (if needed) in parallel with waiting for earnings
        history_data = {}
        if symbols_needing_history and earnings_task:
            history_task = asyncio.to_thread(
                batch_fetch_history, symbols_needing_history, "1y"
            )
            history_data, earnings_data = await asyncio.gather(history_task, earnings_task)
        elif symbols_needing_history:
            history_data = await asyncio.to_thread(
                batch_fetch_history, symbols_needing_history, "1y"
            )
            earnings_data = {}
        elif earnings_task:
            earnings_data = await earnings_task
        else:
            earnings_data = {}
        
        # Process history data for 52-week range
        for symbol in symbols_needing_history:
            df = history_data.get(symbol)
            if df is not None and not df.empty and "High" in df.columns and "Low" in df.columns:
                high_52 = df["High"].max()
                low_52 = df["Low"].min()
                current = df["Close"].iloc[-1] if "Close" in df.columns else None
                
                if current and high_52 and low_52 and high_52 > low_52:
                    range_pct = ((current - low_52) / (high_52 - low_52)) * 100
                    range_52w_data[symbol] = float(range_pct)
        
        # Track symbols that failed to get 52-week range data
        failed_range_symbols = all_symbols - set(range_52w_data.keys())
        
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
        
        # Determine if data is complete or has failures
        has_failures = len(failed_range_symbols) > 0
        
        # Cache results with appropriate TTL based on completeness
        # Incomplete data gets a shorter TTL to allow faster retry
        cache_ttl = 30 if has_failures else MARKET_DATA_TTL
        set_cached(cache_key, {
            "sector_data": sector_data, 
            "range_data": range_52w_data,
            "earnings_data": earnings_data,
            "incomplete": has_failures,
            "failed_symbols": list(failed_range_symbols) if has_failures else [],
        }, cache_ttl)
        
        return sector_data, range_52w_data, earnings_data, has_failures

    @rx.event(background=True)
    async def fetch_all_portfolio_data(self):
        """Fetch core portfolio data (holdings, prices, P/L).
        
        This method fetches the essential portfolio data and updates the UI
        immediately. The analysis phase (sector, 52-week range, earnings) runs
        as a separate background task to keep the UI responsive.
        
        Guards against concurrent fetches: if already loading, returns early.
        Sets cache immediately after core data fetch so subsequent page visits
        can use cached data even if analysis hasn't completed yet.
        """
        # Guard against concurrent fetches
        async with self:
            if self.loading_phase != PortfolioLoadingPhase.IDLE:
                return  # Already fetching, don't start another
            self._set_loading_phase(PortfolioLoadingPhase.FETCHING)
            self.is_portfolio_loading = True  # Global flag for loading indicator on any page

        try:
            # Check cache first
            cached_data = get_cached("portfolio_data")
            if cached_data:
                # Restore from cache using multiple brief lock acquisitions
                # This allows tab switch events to interleave, keeping UI responsive
                
                # Get account names outside the lock (avoid computed var access inside lock)
                account_names = list(cached_data["account_map"].keys())
                
                async with self:
                    self.account_map = cached_data["account_map"]
                
                async with self:
                    self.all_stock_holdings = cached_data["all_stock_holdings"]
                    self.all_options_holdings = cached_data["all_options_holdings"]
                
                async with self:
                    self.metric_data = cached_data["metric_data"]
                    self.sp500_daily_change_pct = cached_data.get("sp500_daily_pct", 0.0)
                
                async with self:
                    self.sector_data = cached_data.get("sector_data", {})
                    self.range_52w_data = cached_data.get("range_52w_data", {})
                    self.earnings_data = cached_data.get("earnings_data", {})
                
                async with self:
                    # Clear stale caches (computed vars will lazily rebuild on access)
                    self._cached_stock_holdings = {}
                    self._cached_option_holdings = {}
                    self._cached_delta_exposure = {}
                    self._cached_treemaps = {}
                    self._cached_sector_charts = {}
                
                async with self:
                    if not self.selected_account and account_names:
                        self.selected_account = account_names[0]
                    self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                    self.is_portfolio_loading = False  # Hide global loading indicator
                
                yield rx.toast.success("Portfolio loaded from cache")
                return

            # Fetch all accounts
            url = "https://api.robinhood.com/accounts/?default_to_all_accounts=true&include_managed=true&include_multiple_individual=true"
            res = await asyncio.to_thread(rs.request_get, url, "regular")
            
            if res is None:
                async with self:
                    self.is_logged_in = False
                    self.account_name = "User"
                    self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                    self.is_portfolio_loading = False
                yield rx.toast.info("Session expired. Please sign in to view portfolio.")
                return
            
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

            # Update state with core portfolio data immediately
            # This makes the UI responsive while analysis runs in background
            # Use multiple brief lock acquisitions to allow tab switches to interleave
            async with self:
                self.all_stock_holdings = all_stocks
                self.all_options_holdings = all_options
            
            async with self:
                self.metric_data = all_metrics
                self.sp500_daily_change_pct = sp500_pct
            
            async with self:
                # Clear stale caches (computed vars will lazily rebuild on access)
                self._cached_stock_holdings = {}
                self._cached_option_holdings = {}
                self._cached_delta_exposure = {}
                self._cached_treemaps = {}
                self._cached_sector_charts = {}
            
            async with self:
                self.loading_accounts = set()
                # Transition to ANALYZING phase. UI is now interactive since
                # the loading overlay only shows during FETCHING. Tab switching
                # is allowed during ANALYZING since holdings data is cached.
                # analyze_portfolio_positions will set phase to IDLE when complete.
                self._set_loading_phase(PortfolioLoadingPhase.ANALYZING)
            
            # Set cache immediately with core data (before analysis completes)
            # This ensures subsequent page visits can use cached data even if
            # the user navigates away before analysis finishes
            set_cached("portfolio_data", {
                "account_map": temp_map,
                "all_stock_holdings": all_stocks,
                "all_options_holdings": all_options,
                "metric_data": all_metrics,
                "sp500_daily_pct": sp500_pct,
                # Analysis data will be empty initially, updated when analysis completes
                "sector_data": {},
                "range_52w_data": {},
                "earnings_data": {},
            }, PORTFOLIO_TTL)

            # Trigger analysis phase as separate background task
            # This fetches sector, 52-week range, and earnings data
            yield PortfolioState.analyze_portfolio_positions

            yield rx.toast.success("Portfolio loaded")
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "Unauthorized" in error_str:
                async with self:
                    self.is_logged_in = False
                    self.account_name = "User"
                    self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                    self.is_portfolio_loading = False
                yield rx.toast.info("Session expired. Please sign in to view portfolio.")
                return
            # Reset loading phase on error since analyze_portfolio_positions won't run
            async with self:
                self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                self.is_portfolio_loading = False
            yield rx.toast.error(f"Sync failed: {error_str}")
        finally:
            # No cleanup needed here - phase transitions are handled in try/except blocks
            # and analyze_portfolio_positions handles cleanup on success path
            pass

    @rx.event(background=True)
    async def analyze_portfolio_positions(self):
        """Fetch sector, 52-week range, and earnings data in background.
        
        Runs as a separate background task after core portfolio data loads,
        keeping the UI responsive for tab switching and other interactions.
        
        Note: loading_phase is set to ANALYZING by fetch_all_portfolio_data
        before this method is called, eliminating timing gaps. This method
        is responsible for setting loading_phase to IDLE when complete.
        
        Caches are cleared when new data arrives; computed vars lazily rebuild
        them on access.
        """
        # Capture local copies of state for consistency during async operations
        # Also reset retry count since this is a fresh analysis
        async with self:
            all_stocks = dict(self.all_stock_holdings)
            all_options = dict(self.all_options_holdings)
            metric_data = dict(self.metric_data)
            sp500_pct = self.sp500_daily_change_pct
            account_map = dict(self.account_map)
            self._retry_count = 0  # Reset for fresh analysis

        try:
            if not all_stocks:
                return
            
            # Fetch sector, range, and earnings data
            sector_data, range_52w_data, earnings_data, has_failures = await self._fetch_sector_and_range_data(all_stocks)

            # Update reactive state variables (brief lock)
            # Caches are cleared; computed vars will lazily rebuild on access
            async with self:
                self.sector_data = sector_data
                self.range_52w_data = range_52w_data
                self.earnings_data = earnings_data
                # Clear stale caches (computed vars will lazily rebuild on access)
                self._cached_stock_holdings = {}
                self._cached_sector_charts = {}
            
            # If some symbols failed, schedule a background retry for eventual consistency
            if has_failures:
                async with self:
                    self._set_loading_phase(PortfolioLoadingPhase.RETRYING)
                yield PortfolioState.retry_failed_analysis

            # Update cache with complete data (using local copies for consistency)
            set_cached("portfolio_data", {
                "account_map": account_map,
                "all_stock_holdings": all_stocks,
                "all_options_holdings": all_options,
                "metric_data": metric_data,
                "sp500_daily_pct": sp500_pct,
                "sector_data": sector_data,
                "range_52w_data": range_52w_data,
                "earnings_data": earnings_data,
            }, PORTFOLIO_TTL)

        except Exception as e:
            print(f"Error analyzing portfolio: {e}")
        finally:
            # Only reset to IDLE if we're not scheduling a retry
            # (retry_failed_analysis will handle its own cleanup)
            async with self:
                if self.loading_phase != PortfolioLoadingPhase.RETRYING:
                    self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                    self.is_portfolio_loading = False  # Hide global loading indicator


    @rx.event(background=True)
    async def retry_failed_analysis(self):
        """Retry fetching Yahoo Finance data for symbols that previously failed.
        
        Called automatically when initial analysis has failures. Uses exponential
        backoff (30s, 60s, 120s, 240s, 480s) to avoid hammering Yahoo Finance and
        to allow transient issues (like "Invalid Crumb" errors) to resolve.
        
        Provides eventual consistency: even if some symbols fail initially,
        they will be retried and the UI will update when data becomes available.
        Stops after MAX_RETRIES attempts to prevent infinite loops.
        """
        import random
        
        # Increment retry count and check limit
        async with self:
            self._retry_count += 1
            retry_num = self._retry_count
            max_retries = self.MAX_RETRIES
        
        if retry_num > max_retries:
            print(f"Yahoo Finance retry limit ({max_retries}) reached. Some data may be incomplete.")
            # Reset to IDLE since we're done retrying
            async with self:
                self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                self.is_portfolio_loading = False
            return
        
        # Exponential backoff: 30s, 60s, 120s, 240s, 480s
        # Add 10% jitter to avoid thundering herd if multiple users hit same issue
        base_delay = 30.0
        delay = base_delay * (2 ** (retry_num - 1))
        jitter = random.uniform(0, delay * 0.1)
        await asyncio.sleep(delay + jitter)
        
        # Capture current state
        async with self:
            all_stocks = dict(self.all_stock_holdings)
            account_map = dict(self.account_map)
            metric_data = dict(self.metric_data)
            sp500_pct = self.sp500_daily_change_pct
            all_options = dict(self.all_options_holdings)
        
        if not all_stocks:
            async with self:
                self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                self.is_portfolio_loading = False
            return
        
        try:
            # Re-fetch (short TTL cache will have expired, forcing fresh fetch)
            sector_data, range_52w_data, earnings_data, has_failures = await self._fetch_sector_and_range_data(all_stocks)
            
            # Update state with new data
            async with self:
                self.sector_data = sector_data
                self.range_52w_data = range_52w_data
                self.earnings_data = earnings_data
                self._cached_stock_holdings = {}
                self._cached_sector_charts = {}
            
            # Update the main portfolio cache with complete data
            set_cached("portfolio_data", {
                "account_map": account_map,
                "all_stock_holdings": all_stocks,
                "all_options_holdings": all_options,
                "metric_data": metric_data,
                "sp500_daily_pct": sp500_pct,
                "sector_data": sector_data,
                "range_52w_data": range_52w_data,
                "earnings_data": earnings_data,
            }, PORTFOLIO_TTL)
            
            # If still has failures and under retry limit, schedule another retry
            # Otherwise, we're done - reset to IDLE
            if has_failures and retry_num < max_retries:
                yield PortfolioState.retry_failed_analysis
            else:
                async with self:
                    self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                    self.is_portfolio_loading = False
                
        except Exception as e:
            print(f"Error in retry_failed_analysis (attempt {retry_num}): {e}")
            # Reset to IDLE on error
            async with self:
                self._set_loading_phase(PortfolioLoadingPhase.IDLE)
                self.is_portfolio_loading = False
