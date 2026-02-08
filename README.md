# Zack Stinks - Portfolio Dashboard

A personal stock portfolio dashboard built with Reflex that integrates with Robinhood to display your holdings, track performance, and provide technical analysis tools.

## Features

- **Market Overview**: Real-time market indices (S&P 500, Nasdaq, Dow Jones, VIX) with 30-day momentum chart
- **Portfolio Management**: Multi-account support with holdings breakdown, P/L tracking, and asset allocation treemap
- **Stock Research**: Technical analysis with RSI, MACD, moving averages, and interactive price charts
- **Portfolio Signals**: Gap event detection and moving average proximity alerts for your holdings

## Project Structure

```
zack_stinks/
├── zack_stinks.py        # App entry point and route definitions
├── analyzer.py           # Market analysis logic
├── components/
│   ├── __init__.py       # Component exports
│   ├── cards.py          # Reusable card components
│   ├── disclaimer.py     # Disclaimer banner
│   ├── layout.py         # Shared page layout wrapper
│   └── sidebar.py        # Navigation sidebar
├── pages/
│   ├── market.py         # Market overview page (/)
│   ├── portfolio.py      # Portfolio page (/portfolio)
│   └── research.py       # Research page (/research)
├── state/
│   ├── __init__.py       # State exports
│   ├── base.py           # Shared state
│   ├── market.py         # Market page state
│   ├── portfolio.py      # Portfolio page state
│   └── research.py       # Research page state
├── styles/
│   ├── __init__.py       # Style exports
│   └── constants.py      # Centralized theming constants
└── utils/
    ├── auth.py           # Credential loading
    ├── cache.py          # API response caching
    └── technical.py      # Technical indicators
```

## Setup

### Prerequisites

- Python 3.11 or higher
- A Robinhood account

### Installation

**macOS:**
```bash
# Install Python if needed
brew install python@3.11

# Clone the repository
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows:**
```powershell
# 1. Install Python from https://www.python.org/downloads/ (3.11+)
#    During installation, check "Add Python to PATH"

# 2. Install Git from https://git-scm.com/download/win
#    Use default options during installation

# 3. Open PowerShell or Command Prompt, then clone the repository
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks

# 4. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 5. Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `credentials.json` file in the project root:

```json
{
    "username": "your_robinhood_email",
    "password": "your_robinhood_password"
}
```

**Note:** Your credentials are transmitted securely over HTTPS to Robinhood's OAuth2 endpoint. The robin_stocks library stores session tokens locally at `~/.tokens/robinhood.pickle` for session persistence.

### Running the App

```bash
# Activate virtual environment (if not already active)
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Start the development server
reflex run
```

The app will be available at `http://localhost:3000`.

## Dependencies

- **reflex** - Web framework
- **robin_stocks** - Robinhood API client
- **yfinance** - Yahoo Finance market data
- **plotly** - Interactive charts
- **pandas** - Data processing
