import reflex as rx

from .state.market import MarketState
from .state.portfolio import PortfolioState
from .pages.market import market_page
from .pages.portfolio import portfolio_page

app = rx.App()

# Market Overview Page
app.add_page(
    market_page,
    route="/",
    on_load=MarketState.setup_market_page
)

# Portfolio Page (Placeholder)
app.add_page(
    portfolio_page,
    route="/portfolio",
    on_load=PortfolioState.setup_portfolio_page
)