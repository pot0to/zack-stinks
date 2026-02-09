"""Portfolio page UI.

Displays user's Robinhood portfolio with holdings, options, and performance metrics.
"""
import reflex as rx
from ..components.layout import page_layout
from ..components.cards import metric_card
from ..state import PortfolioState, State
from ..styles.constants import MASK_SHARES, MASK_DOLLAR, MASK_PERCENT, MASK_DELTA


def portfolio_page() -> rx.Component:
    """Portfolio page with shared layout."""
    return page_layout(_portfolio_content(), use_container=False)


def _login_required_view() -> rx.Component:
    """Placeholder shown when user is not authenticated."""
    return rx.center(
        rx.vstack(
            rx.icon("lock", size=48, color="gray"),
            rx.text("Login Required", size="6", weight="bold", color="gray"),
            rx.text(
                "Sign in to Robinhood to view your portfolio holdings and performance.",
                size="3",
                color="gray",
                text_align="center",
                max_width="400px",
            ),
            rx.link(
                rx.button("Sign In", size="3", variant="solid"),
                href="/login",
            ),
            spacing="4",
            align="center",
            padding="4em",
        ),
        width="100%",
        min_height="60vh",
    )


def _portfolio_content() -> rx.Component:
    """Main portfolio content with account tabs."""
    return rx.container(
        rx.vstack(
            rx.heading("My Portfolio", size="8", margin_bottom="0.5em"),
            rx.cond(
                State.is_logged_in,
                rx.tabs.root(
                    rx.tabs.list(
                        rx.foreach(
                            PortfolioState.account_names,
                            lambda name: rx.tabs.trigger(name, value=name),
                        ),
                    ),
                    rx.foreach(
                        PortfolioState.account_names,
                        lambda name: rx.tabs.content(_account_summary(name), value=name),
                    ),
                    value=PortfolioState.selected_account,
                    on_change=PortfolioState.change_tab,
                    width="100%",
                ),
                _login_required_view(),
            ),
        ),
        width="100%",
        padding="2em",
        size="4",
    )


def _stats_header() -> rx.Component:
    """Portfolio stats header with key metrics and privacy masking."""
    return rx.grid(
        rx.card(
            rx.vstack(
                rx.text("Total Portfolio Value", size="2", color="gray", weight="medium"),
                rx.heading(
                    rx.cond(State.hide_portfolio_values, MASK_DOLLAR, PortfolioState.selected_account_balance),
                    size="7"
                ),
                rx.badge(
                    rx.cond(State.hide_portfolio_values, MASK_PERCENT, PortfolioState.selected_account_change),
                    color_scheme=rx.cond(
                        State.hide_portfolio_values,
                        "gray",
                        rx.cond(PortfolioState.selected_account_change.contains("-"), "red", "green")
                    ),
                    variant="soft",
                    size="2",
                ),
                rx.text(
                    rx.cond(State.hide_portfolio_values, "***% vs S&P", PortfolioState.benchmark_comparison),
                    size="1",
                    color=rx.cond(
                        State.hide_portfolio_values,
                        "gray",
                        rx.cond(PortfolioState.benchmark_comparison.contains("-"), "red", "green")
                    ),
                    weight="medium",
                ),
                align_items="start",
                spacing="1",
            )
        ),
        rx.card(
            rx.vstack(
                rx.text("Cash Balance", size="2", color="gray", weight="medium"),
                rx.heading(
                    rx.cond(State.hide_portfolio_values, MASK_DOLLAR, PortfolioState.cash_balance),
                    size="7"
                ),
                rx.text("Available to withdraw", size="1", color="slate"),
                align_items="start",
                spacing="1",
            )
        ),
        rx.card(
            rx.vstack(
                rx.text("Buying Power", size="2", color="gray", weight="medium"),
                rx.heading(
                    rx.cond(State.hide_portfolio_values, MASK_DOLLAR, PortfolioState.buying_power),
                    size="7"
                ),
                rx.text("Total margin & cash", size="1", color="slate"),
                align_items="start",
                spacing="1",
            )
        ),
        columns="3",
        spacing="4",
        width="100%",
    )


