import reflex as rx
import asyncio
import re
from datetime import datetime
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
from .base import BaseState
from ..utils.cache import get_cached, set_cached, PORTFOLIO_TTL

SHARES_PER_CONTRACT = 100


def _mask_value(value: str) -> str:
    """Replace digits with asterisks for privacy mode."""
    return re.sub(r'\d', '*', value)


class PortfolioState(BaseState):
    # Map account names to their internal Robinhood account numbers
    account_map: dict[str, str] = {}
    loading_accounts: set[str] = set()
    selected_account: str = ""

    all_stock_holdings: dict[str, list[dict]] = {}
    all_options_holdings: dict[str, list[dict]] = {}
    metric_data: dict[str, dict[str, str]] = {}

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
        if self.stock_sort_column == column:
            self.stock_sort_ascending = not self.stock_sort_ascending
        else:
            self.stock_sort_column = column
            self.stock_sort_ascending = True
    
    def set_options_sort(self, column: str):
        """Toggle sort direction if same column, otherwise set new column ascending."""
        if self.options_sort_column == column:
            self.options_sort_ascending = not self.options_sort_ascending
        else:
            self.options_sort_column = column
            self.options_sort_ascending = True

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
            
            formatted.append({
                "symbol": item.get("symbol", "???"),
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
                "raw_equity": val
            })
        
        # Dynamic sorting based on state
        sort_col = self.stock_sort_column
        ascending = self.stock_sort_ascending
        
        def sort_key(x):
            val = x.get(sort_col)
            # N/A values (None) go to bottom regardless of sort direction
            if val is None:
                return (1, 0)  # (is_none, value) - None items sort last
            # Text columns sort alphabetically
            if isinstance(val, str):
                return (0, val.lower())
            # Numeric columns sort by value
            return (0, val)
        
        formatted.sort(key=sort_key, reverse=not ascending)
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
        
        def sort_key(x):
            val = x.get(sort_col)
            # N/A values (None) go to bottom regardless of sort direction
            if val is None:
                return (1, 0)
            # Text columns sort alphabetically
            if isinstance(val, str):
                return (0, val.lower())
            # Numeric columns sort by value
            return (0, val)
        
        formatted.sort(key=sort_key, reverse=not ascending)
        return formatted
    
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
        # You'll need to store 'equity_change' in holdings_data during fetch to use here
        # For now, returning a placeholder
        return "+$0.00 (0.00%)"

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
        
        def pl_to_color(pl_pct: float | None) -> str:
            """Convert P/L percentage to color. None = gray, positive = green, negative = red.
            Uses lighter shades for readability with dark text."""
            if pl_pct is None:
                return "rgb(128, 128, 128)"  # Neutral gray for N/A
            
            # Clamp percentage to reasonable range for color scaling
            clamped = max(-100, min(100, pl_pct))
            # Normalize to 0-1 range (0 = neutral, 1 = max intensity)
            intensity = abs(clamped) / 100
            
            if pl_pct >= 0:
                # Green gradient: from light green to deeper green
                # Base: rgb(187, 247, 208) -> Deep: rgb(34, 197, 94)
                r = int(187 - (187 - 34) * intensity)
                g = int(247 - (247 - 197) * intensity)
                b = int(208 - (208 - 94) * intensity)
            else:
                # Red gradient: from light red to deeper red
                # Base: rgb(254, 202, 202) -> Deep: rgb(239, 68, 68)
                r = int(254 - (254 - 239) * intensity)
                g = int(202 - (202 - 68) * intensity)
                b = int(202 - (202 - 68) * intensity)
            
            return f"rgb({r}, {g}, {b})"
        
        # Build combined lists for treemap
        labels = []
        values = []
        colors = []
        hover_texts = []  # Custom hover with $ value and P/L %
        
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
            
            colors.append(pl_to_color(pl_pct))
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
            
            colors.append(pl_to_color(pl_pct))
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
    
    async def setup_portfolio_page(self):
        """Setup portfolio page - validate session and fetch data if logged in."""
        await self.validate_existing_session()
        if self.is_logged_in:
            yield PortfolioState.fetch_all_portfolio_data
    
    async def _process_single_account(self, name: str, acc_num: str) -> dict:
        """Process a single account's data. Returns dict with all account data."""
        # Fetch profile, stocks, and options in parallel
        profile_task = asyncio.to_thread(rs.profiles.load_account_profile, account_number=acc_num)
        stocks_task = asyncio.to_thread(rs.account.get_open_stock_positions, account_number=acc_num)
        options_task = asyncio.to_thread(rs.options.get_open_option_positions, account_number=acc_num)
        
        profile, stock_positions, option_positions = await asyncio.gather(
            profile_task, stocks_task, options_task
        )
        
        c_str = f"${float(profile.get('cash', 0)):,.2f}"
        b_str = f"${float(profile.get('buying_power', 0)):,.2f}"
        
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

            # Process ALL accounts in parallel
            account_tasks = [
                self._process_single_account(name, acc_num) 
                for name, acc_num in current_accounts
            ]
            account_results = await asyncio.gather(*account_tasks, return_exceptions=True)

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
                all_metrics[acc_num] = {"cash": result["cash"], "bp": result["buying_power"]}

            # Update state once with all data
            async with self:
                self.all_stock_holdings = all_stocks
                self.all_options_holdings = all_options
                self.metric_data = all_metrics
                
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