"""SQLite persistence for watchlist tickers and alert configuration.

Uses a dedicated database file outside of .states/ (which Reflex manages and
may wipe between restarts). The watchlist DB lives at .data/watchlist.db.
"""
import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / ".data" / "watchlist.db"
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _init_schema(conn)
        _local.conn = conn
    return _local.conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlist_tickers (
            symbol TEXT PRIMARY KEY,
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS watchlist_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL REFERENCES watchlist_tickers(symbol) ON DELETE CASCADE,
            alert_type TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            notify_email INTEGER NOT NULL DEFAULT 0,
            notify_sms INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(symbol, alert_type)
        );
    """)
    conn.commit()


# -- Ticker CRUD --

def get_all_tickers() -> list[str]:
    """Return all watchlist symbols, ordered by most recently added."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT symbol FROM watchlist_tickers ORDER BY added_at DESC"
    ).fetchall()
    return [r[0] for r in rows]


def add_ticker(symbol: str) -> bool:
    """Add a ticker. Returns False if it already exists."""
    conn = _get_conn()
    try:
        conn.execute("INSERT INTO watchlist_tickers (symbol) VALUES (?)", (symbol.upper(),))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_ticker(symbol: str):
    """Remove a ticker and cascade-delete its alerts."""
    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("DELETE FROM watchlist_tickers WHERE symbol = ?", (symbol.upper(),))
    conn.commit()


def ticker_exists(symbol: str) -> bool:
    """Check if a ticker is already in the watchlist."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT 1 FROM watchlist_tickers WHERE symbol = ?", (symbol.upper(),)
    ).fetchone()
    return row is not None


# -- Alert CRUD --

def get_alerts(symbol: str) -> list[dict]:
    """Return all alert configs for a symbol."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT alert_type, enabled, notify_email, notify_sms FROM watchlist_alerts WHERE symbol = ?",
        (symbol.upper(),)
    ).fetchall()
    return [{"alert_type": r[0], "enabled": bool(r[1]), "notify_email": bool(r[2]), "notify_sms": bool(r[3])} for r in rows]


def get_all_alerts() -> dict[str, list[dict]]:
    """Return alert configs for all tickers, keyed by symbol."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT symbol, alert_type, enabled, notify_email, notify_sms FROM watchlist_alerts ORDER BY symbol"
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for r in rows:
        sym = r[0]
        result.setdefault(sym, []).append({
            "alert_type": r[1], "enabled": bool(r[2]),
            "notify_email": bool(r[3]), "notify_sms": bool(r[4]),
        })
    return result


def set_alert(symbol: str, alert_type: str, enabled: bool = True):
    """Insert or update an alert for a symbol."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO watchlist_alerts (symbol, alert_type, enabled)
           VALUES (?, ?, ?)
           ON CONFLICT(symbol, alert_type) DO UPDATE SET enabled = excluded.enabled""",
        (symbol.upper(), alert_type, int(enabled))
    )
    conn.commit()


def toggle_alert(symbol: str, alert_type: str) -> bool:
    """Toggle an alert's enabled state. Returns the new state."""
    conn = _get_conn()
    conn.execute(
        "UPDATE watchlist_alerts SET enabled = NOT enabled WHERE symbol = ? AND alert_type = ?",
        (symbol.upper(), alert_type)
    )
    conn.commit()
    row = conn.execute(
        "SELECT enabled FROM watchlist_alerts WHERE symbol = ? AND alert_type = ?",
        (symbol.upper(), alert_type)
    ).fetchone()
    return bool(row[0]) if row else False


def set_all_alerts_for_ticker(symbol: str, enabled: bool):
    """Bulk enable/disable all alerts for a ticker."""
    conn = _get_conn()
    conn.execute(
        "UPDATE watchlist_alerts SET enabled = ? WHERE symbol = ?",
        (int(enabled), symbol.upper())
    )
    conn.commit()


def ensure_default_alerts(symbol: str, alert_types: list[str]):
    """Ensure all alert types exist for a symbol, inserting missing ones as enabled."""
    conn = _get_conn()
    for at in alert_types:
        conn.execute(
            """INSERT OR IGNORE INTO watchlist_alerts (symbol, alert_type, enabled)
               VALUES (?, ?, 1)""",
            (symbol.upper(), at)
        )
    conn.commit()
