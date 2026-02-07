import reflex as rx
from ..components.sidebar import sidebar
from ..state import MarketState

def market():
    return rx.hstack(
        sidebar(),
        market_overview()
    )

def market_overview():
    return rx.container(
        rx.vstack(
            rx.heading("Market Overview", size="8", weight="bold"),
            rx.grid(
                rx.foreach(
                    MarketState.market_data,
                    lambda x: market_card(x[0], x[1])
                ),
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
        ),
        padding="4em",
        caret_color="transparent",
        size="4"
    )

def market_card(label: str, values: dict):
    return rx.card(
        rx.vstack(
            rx.text(label, font_weight="bold", color="gray"),
            # Direct access = No quotes
            rx.heading(f"$", values["price"], size="6"), 
            rx.text(
                values["change"],
                # We convert to float just for the color logic check
                color=rx.cond(values["change"].to(float) >= 0, "green", "red"),
                font_weight="medium"
            ),
            align_items="start",
        )
    )