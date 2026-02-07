import reflex as rx
import asyncio
import json
from datetime import datetime
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
from .base import BaseState
from ..utils.auth import get_rh_credentials

SHARES_PER_CONTRACT = 100

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
                "pl_pct_formatted": (f"{abs(pl_pct):.1f}%" if pl_pct >= 0 else f"-{abs(pl_pct):.1f}%") if cost_basis_reliable else "N/A",
                "pl_positive": pl >= 0,
                "cost_basis_reliable": cost_basis_reliable,
                "allocation": f"{allocation:.1f}%",
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
                "pl_pct_formatted": f"{abs(pl_pct):.1f}%" if pl_pct >= 0 else f"-{abs(pl_pct):.1f}%",
                "pl_positive": pl >= 0,
                "weight_raw": weight,
                "weight": f"{weight:.1f}%",
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
        Color indicates direction: green for long, orange for short."""
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
        
        # Add stocks (all long positions, green)
        for s in raw_stocks:
            labels.append(s.get("symbol", "???"))
            values.append(abs(float(s.get("raw_equity", 0))))
            colors.append("rgb(34, 197, 94)")  # Green for long
        
        # Add options with color based on direction
        for o in raw_options:
            symbol = o.get("symbol", "???")
            is_short = o.get("is_short", False)
            # Add suffix to distinguish options from stocks
            labels.append(f"{symbol} (Opt)")
            values.append(abs(float(o.get("raw_equity", 0))))
            colors.append("rgb(249, 115, 22)" if is_short else "rgb(34, 197, 94)")  # Orange for short

        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=[""] * len(labels),
            values=values,
            textinfo="label+percent parent",
            marker=dict(colors=colors),
        ))
        fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), template="plotly_dark", height=300)
        return fig
    
    async def setup_portfolio_page(self):
        yield PortfolioState.login_to_robinhood
        yield PortfolioState.fetch_all_portfolio_data

    async def login_to_robinhood(self):
        self.is_loading = True
        yield 
        creds = get_rh_credentials()
        if not creds:
            yield rx.toast.error("Credentials missing!")
            self.is_loading = False
            return

        try:
            # login_info maintains the session globally in the 'rs' module
            login_info = await asyncio.to_thread(
                rs.login, 
                username=creds["username"], 
                password=creds["password"],
                mfa_code=self.mfa_input if self.mfa_input else None,
                store_session=True
            )

            if login_info and "access_token" in login_info:
                user_profile = await asyncio.to_thread(rs.account.load_user_profile)
                self.account_name = user_profile.get("first_name", "User")
                self.is_logged_in = True
                yield rx.toast.success(f"Connected as {self.account_name}")
            else:
                yield rx.toast.warning("MFA Required or Login Failed.")
        except Exception as e:
            yield rx.toast.error(f"Login Error: {str(e)}")
        
        self.is_loading = False
    
    @rx.event(background=True)
    async def fetch_all_portfolio_data(self):
        async with self:
            self.is_loading = True

        try:
            # 1. Fetch all accounts
            url = "https://api.robinhood.com/accounts/?default_to_all_accounts=true&include_managed=true&include_multiple_individual=true"
            res = await asyncio.to_thread(rs.request_get, url, "regular")
            
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

            # 2. Process each account
            for name, acc_num in current_accounts:
                async with self:
                    self.loading_accounts.add(name)

                # Fetch Metrics
                profile = await asyncio.to_thread(rs.profiles.load_account_profile, account_number=acc_num)
                c_str = f"${float(profile.get('cash', 0)):,.2f}"
                b_str = f"${float(profile.get('buying_power', 0)):,.2f}"

                # Fetch Raw Positions
                stock_positions = await asyncio.to_thread(rs.account.get_open_stock_positions, account_number=acc_num)
                option_positions = await asyncio.to_thread(rs.options.get_open_option_positions, account_number=acc_num)
                
                # --- STOCKS PROCESSING ---
                acc_stocks = []
                if stock_positions:
                    stock_symbols = [await asyncio.to_thread(rs.get_symbol_by_url, p['instrument']) for p in stock_positions]
                    prices = await asyncio.to_thread(rs.stocks.get_latest_price, stock_symbols)
                    
                    for i, p in enumerate(stock_positions):
                        price = float(prices[i]) if prices[i] else 0.0
                        qty = float(p['quantity'])
                        
                        # Get average buy price from position data
                        # Note: This may be inaccurate for transferred positions (ACATS)
                        # as Robinhood's API doesn't expose tax lot cost basis
                        avg_buy_price_raw = p.get('average_buy_price') or p.get('pending_average_buy_price') or 0
                        avg_buy_price = float(avg_buy_price_raw) if avg_buy_price_raw else 0.0
                        
                        # Flag unreliable cost basis (likely transferred positions)
                        # If avg cost is 0 or less than 1% of current price, it's suspect
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

                # --- OPTIONS PROCESSING ---
                acc_options = []
                if option_positions:
                    option_ids = [p['option_id'] for p in option_positions]
                    
                    # Fetch market data and instrument data for each option
                    market_data = await asyncio.to_thread(
                        lambda ids: [rs.options.get_option_market_data_by_id(oid) for oid in ids],
                        option_ids
                    )
                    instrument_data = await asyncio.to_thread(
                        lambda ids: [rs.options.get_option_instrument_data_by_id(oid) for oid in ids],
                        option_ids
                    )
                    
                    # Get unique underlying symbols and fetch their prices
                    underlying_symbols = list(set(p["chain_symbol"] for p in option_positions))
                    underlying_prices_raw = await asyncio.to_thread(rs.stocks.get_latest_price, underlying_symbols)
                    underlying_price_map = {sym: float(underlying_prices_raw[i] or 0) for i, sym in enumerate(underlying_symbols)}
                    
                    for i, p in enumerate(option_positions):
                        m_data = market_data[i] if (market_data and i < len(market_data)) else None
                        i_data = instrument_data[i] if (instrument_data and i < len(instrument_data)) else None

                        mark = 0.0
                        delta = 0.0
                        
                        # API returns a list; extract first element to get the dict
                        if m_data and isinstance(m_data, list) and len(m_data) > 0:
                            option_data = m_data[0]
                            mark = float(option_data.get('adjusted_mark_price') or option_data.get('mark_price') or 0)
                            delta = float(option_data.get('delta') or 0)
                        elif m_data and isinstance(m_data, dict):
                            mark = float(m_data.get('adjusted_mark_price') or m_data.get('mark_price') or 0)
                            delta = float(m_data.get('delta') or 0)
                        
                        # Extract instrument details
                        strike_price = float(i_data.get('strike_price', 0)) if i_data else 0
                        expiration_date = i_data.get('expiration_date', '') if i_data else ''
                        option_type = (i_data.get('type', '') if i_data else '').capitalize()  # "call" or "put"
                        
                        # Calculate DTE
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
                        position_type = p.get('type', 'long')  # "long" or "short"
                        is_short = position_type == 'short'
                        
                        # Cost basis: average_price is already the per-contract price
                        # Use abs() since API may return negative for short positions
                        avg_price = abs(float(p.get('average_price', 0)))
                        cost_basis = avg_price * qty
                        
                        # Current value
                        current_value = qty * mark * SHARES_PER_CONTRACT
                        
                        # P/L calculation: Long = current - cost, Short = cost - current
                        if is_short:
                            pl = cost_basis - current_value  # Profit when value decreases
                        else:
                            pl = current_value - cost_basis  # Profit when value increases
                        
                        # For short positions, value represents liability (negative contribution)
                        signed_value = -current_value if is_short else current_value
                        
                        # Get underlying price
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

                # 3. Update State Dictionaries
                async with self:
                    self.all_stock_holdings[acc_num] = acc_stocks
                    self.all_options_holdings[acc_num] = acc_options
                    self.metric_data[acc_num] = {"cash": c_str, "bp": b_str}
                    
                    if self.selected_account == name:
                        self.cash_balance = c_str
                        self.buying_power = b_str
                    self.loading_accounts.remove(name)

            return rx.toast.success("Portfolio Updated")
        except Exception as e:
            return rx.toast.error(f"Sync failed: {str(e)}")
        finally:
            async with self:
                self.is_loading = False