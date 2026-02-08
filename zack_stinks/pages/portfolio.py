import reflex as rx
from ..state import PortfolioState
from ..components.sidebar import sidebar
from ..components.disclaimer import disclaimer_banner

def portfolio_page():
    return rx.vstack(
        disclaimer_banner(),
        rx.hstack(
            sidebar(),
            portfolio(),
            width="100%",
        ),
        spacing="0",
        width="100%",
    )

def portfolio():
    return rx.container(
        rx.vstack(
            rx.heading("My Portfolio", size="8", margin_bottom="0.5em"),
            
            rx.tabs.root(
                rx.tabs.list(
                    # These triggers are now ALWAYS clickable
                    rx.foreach(
                        PortfolioState.account_names,
                        lambda name: rx.tabs.trigger(name, value=name)
                    ),
                ),
                # We generate all content containers immediately. 
                # The account_summary handles its own internal loading state.
                rx.foreach(
                    PortfolioState.account_names,
                    lambda name: rx.tabs.content(
                        account_summary(name),
                        value=name,
                    )
                ),
                value=PortfolioState.selected_account,
                on_change=PortfolioState.change_tab,
                width="100%",
            ),
        ),
        margin_left=rx.cond(PortfolioState.sidebar_open, "250px", "74px"),
        width="100%",
        padding="2em",
        size="4", # Wider as requested
        transition="margin-left 0.3s ease",
    )

def metric_card(title: str, value: rx.Var, subtext: str = "", badge: rx.Component = None):
    return rx.card(
        rx.vstack(
            rx.text(title, size="2", color="gray", weight="medium"),
            rx.heading(value, size="7"),
            # Add the third argument here: rx.fragment()
            rx.cond(badge, badge, rx.fragment()), 
            rx.cond(subtext != "", rx.text(subtext, size="1", color="slate"), rx.fragment()),
            align_items="start",
            spacing="1",
        ),
    )

def stats_header():
    return rx.grid(
        metric_card(
            "Total Portfolio Value", 
            PortfolioState.selected_account_balance,
            badge=rx.badge(
                PortfolioState.selected_account_change,
                color_scheme=rx.cond(PortfolioState.selected_account_change.contains("-"), "red", "green"),
                variant="soft",
                size="2",
            )
        ),
        metric_card("Cash Balance", PortfolioState.cash_balance, subtext="Available to withdraw"),
        metric_card("Buying Power", PortfolioState.buying_power, subtext="Total margin & cash"),
        columns="3",
        spacing="4",
        width="100%",
    )

def allocation_view():
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.icon("pie-chart", size=18),
                rx.text("Asset Allocation", weight="bold", size="3"),
                spacing="2",
                align_items="center",
                margin_bottom="1em",
            ),
            rx.plotly(
                data=PortfolioState.portfolio_treemap,
                width="100%",
                height="400px",
            ),
            width="100%",
        ),
        width="100%",
        margin_top="1.5em",
    )

def sortable_stock_header(label: str, sort_key: str):
    """Create a clickable column header for stock table sorting."""
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

def stock_holdings_table():
    return rx.vstack(
        rx.text("Holdings Detail", weight="bold", margin_top="2em", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    sortable_stock_header("Symbol", "symbol"),
                    sortable_stock_header("Price", "price_raw"),
                    sortable_stock_header("Shares", "shares_raw"),
                    sortable_stock_header("Market Value", "value_raw"),
                    sortable_stock_header("Avg Cost", "avg_cost_raw"),
                    sortable_stock_header("P/L ($)", "pl_raw"),
                    sortable_stock_header("P/L (%)", "pl_pct_raw"),
                    sortable_stock_header("Portfolio %", "allocation_raw"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    PortfolioState.selected_account_stock_holdings, 
                    lambda h: rx.table.row(
                        rx.table.cell(rx.text(h["symbol"], weight="bold")),
                        rx.table.cell(h["price"]),
                        rx.table.cell(h["shares"]),
                        rx.table.cell(h["value"]),
                        rx.table.cell(
                            rx.text(
                                h["avg_cost"],
                                color=rx.cond(h["cost_basis_reliable"], "inherit", "gray"),
                            )
                        ),
                        rx.table.cell(
                            rx.text(
                                h["pl_formatted"],
                                color=rx.cond(
                                    h["cost_basis_reliable"],
                                    rx.cond(h["pl_positive"], "green", "red"),
                                    "gray"
                                ),
                                weight="medium",
                            )
                        ),
                        rx.table.cell(
                            rx.text(
                                h["pl_pct_formatted"],
                                color=rx.cond(
                                    h["cost_basis_reliable"],
                                    rx.cond(h["pl_positive"], "green", "red"),
                                    "gray"
                                ),
                                weight="medium",
                            )
                        ),
                        rx.table.cell(h["allocation"]),
                    ),
                )
            ),
            width="100%",
            variant="surface",
            margin_top="1em",
        ),
        width="100%",
    )

