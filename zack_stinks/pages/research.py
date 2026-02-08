"""Stock Research page UI."""
import reflex as rx
from ..components.layout import page_layout
from ..components.cards import stat_card
from ..state.research import ResearchState
from ..styles.constants import ACCENT_PRIMARY, ACCENT_PRIMARY_HOVER


def research_page() -> rx.Component:
    """Stock Research page with shared layout."""
    return page_layout(_research_content(), use_container=False)


def _research_content() -> rx.Component:
    """Main research page content."""
    return rx.box(
        rx.vstack(
            # Page header
            rx.hstack(
                rx.icon(tag="search", size=28, color=ACCENT_PRIMARY),
                rx.text("Stock Research", size="6", weight="bold"),
                align="center",
                spacing="3",
            ),
            # Input controls
            _search_controls(),
            # Stats row
            _stats_row(),
            # Chart
            rx.box(
                rx.plotly(data=ResearchState.price_chart, style={"width": "100%", "height": "100%"}),
                width="100%",
                background=rx.color("gray", 2),
                border_radius="12px",
                border=f"1px solid {rx.color('gray', 4)}",
                padding="1em",
            ),
            spacing="5",
            width="100%",
            padding="2em",
        ),
        min_height="100vh",
        width="100%",
    )


def _search_controls() -> rx.Component:
    """Search input controls."""
    return rx.hstack(
        rx.box(
            rx.vstack(
                rx.text("Symbol", size="1", color="gray"),
                rx.input(
                    value=ResearchState.ticker,
                    on_change=ResearchState.set_ticker,
                    placeholder="AAPL",
                    width="200px",
                ),
                spacing="1",
                align_items="start",
            ),
        ),
        rx.box(
            rx.vstack(
                rx.text("Period", size="1", color="gray"),
                rx.select(
                    ["1mo", "3mo", "6mo", "1y", "2y"],
                    value=ResearchState.period,
                    on_change=ResearchState.set_period,
                    width="120px",
                ),
                spacing="1",
                align_items="start",
            ),
        ),
        rx.button(
            rx.cond(ResearchState.is_loading, rx.spinner(size="1"), rx.text("Search")),
            on_click=ResearchState.fetch_stock_data,
            background=ACCENT_PRIMARY,
            color="white",
            _hover={"background": ACCENT_PRIMARY_HOVER},
            margin_top="1.25em",
        ),
        spacing="4",
        align="end",
        width="100%",
    )


def _rsi_zone_badge() -> rx.Component:
    """Dynamic badge for RSI zone with color-coded buy/sell signal context."""
    return rx.match(
        ResearchState.rsi_zone,
        ("Oversold", rx.badge("Oversold", color_scheme="green")),  # Buy signal
        ("Weak", rx.badge("Weak", color_scheme="orange")),  # Caution
        ("Bullish", rx.badge("Bullish", color_scheme="blue")),  # Hold
        ("Overbought", rx.badge("Overbought", color_scheme="red")),  # Sell signal
        rx.badge(ResearchState.rsi_zone, color_scheme="gray"),  # Fallback
    )


def _volatility_zone_badge() -> rx.Component:
    """Dynamic badge for volatility zone relative to stock's own history."""
    return rx.match(
        ResearchState.volatility_zone,
        ("Low", rx.badge("Low", color_scheme="blue")),  # Calmer than usual
        ("Normal", rx.badge("Normal", color_scheme="green")),  # Typical for this stock
        ("High", rx.badge("High", color_scheme="red")),  # More volatile than usual
        rx.badge(ResearchState.volatility_zone, color_scheme="gray"),  # Fallback
    )


def _stats_row() -> rx.Component:
    """Row of stat cards for research metrics."""
    return rx.hstack(
        stat_card(
            "Price",
            ResearchState.current_price,
            ResearchState.price_change_pct,
            sub_color=rx.cond(ResearchState.price_change_positive, "green", "red"),
        ),
        stat_card(
            "52W Range",
            ResearchState.range_52w,
            "High: " + ResearchState.high_52w,
            info_text="Position within 52-week trading range. 0% = at 52-week low, 100% = at 52-week high.",
        ),
        stat_card(
            "RSI (14)",
            ResearchState.rsi_14,
            badge=_rsi_zone_badge(),
            info_text="RSI zones: Oversold (<30) may signal a bounce, Weak (30-50) indicates bearish momentum, "
                      "Bullish (50-70) suggests healthy uptrend, Overbought (>70) may signal a pullback.",
        ),
        stat_card(
            "Volatility",
            ResearchState.volatility,
            sub_value=ResearchState.volatility_vs_spy,
            badge=_volatility_zone_badge(),
            info_text="HV30: Annualized standard deviation of daily returns over 30 trading days. "
                      "Zone compares current HV30 to the stock's own 52-week rolling average: "
                      "Low (<70% of avg), Normal (70-130%), High (>130%). "
                      "'Normal' means typical for THIS stock, not the market. SPY shown for market baseline.",
        ),
        stat_card("vs 50 MA", ResearchState.ma_50_pct),
        stat_card("vs 200 MA", ResearchState.ma_200_pct),
        stat_card("MACD", ResearchState.macd_signal),
        spacing="3",
        flex_wrap="wrap",
        width="100%",
    )
