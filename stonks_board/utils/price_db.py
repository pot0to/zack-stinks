"""Local SQLite database for daily OHLCV price data.

Eliminates redundant yfinance API calls by persisting historical price data
locally. On each request, only the delta (new trading days since the last
stored date) is fetched from the API and appended to the database.

Schema:
    daily_prices: symbol, date, open, high, low, close, volume

The database file lives alongside the app data in .states/prices.db.
"""
import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional
import threading

# Database location: project root .states directory (already gitignored)
_DB_PATH = Path(__file__).parent.parent.parent / ".states" / "prices.db"

# Thread-local connections (SQLite connections aren't thread-safe)
_local = threading.local()

# Period-to-calendar-days mapping for initial fetch sizing
_PERIOD_CALENDAR_DAYS = {
    "1mo": 35,
    "3mo": 100,
    "6mo": 200,
    "1y": 370,
    "2y": 740,
    "5y": 1850,
}


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection, creating the DB if needed."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
        conn.execute("PRAGMA synchronous=NORMAL")  # Good balance of safety and speed
        _init_schema(conn)
        _local.conn = conn
    return _local.conn


def _init_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, date)
        );
    """)
    conn.commit()


def _store_dataframe(conn: sqlite3.Connection, symbol: str, df: pd.DataFrame):
    """Upsert OHLCV rows from a DataFrame into the database.

    Rows with NaN close prices are skipped (partial/corrupt data).
    Other NaN fields are stored as SQL NULL to preserve data fidelity.
    """
    if df is None or df.empty:
        return

    rows = []
    for idx, row in df.iterrows():
        # Skip rows with no close price (corrupt or partial data)
        close_val = row.get("Close")
        if pd.isna(close_val):
            continue

        # Handle both DatetimeIndex and regular index
        if hasattr(idx, "strftime"):
            date_str = idx.strftime("%Y-%m-%d")
        else:
            date_str = str(idx)

        def _safe_float(val):
            """Convert to float, preserving None for NaN values."""
            if pd.isna(val):
                return None
            return float(val)

        rows.append((
            symbol,
            date_str,
            _safe_float(row.get("Open")),
            _safe_float(row.get("High")),
            _safe_float(row.get("Low")),
            float(close_val),
            _safe_float(row.get("Volume")),
        ))

    if rows:
        conn.executemany(
            """INSERT OR REPLACE INTO daily_prices
               (symbol, date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()


def _load_dataframe(conn: sqlite3.Connection, symbol: str, min_date: Optional[str] = None) -> pd.DataFrame:
    """Load OHLCV data from the database as a DataFrame matching yfinance format."""
    if min_date:
        query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE symbol = ? AND date >= ? ORDER BY date"
        rows = conn.execute(query, (symbol, min_date)).fetchall()
    else:
        query = "SELECT date, open, high, low, close, volume FROM daily_prices WHERE symbol = ? ORDER BY date"
        rows = conn.execute(query, (symbol,)).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    return df


def _get_last_stored_date(conn: sqlite3.Connection, symbol: str) -> Optional[date]:
    """Get the most recent date we have stored for a symbol."""
    row = conn.execute(
        "SELECT MAX(date) FROM daily_prices WHERE symbol = ?", (symbol,)
    ).fetchone()
    if row and row[0]:
        return datetime.strptime(row[0], "%Y-%m-%d").date()
    return None


def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Get OHLCV history for a symbol, using local DB with incremental API fetch.

    The symbol is normalized to yfinance format internally (e.g., "BRK.B" -> "BRK-B"),
    so callers can pass either broker or yfinance format.

    Logic:
    1. Check DB for existing data for this symbol.
    2. If we have recent data (last stored date is today or yesterday on a weekday),
       return from DB without any API call.
    3. If we have some data but it's stale, fetch only the missing days from yfinance.
    4. If we have no data, do a full period fetch and store it.

    Returns a DataFrame with DatetimeIndex and OHLCV columns, matching yfinance format.
    """
    from .technical import normalize_symbol_for_yfinance
    symbol = normalize_symbol_for_yfinance(symbol)

    conn = _get_conn()
    last_stored = _get_last_stored_date(conn, symbol)
    today = date.today()

    # Determine how many calendar days the requested period covers
    needed_calendar_days = _PERIOD_CALENDAR_DAYS.get(period, 370)
    earliest_needed = today - timedelta(days=needed_calendar_days)

    if last_stored is not None:
        days_stale = (today - last_stored).days

        # Fresh enough: no API call needed (0 = today, 1 = yesterday which could be
        # after market close, 2 = covers a weekend gap, 3 = covers a 3-day weekend)
        if days_stale <= 3:
            df = _load_dataframe(conn, symbol, min_date=earliest_needed.strftime("%Y-%m-%d"))
            if not df.empty:
                return df

        # Have some data but stale: fetch only the delta
        # Start from the day after our last stored date
        start_date = last_stored + timedelta(days=1)
        if start_date <= today:
            try:
                ticker = yf.Ticker(symbol)
                delta_df = ticker.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                )
                if delta_df is not None and not delta_df.empty:
                    _store_dataframe(conn, symbol, delta_df)
            except Exception as e:
                print(f"[price_db] Delta fetch failed for {symbol}: {e}")
                # Fall through to return whatever we have

        # Check if our stored data covers the requested period
        df = _load_dataframe(conn, symbol, min_date=earliest_needed.strftime("%Y-%m-%d"))
        if not df.empty:
            return df

    # No data or insufficient coverage: full fetch
    try:
        ticker = yf.Ticker(symbol)
        full_df = ticker.history(period=period)
        if full_df is not None and not full_df.empty:
            _store_dataframe(conn, symbol, full_df)
            return full_df
    except Exception as e:
        print(f"[price_db] Full fetch failed for {symbol}: {e}")

    # Last resort: return whatever we have in DB
    return _load_dataframe(conn, symbol)


def batch_get_history(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Batch fetch OHLCV history for multiple symbols using the local DB.

    For each symbol, checks the local DB first and only fetches the delta from
    yfinance. Symbols that are fully cached require zero API calls.

    For symbols that need fresh data, uses yf.download() in a single batch call
    for efficiency, then stores the results in the DB.

    Returns a dict mapping symbol -> DataFrame with OHLCV columns.
    """
    from .technical import normalize_symbol_for_yfinance

    if not symbols:
        return {}

    conn = _get_conn()
    today = date.today()
    needed_calendar_days = _PERIOD_CALENDAR_DAYS.get(period, 370)
    earliest_needed = today - timedelta(days=needed_calendar_days)
    earliest_str = earliest_needed.strftime("%Y-%m-%d")

    result = {}
    symbols_needing_fetch = []  # (original_symbol, yf_symbol, start_date_or_None)

    # Phase 1: Check DB for each symbol
    for symbol in symbols:
        yf_symbol = normalize_symbol_for_yfinance(symbol)
        last_stored = _get_last_stored_date(conn, yf_symbol)

        if last_stored is not None:
            days_stale = (today - last_stored).days

            if days_stale <= 3:
                # Fresh enough, load from DB
                df = _load_dataframe(conn, yf_symbol, min_date=earliest_str)
                if not df.empty:
                    result[symbol] = df
                    continue

            # Stale: need delta fetch from day after last stored
            start_date = last_stored + timedelta(days=1)
            if start_date <= today:
                symbols_needing_fetch.append((symbol, yf_symbol, start_date))
            else:
                # Edge case: last_stored is today or future (shouldn't happen)
                df = _load_dataframe(conn, yf_symbol, min_date=earliest_str)
                if not df.empty:
                    result[symbol] = df
                    continue
                symbols_needing_fetch.append((symbol, yf_symbol, None))
        else:
            # No data at all: full fetch needed
            symbols_needing_fetch.append((symbol, yf_symbol, None))

    if not symbols_needing_fetch:
        return result

    # Phase 2: Batch fetch from yfinance for symbols that need data
    # Separate into delta fetches (have some data) and full fetches (no data)
    delta_symbols = [(orig, yf, start) for orig, yf, start in symbols_needing_fetch if start is not None]
    full_symbols = [(orig, yf, _) for orig, yf, _ in symbols_needing_fetch if _ is None]

    # Handle full fetches with yf.download (single API call for all)
    if full_symbols:
        yf_syms = [yf for _, yf, _ in full_symbols]
        orig_map = {yf: orig for orig, yf, _ in full_symbols}

        try:
            data = yf.download(yf_syms, period=period, group_by="ticker", threads=True, progress=False)

            if not data.empty:
                if len(yf_syms) == 1:
                    yf_sym = yf_syms[0]
                    orig_sym = orig_map[yf_sym]
                    _store_dataframe(conn, yf_sym, data)
                    result[orig_sym] = data
                else:
                    for yf_sym in yf_syms:
                        if yf_sym in data.columns.get_level_values(0):
                            symbol_df = data[yf_sym].dropna(how="all")
                            if not symbol_df.empty:
                                orig_sym = orig_map[yf_sym]
                                _store_dataframe(conn, yf_sym, symbol_df)
                                result[orig_sym] = symbol_df
        except Exception as e:
            print(f"[price_db] Batch full fetch failed: {e}")

    # Handle delta fetches individually (different start dates per symbol)
    for orig_sym, yf_sym, start_date in delta_symbols:
        try:
            ticker = yf.Ticker(yf_sym)
            delta_df = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
            )
            if delta_df is not None and not delta_df.empty:
                _store_dataframe(conn, yf_sym, delta_df)
        except Exception as e:
            print(f"[price_db] Delta fetch failed for {yf_sym}: {e}")

        # Load full range from DB regardless of whether delta succeeded
        df = _load_dataframe(conn, yf_sym, min_date=earliest_str)
        if not df.empty:
            result[orig_sym] = df

    # Phase 3: Fill in any full-fetch symbols that failed the batch but might have partial DB data
    for orig_sym, yf_sym, _ in full_symbols:
        if orig_sym not in result:
            df = _load_dataframe(conn, yf_sym, min_date=earliest_str)
            if not df.empty:
                result[orig_sym] = df

    return result
