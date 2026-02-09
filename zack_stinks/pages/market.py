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
                    rx.icon("trending-up", size=14),
                    rx.text("Trend Signals"),
                    spacing="2",
                    align="center",
                ),
                value="breakouts",
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
            rx.tabs.trigger(
                rx.hstack(
                    rx.icon("rocket", size=14),
                    rx.text("Near ATH"),
                    spacing="2",
                    align="center",
                ),
                value="near_ath",
            ),
            rx.tabs.trigger(
                rx.hstack(
                    rx.icon("calendar", size=14),
                    rx.text("Upcoming Earnings"),
                    spacing="2",
                    align="center",
                ),
                value="earnings",
            ),
        ),
        rx.tabs.content(_gap_events_content(), value="gaps", padding_top="1em"),
        rx.tabs.content(_breakout_events_content(), value="breakouts", padding_top="1em"),
        rx.tabs.content(_ma_proximity_content(), value="ma_proximity", padding_top="1em"),
        rx.tabs.content(_below_ma_content(), value="below_ma", padding_top="1em"),
        rx.tabs.content(_near_ath_content(), value="near_ath", padding_top="1em"),
        rx.tabs.content(_upcoming_earnings_content(), value="earnings", padding_top="1em"),
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


def _gap_table_header() -> rx.Component:
    """Reusable header for gap events tables."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Type"),
            rx.table.column_header_cell("% Change"),
            rx.table.column_header_cell(
                rx.tooltip(
                    rx.hstack(
                        rx.text("Volume"),
                        rx.icon("info", size=12, color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    content="Volume ratio compares today's volume to the 50-day average. "
                            "Values above 1.5x are flagged as high volume, indicating "
                            "stronger conviction behind the price gap.",
                )
            ),
        ),
    )


def _gap_events_content() -> rx.Component:
    """Gap events tab content, separated by index funds vs individual stocks."""
    no_events = rx.text("No gap events detected in portfolio holdings.", color="gray", size="2")
    
    return rx.cond(
        MarketState.gap_events.length() > 0,
        rx.vstack(
            # Index Funds section
            rx.cond(
                MarketState.index_fund_gap_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=14, color="blue"),
                        rx.text("Index Funds & ETFs", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _gap_table_header(),
                        rx.table.body(rx.foreach(MarketState.index_fund_gap_events, _gap_event_row)),
                        width="100%",
                    ),
                    width="100%",
                    margin_bottom="1.5em",
                ),
                rx.fragment(),
            ),
            # Individual Stocks section
            rx.cond(
                MarketState.individual_gap_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("building-2", size=14, color="green"),
                        rx.text("Individual Stocks", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _gap_table_header(),
                        rx.table.body(rx.foreach(MarketState.individual_gap_events, _gap_event_row)),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
        ),
        no_events,
    )


def _breakout_table_header() -> rx.Component:
    """Header for MA breakout events table."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Direction"),
            rx.table.column_header_cell("Signal Type"),
            rx.table.column_header_cell("Price"),
            rx.table.column_header_cell("MA Value"),
            rx.table.column_header_cell(
                rx.tooltip(
                    rx.hstack(
                        rx.text("Volume"),
                        rx.icon("info", size=12, color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    content="Volume ratio vs 50-day average. Price breakouts require 1.5x (50d) or 2.0x (200d). "
                            "Golden/Death Cross signals don't require volume confirmation.",
                )
            ),
        ),
    )


def _breakout_event_row(event: dict) -> rx.Component:
    """Table row for MA breakout event with color-coded direction."""
    is_bullish = event["direction"] == "Bullish"
    ma_type = event["ma_type"]
    
    # Determine badge for MA type: special styling for Golden/Death Cross
    ma_badge = rx.match(
        ma_type,
        ("Golden Cross", rx.badge("Golden Cross", color_scheme="yellow")),
        ("Death Cross", rx.badge("Death Cross", color_scheme="crimson")),
        ("50-day MA", rx.badge("50d", color_scheme="blue")),
        ("200-day MA", rx.badge("200d", color_scheme="orange")),
        rx.badge(ma_type, color_scheme="gray"),  # fallback
    )
    
    return rx.table.row(
        rx.table.cell(rx.text(event["symbol"], weight="bold")),
        rx.table.cell(
            rx.badge(
                event["direction"],
                color_scheme=rx.cond(is_bullish, "green", "red"),
            )
        ),
        rx.table.cell(ma_badge),
        rx.table.cell(event["price"]),
        rx.table.cell(event["ma_value"]),
        rx.table.cell(rx.text(event["volume_ratio"], " avg")),
        background_color=rx.cond(is_bullish, "rgba(34, 197, 94, 0.1)", "rgba(239, 68, 68, 0.1)"),
    )


