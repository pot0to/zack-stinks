"""Sidebar navigation component."""
import reflex as rx
from ..state import State
from ..styles.constants import (
    SIDEBAR_WIDTH_OPEN,
    SIDEBAR_WIDTH_COLLAPSED,
    ACCENT_PRIMARY,
    ACCENT_PRIMARY_HOVER,
    COLOR_SUCCESS,
    COLOR_NEUTRAL,
    BG_SIDEBAR,
    BG_HOVER,
    BORDER_SUBTLE,
)


def _nav_link(icon: str, label: str, href: str) -> rx.Component:
    """Navigation link with icon."""
    return rx.link(
        rx.hstack(rx.icon(tag=icon, size=20), rx.text(label)),
        href=href,
        padding="0.75em 1.25em",
        width="100%",
        border_radius="8px",
        _hover={"background": BG_HOVER, "color": ACCENT_PRIMARY},
    )


def _status_indicator() -> rx.Component:
    """Connection status indicator at bottom of sidebar."""
    connected_card = rx.hstack(
        rx.box(
            width="10px",
            height="10px",
            background_color=COLOR_SUCCESS,
            border_radius="50%",
            box_shadow=f"0 0 10px rgba(34, 197, 94, 0.6)",
        ),
        rx.vstack(
            rx.text(f"Connected as {State.account_name}", size="1", weight="bold"),
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
    )

    disconnected_card = rx.hstack(
        rx.box(
            width="10px",
            height="10px",
            background_color=COLOR_NEUTRAL,
            border_radius="50%",
        ),
        rx.vstack(
            rx.text("Not Connected", size="1", weight="bold"),
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
    )

    collapsed_dot = rx.center(
        rx.box(
            width="12px",
            height="12px",
            background_color=rx.cond(State.is_logged_in, COLOR_SUCCESS, COLOR_NEUTRAL),
            border_radius="50%",
            box_shadow=rx.cond(State.is_logged_in, "0 0 12px rgba(34, 197, 94, 0.8)", "none"),
        ),
        width="100%",
        padding_bottom="2em",
    )

    return rx.box(
        rx.cond(
            State.sidebar_open,
            rx.cond(State.is_logged_in, connected_card, disconnected_card),
            collapsed_dot,
        ),
        width="100%",
    )


def sidebar() -> rx.Component:
    """Main sidebar navigation component."""
    return rx.box(
        rx.vstack(
            # Header with toggle
            rx.hstack(
                rx.button(
                    rx.icon(tag="menu", size=24),
                    on_click=State.toggle_sidebar,
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
                        color=ACCENT_PRIMARY,
                        white_space="nowrap",
                        margin_left="-0.25em",
                    ),
                ),
                align="center",
                spacing="2",
                padding="0.5em",
                width="100%",
            ),
            # Navigation links (only when expanded)
            rx.cond(
                State.sidebar_open,
                rx.vstack(
                    _nav_link("layout-dashboard", "Dashboard", "/"),
                    _nav_link("briefcase", "Portfolio", "/portfolio"),
                    _nav_link("search", "Stock Research", "/research"),
                    spacing="1",
                    padding_x="0.5em",
                    width=SIDEBAR_WIDTH_OPEN,
                ),
            ),
            rx.spacer(),
            _status_indicator(),
            height="100%",
            align_items="start",
        ),
        height="100vh",
        position="fixed",
        left="0",
        top="0",
        z_index="100",
        background_color=BG_SIDEBAR,
        border_right=BORDER_SUBTLE,
        width=rx.cond(State.sidebar_open, SIDEBAR_WIDTH_OPEN, SIDEBAR_WIDTH_COLLAPSED),
        transition="width 0.3s ease",
        overflow="hidden",
    )