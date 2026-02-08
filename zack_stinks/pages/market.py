"""Market Overview page UI."""
import reflex as rx
from ..components.layout import page_layout
from ..state import MarketState


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
    """Portfolio spotlight section with gap events and MA proximity."""
    return rx.card(
        rx.vstack(
            rx.text("Portfolio Spotlight", weight="bold", size="4"),
            rx.divider(margin_y="1em"),
            rx.text("Price Gaps", weight="medium", size="3", color="gray"),
            rx.cond(
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
            ),
            rx.divider(margin_y="1em"),
            rx.text("Near Key Levels", weight="medium", size="3", color="gray"),
            rx.cond(
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
            ),
            align_items="start",
            width="100%",
        ),
        width="100%",
        margin_top="2em",
        padding="1em",
    )


def _gap_event_row(event: dict) -> rx.Component:
    """Table row for gap event."""
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
    """Table row for MA proximity event."""
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
