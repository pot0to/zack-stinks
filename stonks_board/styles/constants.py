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
MASK_ACCOUNTS = "********, ********"  # Multi-account strings

# Disclaimer banner colors
DISCLAIMER_BG = "rgb(254, 249, 195)"
DISCLAIMER_TEXT = "rgb(133, 100, 0)"
DISCLAIMER_ICON = "rgb(161, 128, 0)"
DISCLAIMER_BORDER = "rgb(234, 219, 102)"

# Treemap P/L color buckets for lifetime portfolio performance
# Designed for long-term holdings where gains/losses can exceed 100%.
# Thresholds: 5%, 15%, 30%, 50%, 100%, 200%+
#
# Each bucket is (threshold_pct, rgb_tuple) - threshold is the UPPER bound
# Colors progress from pale (near breakeven) to deep/saturated (large moves)

PL_GAIN_BUCKETS = [
    (5.0, (200, 235, 205)),     # 0-5%: Light green (visible tint, not white)
    (15.0, (175, 220, 180)),    # 5-15%: Light-medium green
    (30.0, (145, 205, 155)),    # 15-30%: Medium-light green
    (50.0, (102, 187, 106)),    # 30-50%: Medium green
    (100.0, (67, 160, 71)),     # 50-100%: Medium-dark green
    (200.0, (46, 125, 50)),     # 100-200%: Dark green (doubled)
    (float('inf'), (27, 94, 32)),  # 200%+: Deep green (multi-bagger)
]

PL_LOSS_BUCKETS = [
    (5.0, (255, 210, 215)),     # 0-5%: Light red/pink (visible tint, not white)
    (15.0, (250, 180, 185)),    # 5-15%: Light-medium red
    (30.0, (240, 150, 155)),    # 15-30%: Medium-light red
    (50.0, (229, 115, 115)),    # 30-50%: Medium red
    (100.0, (211, 47, 47)),     # 50-100%: Medium-dark red (significant loss)
    (200.0, (183, 28, 28)),     # 100-200%: Dark red (severe, e.g. options)
    (float('inf'), (127, 0, 0)),   # 200%+: Deep red (catastrophic)
]

# Neutral gray for N/A values
PL_NEUTRAL = (128, 128, 128)

# Cash position color (light blue to distinguish from P/L spectrum and N/A gray)
CASH_COLOR = (135, 180, 220)
