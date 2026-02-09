"""Skeleton loader components for progressive data loading.

Skeleton loaders communicate "loading" state without implying errors or missing data.
They maintain layout stability by reserving exact space for content.
"""
import reflex as rx


def skeleton_box(
    width: str = "80px",
    height: str = "20px",
    border_radius: str = "4px",
) -> rx.Component:
    """Basic skeleton box with pulse animation.
    
    Args:
        width: Box width (CSS value)
        height: Box height (CSS value)
        border_radius: Corner radius
    """
    return rx.box(
        width=width,
        height=height,
        background=rx.color("gray", 4),
        border_radius=border_radius,
        class_name="skeleton-pulse",
    )


def skeleton_text(width: str = "60px", size: str = "sm") -> rx.Component:
    """Skeleton placeholder for text content.
    
    Args:
        width: Text width
        size: Text size (sm, md, lg) affects height
    """
    heights = {"sm": "14px", "md": "20px", "lg": "28px"}
    return skeleton_box(width=width, height=heights.get(size, "16px"))


def skeleton_badge() -> rx.Component:
    """Skeleton placeholder for badge components."""
    return skeleton_box(width="24px", height="20px", border_radius="9999px")


def skeleton_range_bar() -> rx.Component:
    """Skeleton placeholder for 52-week range progress bar."""
    return rx.vstack(
        rx.box(
            width="60px",
            height="6px",
            background=rx.color("gray", 5),
            border_radius="2px",
            class_name="skeleton-pulse",
        ),
        rx.box(
            width="30px",
            height="12px",
            background=rx.color("gray", 4),
            border_radius="2px",
            class_name="skeleton-pulse",
        ),
        spacing="1",
        align="center",
    )


def skeleton_stat_card(label: str) -> rx.Component:
    """Skeleton placeholder for stat cards during loading.
    
    Maintains exact dimensions of real stat cards to prevent layout shift.
    """
    return rx.box(
        rx.vstack(
            rx.text(label, size="1", color=rx.color("gray", 10)),
            skeleton_box(width="80px", height="24px"),
            skeleton_box(width="50px", height="16px"),
            spacing="1",
            align_items="start",
        ),
        padding="1em",
        background=rx.color("gray", 2),
        border_radius="8px",
        border=f"1px solid {rx.color('gray', 4)}",
        min_width="140px",
    )


def skeleton_donut_chart() -> rx.Component:
    """Skeleton placeholder for donut/pie charts.
    
    Shows a gray ring to indicate chart is loading.
    """
    return rx.center(
        rx.box(
            rx.box(
                width="120px",
                height="120px",
                background=rx.color("gray", 2),
                border_radius="50%",
                position="absolute",
                top="50%",
                left="50%",
                transform="translate(-50%, -50%)",
            ),
            width="200px",
            height="200px",
            background=rx.color("gray", 4),
            border_radius="50%",
            position="relative",
            class_name="skeleton-pulse",
        ),
        width="100%",
        height="280px",
    )


def skeleton_table_rows(num_rows: int = 3, num_cols: int = 5) -> rx.Component:
    """Skeleton placeholder for table content.
    
    Args:
        num_rows: Number of skeleton rows to show
        num_cols: Number of columns per row
    """
    def skeleton_row():
        return rx.table.row(
            *[rx.table.cell(skeleton_box(width="60px", height="16px")) for _ in range(num_cols)]
        )
    
    return rx.table.body(
        *[skeleton_row() for _ in range(num_rows)]
    )


def inline_spinner(text: str = "Loading...") -> rx.Component:
    """Small inline spinner with optional text for subtle loading indication."""
    return rx.hstack(
        rx.spinner(size="1"),
        rx.text(text, size="1", color="gray"),
        spacing="2",
        align="center",
    )
