import reflex as rx
import asyncio
import json
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
from .base import BaseState
from ..utils.auth import get_rh_credentials

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
            # Force everything to float for the math
            val = float(item.get("raw_equity", 0))
            shares = float(item.get("shares", 0))
            
            allocation = (val / total_equity * 100) if total_equity > 0 else 0
            
            formatted.append({
                "symbol": item.get("symbol", "???"),
                "shares": f"{shares:.4f}",
                "value": f"${val:,.2f}",
                "allocation": f"{allocation:.1f}%",
                "raw_equity": val
            })
        return formatted
    
    @rx.var
    def selected_account_option_holdings(self) -> list[dict]:
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num: return []
        
        # 1. Get raw data from storage
        raw_options = self.all_options_holdings.get(acc_num, [])
        raw_stocks = self.all_stock_holdings.get(acc_num, [])
        
        # 2. Calculate TOTAL equity (Stocks + Options) for accurate allocation %
        stock_total = sum(float(s.get("raw_equity", 0)) for s in raw_stocks)
        option_total = sum(float(o.get("raw_equity", 0)) for o in raw_options)
        total_account_equity = stock_total + option_total
        
        formatted = []
        for item in raw_options:
            val = float(item.get("raw_equity", 0))
            contracts = float(item.get("shares", 0)) # Using shares key as contracts
            
            # Calculate % of the TOTAL account
            allocation = (val / total_account_equity * 100) if total_account_equity > 0 else 0
            
            formatted.append({
                "symbol": item.get("symbol", "???"),
                "contracts": f"{contracts:.0f}", # Options are usually whole numbers
                "value": f"${val:,.2f}",
                "allocation": f"{allocation:.1f}%",
                "raw_equity": val
            })
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
        # Use the specifically named computed var, not the base var
        holdings = self.selected_account_stock_holdings 
        if not holdings: 
            return go.Figure()

        fig = go.Figure(go.Treemap(
            labels=[h["symbol"] for h in holdings],
            parents=[""] * len(holdings),
            values=[h["raw_equity"] for h in holdings],
            textinfo="label+percent parent",
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
                        acc_stocks.append({
                            "symbol": stock_symbols[i],
                            "shares": qty,
                            "raw_equity": qty * price,
                            "type": "Stock"
                        })

                # --- OPTIONS PROCESSING ---
                acc_options = []
                if option_positions:
                    option_ids = [p['option_id'] for p in option_positions]
                    
                    # get_quotes is the specific batch-fetcher for Option IDs
                    market_data = await asyncio.to_thread(
                        lambda ids: [rs.options.get_option_market_data_by_id(oid) for oid in ids],
                        option_ids
                    )
                    
                    for i, p in enumerate(option_positions):
                        m_data = market_data[i] if (market_data and i < len(market_data)) else None

                        mark = 0.0
                        # Default label if market data is missing
                        symbol_label = "Unknown Option"
                        
                        if m_data and isinstance(m_data, dict):
                            mark = float(m_data.get('mark_price', 0) or 0)
                            # Pull the strike and symbol from the market data instead of p
                            strike = m_data.get('strike_price', '??')
                            ticker = m_data.get('symbol', p.get('chain_symbol', 'OPT'))
                            type_ = m_data.get('type', '??').upper()
                    
                        qty = float(p['quantity'])
                        acc_options.append({
                            "symbol": p["chain_symbol"],
                            "contracts": qty, 
                            "value": qty * mark * 100,
                            "type": "Option"
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