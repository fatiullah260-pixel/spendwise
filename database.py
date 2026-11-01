"""database.py - All SQLite operations for SpendWise.

The database file is created automatically on first run, so records
survive restarting the app (on your own computer).
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "SPENDWISE_DB_PATH", os.path.join(BASE_DIR, "data", "spendwise.db")
)

# Special category name used to store the overall monthly budget.
TOTAL_KEY = "__TOTAL__"


@contextmanager
def get_conn():
    """Open a connection, commit on success, roll back on error, always close."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they do not exist yet."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
                amount REAL NOT NULL CHECK (amount > 0),
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                UNIQUE (month, category)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date)")


# ---------------------------------------------------------------- validation
def validate_transaction(t_type, amount, category, tx_date, description):
    """Check and clean the values. Raises ValueError with a friendly message."""
    if t_type not in ("income", "expense"):
        raise ValueError("Transaction type must be 'income' or 'expense'.")

    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("Amount must be a number.")
    if amount != amount or amount in (float("inf"), float("-inf")):
        raise ValueError("Amount must be a valid number.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if amount > 1_000_000_000_000:
        raise ValueError("Amount is too large.")

    category = (category or "").strip()
    if not category:
        raise ValueError("Please choose a category / source.")

    if isinstance(tx_date, datetime):
        tx_date = tx_date.date()
    if isinstance(tx_date, date):
        iso_date = tx_date.isoformat()
    else:
        try:
            iso_date = date.fromisoformat(str(tx_date).strip()[:10]).isoformat()
        except ValueError:
            raise ValueError("Date is not valid (use YYYY-MM-DD).")

    description = (description or "").strip()[:255]
    return t_type, amount, category, iso_date, description


# -------------------------------------------------------------- transactions
def add_transaction(t_type, amount, category, tx_date, description=""):
    values = validate_transaction(t_type, amount, category, tx_date, description)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO transactions (type, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            values,
        )
        return cur.lastrowid


def add_transactions_bulk(rows):
    """rows: list of (type, amount, category, date, description) already validated."""
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO transactions (type, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def update_transaction(tx_id, t_type, amount, category, tx_date, description=""):
    values = validate_transaction(t_type, amount, category, tx_date, description)
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET type=?, amount=?, category=?, date=?, "
            "description=? WHERE id=?",
            values + (int(tx_id),),
        )
        if cur.rowcount == 0:
            raise ValueError("Transaction not found.")


def delete_transaction(tx_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions WHERE id=?", (int(tx_id),))
        if cur.rowcount == 0:
            raise ValueError("Transaction not found.")


def get_transactions(start=None, end=None, categories=None, t_type=None):
    """Return a list of dicts, newest first. All filters are optional."""
    sql = "SELECT id, type, amount, category, date, description FROM transactions"
    where, params = [], []
    if start:
        where.append("date >= ?")
        params.append(start.isoformat() if hasattr(start, "isoformat") else str(start))
    if end:
        where.append("date <= ?")
        params.append(end.isoformat() if hasattr(end, "isoformat") else str(end))
    if categories:
        where.append("category IN (%s)" % ",".join("?" * len(categories)))
        params.extend(categories)
    if t_type in ("income", "expense"):
        where.append("type = ?")
        params.append(t_type)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, id DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ------------------------------------------------------------------- budgets
def set_budget(month, category, amount):
    """Save a budget. An amount of 0 (or less) removes that budget."""
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("Budget must be a number.")
    if amount != amount:
        raise ValueError("Budget must be a valid number.")
    with get_conn() as conn:
        if amount <= 0:
            conn.execute(
                "DELETE FROM budgets WHERE month=? AND category=?", (month, category)
            )
        else:
            conn.execute(
                "INSERT INTO budgets (month, category, amount) VALUES (?, ?, ?) "
                "ON CONFLICT(month, category) DO UPDATE SET amount=excluded.amount",
                (month, category, amount),
            )


def get_budgets(month):
    """Return {category: amount} for the month. Overall budget uses TOTAL_KEY."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT category, amount FROM budgets WHERE month=?", (month,)
        ).fetchall()
    return {r["category"]: r["amount"] for r in rows}
