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

# Navigate to where you want to store the project (e.g., Documents or a Dev folder)
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

**Windows (Git Bash - Recommended):**

Git Bash is included with Git for Windows and uses Unix-style commands, making it the easiest option.

```bash
# 1. Install Python from https://www.python.org/downloads/ (3.11+)
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

**Windows (PowerShell):**
```powershell
# After installing Python and Git (see above)
cd ~\Documents
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (Command Prompt):**
```cmd
# After installing Python and Git (see above)
cd %USERPROFILE%\Documents
git clone https://github.com/pot0to/zack-stinks.git
cd zack-stinks
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If you forgot to check "Add Python to PATH" during installation, you can either reinstall Python with that option checked, or manually add it. To find your Python installation path, open Command Prompt and run `where python` (if Python runs at all) or check the default location at `C:\Users\<YourUsername>\AppData\Local\Programs\Python\`. Once you find the folder containing `python.exe`, add both that folder and its `Scripts` subfolder to your PATH via Settings > System > About > Advanced system settings > Environment Variables.

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

### Updating the Project

To pull the latest changes when the project is updated:

```bash
# Navigate to the project directory
cd zack-stinks

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate
# Windows (Git Bash):
source .venv/Scripts/activate
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate

# Pull latest changes
git pull

# Install any new dependencies
pip install -r requirements.txt

# Restart the app
reflex run
```

## Dependencies

- **reflex** - Web framework
- **robin_stocks** - Robinhood API client
- **yfinance** - Yahoo Finance market data
- **plotly** - Interactive charts
- **pandas** - Data processing
