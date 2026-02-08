"""Data disclaimer banner component."""
import reflex as rx
from ..styles.constants import SIDEBAR_WIDTH_COLLAPSED


# Disclaimer-specific colors (not in main constants as they're unique to this component)
_DISCLAIMER_BG = "rgb(254, 249, 195)"
_DISCLAIMER_TEXT = "rgb(133, 100, 0)"
_DISCLAIMER_ICON = "rgb(161, 128, 0)"
_DISCLAIMER_BORDER = "rgb(234, 219, 102)"


def disclaimer_banner() -> rx.Component:
    """Pale yellow disclaimer banner for data limitations."""
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=16, color=_DISCLAIMER_ICON),
            rx.text(
                "Market data is for informational purposes only. "
                "Prices may be delayed 15-30 minutes. "
                "Data from unofficial APIs; accuracy not guaranteed. "
                "Not investment advice.",
                size="1",
                color=_DISCLAIMER_TEXT,
            ),
            spacing="2",
            align="center",
            justify="center",
            width="100%",
        ),
        background=_DISCLAIMER_BG,
        padding="0.5em 1em",
        padding_left=f"calc({SIDEBAR_WIDTH_COLLAPSED} + 16px)",
        width="100%",
        border_bottom=f"1px solid {_DISCLAIMER_BORDER}",
    )