def sortable_options_header(label: str, sort_key: str):
    """Create a clickable column header for options table sorting."""
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

def options_holdings_table():
    return rx.vstack(
        rx.text("Options Detail", weight="bold", margin_top="2em", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    sortable_options_header("Symbol", "symbol"),
                    sortable_options_header("Strike", "strike_raw"),
                    sortable_options_header("Type", "option_type"),
                    sortable_options_header("Side", "side"),
                    sortable_options_header("DTE", "dte_raw"),
                    sortable_options_header("Underlying", "underlying_raw"),
                    sortable_options_header("Delta", "delta_raw"),
                    sortable_options_header("Cost Basis", "cost_basis_raw"),
                    sortable_options_header("Current Value", "current_value_raw"),
                    sortable_options_header("P/L ($)", "pl_raw"),
                    sortable_options_header("P/L (%)", "pl_pct_raw"),
                    sortable_options_header("Weight", "weight_raw"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    PortfolioState.selected_account_option_holdings, 
                    lambda h: rx.table.row(
                        rx.table.cell(rx.text(h["symbol"], weight="bold")),
                        rx.table.cell(h["strike"]),
                        rx.table.cell(
                            rx.badge(
                                h["option_type"],
                                color_scheme=rx.cond(h["option_type"] == "Call", "blue", "purple"),
                                variant="soft",
                            )
                        ),
                        rx.table.cell(
                            rx.badge(
                                h["side"],
                                color_scheme=rx.cond(h["is_short"], "orange", "green"),
                                variant="soft",
                            )
                        ),
                        rx.table.cell(h["dte"]),
                        rx.table.cell(h["underlying"]),
                        rx.table.cell(h["delta"]),
                        rx.table.cell(h["cost_basis"]),
                        rx.table.cell(h["current_value"]),
                        rx.table.cell(
                            rx.text(
                                h["pl_formatted"],
                                color=rx.cond(h["pl_positive"], "green", "red"),
                                weight="medium",
                            )
                        ),
                        rx.table.cell(
                            rx.text(
                                h["pl_pct_formatted"],
                                color=rx.cond(h["pl_positive"], "green", "red"),
                                weight="medium",
                            )
                        ),
                        rx.table.cell(h["weight"]),
                        # ITM highlight: yellow background for in-the-money options
                        background_color=rx.cond(h["is_itm"], "rgba(250, 204, 21, 0.15)", "transparent"),
                    ),
                )
            ),
            width="100%",
            variant="surface",
            margin_top="1em",
        ),
        width="100%",
    )

def holdings_section():
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Options", value="options_tab"),
            rx.tabs.trigger("Stocks", value="stocks_tab"),
        ),
        rx.tabs.content(
            options_holdings_table(),
            value="options_tab"
        ),
        rx.tabs.content(
            stock_holdings_table(), 
            value="stocks_tab"
        ),
        # This is the key: match the 'value' of your options tab
        default_value="options_tab",
        width="100%",
    )

def account_summary(name: str):
    # The Loading Spinner Component
    loader = rx.center(
        rx.vstack(
            rx.spinner(size="3"),
            rx.text(f"Refreshing {name}...", color="gray", size="2"),
            spacing="3",
            padding="10em",
        ),
        width="100%",
    )

    # The Actual Dashboard Content
    content = rx.vstack(
        stats_header(),
        allocation_view(),
        holdings_section(),
        width="100%",
        align_items="start",
        animation="fadeIn 0.4s ease-in-out",
    )

    return rx.vstack(
        rx.cond(
            PortfolioState.loading_accounts.contains(name),
            loader,
            content,
        ),
        width="100%",
    )