import reflex as rx
import asyncio
import json
import robin_stocks.robinhood as rs
import plotly.graph_objects as go
import pandas as pd
from .base import BaseState
from ..utils.auth import get_rh_credentials

class PortfolioState(BaseState):
    selected_account: str = ""
    # Map account names to their internal Robinhood account numbers
    account_map: dict[str, str] = {}
    holdings_data: dict[str, list[dict]] = {}

    @rx.var
    def account_names(self) -> list[str]:
        return list(self.account_map.keys())
    
    def change_tab(self, new_name: str):
        """Handle manual tab switching."""
        self.selected_account = new_name
        # If you want to force a refresh on every click:
        # return PortfolioState.fetch_all_portfolio_data
    
    @rx.var
    def current_holdings(self) -> list[dict]:
        """Returns the list of holdings for the currently selected tab."""
        acc_num = self.account_map.get(self.selected_account)
        if not acc_num:
            return []
        
        raw_data = self.holdings_data.get(acc_num, [])
        
        # Calculate total equity for 'allocation' percentages
        total_equity = sum(item["Equity"] for item in raw_data) if raw_data else 0
        
        # Transform for the UI (matching your table keys)
        formatted = []
        for item in raw_data:
            allocation = (item["Equity"] / total_equity * 100) if total_equity > 0 else 0
            formatted.append({
                "symbol": item["Ticker"],
                "shares": f"{item['Qty']:.4f}",
                "value": f"${item['Equity']:,.2f}",
                "allocation": f"{allocation:.1f}%",
                "raw_equity": item["Equity"] # useful for treemap
            })
        return formatted
    
    @rx.var
    def selected_account_balance(self) -> str:
        total = sum(item["raw_equity"] for item in self.current_holdings)
        return f"${total:,.2f}"

    @rx.var
    def selected_account_change(self) -> str:
        # You'll need to store 'equity_change' in holdings_data during fetch to use here
        # For now, returning a placeholder
        return "+$0.00 (0.00%)"

    @rx.var
    def portfolio_treemap(self) -> go.Figure:
        holdings = self.current_holdings
        if not holdings:
            return go.Figure()

        fig = go.Figure(go.Treemap(
            labels=[h["symbol"] for h in holdings],
            parents=[""] * len(holdings),
            values=[h["raw_equity"] for h in holdings],
            textinfo="label+percent parent",
            marker=dict(colors=["#a855f7", "#7c3aed", "#6d28d9", "#4c1d95"]),
        ))
        fig.update_layout(
            margin=dict(t=0, l=0, r=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=300,
            template="plotly_dark"
        )
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
    
    async def fetch_all_portfolio_data(self):
        self.is_loading = True
        yield
        try:
            url = "https://api.robinhood.com/accounts/?default_to_all_accounts=true&include_managed=true&include_multiple_individual=true"
            res = await asyncio.to_thread(rs.request_get, url, "regular")
            new_map = {}
            for acc in res.get('results', []):
                if acc["state"] == "active":
                    nickname = (acc['nickname'] or acc['brokerage_account_type'].replace('_', ' ')).title()
                    acc_num = acc['account_number']
                    key = f"{nickname}*{acc_num[-4:]}"
                    new_map[key] = acc_num
            self.account_map = new_map
            
            # Set default selection if none exists
            if not self.selected_account and self.account_names:
                self.selected_account = self.account_names[0]

            # Fetch positions for each account
            for name, acc_num in self.account_map.items():
                positions = await asyncio.to_thread(rs.account.get_open_stock_positions, account_number=acc_num)
                
                acc_holdings = []
                for p in positions:
                    symbol = await asyncio.to_thread(rs.get_symbol_by_url, p['instrument'])
                    latest_price = float((await asyncio.to_thread(rs.stocks.get_latest_price, symbol))[0])
                    qty = float(p['quantity'])
                    
                    acc_holdings.append({
                        'Ticker': symbol,
                        'Qty': qty,
                        'Equity': qty * latest_price,
                    })
                
                self.holdings_data[acc_num] = acc_holdings

            yield rx.toast.success("Portfolio Synced")
        except Exception as e:
            yield rx.toast.error(f"Sync failed: {str(e)}")
        finally:
            self.is_loading = False