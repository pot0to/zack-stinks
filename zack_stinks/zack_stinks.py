import reflex as rx

from .state.market import MarketState
from .state.portfolio import PortfolioState
from .state.research import ResearchState
from .pages.market import market_page
from .pages.portfolio import portfolio_page
from .pages.research import research_page
from .pages.login import login_page

# App with dark theme (color constants are optimized for dark backgrounds)
# Note: For true adaptive light/dark, colors would need to use Reflex theme tokens
app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="purple",
        radius="medium",
    )
)

# Login Page
app.add_page(
    login_page,
    route="/login",
)

# Market Overview Page
app.add_page(
    market_page,
    route="/",
    on_load=MarketState.setup_market_page
)

# Portfolio Page
app.add_page(
    portfolio_page,
    route="/portfolio",
    on_load=PortfolioState.setup_portfolio_page
)

# Stock Research Page
app.add_page(
    research_page,
    route="/research",
)
