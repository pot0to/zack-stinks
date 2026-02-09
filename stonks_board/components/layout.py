"""Shared page layout components."""
import reflex as rx
from ..state import State
from ..styles.constants import (
    CONTENT_MARGIN_OPEN,
    CONTENT_MARGIN_COLLAPSED,
    CONTENT_PADDING,
    CONTAINER_SIZE,
)
from .sidebar import sidebar
from .disclaimer import disclaimer_banner


def _global_loading_indicator() -> rx.Component:
    """Global loading indicator shown when portfolio data is being fetched.
    
    Appears in the bottom-right corner on any page, providing feedback that
    data is loading in the background. This ensures users know the dashboard
    is working even if they navigate away from the portfolio page.
    """
    return rx.cond(
        State.is_portfolio_loading,
        rx.box(
            rx.hstack(
                rx.spinner(size="1"),
                rx.text("Loading portfolio data...", size="2"),
                spacing="2",
                align="center",
            ),
            position="fixed",
            bottom="1em",
            right="1em",
            background="rgba(0, 0, 0, 0.85)",
            padding="0.75em 1em",
            border_radius="8px",
            z_index="999",
            color="white",
        ),
        rx.fragment(),
    )


def page_layout(content: rx.Component, use_container: bool = True) -> rx.Component:
    """Standard page layout wrapper with sidebar and disclaimer.
    
    Args:
        content: The page content to render
        use_container: Whether to wrap content in rx.container (default True)
    
    Returns:
        Complete page layout with sidebar, disclaimer, and content
    """
    wrapped_content = (
        rx.container(
            content,
            margin_left=rx.cond(State.sidebar_open, CONTENT_MARGIN_OPEN, CONTENT_MARGIN_COLLAPSED),
            transition="margin-left 0.3s ease",
            padding=CONTENT_PADDING,
            size=CONTAINER_SIZE,
        )
        if use_container
        else rx.box(
            content,
            margin_left=rx.cond(State.sidebar_open, CONTENT_MARGIN_OPEN, CONTENT_MARGIN_COLLAPSED),
            transition="margin-left 0.3s ease",
            padding=CONTENT_PADDING,
            width="100%",
        )
    )
    
    return rx.vstack(
        disclaimer_banner(),
        rx.hstack(
            sidebar(),
            wrapped_content,
            width="100%",
        ),
        _global_loading_indicator(),  # Shows on any page when portfolio is loading
        spacing="0",
        width="100%",
    )
