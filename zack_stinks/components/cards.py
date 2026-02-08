"""Reusable card components for displaying metrics and stats."""
import reflex as rx
from ..styles.constants import CARD_PADDING


def stat_card(
    label: str,
    value: rx.Var,
    sub_value: rx.Var = None,
    sub_color = "gray",
    badge: rx.Component = None,
    info_text: str = None,
) -> rx.Component:
    """Unified stat card for displaying metrics.
    
    Args:
        label: Card title/label
        value: Main value to display
        sub_value: Optional secondary value (e.g., percentage change)
        sub_color: Color for sub_value text (can be string or rx.cond for dynamic color)
        badge: Optional badge component to display
        info_text: Optional explanation text shown in popover on info icon click
    """
    # Build label row with optional info icon
    if info_text:
        label_row = rx.hstack(
            rx.text(label, size="1", color=rx.color("gray", 10)),
            rx.popover.root(
                rx.popover.trigger(
                    rx.icon("info", size=12, color="gray", cursor="pointer"),
                ),
                rx.popover.content(
                    rx.text(info_text, size="2"),
                    side="top",
                    max_width="280px",
                ),
            ),
            spacing="1",
            align="center",
        )
    else:
        label_row = rx.text(label, size="1", color=rx.color("gray", 10))
    
    children = [
        label_row,
        rx.text(value, size="6", weight="bold"),
    ]
    if badge is not None:
        children.append(badge)
    if sub_value is not None:
        children.append(rx.text(sub_value, size="2", color=sub_color))
    
    return rx.box(
        rx.vstack(*children, spacing="1", align_items="start"),
        padding=CARD_PADDING,
        background=rx.color("gray", 2),
        border_radius="8px",
        border=f"1px solid {rx.color('gray', 4)}",
        min_width="140px",
    )


def metric_card(
    title: str,
    value: rx.Var,
    subtext: str = "",
    badge: rx.Component = None,
) -> rx.Component:
    """Metric card with optional subtext and badge.
    
    Args:
        title: Card title
        value: Main metric value
        subtext: Optional description text below value
        badge: Optional badge component
    """
    children = [
        rx.text(title, size="2", color=rx.color("gray", 10), weight="medium"),
        rx.heading(value, size="7"),
    ]
    if badge is not None:
        children.append(badge)
    if subtext:
        children.append(rx.text(subtext, size="1", color=rx.color("gray", 9)))
    
    return rx.card(rx.vstack(*children, align_items="start", spacing="1"))
