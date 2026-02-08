"""Centralized style constants for consistent theming across the app."""

# Sidebar dimensions
SIDEBAR_WIDTH_OPEN = "240px"
SIDEBAR_WIDTH_COLLAPSED = "64px"

# Content margins (sidebar width + gap)
CONTENT_MARGIN_OPEN = "250px"
CONTENT_MARGIN_COLLAPSED = "74px"

# Accent colors
ACCENT_PRIMARY = "#a855f7"
ACCENT_PRIMARY_HOVER = "#9333ea"

# Status colors
COLOR_SUCCESS = "rgb(34, 197, 94)"
COLOR_ERROR = "rgb(239, 68, 68)"
COLOR_WARNING = "rgb(250, 204, 21)"
COLOR_NEUTRAL = "rgb(156, 163, 175)"

# Borders - now using theme-aware approach via rx.color() in components
# Legacy static values kept for reference:
# BORDER_SUBTLE = "1px solid rgba(255,255,255,0.05)"
# BORDER_CARD = "1px solid rgba(255,255,255,0.1)"

# Backgrounds - now using theme-aware approach via rx.color() in components
# Legacy static values kept for reference:
# BG_CARD = "rgba(255,255,255,0.02)"
# BG_HOVER = "rgba(255,255,255,0.05)"
# BG_SIDEBAR = "rgba(15, 15, 15, 0.98)"

# Spacing
CONTENT_PADDING = "2em"
CARD_PADDING = "1em"

# Container size (Reflex container size prop)
CONTAINER_SIZE = "4"

# Privacy mask strings (fixed-length to prevent layout shift)
MASK_SHARES = "******"     # ~123.4567
MASK_DOLLAR = "********"   # ~$12,345.67
MASK_PERCENT = "*****"     # ~12.34%
MASK_DELTA = "******"      # ~0.1234

# Disclaimer banner colors
DISCLAIMER_BG = "rgb(254, 249, 195)"
DISCLAIMER_TEXT = "rgb(133, 100, 0)"
DISCLAIMER_ICON = "rgb(161, 128, 0)"
DISCLAIMER_BORDER = "rgb(234, 219, 102)"

# Treemap P/L color gradients (base -> deep for intensity interpolation)
# Green gradient for gains
PL_GREEN_BASE = (187, 247, 208)
PL_GREEN_DEEP = (34, 197, 94)
# Red gradient for losses
PL_RED_BASE = (254, 202, 202)
PL_RED_DEEP = (239, 68, 68)
# Neutral gray for N/A
PL_NEUTRAL = (128, 128, 128)
