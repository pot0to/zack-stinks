"""Reusable card components for displaying metrics and stats."""
import reflex as rx
from ..styles.constants import BG_CARD, BORDER_CARD, CARD_PADDING


def stat_card(
    label: str,
    value: rx.Var,
    sub_value: rx.Var = None,
    sub_color: str = "gray",
    badge: rx.Component = None,
) -> rx.Component:
    """Unified stat card for displaying metrics.
    
    Args:
        label: Card title/label
        value: Main value to display
        sub_value: Optional secondary value (e.g., percentage change)
        sub_color: Color for sub_value text
        badge: Optional badge component to display
    """
    children = [
        rx.text(label, size="1", color="gray"),
        rx.text(value, size="6", weight="bold"),
    ]
    if badge is not None:
        children.append(badge)
    if sub_value is not None:
        children.append(rx.text(sub_value, size="2", color=sub_color))
    
    return rx.box(
        rx.vstack(*children, spacing="1", align_items="start"),
        padding=CARD_PADDING,
        background=BG_CARD,
        border_radius="8px",
        border=BORDER_CARD,
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
        rx.text(title, size="2", color="gray", weight="medium"),
        rx.heading(value, size="7"),
    ]
    if badge is not None:
        children.append(badge)
    if subtext:
        children.append(rx.text(subtext, size="1", color="slate"))
    
    return rx.card(rx.vstack(*children, align_items="start", spacing="1"))