def _allocation_view() -> rx.Component:
    """Asset allocation treemap, sector exposure, and delta exposure in a tabbed layout."""
    return rx.card(
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger("Asset Allocation", value="treemap_tab"),
                rx.tabs.trigger("Sector Exposure", value="sector_tab"),
                rx.tabs.trigger("Delta Exposure", value="delta_tab"),
            ),
            rx.tabs.content(
                rx.vstack(
                    rx.plotly(data=PortfolioState.portfolio_treemap, width="100%", height="350px"),
                    width="100%",
                    padding_top="1em",
                ),
                value="treemap_tab",
            ),
            rx.tabs.content(
                rx.vstack(
                    rx.hstack(
                        rx.popover.root(
                            rx.popover.trigger(
                                rx.icon("info", size=14, color="gray", cursor="pointer"),
                            ),
                            rx.popover.content(
                                rx.text(
                                    "Sector breakdown for individual stocks only. "
                                    "Index funds and ETFs are excluded since they provide diversified exposure.",
                                    size="2",
                                ),
                                side="top",
                                max_width="280px",
                            ),
                        ),
                        rx.text("Individual stocks only", size="1", color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    rx.plotly(data=PortfolioState.sector_exposure_chart, width="100%", height="320px"),
                    width="100%",
                    padding_top="1em",
                ),
                value="sector_tab",
            ),
            rx.tabs.content(
                _delta_exposure_content(),
                value="delta_tab",
            ),
            default_value="treemap_tab",
            width="100%",
        ),
        width="100%",
        margin_top="1.5em",
    )


def _delta_exposure_content() -> rx.Component:
    """Delta exposure tab content showing per-ticker directional exposure for options positions."""
    return rx.vstack(
        rx.hstack(
            rx.popover.root(
                rx.popover.trigger(
                    rx.icon("info", size=14, color="gray", cursor="pointer"),
                ),
                rx.popover.content(
                    rx.text(
                        "Shows tickers with open options positions and their net directional exposure. "
                        "Stock-only positions are shown in the Asset Allocation treemap. "
                        "Stock delta = 1 per share. Options delta = contracts × 100 × option delta. "
                        "Positive (green) = bullish, negative (red) = bearish.",
                        size="2",
                    ),
                    side="top",
                    max_width="320px",
                ),
            ),
            rx.text("Tickers with options positions", size="1", color="gray"),
            spacing="1",
            align="center",
        ),
        # Individual stocks section
        rx.cond(
            PortfolioState.selected_account_individual_delta_exposure.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("building-2", size=14, color="green"),
                    rx.text("Individual Stocks", weight="medium", size="2"),
                    spacing="2",
                    align="center",
                    margin_top="1em",
                ),
                _delta_exposure_table(PortfolioState.selected_account_individual_delta_exposure),
                width="100%",
            ),
            rx.fragment(),
        ),
        # Index funds section
        rx.cond(
            PortfolioState.selected_account_index_fund_delta_exposure.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("layers", size=14, color="blue"),
                    rx.text("Index Funds & ETFs", weight="medium", size="2"),
                    spacing="2",
                    align="center",
                    margin_top="1.5em",
                ),
                _delta_exposure_table(PortfolioState.selected_account_index_fund_delta_exposure),
                width="100%",
            ),
            rx.fragment(),
        ),
        # Empty state
        rx.cond(
            PortfolioState.selected_account_delta_exposure.length() == 0,
            rx.center(
                rx.vstack(
                    rx.text("No open options positions", color="gray", size="2"),
                    rx.text(
                        "Stock-only positions are shown in the Asset Allocation tab.",
                        color="gray",
                        size="1",
                    ),
                    spacing="1",
                    align="center",
                ),
                padding="2em",
            ),
            rx.fragment(),
        ),
        width="100%",
        padding_top="1em",
    )


def _delta_exposure_table(data: list) -> rx.Component:
    """Table showing per-ticker delta breakdown."""
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Symbol"),
                rx.table.column_header_cell("Stock Δ"),
                rx.table.column_header_cell("Options Δ"),
                rx.table.column_header_cell("Net Δ"),
                rx.table.column_header_cell(""),  # Bar column
            ),
        ),
        rx.table.body(
            rx.foreach(data, _delta_exposure_row),
        ),
        width="100%",
        variant="surface",
        size="1",
    )


