"""Market Overview page UI."""
import reflex as rx
from ..components.layout import page_layout
from ..state import MarketState, State


def market_page() -> rx.Component:
    """Market Overview page with shared layout."""
    return page_layout(_market_content())


def _market_content() -> rx.Component:
    """Main market overview content."""
    return rx.vstack(
        rx.heading("Market Overview", size="8", weight="bold"),
        rx.grid(
            rx.foreach(MarketState.market_data, lambda x: _market_card(x[0], x[1])),
            columns=rx.breakpoints(initial="2", sm="4", lg="6"),
            spacing="4",
            width="100%",
        ),
        rx.card(
            rx.vstack(
                rx.text("Market Momentum", weight="bold", size="4"),
                rx.plotly(data=MarketState.trend_fig, width="100%"),
            ),
            width="100%",
            margin_top="2em",
            padding="1em",
        ),
        _portfolio_spotlight(),
        width="100%",
        caret_color="transparent",
    )


def _portfolio_spotlight() -> rx.Component:
    """Portfolio spotlight section with tabbed gap events, MA proximity, and below MA alerts."""
    # Login required state
    login_required_view = rx.center(
        rx.vstack(
            rx.icon("lock", size=24, color="gray"),
            rx.text("Login Required", weight="medium", color="gray"),
            rx.text(
                "Sign in to Robinhood to see alerts for your portfolio holdings.",
                size="2",
                color="gray",
                text_align="center",
            ),
            rx.link(
                rx.button("Sign In", variant="outline", size="2"),
                href="/login",
            ),
            spacing="2",
            align="center",
        ),
        padding="2em",
        width="100%",
    )
    
    # Loading state
    loading_view = rx.center(
        rx.hstack(
            rx.spinner(size="2"),
            rx.text("Analyzing portfolio signals...", color="gray", size="2"),
            spacing="2",
        ),
        padding="2em",
        width="100%",
    )
    
    # No portfolio data state (logged in but portfolio not loaded yet)
    no_data_view = rx.center(
        rx.vstack(
            rx.icon("briefcase", size=24, color="gray"),
            rx.text("Portfolio data not loaded", weight="medium", color="gray"),
            rx.text(
                "Visit the Portfolio page first to load your holdings, then return here.",
                size="2",
                color="gray",
                text_align="center",
            ),
            rx.link(
                rx.button("Go to Portfolio", variant="outline", size="2"),
                href="/portfolio",
            ),
            spacing="2",
            align="center",
        ),
        padding="2em",
        width="100%",
    )
    
    # Tabbed data view
    data_view = rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger(
                rx.hstack(
                    rx.icon("zap", size=14),
                    rx.text("Price Gaps"),
                    spacing="2",
                    align="center",
                ),
                value="gaps",
            ),
            rx.tabs.trigger(
                rx.hstack(
                    rx.icon("target", size=14),
                    rx.text("Near Key Levels"),
                    spacing="2",
                    align="center",
                ),
                value="ma_proximity",
            ),
            rx.tabs.trigger(
                rx.hstack(
                    rx.icon("triangle-alert", size=14),
                    rx.text("Below 200d MA"),
                    spacing="2",
                    align="center",
                ),
                value="below_ma",
            ),
        ),
        rx.tabs.content(_gap_events_content(), value="gaps", padding_top="1em"),
        rx.tabs.content(_ma_proximity_content(), value="ma_proximity", padding_top="1em"),
        rx.tabs.content(_below_ma_content(), value="below_ma", padding_top="1em"),
        default_value="gaps",
        width="100%",
    )
    
    # Determine which view to show based on auth and data state
    authenticated_content = rx.cond(
        MarketState.portfolio_signals_loading,
        loading_view,
        rx.cond(
            MarketState.portfolio_data_available,
            data_view,
            no_data_view,
        ),
    )
    
    return rx.card(
        rx.vstack(
            rx.text("Portfolio Spotlight", weight="bold", size="4"),
            rx.divider(margin_y="1em"),
            rx.cond(
                State.is_logged_in,
                authenticated_content,
                login_required_view,
            ),
            align_items="start",
            width="100%",
        ),
        width="100%",
        margin_top="2em",
        padding="1em",
    )


def _gap_events_content() -> rx.Component:
    """Gap events tab content."""
    return rx.cond(
        MarketState.gap_events.length() > 0,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Ticker"),
                    rx.table.column_header_cell("Type"),
                    rx.table.column_header_cell("% Change"),
                    rx.table.column_header_cell("Volume"),
                ),
            ),
            rx.table.body(rx.foreach(MarketState.gap_events, _gap_event_row)),
            width="100%",
        ),
        rx.text("No gap events detected in portfolio holdings.", color="gray", size="2"),
    )


