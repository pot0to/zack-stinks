# StonksBoard - Portfolio Dashboard

A personal stock portfolio dashboard built with Reflex that integrates with Robinhood to display your holdings, track performance, and provide technical analysis tools. Designed for self-directed investors and swing traders who want deeper market insights than Robinhood's native interface provides.

## Features

**Market Overview**
- Real-time market indices (S&P 500, Nasdaq, Dow Jones, VIX) with daily changes and 1-month high/low
- 30-day momentum trend chart comparing major indices
- Portfolio Spotlight alerts for your holdings: price gaps, trend signals (Golden Cross/Death Cross), MA proximity, below 200d MA, near 52-week highs, and upcoming earnings

**Portfolio Management**
- Multi-account support with tab switching
- Daily P/L tracking with S&P 500 benchmark comparison
- Treemap visualization with P/L-based color gradients
- Stock and options holdings tables (sortable by multiple columns)
- Sector exposure breakdown (donut chart, excludes index funds)
- Per-ticker delta exposure combining stocks and options
- 52-week range position with visual progress bars
- Earnings urgency badges (red 0-3 days, yellow 4-7 days)
- Privacy mode (hides dollar amounts and account names for screen sharing)

**Stock Research**
- Ticker search with period selector (1mo to 2y)
- Technical indicators: RSI (14-day), MACD, 50/200-day moving averages, volatility
- Fundamental indicators: P/E ratio, revenue growth, profit margin, ROE, debt-to-equity
- Interactive candlestick chart with volume and MA overlays

## Project Structure

```
stonks_board/
├── stonks_board.py       # App entry point and route definitions
├── analyzer.py           # Market analysis and signal detection
├── components/
│   ├── cards.py          # Reusable card components
│   ├── disclaimer.py     # Disclaimer banner
│   ├── layout.py         # Shared page layout wrapper
│   ├── sidebar.py        # Navigation sidebar
│   └── skeleton.py       # Loading skeleton components
├── pages/
│   ├── login.py          # Authentication page
│   ├── market.py         # Market overview page (/)
│   ├── portfolio.py      # Portfolio page (/portfolio)
│   └── research.py       # Research page (/research)
├── state/
│   ├── base.py           # Shared state and authentication
│   ├── market.py         # Market page state
│   ├── portfolio.py      # Portfolio page state
│   └── research.py       # Research page state
├── styles/
│   └── constants.py      # Centralized theming constants
└── utils/
    ├── api_limits.py     # API rate limiting
    ├── auth.py           # Credential loading (dev fallback)
    ├── cache.py          # API response caching
    ├── symbols.py        # Symbol classification
    └── technical.py      # Technical indicator calculations
```

## Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A Robinhood account

### Installation

**macOS:**
```bash
# Install Python if needed
brew install python@3.11

# Navigate to where you want to store the project
cd ~/Documents

# Clone the repository
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows (Git Bash):**

Git Bash is included with Git for Windows and provides a Unix-like terminal experience.

```bash
# 1. Install Python from https://www.python.org/downloads/ (3.11+)
#    IMPORTANT: Use the python.org installer, NOT the Microsoft Store version
#    During installation, check "Add Python to PATH"

# 2. Install Git from https://git-scm.com/download/win
#    Use default options during installation

# 3. Open Git Bash (right-click in any folder > "Git Bash Here", or search for it)

# 4. Navigate to where you want to store the project
cd ~/Documents

# 5. Clone and enter the repository
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks

# 6. Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate

# 7. Install dependencies
pip install -r requirements.txt
```

**Troubleshooting Windows Python Issues:**

If you see "Python was not found; run without arguments to install from the Microsoft Store", Windows is intercepting the `python` command. Go to Settings > Apps > Advanced app settings > App execution aliases, then turn off the toggles for "python.exe" and "python3.exe". Close and reopen Git Bash for the changes to take effect.

If you forgot to check "Add Python to PATH" during installation, reinstall Python with that option checked, or manually add the Python installation folder and its `Scripts` subfolder to your PATH via Settings > System > About > Advanced system settings > Environment Variables.

### Configuration

**Option 1: Login Form (Recommended)**

Run the app and use the login form to enter your Robinhood email and password. Your credentials are sent directly to Robinhood over HTTPS and are not stored locally. If MFA is required, you'll be prompted to enter your code in the web UI.

**Option 2: credentials.json (Fallback)**

If the login form doesn't work for you, create a `credentials.json` file in the project root:

```json
{
    "username": "your_robinhood_email",
    "password": "your_robinhood_password"
}
```

Then click "Use credentials.json instead" on the login page.

**Session Persistence:** The robin_stocks library stores session tokens locally (at `~/.tokens/robinhood.pickle` on macOS or `C:\Users\<username>\.tokens\robinhood.pickle` on Windows), so you won't need to log in every time.

### Running the App

```bash
# Activate virtual environment (if not already active)
# macOS:
source .venv/bin/activate
# Windows (Git Bash):
source .venv/Scripts/activate

# Start the development server
reflex run
```

On first run, Reflex will compile the frontend which may take a minute or two. Once you see "App running at" in the terminal, open `http://localhost:3000` in your browser. To stop the app, press `Ctrl+C` in the terminal.

### Updating the Project

To pull the latest changes when the project is updated:

```bash
# Navigate to the project directory
cd zack-stinks

# Activate virtual environment
# macOS:
source .venv/bin/activate
# Windows (Git Bash):
source .venv/Scripts/activate

# Pull latest changes
git pull

# Install any new dependencies
pip install -r requirements.txt

# Start the app
reflex run
```

## Dependencies

- **reflex** - Full-stack Python web framework
- **robin_stocks** - Robinhood API client
- **yfinance** - Yahoo Finance market data
- **plotly** - Interactive charts
- **pandas** - Data processing
- **lxml** - HTML/XML parsing

## Technical Notes

The dashboard uses a two-phase loading pattern for portfolio data. Phase 1 fetches core holdings and prices (blocking), while Phase 2 runs background analysis for sector exposure, 52-week ranges, and earnings data (non-blocking). This keeps the UI responsive while enriching data in the background.

API responses are cached with appropriate TTLs (1-5 minutes for volatile data, 24 hours for static data) to minimize API calls and improve performance.
