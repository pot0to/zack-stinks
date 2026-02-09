"""Stock Research page UI with Technical and Fundamental analysis tabs."""
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
            # Tab navigation and stats
            _tabbed_stats(),
            # Chart (conditionally rendered based on data availability)
            rx.cond(
                ResearchState.phase1_complete,
                # Show chart once data is loaded
                rx.box(
                    rx.plotly(data=ResearchState.price_chart, style={"width": "100%", "height": "100%"}),
                    width="100%",
                    background=rx.color("gray", 2),
                    border_radius="12px",
                    border=f"1px solid {rx.color('gray', 4)}",
                    padding="1em",
                ),
                # Show placeholder before first search
                rx.box(
                    rx.center(
                        rx.vstack(
                            rx.icon("chart-candlestick", size=48, color=rx.color("gray", 6)),
                            rx.text(
                                "Enter a ticker symbol and click Search",
                                color=rx.color("gray", 9),
                                size="3",
                            ),
                            spacing="3",
                            align="center",
                        ),
                        height="700px",
                    ),
                    width="100%",
                    background=rx.color("gray", 2),
                    border_radius="12px",
                    border=f"1px solid {rx.color('gray', 4)}",
                    padding="1em",
                ),
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


def _tabbed_stats() -> rx.Component:
    """Tabbed interface for Technical and Fundamental indicators."""
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Technical", value="technical"),
            rx.cond(
                ResearchState.has_fundamentals,
                rx.tabs.trigger("Fundamentals", value="fundamentals"),
                rx.fragment(),
            ),
        ),
        rx.tabs.content(
            _technical_stats_row(),
            value="technical",
            padding_top="1em",
        ),
        rx.tabs.content(
            rx.cond(
                ResearchState.has_fundamentals,
                _fundamental_stats_row(),
                _no_fundamentals_message(),
            ),
            value="fundamentals",
            padding_top="1em",
        ),
        value=ResearchState.active_tab,
        on_change=ResearchState.set_active_tab,
        width="100%",
    )


# --- Technical Indicator Badges ---

def _rsi_zone_badge() -> rx.Component:
    """Dynamic badge for RSI zone with color-coded buy/sell signal context."""
    return rx.match(
        ResearchState.rsi_zone,
        ("Oversold", rx.badge("Oversold", color_scheme="green")),
        ("Weak", rx.badge("Weak", color_scheme="orange")),
        ("Bullish", rx.badge("Bullish", color_scheme="blue")),
        ("Overbought", rx.badge("Overbought", color_scheme="red")),
        rx.badge(ResearchState.rsi_zone, color_scheme="gray"),
    )


def _volatility_zone_badge() -> rx.Component:
    """Dynamic badge for volatility zone relative to stock's own history."""
    return rx.match(
        ResearchState.volatility_zone,
        ("Low", rx.badge("Low", color_scheme="blue")),
        ("Normal", rx.badge("Normal", color_scheme="green")),
        ("High", rx.badge("High", color_scheme="red")),
        rx.badge(ResearchState.volatility_zone, color_scheme="gray"),
    )


def _technical_stats_row() -> rx.Component:
    """Row of stat cards for technical indicators."""
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
            "Next Earnings",
            ResearchState.next_earnings,
            ResearchState.next_earnings_detail,
            info_text="Next scheduled earnings announcement date. BMO = Before Market Open (pre-market), "
                      "AMC = After Market Close (after-hours). ETFs and index funds do not have earnings dates.",
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
                      "Low (<70% of avg), Normal (70-130%), High (>130%). SPY shown for market baseline.",
        ),
        stat_card("vs 50 MA", ResearchState.ma_50_pct),
        stat_card("vs 200 MA", ResearchState.ma_200_pct),
        stat_card("MACD", ResearchState.macd_signal),
        spacing="3",
        flex_wrap="wrap",
        width="100%",
    )


# --- Fundamental Indicator Badges ---

def _pe_zone_badge() -> rx.Component:
    """Dynamic badge for P/E ratio zone. Premium uses orange to indicate attention needed."""
    return rx.match(
        ResearchState.pe_zone,
        ("Value", rx.badge("Value", color_scheme="green")),
        ("Fair", rx.badge("Fair", color_scheme="gray")),
        ("Premium", rx.badge("Premium", color_scheme="orange")),
        ("Unprofitable", rx.badge("Unprofitable", color_scheme="red")),
        rx.badge(ResearchState.pe_zone, color_scheme="gray"),
    )


