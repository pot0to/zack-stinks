import reflex as rx
# Import both so the sidebar can see global UI state AND specific market data
from ..state import State, MarketState, PortfolioState

def sidebar():
    return rx.box(
        rx.vstack(
            # --- HEADER SECTION ---
            rx.hstack(
                rx.button(
                    rx.icon(tag="menu", color="white", size=24),
                    on_click=State.toggle_sidebar, # BaseState owns the toggle
                    background="transparent",
                    _hover={"background": "rgba(255, 255, 255, 0.1)"},
                    _focus={"box_shadow": "none"},
                    padding="0.75em",
                    border_radius="8px",
                ),
                rx.cond(
                    State.sidebar_open,
                    rx.text(
                        "Zack Stinks",
                        font_size="1.25em",
                        weight="bold",
                        color="#a855f7",
                        white_space="nowrap",
                        margin_left="-0.25em", 
                    ),
                ),
                align="center",
                spacing="2",
                padding="0.5em",
                width="100%",
            ),

            # --- NAVIGATION LINKS ---
            rx.cond(
                State.sidebar_open,
                rx.vstack(
                    rx.link(
                        rx.hstack(rx.icon(tag="layout-dashboard", size=20), rx.text("Dashboard")),
                        href="/",
                        padding="0.75em 1.25em",
                        width="100%",
                        border_radius="8px",
                        _hover={"background": "rgba(255,255,255,0.05)", "color": "#a855f7"},
                    ),
                    rx.link(
                        rx.hstack(rx.icon(tag="briefcase", size=20), rx.text("Portfolio")),
                        href="/portfolio",
                        padding="0.75em 1.25em",
                        width="100%",
                        border_radius="8px",
                        _hover={"background": "rgba(255,255,255,0.05)", "color": "#a855f7"},
                    ),
                    spacing="1",
                    padding_x="0.5em",
                    width="240px",
                ),
            ),

            rx.spacer(),

            # --- STATUS INDICATOR (conditional on login state) ---
            rx.box(
                rx.cond(
                    State.sidebar_open,
                    # Expanded sidebar: show full status card
                    rx.cond(
                        State.is_logged_in,
                        # Connected state
                        rx.hstack(
                            rx.box(
                                width="10px",
                                height="10px",
                                background_color="rgb(34, 197, 94)",
                                border_radius="50%",
                                box_shadow="0 0 10px rgba(34, 197, 94, 0.6)",
                            ),
                            rx.vstack(
                                rx.text(f"Connected as {State.account_name}", size="1", weight="bold", color="white"),
                                rx.text("Robinhood Active", size="1", color="gray"),
                                spacing="0",
                                align_items="start",
                            ),
                            align="center",
                            spacing="3",
                            background="rgba(34, 197, 94, 0.1)",
                            padding="0.75em 1em",
                            border_radius="10px",
                            margin="1em",
                            width="calc(100% - 2em)",
                            border="1px solid rgba(34, 197, 94, 0.2)",
                        ),
                        # Disconnected state
                        rx.hstack(
                            rx.box(
                                width="10px",
                                height="10px",
                                background_color="rgb(156, 163, 175)",
                                border_radius="50%",
                            ),
                            rx.vstack(
                                rx.text("Not Connected", size="1", weight="bold", color="white"),
                                rx.text("Robinhood Offline", size="1", color="gray"),
                                spacing="0",
                                align_items="start",
                            ),
                            align="center",
                            spacing="3",
                            background="rgba(156, 163, 175, 0.1)",
                            padding="0.75em 1em",
                            border_radius="10px",
                            margin="1em",
                            width="calc(100% - 2em)",
                            border="1px solid rgba(156, 163, 175, 0.2)",
                        ),
                    ),
                    # Collapsed sidebar: show only status dot
                    rx.center(
                        rx.box(
                            width="12px",
                            height="12px",
                            background_color=rx.cond(
                                State.is_logged_in,
                                "rgb(34, 197, 94)",
                                "rgb(156, 163, 175)",
                            ),
                            border_radius="50%",
                            box_shadow=rx.cond(
                                State.is_logged_in,
                                "0 0 12px rgba(34, 197, 94, 0.8)",
                                "none",
                            ),
                        ),
                        width="100%",
                        padding_bottom="2em",
                    ),
                ),
                width="100%",
            ),
            height="100%",
            align_items="start",
        ),
        height="100vh",
        position="fixed",
        left="0",
        top="0",
        z_index="100",
        background_color="rgba(15, 15, 15, 0.98)",
        border_right="1px solid rgba(255,255,255,0.05)",
        width=rx.cond(State.sidebar_open, "240px", "64px"),
        transition="width 0.3s ease",
        overflow="hidden",
    )