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
        spacing="0",
        width="100%",
    )
