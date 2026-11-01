"""utils.py - Helpers: constants, formatting, data processing, CSV, styling."""

import csv
import io
from datetime import date

import pandas as pd

from database import validate_transaction

EXPENSE_CATEGORIES = [
    "Food",
    "Education",
    "Transport",
    "Shopping",
    "Healthcare",
    "Entertainment",
    "Bills",
    "Other",
]
INCOME_SOURCES = ["Salary", "Business", "Freelance", "Investment", "Gift", "Other"]

NAVY = "#0A1F44"
BLUE = "#2F6FED"
GREEN = "#12B76A"
RED = "#F04438"
AMBER = "#F79009"

DF_COLUMNS = ["id", "type", "amount", "category", "date", "description", "month"]


# ---------------------------------------------------------------- formatting
def format_pkr(value):
    """Format a number as Pakistani Rupees, e.g. Rs. 12,500 or Rs. 1,250.50"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    sign = "-" if value < 0 else ""
    value = abs(value)
    if abs(value - round(value)) < 0.005:
        return f"{sign}Rs. {round(value):,}"
    return f"{sign}Rs. {value:,.2f}"


def month_key(d):
    """date -> 'YYYY-MM'"""
    return f"{d.year}-{d.month:02d}"


def month_label(key):
    """'2026-11' -> 'November 2026'"""
    y, m = key.split("-")
    return date(int(y), int(m), 1).strftime("%B %Y")


# ------------------------------------------------------------ data processing
def to_dataframe(rows):
    """Turn a list of transaction dicts into a DataFrame (works when empty)."""
    if not rows:
        df = pd.DataFrame(columns=DF_COLUMNS)
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = df["amount"].astype(float)
        return df
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    return df


def monthly_summary(df):
    """One row per month with income, expense and savings."""
    if df.empty:
        return pd.DataFrame(columns=["month", "income", "expense", "savings"])
    p = df.pivot_table(
        index="month", columns="type", values="amount", aggfunc="sum", fill_value=0.0
    )
    p.columns.name = None
    for col in ("income", "expense"):
        if col not in p.columns:
            p[col] = 0.0
    p["savings"] = p["income"] - p["expense"]
    return p.reset_index()[["month", "income", "expense", "savings"]].sort_values(
        "month"
    )


def budget_status(spent, budget):
    """Return (percent_used, status) where status is none/ok/warning/over."""
    if not budget or budget <= 0:
        return 0.0, "none"
    pct = spent / budget * 100
    if pct > 100:
        return pct, "over"
    if pct >= 80:
        return pct, "warning"
    return pct, "ok"


# ----------------------------------------------------------------------- CSV
def transactions_csv(df):
    """All transactions as CSV bytes (Excel friendly)."""
    out = df.copy()
    if out.empty:
        out = pd.DataFrame(columns=["id", "date", "type", "category", "amount", "description"])
    else:
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        out = out[["id", "date", "type", "category", "amount", "description"]]
    return out.to_csv(index=False).encode("utf-8-sig")


def monthly_report_csv(df, month):
    """A readable monthly report: summary, category totals, then transactions."""
    m = df[df["month"] == month] if not df.empty else df
    income = m.loc[m["type"] == "income", "amount"].sum() if not m.empty else 0.0
    expense = m.loc[m["type"] == "expense", "amount"].sum() if not m.empty else 0.0

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["SpendWise Monthly Report", month_label(month)])
    w.writerow([])
    w.writerow(["Summary"])
    w.writerow(["Total Income (PKR)", f"{income:.2f}"])
    w.writerow(["Total Expenses (PKR)", f"{expense:.2f}"])
    w.writerow(["Savings (PKR)", f"{income - expense:.2f}"])
    w.writerow([])
    w.writerow(["Expenses by Category"])
    w.writerow(["Category", "Amount (PKR)"])
    if not m.empty:
        cats = (
            m[m["type"] == "expense"]
            .groupby("category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        for cat, amt in cats.items():
            w.writerow([cat, f"{amt:.2f}"])
    w.writerow([])
    w.writerow(["Transactions"])
    w.writerow(["Date", "Type", "Category", "Amount (PKR)", "Description"])
    if not m.empty:
        for _, r in m.sort_values("date").iterrows():
            w.writerow(
                [
                    r["date"].strftime("%Y-%m-%d"),
                    r["type"],
                    r["category"],
                    f"{r['amount']:.2f}",
                    r["description"] or "",
                ]
            )
    return buf.getvalue().encode("utf-8-sig")


def parse_import_csv(uploaded_file):
    """Read a CSV made by 'Download all transactions'.

    Returns (valid_rows, error_messages). Needs columns:
    date, type, category, amount (description is optional).
    """
    try:
        raw = pd.read_csv(uploaded_file, dtype=str).fillna("")
    except Exception as exc:  # unreadable / not a CSV
        return [], [f"Could not read the file: {exc}"]

    raw.columns = [c.strip().lower() for c in raw.columns]
    missing = [c for c in ("date", "type", "category", "amount") if c not in raw.columns]
    if missing:
        return [], [f"Missing column(s): {', '.join(missing)}"]

    rows, errors = [], []
    for i, r in raw.iterrows():
        try:
            rows.append(
                validate_transaction(
                    r["type"].strip().lower(),
                    r["amount"].replace(",", ""),
                    r["category"],
                    r["date"],
                    r.get("description", ""),
                )
            )
        except ValueError as exc:
            errors.append(f"Row {i + 2}: {exc}")
    return rows, errors


# --------------------------------------------------------------------- styling
APP_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: #F5F7FB; }}
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.15); }}
[data-testid="stSidebar"] div[role="radiogroup"] > label {{
    padding: 10px 14px; border-radius: 10px; margin-bottom: 4px; width: 100%;
}}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
    background: rgba(255,255,255,0.10);
}}

/* Headings */
h1, h2, h3 {{ color: {NAVY}; font-weight: 700; letter-spacing: -0.3px; }}
.page-sub {{ color: #667085; margin-top: -0.6rem; margin-bottom: 1.4rem; }}

/* Cards */
.kpi {{
    background: #FFFFFF; border-radius: 16px; padding: 20px 22px;
    box-shadow: 0 2px 10px rgba(10,31,68,0.07); border-left: 6px solid {BLUE};
    margin-bottom: 12px;
}}
.kpi .label {{ color: #667085; font-size: 0.82rem; font-weight: 600;
              text-transform: uppercase; letter-spacing: 0.6px; }}
.kpi .value {{ color: {NAVY}; font-size: 1.65rem; font-weight: 700; margin-top: 4px; }}
.kpi .sub {{ color: #98A2B3; font-size: 0.8rem; margin-top: 2px; }}
.kpi.navy {{ background: {NAVY}; border-left-color: #6C9BFF; }}
.kpi.navy .label, .kpi.navy .sub {{ color: #B9C6E4; }}
.kpi.navy .value {{ color: #FFFFFF; }}
.kpi.green {{ border-left-color: {GREEN}; }}
.kpi.red {{ border-left-color: {RED}; }}

/* Buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
    background: {NAVY}; color: #FFFFFF; border: none; border-radius: 10px;
    padding: 0.55rem 1.2rem; font-weight: 600;
}}
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
    background: {BLUE}; color: #FFFFFF; border: none;
}}
[data-testid="stForm"] {{ background: #FFFFFF; border-radius: 16px; border: none;
    box-shadow: 0 2px 10px rgba(10,31,68,0.07); padding: 1.4rem; }}

@media (max-width: 768px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
    .kpi .value {{ font-size: 1.35rem; }}
}}
</style>
"""


def kpi_card(label, value, sub="", style=""):
    """HTML for one dashboard card. Only trusted, computed text goes in here."""
    return (
        f'<div class="kpi {style}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>'
    )
