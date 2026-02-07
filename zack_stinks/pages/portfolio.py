import reflex as rx
from ..state import PortfolioState
from ..components.sidebar import sidebar

def portfolio():
    return rx.hstack(
        sidebar(),
        rx.container(
            rx.vstack(
                rx.heading("My Portfolio", size="8", margin_bottom="0.5em"),
                
                # Dynamic Tabs based on live Robinhood accounts
                rx.tabs.root(
                    rx.tabs.list(
                        # Iterates over account names (Individual, IRA, Crypto, etc.)
                        rx.foreach(
                            PortfolioState.account_names,
                            lambda name: rx.tabs.trigger(name, value=name)
                        ),
                    ),
                    # CONTENT: We use a single foreach for content too
                    rx.foreach(
                        PortfolioState.account_names,
                        lambda name: rx.tabs.content(
                            # We pass the account name to your existing summary component
                            account_summary(name),
                            value=name,
                        )
                    ),
                    # on_change=PortfolioState.set_account,
                    value=PortfolioState.selected_account,
                    width="100%",
                ),
            ),
            # Transition matches sidebar toggle
            margin_left=rx.cond(PortfolioState.sidebar_open, "250px", "74px"),
            width="100%",
            padding="2em",
            transition="margin-left 0.3s ease",
        ),
    )

def account_summary(name: str):
    """
    Renders the layout for a single account tab with a loading state.
    """
    return rx.cond(
        # 1. Is this tab even active?
        PortfolioState.selected_account == name,
        
        # 2. IF ACTIVE: Is it currently loading data?
        rx.cond(
            PortfolioState.is_loading,
            # SHOW LOADING WHEEL
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Fetching your Robinhood data...", color="gray", size="2"),
                    spacing="3",
                    padding="10em",
                ),
                width="100%",
            ),
            # SHOW ACTUAL CONTENT
            rx.vstack(
                rx.hstack(
                    # Left Card: Balance & Performance
                    rx.card(
                        rx.vstack(
                            rx.text(f"Account: {name}", size="2", color="gray"),
                            rx.heading(PortfolioState.selected_account_balance, size="8"),
                            rx.badge(
                                PortfolioState.selected_account_change,
                                color_scheme=rx.cond(
                                    PortfolioState.selected_account_change.contains("-"),
                                    "red",
                                    "green"
                                ),
                                variant="soft",
                                size="2",
                            ),
                            align_items="start",
                            spacing="2",
                        ),
                        width="40%",
                    ),
                    
                    # Right Card: Asset Allocation Treemap
                    rx.card(
                        rx.plotly(
                            data=PortfolioState.portfolio_treemap,
                            width="100%",
                        ),
                        width="60%",
                    ),
                    width="100%",
                    spacing="4",
                ),
                
                rx.text("Holdings Detail", weight="bold", margin_top="2em", size="4"),
                
                # Table: Full Asset List
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Symbol"),
                            rx.table.column_header_cell("Shares"),
                            rx.table.column_header_cell("Market Value"),
                            rx.table.column_header_cell("Portfolio %"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            PortfolioState.current_holdings,
                            lambda holding: rx.table.row(
                                rx.table.cell(rx.text(holding["symbol"], weight="bold")),
                                rx.table.cell(holding["shares"]),
                                rx.table.cell(holding["value"]),
                                rx.table.cell(holding["allocation"]),
                            ),
                        )
                    ),
                    width="100%",
                    variant="surface",
                    margin_top="1em",
                ),
                width="100%",
                align_items="start",
                # Smooth fade-in when loading finishes
                animation="fadeIn 0.5s ease-in-out",
            ),
        ),
        
        # 3. IF INACTIVE: Placeholder
        rx.center(
            rx.text("Tab not selected", color="gray", size="2"),
            width="100%",
            padding="5em"
        ) 
    )