def _delta_exposure_row(item: dict) -> rx.Component:
    """Single row in delta exposure table."""
    return rx.table.row(
        rx.table.cell(rx.text(item["symbol"], weight="bold", size="2")),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_DELTA, item["stock_delta"]),
                size="2",
                color="gray",
            )
        ),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_DELTA, item["options_delta"]),
                size="2",
                color="gray",
            )
        ),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_DELTA, item["net_delta"]),
                size="2",
                weight="medium",
                color=rx.cond(
                    State.hide_portfolio_values,
                    "gray",
                    rx.cond(item["is_bullish"], "green", "red")
                ),
            )
        ),
        rx.table.cell(
            rx.box(
                rx.box(
                    width=item["bar_width"],
                    height="100%",
                    background=rx.cond(
                        State.hide_portfolio_values,
                        rx.color("gray", 6),
                        rx.cond(
                            item["is_bullish"],
                            "rgb(34, 197, 94)",  # Green
                            "rgb(239, 68, 68)",  # Red
                        ),
                    ),
                    border_radius="2px",
                ),
                width="80px",
                height="8px",
                background=rx.color("gray", 4),
                border_radius="2px",
                overflow="hidden",
            ),
        ),
    )


def _sortable_stock_header(label: str, sort_key: str) -> rx.Component:
    """Clickable column header for stock table sorting."""
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(label),
            rx.cond(
                PortfolioState.stock_sort_column == sort_key,
                rx.icon(
                    rx.cond(PortfolioState.stock_sort_ascending, "chevron-up", "chevron-down"),
                    size=14,
                ),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
            cursor="pointer",
        ),
        on_click=lambda: PortfolioState.set_stock_sort(sort_key),
    )


def _stock_table_header() -> rx.Component:
    """Reusable header row for stock tables."""
    return rx.table.header(
        rx.table.row(
            _sortable_stock_header("Symbol", "symbol"),
            _sortable_stock_header("Price", "price_raw"),
            _sortable_stock_header("Shares", "shares_raw"),
            _sortable_stock_header("Market Value", "value_raw"),
            _sortable_stock_header("Avg Cost", "avg_cost_raw"),
            _sortable_stock_header("P/L ($)", "pl_raw"),
            _sortable_stock_header("P/L (%)", "pl_pct_raw"),
            # 52W Range with tooltip explaining color coding
            rx.table.column_header_cell(
                rx.hstack(
                    rx.text("52W Range"),
                    rx.popover.root(
                        rx.popover.trigger(
                            rx.icon("info", size=12, color="gray", cursor="pointer"),
                        ),
                        rx.popover.content(
                            rx.text(
                                "Position within 52-week trading range. "
                                "Green (>70%) = near highs, Blue (30-70%) = mid-range, "
                                "Red (<30%) = near lows.",
                                size="2",
                            ),
                            side="top",
                            max_width="260px",
                        ),
                    ),
                    spacing="1",
                    align="center",
                ),
            ),
            _sortable_stock_header("Portfolio %", "allocation_raw"),
        ),
    )


