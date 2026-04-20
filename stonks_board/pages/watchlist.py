"""Watchlist page UI.

Displays user's tracked tickers with technical alert evaluation and conviction scoring.
"""
import reflex as rx
from ..components.layout import page_layout
from ..components.skeleton import skeleton_table_rows, inline_spinner
from ..state import State
from ..state.watchlist import WatchlistState, ALERT_META
from ..styles.constants import ACCENT_PRIMARY


def watchlist_page() -> rx.Component:
    """Watchlist page with shared layout."""
    return page_layout(_watchlist_content())


def _watchlist_content() -> rx.Component:
    """Main watchlist content."""
    return rx.vstack(
        _header(),
        _add_ticker_bar(),
        rx.cond(
            WatchlistState.has_tickers,
            rx.vstack(
                _summary_bar(),
                rx.cond(
                    WatchlistState.phase2_complete,
                    _watchlist_table(),
                    rx.cond(
                        WatchlistState.is_loading,
                        skeleton_table_rows(num_rows=5, num_cols=6),
                        _watchlist_table(),
                    ),
                ),
                width="100%",
                spacing="4",
            ),
            rx.cond(
                WatchlistState.is_loading,
                rx.fragment(),
                _empty_state(),
            ),
        ),
        width="100%",
        spacing="4",
        caret_color="transparent",
    )


def _header() -> rx.Component:
    """Page header with title and refresh button."""
    return rx.hstack(
        rx.heading("Watchlist", size="8", weight="bold"),
        rx.spacer(),
        rx.hstack(
            rx.cond(
                WatchlistState.last_refresh_at != "",
                rx.text(
                    "Updated " + WatchlistState.last_refresh_at,
                    size="1", color="gray",
                ),
                rx.fragment(),
            ),
            rx.button(
                rx.cond(WatchlistState.is_loading, inline_spinner(), rx.icon("refresh-cw", size=14)),
                on_click=WatchlistState.refresh_alerts,
                variant="ghost",
                size="1",
                disabled=WatchlistState.is_loading,
            ),
            spacing="2",
            align="center",
        ),
        width="100%",
        align="center",
    )


def _add_ticker_bar() -> rx.Component:
    """Input bar for adding new tickers."""
    return rx.form(
        rx.hstack(
            rx.input(
                value=WatchlistState.add_ticker_input,
                on_change=WatchlistState.set_add_ticker_input,
                placeholder="Enter ticker symbol...",
                width="200px",
                name="ticker",
            ),
            rx.button(
                rx.cond(WatchlistState.is_validating_ticker, inline_spinner(), rx.text("Add")),
                type="submit",
                background=ACCENT_PRIMARY,
                disabled=WatchlistState.is_validating_ticker,
            ),
            spacing="2",
            align="center",
        ),
        on_submit=lambda _: WatchlistState.add_ticker(),
        reset_on_submit=False,
    )


def _summary_bar() -> rx.Component:
    """Minimal summary -- just ticker count."""
    return rx.text(
        WatchlistState.summary_total.to(str) + " tickers tracked",
        size="1", color="gray",
    )


def _empty_state() -> rx.Component:
    """Empty watchlist prompt."""
    return rx.text(
        "No tickers in your watchlist yet. Add one above to get started.",
        size="2", color="gray", padding_y="2em",
    )


def _watchlist_table() -> rx.Component:
    """Main watchlist table."""
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Ticker"),
                rx.table.column_header_cell("Price"),
                rx.table.column_header_cell("Change"),
                rx.table.column_header_cell(rx.text("Bullish Signals", color="green")),
                rx.table.column_header_cell(rx.text("Bearish Signals", color="red")),
                rx.table.column_header_cell(""),
            ),
        ),
        rx.table.body(
            rx.foreach(WatchlistState.sorted_tickers, _ticker_row),
        ),
        width="100%",
    )


