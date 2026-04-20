from .base import BaseState
from .market import MarketState
from .portfolio import PortfolioState
from .research import ResearchState
from .watchlist import WatchlistState

# This alias allows your existing code to find "State"
State = BaseState