def _breakout_events_content() -> rx.Component:
    """MA breakout events tab content with bullish and bearish signals."""
    no_events = rx.text(
        "No MA breakout events detected. Breakouts occur when price crosses above or below "
        "a key moving average (50d or 200d) with significant volume.",
        color="gray",
        size="2",
    )
    
    return rx.cond(
        MarketState.ma_breakout_events.length() > 0,
        rx.vstack(
            # Index Funds section
            rx.cond(
                MarketState.index_fund_ma_breakout_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=14, color="blue"),
                        rx.text("Index Funds & ETFs", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _breakout_table_header(),
                        rx.table.body(rx.foreach(MarketState.index_fund_ma_breakout_events, _breakout_event_row)),
                        width="100%",
                    ),
                    width="100%",
                    margin_bottom="1.5em",
                ),
                rx.fragment(),
            ),
            # Individual Stocks section
            rx.cond(
                MarketState.individual_ma_breakout_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("building-2", size=14, color="green"),
                        rx.text("Individual Stocks", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _breakout_table_header(),
                        rx.table.body(rx.foreach(MarketState.individual_ma_breakout_events, _breakout_event_row)),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
        ),
        no_events,
    )


def _ma_proximity_table_header() -> rx.Component:
    """Reusable header for MA proximity tables."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Price"),
            rx.table.column_header_cell("MA Value"),
            rx.table.column_header_cell("Offset"),
        ),
    )


def _ma_proximity_content() -> rx.Component:
    """MA proximity tab content, separated by index funds vs individual stocks."""
    no_events = rx.text("No positions near key moving averages.", color="gray", size="2")
    
    return rx.cond(
        MarketState.ma_proximity_events.length() > 0,
        rx.vstack(
            # Index Funds section
            rx.cond(
                MarketState.index_fund_ma_proximity_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=14, color="blue"),
                        rx.text("Index Funds & ETFs", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _ma_proximity_table_header(),
                        rx.table.body(rx.foreach(MarketState.index_fund_ma_proximity_events, _ma_proximity_row)),
                        width="100%",
                    ),
                    width="100%",
                    margin_bottom="1.5em",
                ),
                rx.fragment(),
            ),
            # Individual Stocks section
            rx.cond(
                MarketState.individual_ma_proximity_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("building-2", size=14, color="green"),
                        rx.text("Individual Stocks", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _ma_proximity_table_header(),
                        rx.table.body(rx.foreach(MarketState.individual_ma_proximity_events, _ma_proximity_row)),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
        ),
        no_events,
    )


def _below_ma_table_header() -> rx.Component:
    """Reusable header for below 200d MA tables."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Price"),
            rx.table.column_header_cell("200d MA"),
            rx.table.column_header_cell("% Below"),
            rx.table.column_header_cell("Accounts"),
        ),
    )


def _below_ma_content() -> rx.Component:
    """Below 200-day MA tab content, separated by index funds vs individual stocks."""
    no_events = rx.text("No holdings currently below their 200-day moving average.", color="gray", size="2")
    
    return rx.cond(
        MarketState.below_ma_200_events.length() > 0,
        rx.vstack(
            # Index Funds section
            rx.cond(
                MarketState.index_fund_below_ma_200_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=14, color="blue"),
                        rx.text("Index Funds & ETFs", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _below_ma_table_header(),
                        rx.table.body(rx.foreach(MarketState.index_fund_below_ma_200_events, _below_ma_row)),
                        width="100%",
                    ),
                    width="100%",
                    margin_bottom="1.5em",
                ),
                rx.fragment(),
            ),
            # Individual Stocks section
            rx.cond(
                MarketState.individual_below_ma_200_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("building-2", size=14, color="green"),
                        rx.text("Individual Stocks", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _below_ma_table_header(),
                        rx.table.body(rx.foreach(MarketState.individual_below_ma_200_events, _below_ma_row)),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
        ),
        no_events,
    )


def _below_ma_row(event: dict) -> rx.Component:
    """Table row for below 200-day MA event. Only accounts are masked for privacy."""
    # Longer mask to approximate typical multi-account strings like "Account Name*1234, Other Account*5678"
    MASK_ACCOUNTS = "********, ********"
    
    return rx.table.row(
        rx.table.cell(rx.text(event["symbol"], weight="bold")),
        rx.table.cell(event["price"]),
        rx.table.cell(event["ma_200_value"]),
        rx.table.cell(
            rx.text(
                event["pct_below"], "%",
                color="red",
                weight="medium",
            )
        ),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_ACCOUNTS, event["accounts"]),
                size="2",
                color="gray"
            )
        ),
    )


