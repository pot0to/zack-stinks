"""Stock Research page UI."""
import reflex as rx
from ..components.sidebar import sidebar
from ..components.disclaimer import disclaimer_banner
from ..state.research import ResearchState


def stat_card(label: str, value: rx.Var, sub_value: rx.Var = None, sub_color: str = "gray"):
    """Reusable stat card component."""
    return rx.box(
        rx.vstack(
            rx.text(label, size="1", color="gray"),
            rx.text(value, size="6", weight="bold", color="white"),
            rx.cond(
                sub_value != None,
                rx.text(sub_value, size="2", color=sub_color),
                rx.fragment(),
            ),
            spacing="1",
            align_items="start",
        ),
        padding="1em",
        background="rgba(255,255,255,0.02)",
        border_radius="8px",
        border="1px solid rgba(255,255,255,0.05)",
        min_width="140px",
    )


def research():
    """Stock Research page layout."""
    return rx.vstack(
        disclaimer_banner(),
        rx.box(
            sidebar(),
            rx.box(
                rx.vstack(
                    # Page header
                    rx.hstack(
                        rx.icon(tag="search", size=28, color="#a855f7"),
                        rx.text("Stock Research", size="6", weight="bold", color="white"),
                        align="center",
                        spacing="3",
                    ),

                    # Input controls
                    rx.hstack(
                        rx.box(
                            rx.vstack(
                                rx.text("Symbol", size="1", color="gray"),
                                rx.input(
                                    value=ResearchState.ticker,
                                    on_change=ResearchState.set_ticker,
                                    placeholder="AAPL",
                                    background="rgba(255,255,255,0.05)",
                                    border="1px solid rgba(255,255,255,0.1)",
                                    color="white",
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
                            rx.cond(
                                ResearchState.is_loading,
                                rx.spinner(size="1"),
                                rx.text("Search"),
                            ),
                            on_click=ResearchState.fetch_stock_data,
                            background="#a855f7",
                            color="white",
                            _hover={"background": "#9333ea"},
                            margin_top="1.25em",
                        ),
                        spacing="4",
                        align="end",
                        width="100%",
                    ),

                    # Stats row
                    rx.hstack(
                        stat_card("Price", ResearchState.current_price, ResearchState.price_change_pct),
                        stat_card("52W High", ResearchState.high_52w),
                        stat_card("RSI (14)", ResearchState.rsi_14),
                        stat_card("Volatility", ResearchState.volatility),
                        stat_card("vs 50 MA", ResearchState.ma_50_pct),
                        stat_card("vs 200 MA", ResearchState.ma_200_pct),
                        stat_card("MACD", ResearchState.macd_signal),
                        spacing="3",
                        flex_wrap="wrap",
                        width="100%",
                    ),

                    # Chart
                    rx.box(
                        rx.plotly(data=ResearchState.price_chart, style={"width": "100%", "height": "100%"}),
                        width="100%",
                        background="rgba(255,255,255,0.02)",
                        border_radius="12px",
                        border="1px solid rgba(255,255,255,0.05)",
                        padding="1em",
                    ),

                    spacing="5",
                    width="100%",
                    padding="2em",
                ),
                margin_left=rx.cond(ResearchState.sidebar_open, "240px", "64px"),
                transition="margin-left 0.3s ease",
                min_height="100vh",
                background="#0a0a0a",
            ),
        ),
        spacing="0",
        width="100%",
    )
