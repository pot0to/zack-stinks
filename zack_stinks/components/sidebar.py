"""Sidebar navigation component with theme-adaptive styling."""
import reflex as rx
from ..state import State
from ..styles.constants import (
    SIDEBAR_WIDTH_OPEN,
    SIDEBAR_WIDTH_COLLAPSED,
    ACCENT_PRIMARY,
    COLOR_SUCCESS,
    COLOR_NEUTRAL,
)


def _nav_link(icon: str, label: str, href: str) -> rx.Component:
    """Navigation link with icon."""
    return rx.link(
        rx.hstack(rx.icon(tag=icon, size=20), rx.text(label)),
        href=href,
        padding="0.75em 1.25em",
        width="100%",
        border_radius="8px",
        _hover={"background": rx.color("gray", 4), "color": ACCENT_PRIMARY},
    )


def _privacy_toggle() -> rx.Component:
    """Toggle to hide portfolio values for screen sharing."""
    expanded_toggle = rx.hstack(
        rx.icon(
            rx.cond(State.hide_portfolio_values, "eye-off", "eye"),
            size=16,
            color=rx.color("gray", 11),
        ),
        rx.text(
            rx.cond(State.hide_portfolio_values, "Values Hidden", "Hide Values"),
            size="1",
            color=rx.color("gray", 11),
        ),
        align="center",
        spacing="2",
        padding="0.5em 1em",
        margin_x="0.5em",
        border_radius="8px",
        cursor="pointer",
        background=rx.cond(State.hide_portfolio_values, "rgba(168, 85, 247, 0.2)", "transparent"),
        _hover={"background": rx.color("gray", 4)},
        on_click=State.toggle_hide_values,
    )
    
    collapsed_toggle = rx.center(
        rx.icon(
            rx.cond(State.hide_portfolio_values, "eye-off", "eye"),
            size=18,
            color=rx.color("gray", 11),
            cursor="pointer",
            on_click=State.toggle_hide_values,
        ),
        width="100%",
        padding="0.5em",
    )
    
    return rx.cond(State.sidebar_open, expanded_toggle, collapsed_toggle)


def _status_indicator() -> rx.Component:
    """Connection status indicator at bottom of sidebar."""
    connected_card = rx.hstack(
        rx.box(
            width="10px",
            height="10px",
            background_color=COLOR_SUCCESS,
            border_radius="50%",
            box_shadow="0 0 10px rgba(34, 197, 94, 0.6)",
        ),
        rx.vstack(
            rx.text(
                f"Connected as {State.account_name}",
                size="1",
                weight="bold",
                color=rx.color("gray", 12),
            ),
            rx.text("Robinhood Active", size="1", color=rx.color("gray", 10)),
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
            rx.text(
                "Not Connected",
                size="1",
                weight="bold",
                color=rx.color("gray", 12),
            ),
            rx.text("Robinhood Offline", size="1", color=rx.color("gray", 10)),
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
                    _hover={"background": rx.color("gray", 4)},
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
            _privacy_toggle(),
            _status_indicator(),
            height="100%",
            align_items="start",
        ),
        height="100vh",
        position="fixed",
        left="0",
        top="0",
        z_index="100",
        background_color=rx.color("gray", 2),
        border_right=f"1px solid {rx.color('gray', 4)}",
        width=rx.cond(State.sidebar_open, SIDEBAR_WIDTH_OPEN, SIDEBAR_WIDTH_COLLAPSED),
        transition="width 0.3s ease",
        overflow="hidden",
    )
