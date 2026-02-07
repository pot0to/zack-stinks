import reflex as rx

from .state.market import MarketState
from .state.portfolio import PortfolioState
from .state.research import ResearchState
from .pages.market import market
from .pages.portfolio import portfolio
from .pages.research import research

app = rx.App()

# Market Overview Page
app.add_page(
    market,
    route="/",
    on_load=MarketState.setup_market_page
)

# Portfolio Page
app.add_page(
    portfolio,
    route="/portfolio",
    on_load=PortfolioState.setup_portfolio_page
)

# Stock Research Page
app.add_page(
    research,
    route="/research",
)