def _ticker_row(item: dict) -> rx.Component:
    """A single ticker row with expandable detail."""
    return rx.fragment(
        rx.table.row(
            # Ticker
            rx.table.cell(
                rx.text(
                    item["symbol"],
                    weight="bold",
                    cursor="pointer",
                    _hover={"color": ACCENT_PRIMARY},
                    on_click=WatchlistState.toggle_expanded(item["symbol"]),
                ),
            ),
            # Price
            rx.table.cell(rx.text(item["price"], size="2")),
            # Change
            rx.table.cell(
                rx.text(
                    item["change_pct"],
                    size="2",
                    color=rx.cond(item["change_positive"], "green", "red"),
                ),
            ),
            # Bullish signals -- show triggered signal names
            rx.table.cell(
                rx.cond(
                    item["bullish_signals"] != "",
                    rx.text(item["bullish_signals"], size="1", color="green", wrap="wrap"),
                    rx.text("--", size="1", color="gray"),
                ),
            ),
            # Bearish signals -- show triggered signal names
            rx.table.cell(
                rx.cond(
                    item["bearish_signals"] != "",
                    rx.text(item["bearish_signals"], size="1", color="red", wrap="wrap"),
                    rx.text("--", size="1", color="gray"),
                ),
            ),
            # Remove button
            rx.table.cell(
                rx.icon(
                    "x",
                    size=14,
                    color="gray",
                    cursor="pointer",
                    _hover={"color": "red"},
                    on_click=WatchlistState.remove_ticker(item["symbol"]),
                ),
            ),
            # Row background based on dominant signal count
            background=rx.cond(
                item["bullish_triggered"].to(int) >= 4,
                "rgba(34, 197, 94, 0.06)",
                rx.cond(
                    item["bearish_triggered"].to(int) >= 4,
                    "rgba(239, 68, 68, 0.06)",
                    "transparent",
                ),
            ),
            border_left=rx.cond(
                item["total_triggered"].to(int) >= 2,
                rx.cond(
                    item["bullish_triggered"].to(int) > item["bearish_triggered"].to(int),
                    "2px solid rgba(34, 197, 94, 0.5)",
                    rx.cond(
                        item["bearish_triggered"].to(int) > item["bullish_triggered"].to(int),
                        "2px solid rgba(239, 68, 68, 0.5)",
                        f"2px solid {ACCENT_PRIMARY}",
                    ),
                ),
                "2px solid transparent",
            ),
        ),
        # Expanded detail row
        rx.cond(
            WatchlistState.expanded_ticker == item["symbol"],
            _expanded_detail(item["symbol"]),
            rx.fragment(),
        ),
    )


def _expanded_detail(symbol: str) -> rx.Component:
    """Expanded alert detail panel for a ticker."""
    return rx.table.row(
        rx.table.cell(
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.text("Alert Configuration", weight="bold", size="3"),
                        rx.spacer(),
                        rx.button(
                            "Toggle All",
                            on_click=WatchlistState.toggle_all_alerts(symbol),
                            variant="ghost",
                            size="1",
                        ),
                        width="100%",
                        align="center",
                    ),
                    rx.separator(),
                    # Bullish alerts section
                    rx.text("Bullish Signals", size="2", weight="medium", color="green"),
                    rx.foreach(
                        WatchlistState.expanded_alerts,
                        lambda a: rx.cond(
                            a["direction"] == "bullish",
                            _alert_row(symbol, a),
                            rx.fragment(),
                        ),
                    ),
                    rx.separator(),
                    # Bearish alerts section
                    rx.text("Bearish Signals", size="2", weight="medium", color="red"),
                    rx.foreach(
                        WatchlistState.expanded_alerts,
                        lambda a: rx.cond(
                            a["direction"] == "bearish",
                            _alert_row(symbol, a),
                            rx.fragment(),
                        ),
                    ),
                    spacing="2",
                    width="100%",
                ),
                width="100%",
            ),
            col_span=6,
        ),
    )


def _alert_row(symbol: str, alert: dict) -> rx.Component:
    """Single alert row in the expanded detail panel."""
    return rx.hstack(
        # Status indicator
        rx.cond(
            ~alert["enabled"],
            rx.icon("minus", size=14, color="gray"),
            rx.cond(
                alert["triggered"],
                rx.icon("circle-check", size=14, color=rx.cond(
                    alert["direction"] == "bullish", "green", "red"
                )),
                rx.icon("circle", size=14, color="gray"),
            ),
        ),
        # Alert name
        rx.text(alert["name"], size="2", flex="1"),
        # Current value
        rx.text(alert["value"], size="1", color="gray"),
        # Enable/disable switch
        rx.switch(
            checked=alert["enabled"],
            on_change=WatchlistState.toggle_alert(symbol, alert["type"]),
            size="1",
        ),
        spacing="3",
        align="center",
        width="100%",
        padding_y="0.25em",
        opacity=rx.cond(alert["enabled"], "1", "0.5"),
    )
