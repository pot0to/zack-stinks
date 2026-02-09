"""Symbol classification utilities.

Provides functions to categorize securities (index funds vs individual stocks)
for display and analysis purposes.
"""

# Broad market index funds and sector ETFs that should be displayed separately
# from individual stock positions. These represent diversified exposure rather
# than single-company bets.
INDEX_FUND_SYMBOLS = frozenset({
    # S&P 500 trackers
    "VOO", "SPY", "IVV", "SPLG",
    # Total market
    "VTI", "ITOT", "SPTM",
    # Nasdaq / tech-heavy
    "QQQ", "QQQM", "VGT", "XLK",
    # Growth / Value
    "VUG", "VTV", "IWF", "IWD",
    # Small cap
    "IWM", "VB", "SCHA",
    # Mid cap
    "VO", "IJH", "SCHM",
    # Dow Jones
    "DIA",
    # Sector ETFs
    "SMH", "SOXX",  # Semiconductors
    "XLF", "VFH",   # Financials
    "XLE", "VDE",   # Energy
    "XLV", "VHT",   # Healthcare
    "XLI", "VIS",   # Industrials
    "XLB", "VAW",   # Materials
    "XLU", "VPU",   # Utilities
    "XLP", "VDC",   # Consumer staples
    "XLY", "VCR",   # Consumer discretionary
    "XLRE", "VNQ",  # Real estate
    "XLC",          # Communication services
    # International
    "VEA", "IEFA", "EFA",   # Developed markets
    "VWO", "IEMG", "EEM",   # Emerging markets
    "VXUS",                  # Total international
    # Bonds (if held)
    "BND", "AGG", "TLT", "IEF", "SHY",
    # Thematic / ARK
    "ARKK", "ARKW", "ARKF", "ARKG", "ARKQ",
    # Thematic / Other
    "FINX",  # Global FinTech
    "SPMO",  # S&P 500 Momentum
    "SHLD",  # Global X Defense Tech
    # Leveraged (common ones)
    "TQQQ", "SQQQ", "SPXL", "SPXS", "UPRO",
})


def is_index_fund(symbol: str) -> bool:
    """Check if a symbol is a broad market index fund or sector ETF.
    
    Used to separate diversified holdings from individual stock positions
    in portfolio displays and signal analysis.
    """
    return symbol.upper() in INDEX_FUND_SYMBOLS
