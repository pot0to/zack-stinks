"""Portfolio page UI."""
import reflex as rx
from ..components.layout import page_layout
from ..components.cards import metric_card
from ..state import PortfolioState, State


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
    """Portfolio stats header with key metrics."""
    return rx.grid(
        metric_card(
            "Total Portfolio Value",
            PortfolioState.selected_account_balance,
            badge=rx.badge(
                PortfolioState.selected_account_change,
                color_scheme=rx.cond(
                    PortfolioState.selected_account_change.contains("-"), "red", "green"
                ),
                variant="soft",
                size="2",
            ),
        ),
        metric_card("Cash Balance", PortfolioState.cash_balance, subtext="Available to withdraw"),
        metric_card("Buying Power", PortfolioState.buying_power, subtext="Total margin & cash"),
        columns="3",
        spacing="4",
        width="100%",
    )


def _allocation_view() -> rx.Component:
    """Asset allocation treemap."""
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("pie-chart", size=18),
                rx.text("Asset Allocation", weight="bold", size="3"),
                spacing="2",
                align_items="center",
                margin_bottom="1em",
            ),
            rx.plotly(data=PortfolioState.portfolio_treemap, width="100%", height="400px"),
            width="100%",
        ),
        width="100%",
        margin_top="1.5em",
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


def _stock_holdings_table() -> rx.Component:
    """Stock holdings detail table."""
    return rx.vstack(
        rx.text("Holdings Detail", weight="bold", margin_top="2em", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    _sortable_stock_header("Symbol", "symbol"),
                    _sortable_stock_header("Price", "price_raw"),
                    _sortable_stock_header("Shares", "shares_raw"),
                    _sortable_stock_header("Market Value", "value_raw"),
                    _sortable_stock_header("Avg Cost", "avg_cost_raw"),
                    _sortable_stock_header("P/L ($)", "pl_raw"),
                    _sortable_stock_header("P/L (%)", "pl_pct_raw"),
                    _sortable_stock_header("Portfolio %", "allocation_raw"),
                ),
            ),
            rx.table.body(
                rx.foreach(PortfolioState.selected_account_stock_holdings, _stock_row),
            ),
            width="100%",
            variant="surface",
            margin_top="1em",
        ),
        width="100%",
    )


def _stock_row(h: dict) -> rx.Component:
    """Individual stock holding row."""
    return rx.table.row(
        rx.table.cell(rx.text(h["symbol"], weight="bold")),
        rx.table.cell(h["price"]),
        rx.table.cell(h["shares"]),
        rx.table.cell(h["value"]),
        rx.table.cell(rx.text(h["avg_cost"], color=rx.cond(h["cost_basis_reliable"], "inherit", "gray"))),
        rx.table.cell(
            rx.text(
                h["pl_formatted"],
                color=rx.cond(h["cost_basis_reliable"], rx.cond(h["pl_positive"], "green", "red"), "gray"),
                weight="medium",
            )
        ),
        rx.table.cell(
            rx.text(
                h["pl_pct_formatted"],
                color=rx.cond(h["cost_basis_reliable"], rx.cond(h["pl_positive"], "green", "red"), "gray"),
                weight="medium",
            )
        ),
        rx.table.cell(h["allocation"]),
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


def _options_holdings_table() -> rx.Component:
    """Options holdings detail table."""
    return rx.vstack(
        rx.text("Options Detail", weight="bold", margin_top="2em", size="4"),
        rx.table.root(
            rx.table.header(
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
            ),
            rx.table.body(
                rx.foreach(PortfolioState.selected_account_option_holdings, _options_row),
            ),
            width="100%",
            variant="surface",
            margin_top="1em",
        ),
        width="100%",
    )


def _options_row(h: dict) -> rx.Component:
    """Individual options holding row."""
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
        rx.table.cell(h["strike"]),
        rx.table.cell(
            rx.badge(h["option_type"], color_scheme=rx.cond(h["option_type"] == "Call", "blue", "purple"), variant="soft")
        ),
        rx.table.cell(
            rx.badge(h["side"], color_scheme=rx.cond(h["is_short"], "orange", "green"), variant="soft")
        ),
        rx.table.cell(h["dte"]),
        rx.table.cell(h["underlying"]),
        rx.table.cell(h["delta"]),
        rx.table.cell(h["cost_basis"]),
        rx.table.cell(h["current_value"]),
        rx.table.cell(
            rx.text(h["pl_formatted"], color=rx.cond(h["pl_positive"], "green", "red"), weight="medium")
        ),
        rx.table.cell(
            rx.text(h["pl_pct_formatted"], color=rx.cond(h["pl_positive"], "green", "red"), weight="medium")
        ),
        rx.table.cell(h["weight"]),
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