def _ma_proximity_content() -> rx.Component:
    """MA proximity tab content."""
    return rx.cond(
        MarketState.ma_proximity_events.length() > 0,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Ticker"),
                    rx.table.column_header_cell("Price"),
                    rx.table.column_header_cell("MA Value"),
                    rx.table.column_header_cell("Offset"),
                ),
            ),
            rx.table.body(rx.foreach(MarketState.ma_proximity_events, _ma_proximity_row)),
            width="100%",
        ),
        rx.text("No positions near key moving averages.", color="gray", size="2"),
    )


def _below_ma_content() -> rx.Component:
    """Below 200-day MA tab content."""
    return rx.cond(
        MarketState.below_ma_200_events.length() > 0,
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Ticker"),
                    rx.table.column_header_cell("Price"),
                    rx.table.column_header_cell("200d MA"),
                    rx.table.column_header_cell("% Below"),
                    rx.table.column_header_cell("Accounts"),
                ),
            ),
            rx.table.body(rx.foreach(MarketState.below_ma_200_events, _below_ma_row)),
            width="100%",
        ),
        rx.text("No holdings currently below their 200-day moving average.", color="gray", size="2"),
    )


def _below_ma_row(event: dict) -> rx.Component:
    """Table row for below 200-day MA event with privacy masking."""
    def masked(val):
        str_val = val.to(str)
        return rx.cond(
            State.hide_portfolio_values,
            str_val.replace("0", "*").replace("1", "*").replace("2", "*").replace("3", "*").replace("4", "*").replace("5", "*").replace("6", "*").replace("7", "*").replace("8", "*").replace("9", "*"),
            str_val,
        )
    
    return rx.table.row(
        rx.table.cell(rx.text(event["symbol"], weight="bold")),
        rx.table.cell(masked(event["price"])),
        rx.table.cell(masked(event["ma_200_value"])),
        rx.table.cell(
            rx.text(
                masked(event["pct_below"]), "%",
                color="red",
                weight="medium",
            )
        ),
        rx.table.cell(
            rx.text(event["accounts"], size="2", color="gray")
        ),
    )


def _gap_event_row(event: dict) -> rx.Component:
    """Table row for gap event with privacy masking."""
    def masked(val):
        str_val = val.to(str)
        return rx.cond(
            State.hide_portfolio_values,
            str_val.replace("0", "*").replace("1", "*").replace("2", "*").replace("3", "*").replace("4", "*").replace("5", "*").replace("6", "*").replace("7", "*").replace("8", "*").replace("9", "*"),
            str_val,
        )
    
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(event["symbol"], weight="bold"),
                rx.cond(
                    event["is_high_volume"] == "True",
                    rx.badge("High Vol", color_scheme="yellow"),
                    rx.fragment(),
                ),
                spacing="2",
            )
        ),
        rx.table.cell(event["gap_type"]),
        rx.table.cell(
            rx.text(
                masked(event["pct_change"]), "%",
                color=rx.cond(event["pct_change_val"].to(float) >= 0, "green", "red"),
                weight="medium",
            )
        ),
        rx.table.cell(rx.text(masked(event["volume_ratio"]), "x avg")),
    )


def _ma_proximity_row(event: dict) -> rx.Component:
    """Table row for MA proximity event with privacy masking."""
    def masked(val):
        str_val = val.to(str)
        return rx.cond(
            State.hide_portfolio_values,
            str_val.replace("0", "*").replace("1", "*").replace("2", "*").replace("3", "*").replace("4", "*").replace("5", "*").replace("6", "*").replace("7", "*").replace("8", "*").replace("9", "*"),
            str_val,
        )
    
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.text(event["symbol"], weight="bold"),
                rx.cond(
                    event["ma_type"] == "50-day MA",
                    rx.badge("50d", color_scheme="blue"),
                    rx.badge("200d", color_scheme="orange"),
                ),
                spacing="2",
            )
        ),
        rx.table.cell(masked(event["price"])),
        rx.table.cell(masked(event["ma_value"])),
        rx.table.cell(
            rx.text(
                masked(event["pct_offset"]), "%",
                color=rx.cond(event["pct_offset_val"].to(float) >= 0, "green", "red"),
                weight="medium",
            )
        ),
    )


def _market_card(label: str, values: dict) -> rx.Component:
    """Individual market index card."""
    return rx.card(
        rx.vstack(
            rx.text(label, font_weight="bold", color="gray"),
            rx.cond(
                values["is_currency"] == "True",
                rx.heading("$", values["price"], size="6"),
                rx.heading(values["price"], size="6"),
            ),
            rx.text(
                values["change"],
                color=rx.cond(values["change_val"].to(float) >= 0, "green", "red"),
                font_weight="medium",
            ),
            rx.text("H: ", values["high"], size="1", color="gray"),
            rx.text("L: ", values["low"], size="1", color="gray"),
            align_items="start",
        )
    )