def _stock_holdings_table() -> rx.Component:
    """Stock holdings detail tables, separated by index funds vs individual stocks."""
    return rx.vstack(
        # Index Funds & ETFs section
        rx.cond(
            PortfolioState.selected_account_index_fund_holdings.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("layers", size=16, color="blue"),
                    rx.text("Index Funds & ETFs", weight="bold", size="4"),
                    spacing="2",
                    align_items="center",
                    margin_top="2em",
                ),
                rx.table.root(
                    _stock_table_header(),
                    rx.table.body(
                        rx.foreach(PortfolioState.selected_account_index_fund_holdings, _stock_row),
                    ),
                    width="100%",
                    variant="surface",
                    margin_top="1em",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
        # Individual Stocks section
        rx.cond(
            PortfolioState.selected_account_individual_stock_holdings.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("building-2", size=16, color="green"),
                    rx.text("Individual Stocks", weight="bold", size="4"),
                    spacing="2",
                    align_items="center",
                    margin_top="2em",
                ),
                rx.table.root(
                    _stock_table_header(),
                    rx.table.body(
                        rx.foreach(PortfolioState.selected_account_individual_stock_holdings, _stock_row),
                    ),
                    width="100%",
                    variant="surface",
                    margin_top="1em",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
        width="100%",
    )


def _stock_row(h: dict) -> rx.Component:
    """Individual stock holding row with privacy masking support.
    
    Only position-specific values are masked (shares, value, cost, P/L, allocation).
    Current price is market data and not masked.
    """
    return rx.table.row(
        rx.table.cell(rx.text(h["symbol"], weight="bold")),
        rx.table.cell(h["price"]),  # Market price - not masked
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_SHARES, h["shares"])),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["value"])),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["avg_cost"]),
                color=rx.cond(h["cost_basis_reliable"], "inherit", "gray")
            )
        ),
        rx.table.cell(
            rx.hstack(
                rx.text(
                    rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["pl_formatted"]),
                    color=rx.cond(
                        State.hide_portfolio_values,
                        "gray",
                        rx.cond(h["cost_basis_reliable"], rx.cond(h["pl_positive"], "green", "red"), "gray")
                    ),
                    weight="medium",
                ),
                # Info icon for N/A cost basis with tooltip explanation
                rx.cond(
                    h["cost_basis_reliable"],
                    rx.fragment(),
                    rx.popover.root(
                        rx.popover.trigger(
                            rx.icon("info", size=14, color="slate", cursor="pointer"),
                        ),
                        rx.popover.content(
                            rx.text(
                                "Cost basis unavailable. This can happen with transferred positions, "
                                "corporate actions, or shares acquired before 2011.",
                                size="2",
                            ),
                            side="top",
                            max_width="280px",
                        ),
                    ),
                ),
                spacing="1",
                align="center",
            )
        ),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_PERCENT, h["pl_pct_formatted"]),
                color=rx.cond(
                    State.hide_portfolio_values,
                    "gray",
                    rx.cond(h["cost_basis_reliable"], rx.cond(h["pl_positive"], "green", "red"), "gray")
                ),
                weight="medium",
            )
        ),
        rx.table.cell(_range_52w_cell(h)),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_PERCENT, h["allocation"])),
    )


def _range_52w_cell(h: dict) -> rx.Component:
    """52-week range cell with visual progress bar and percentage.
    
    Shows a horizontal bar indicating where the current price sits within
    the 52-week trading range. 0% = at 52-week low, 100% = at 52-week high.
    """
    # Cast to number for comparison operations
    range_val = h["range_52w_raw"].to(int)
    
    return rx.cond(
        h["range_52w_raw"] != None,
        rx.vstack(
            rx.box(
                rx.box(
                    width=h["range_52w"],
                    height="100%",
                    background=rx.cond(
                        range_val > 70,
                        "rgb(34, 197, 94)",  # Green for strong momentum
                        rx.cond(
                            range_val < 30,
                            "rgb(239, 68, 68)",  # Red for weakness
                            "rgb(59, 130, 246)",  # Blue for neutral
                        ),
                    ),
                    border_radius="2px",
                ),
                width="60px",
                height="6px",
                background=rx.color("gray", 5),
                border_radius="2px",
                overflow="hidden",
            ),
            rx.text(h["range_52w"], size="1", color="gray"),
            spacing="1",
            align="center",
        ),
        rx.text("N/A", size="2", color="gray"),
    )


def _sortable_options_header(label: str, sort_key: str) -> rx.Component:
    """Clickable column header for options table sorting."""
    return rx.table.column_header_cell(
        rx.hstack(
            rx.text(label),
            rx.cond(
                PortfolioState.options_sort_column == sort_key,
                rx.icon(
                    rx.cond(PortfolioState.options_sort_ascending, "chevron-up", "chevron-down"),
                    size=14,
                ),
                rx.fragment(),
            ),
            spacing="1",
            align="center",
            cursor="pointer",
        ),
        on_click=lambda: PortfolioState.set_options_sort(sort_key),
    )


def _options_table_header() -> rx.Component:
    """Reusable header row for options tables."""
    return rx.table.header(
        rx.table.row(
            _sortable_options_header("Symbol", "symbol"),
            _sortable_options_header("Strike", "strike_raw"),
            _sortable_options_header("Type", "option_type"),
            _sortable_options_header("Side", "side"),
            _sortable_options_header("DTE", "dte_raw"),
            _sortable_options_header("Underlying", "underlying_raw"),
            _sortable_options_header("Delta", "delta_raw"),
            _sortable_options_header("Cost Basis", "cost_basis_raw"),
            _sortable_options_header("Current Value", "current_value_raw"),
            _sortable_options_header("P/L ($)", "pl_raw"),
            _sortable_options_header("P/L (%)", "pl_pct_raw"),
            _sortable_options_header("Weight", "weight_raw"),
        ),
    )


