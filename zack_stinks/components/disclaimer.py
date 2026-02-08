"""Data disclaimer banner component."""
import reflex as rx


def disclaimer_banner() -> rx.Component:
    """Pale yellow disclaimer banner for data limitations."""
    return rx.box(
        rx.hstack(
            rx.icon("triangle-alert", size=16, color="rgb(161, 128, 0)"),
            rx.text(
                "Market data is for informational purposes only. "
                "Prices may be delayed 15-30 minutes. "
                "Data from unofficial APIs; accuracy not guaranteed. "
                "Not investment advice.",
                size="1",
                color="rgb(133, 100, 0)",
            ),
            spacing="2",
            align="center",
            justify="center",
            width="100%",
        ),
        background="rgb(254, 249, 195)",
        padding="0.5em 1em",
        padding_left="80px",  # Account for collapsed sidebar (64px + some margin)
        width="100%",
        border_bottom="1px solid rgb(234, 219, 102)",
    )
