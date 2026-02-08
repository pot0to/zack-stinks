"""Data disclaimer banner component."""
import reflex as rx
from ..styles.constants import (
    SIDEBAR_WIDTH_COLLAPSED,
    DISCLAIMER_BG,
    DISCLAIMER_TEXT,
    DISCLAIMER_ICON,
    DISCLAIMER_BORDER,
)


def disclaimer_banner() -> rx.Component:
    """Pale yellow disclaimer banner for data limitations."""
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=16, color=DISCLAIMER_ICON),
            rx.text(
                "Market data is for informational purposes only. "
                "Prices may be delayed 15-30 minutes. "
                "Data from unofficial APIs; accuracy not guaranteed. "
                "Not investment advice.",
                size="1",
                color=DISCLAIMER_TEXT,
            ),
            spacing="2",
            align="center",
            justify="center",
            width="100%",
        ),
        background=DISCLAIMER_BG,
        padding="0.5em 1em",
        padding_left=f"calc({SIDEBAR_WIDTH_COLLAPSED} + 16px)",
        width="100%",
        border_bottom=f"1px solid {DISCLAIMER_BORDER}",
    )