def _options_holdings_table() -> rx.Component:
    """Options holdings detail tables, separated by index funds vs individual stocks."""
    return rx.vstack(
        # Index Fund / ETF Options section
        rx.cond(
            PortfolioState.selected_account_index_fund_options.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("layers", size=16, color="blue"),
                    rx.text("Index Fund & ETF Options", weight="bold", size="4"),
                    spacing="2",
                    align_items="center",
                    margin_top="2em",
                ),
                rx.table.root(
                    _options_table_header(),
                    rx.table.body(
                        rx.foreach(PortfolioState.selected_account_index_fund_options, _options_row),
                    ),
                    width="100%",
                    variant="surface",
                    margin_top="1em",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
        # Individual Stock Options section
        rx.cond(
            PortfolioState.selected_account_individual_options.length() > 0,
            rx.vstack(
                rx.hstack(
                    rx.icon("building-2", size=16, color="green"),
                    rx.text("Individual Stock Options", weight="bold", size="4"),
                    spacing="2",
                    align_items="center",
                    margin_top="2em",
                ),
                rx.table.root(
                    _options_table_header(),
                    rx.table.body(
                        rx.foreach(PortfolioState.selected_account_individual_options, _options_row),
                    ),
                    width="100%",
                    variant="surface",
                    margin_top="1em",
                ),
                width="100%",
            ),
            rx.fragment(),
        ),
        width="100%",
    )


def _options_row(h: dict) -> rx.Component:
    """Individual options holding row with privacy masking support.
    
    Position-specific values are masked (strike, delta, cost basis, current value, P/L, weight).
    Underlying price and DTE are market data and not masked.
    """
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(h["symbol"], weight="bold"),
                rx.cond(
                    h["is_itm"],
                    rx.badge("ITM", color_scheme="yellow", variant="soft"),
                    rx.fragment(),
                ),
                spacing="2",
            )
        ),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["strike"])),
        rx.table.cell(
            rx.badge(h["option_type"], color_scheme=rx.cond(h["option_type"] == "Call", "blue", "purple"), variant="soft")
        ),
        rx.table.cell(
            rx.badge(h["side"], color_scheme=rx.cond(h["is_short"], "orange", "green"), variant="soft")
        ),
        rx.table.cell(h["dte"]),
        rx.table.cell(h["underlying"]),  # Market data - not masked
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_DELTA, h["delta"])),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["cost_basis"])),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["current_value"])),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_DOLLAR, h["pl_formatted"]),
                color=rx.cond(State.hide_portfolio_values, "gray", rx.cond(h["pl_positive"], "green", "red")),
                weight="medium"
            )
        ),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_PERCENT, h["pl_pct_formatted"]),
                color=rx.cond(State.hide_portfolio_values, "gray", rx.cond(h["pl_positive"], "green", "red")),
                weight="medium"
            )
        ),
        rx.table.cell(rx.cond(State.hide_portfolio_values, MASK_PERCENT, h["weight"])),
    )


def _holdings_section() -> rx.Component:
    """Holdings tabs for options and stocks."""
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Options", value="options_tab"),
            rx.tabs.trigger("Stocks", value="stocks_tab"),
        ),
        rx.tabs.content(_options_holdings_table(), value="options_tab"),
        rx.tabs.content(_stock_holdings_table(), value="stocks_tab"),
        default_value="options_tab",
        width="100%",
    )


def _account_summary(name: str) -> rx.Component:
    """Account summary with loading state."""
    loader = rx.center(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text(f"Refreshing {name}...", color="gray", size="2"),
            spacing="3",
            padding="10em",
        ),
        width="100%",
    )

    content = rx.vstack(
        _stats_header(),
        _allocation_view(),
        _holdings_section(),
        width="100%",
        align_items="start",
        animation="fadeIn 0.4s ease-in-out",
    )

    return rx.vstack(
        rx.cond(PortfolioState.loading_accounts.contains(name), loader, content),
        width="100%",
    )