def _near_ath_table_header() -> rx.Component:
    """Reusable header for near 52-week high tables."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Price"),
            rx.table.column_header_cell("52-Week High"),
            rx.table.column_header_cell("% From High"),
            rx.table.column_header_cell("Accounts"),
        ),
    )


def _near_ath_content() -> rx.Component:
    """Near 52-week high tab content, separated by index funds vs individual stocks."""
    no_events = rx.text("No holdings currently within 5% of their 52-week high.", color="gray", size="2")
    
    return rx.cond(
        MarketState.near_ath_events.length() > 0,
        rx.vstack(
            # Index Funds section
            rx.cond(
                MarketState.index_fund_near_ath_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("layers", size=14, color="blue"),
                        rx.text("Index Funds & ETFs", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _near_ath_table_header(),
                        rx.table.body(rx.foreach(MarketState.index_fund_near_ath_events, _near_ath_row)),
                        width="100%",
                    ),
                    width="100%",
                    margin_bottom="1.5em",
                ),
                rx.fragment(),
            ),
            # Individual Stocks section
            rx.cond(
                MarketState.individual_near_ath_events.length() > 0,
                rx.vstack(
                    rx.hstack(
                        rx.icon("building-2", size=14, color="green"),
                        rx.text("Individual Stocks", weight="medium", size="2"),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.table.root(
                        _near_ath_table_header(),
                        rx.table.body(rx.foreach(MarketState.individual_near_ath_events, _near_ath_row)),
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            width="100%",
        ),
        no_events,
    )


def _near_ath_row(event: dict) -> rx.Component:
    """Table row for near all-time high event. Only accounts are masked for privacy."""
    MASK_ACCOUNTS = "********, ********"
    
    return rx.table.row(
        rx.table.cell(rx.text(event["symbol"], weight="bold")),
        rx.table.cell(event["price"]),
        rx.table.cell(event["all_time_high"]),
        rx.table.cell(rx.text(event["pct_from_ath"], "%")),
        rx.table.cell(
            rx.text(
                rx.cond(State.hide_portfolio_values, MASK_ACCOUNTS, event["accounts"]),
                size="2",
                color="gray"
            )
        ),
    )


def _gap_event_row(event: dict) -> rx.Component:
    """Table row for gap event. No masking needed as this doesn't reveal position size."""
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
                event["pct_change"], "%",
                color=rx.cond(event["pct_change_val"].to(float) >= 0, "green", "red"),
                weight="medium",
            )
        ),
        rx.table.cell(rx.text(event["volume_ratio"], "x avg")),
    )


def _ma_proximity_row(event: dict) -> rx.Component:
    """Table row for MA proximity event. No masking needed as this doesn't reveal position size."""
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
        rx.table.cell(event["price"]),
        rx.table.cell(event["ma_value"]),
        rx.table.cell(
            rx.text(
                event["pct_offset"], "%",
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


def _upcoming_earnings_table_header() -> rx.Component:
    """Header for upcoming earnings table."""
    return rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Ticker"),
            rx.table.column_header_cell("Earnings Date"),
            rx.table.column_header_cell("Days Until"),
            rx.table.column_header_cell(
                rx.tooltip(
                    rx.hstack(
                        rx.text("Timing"),
                        rx.icon("info", size=12, color="gray"),
                        spacing="1",
                        align="center",
                    ),
                    content="BMO = Before Market Open (pre-market), AMC = After Market Close (after-hours). "
                            "Timing may not be available for all stocks.",
                )
            ),
        ),
    )


def _upcoming_earnings_content() -> rx.Component:
    """Upcoming earnings tab content showing holdings with earnings within 7 days."""
    no_events = rx.text(
        "No holdings have earnings announcements in the next 7 days.",
        color="gray",
        size="2",
    )
    
    return rx.cond(
        MarketState.upcoming_earnings_events.length() > 0,
        rx.vstack(
            rx.hstack(
                rx.popover.root(
                    rx.popover.trigger(
                        rx.icon("info", size=14, color="gray", cursor="pointer"),
                    ),
                    rx.popover.content(
                        rx.text(
                            "Shows portfolio holdings with earnings announcements within the next 7 days. "
                            "Earnings can cause significant price volatility. Consider reviewing your "
                            "position sizing and risk exposure before earnings.",
                            size="2",
                        ),
                        side="top",
                        max_width="300px",
                    ),
                ),
                rx.text("Holdings with upcoming earnings", size="1", color="gray"),
                spacing="1",
                align="center",
            ),
            rx.table.root(
                _upcoming_earnings_table_header(),
                rx.table.body(rx.foreach(MarketState.upcoming_earnings_events, _upcoming_earnings_row)),
                width="100%",
            ),
            width="100%",
        ),
        no_events,
    )


def _upcoming_earnings_row(event: dict) -> rx.Component:
    """Table row for upcoming earnings event with urgency-based color coding."""
    # Urgency badge: red for imminent (0-3 days), yellow for soon (4-7 days)
    urgency_badge = rx.cond(
        event["urgency"] == "imminent",
        rx.badge(event["days_until_str"], color_scheme="red"),
        rx.badge(event["days_until_str"], color_scheme="yellow"),
    )
    
    return rx.table.row(
        rx.table.cell(rx.text(event["symbol"], weight="bold")),
        rx.table.cell(event["earnings_date"]),
        rx.table.cell(urgency_badge),
        rx.table.cell(
            rx.cond(
                event["timing"] != None,
                rx.badge(event["timing"], color_scheme="gray", variant="soft"),
                rx.text("--", color="gray"),
            )
        ),
    )