def _revenue_growth_badge() -> rx.Component:
    """Dynamic badge for revenue growth zone."""
    return rx.match(
        ResearchState.revenue_growth_zone,
        ("Accelerating", rx.badge("Accelerating", color_scheme="green")),
        ("Stable", rx.badge("Stable", color_scheme="gray")),
        ("Declining", rx.badge("Declining", color_scheme="red")),
        rx.badge(ResearchState.revenue_growth_zone, color_scheme="gray"),
    )


def _profit_margin_badge() -> rx.Component:
    """Dynamic badge for profit margin zone."""
    return rx.match(
        ResearchState.profit_margin_zone,
        ("Strong", rx.badge("Strong", color_scheme="green")),
        ("Average", rx.badge("Average", color_scheme="gray")),
        ("Weak", rx.badge("Weak", color_scheme="red")),
        rx.badge(ResearchState.profit_margin_zone, color_scheme="gray"),
    )


def _roe_badge() -> rx.Component:
    """Dynamic badge for ROE zone."""
    return rx.match(
        ResearchState.roe_zone,
        ("Strong", rx.badge("Strong", color_scheme="green")),
        ("Average", rx.badge("Average", color_scheme="gray")),
        ("Weak", rx.badge("Weak", color_scheme="red")),
        rx.badge(ResearchState.roe_zone, color_scheme="gray"),
    )


def _debt_to_equity_badge() -> rx.Component:
    """Dynamic badge for debt-to-equity zone."""
    return rx.match(
        ResearchState.debt_to_equity_zone,
        ("Conservative", rx.badge("Conservative", color_scheme="green")),
        ("Moderate", rx.badge("Moderate", color_scheme="gray")),
        ("Aggressive", rx.badge("Aggressive", color_scheme="red")),
        rx.badge(ResearchState.debt_to_equity_zone, color_scheme="gray"),
    )


def _fundamental_stats_row() -> rx.Component:
    """Row of stat cards for fundamental indicators."""
    return rx.hstack(
        stat_card(
            "P/E Ratio",
            ResearchState.pe_ratio,
            badge=_pe_zone_badge(),
            info_text="Price-to-Earnings ratio measures how much investors pay per dollar of earnings. "
                      "Value (<15) may indicate undervaluation, Fair (15-25) is typical, "
                      "Premium (>25) suggests growth expectations. Compare within same sector.",
        ),
        stat_card(
            "Revenue Growth",
            ResearchState.revenue_growth,
            badge=_revenue_growth_badge(),
            info_text="Year-over-year revenue change. Accelerating (>10%) indicates strong expansion, "
                      "Stable (0-10%) is healthy maintenance, Declining (<0%) warrants investigation.",
        ),
        stat_card(
            "Profit Margin",
            ResearchState.profit_margin,
            badge=_profit_margin_badge(),
            info_text="Net profit margin shows what percentage of revenue becomes profit after all expenses. "
                      "Strong (>15%) indicates pricing power, Average (5-15%) is typical, "
                      "Weak (<5%) may signal competitive pressure or inefficiency.",
        ),
        stat_card(
            "ROE",
            ResearchState.roe,
            badge=_roe_badge(),
            info_text="Return on Equity measures how efficiently the company generates profit from shareholder capital. "
                      "Strong (>15%) indicates effective management, Average (8-15%) is acceptable, "
                      "Weak (<8%) suggests poor capital efficiency.",
        ),
        stat_card(
            "Debt/Equity",
            ResearchState.debt_to_equity,
            badge=_debt_to_equity_badge(),
            info_text="Debt-to-Equity ratio shows financial leverage. Conservative (<0.5) means low risk, "
                      "Moderate (0.5-1.5) is typical, Aggressive (>1.5) indicates higher financial risk. "
                      "Capital-intensive industries naturally carry more debt.",
        ),
        spacing="3",
        flex_wrap="wrap",
        width="100%",
    )


def _no_fundamentals_message() -> rx.Component:
    """Message shown when fundamental data is not available (ETFs, etc.)."""
    return rx.box(
        rx.hstack(
            rx.icon("info", size=16, color="gray"),
            rx.text(
                "Fundamental data is not available for ETFs and index funds. "
                "Use the Technical tab for analysis.",
                size="2",
                color="gray",
            ),
            spacing="2",
            align="center",
        ),
        padding="1em",
        background=rx.color("gray", 2),
        border_radius="8px",
        border=f"1px solid {rx.color('gray', 4)}",
    )
