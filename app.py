"""app.py - SpendWise: Smart Expense Tracker (Streamlit web app).

Run locally with:  streamlit run app.py
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import database as db
from utils import (
    APP_CSS,
    AMBER,
    BLUE,
    EXPENSE_CATEGORIES,
    GREEN,
    INCOME_SOURCES,
    NAVY,
    RED,
    budget_status,
    format_pkr,
    kpi_card,
    month_key,
    month_label,
    monthly_report_csv,
    monthly_summary,
    parse_import_csv,
    to_dataframe,
    transactions_csv,
)

st.set_page_config(
    page_title="SpendWise - Smart Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)


@st.cache_resource
def setup_database():
    db.init_db()
    return True


setup_database()

PLOT_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, sans-serif", color=NAVY),
    margin=dict(l=10, r=10, t=50, b=10),
    legend=dict(orientation="h", y=-0.2),
)


# ------------------------------------------------------------------- helpers
def load_df():
    return to_dataframe(db.get_transactions())


def page_header(title, subtitle):
    st.title(title)
    st.markdown(f'<p class="page-sub">{subtitle}</p>', unsafe_allow_html=True)


def show_table(df):
    """Show a clean, formatted transaction table."""
    if df.empty:
        st.info("No transactions to show yet.")
        return
    view = pd.DataFrame(
        {
            "ID": df["id"],
            "Date": df["date"].dt.strftime("%d %b %Y"),
            "Type": df["type"].str.capitalize(),
            "Category": df["category"],
            "Amount": df["amount"].map(format_pkr),
            "Description": df["description"],
        }
    )
    st.dataframe(view, hide_index=True)


def month_options(df):
    """Months that have data (newest first), always including this month."""
    months = set(df["month"].unique()) if not df.empty else set()
    months.add(month_key(date.today()))
    return sorted(months, reverse=True)


# ------------------------------------------------------------------ dashboard
def page_dashboard():
    page_header("Dashboard", "Your money at a glance.")
    df = load_df()
    cur = month_key(date.today())

    total_income = df.loc[df["type"] == "income", "amount"].sum()
    total_expense = df.loc[df["type"] == "expense", "amount"].sum()
    balance = total_income - total_expense

    cur_df = df[df["month"] == cur] if not df.empty else df
    m_income = cur_df.loc[cur_df["type"] == "income", "amount"].sum()
    m_expense = cur_df.loc[cur_df["type"] == "expense", "amount"].sum()
    m_savings = m_income - m_expense

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Total Income", format_pkr(total_income), "All time", "green"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Total Expenses", format_pkr(total_expense), "All time", "red"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Remaining Balance", format_pkr(balance), "Income - Expenses", "navy"), unsafe_allow_html=True)
    c4.markdown(
        kpi_card("Monthly Savings", format_pkr(m_savings), f"{month_label(cur)}"),
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("Welcome! Add your first income or expense from the sidebar to see your dashboard come alive.")
        return

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Monthly Financial Overview")
        ms = monthly_summary(df).tail(6)
        fig = go.Figure()
        fig.add_bar(x=[month_label(m) for m in ms["month"]], y=ms["income"], name="Income", marker_color=GREEN)
        fig.add_bar(x=[month_label(m) for m in ms["month"]], y=ms["expense"], name="Expenses", marker_color=RED)
        fig.add_scatter(
            x=[month_label(m) for m in ms["month"]], y=ms["savings"], name="Savings",
            mode="lines+markers", line=dict(color=NAVY, width=3),
        )
        fig.update_layout(barmode="group", yaxis_title="PKR", **PLOT_LAYOUT)
        st.plotly_chart(fig)
    with right:
        st.subheader("This Month's Spending")
        exp = cur_df[cur_df["type"] == "expense"].groupby("category")["amount"].sum().reset_index()
        if exp.empty:
            st.info("No expenses recorded this month.")
        else:
            fig = px.pie(exp, names="category", values="amount", hole=0.55,
                         color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig)

    st.subheader("Recent Transactions")
    show_table(df.head(10))


# --------------------------------------------------------------- add forms
def transaction_form(kind):
    is_income = kind == "income"
    page_header(
        "Add Income" if is_income else "Add Expense",
        "Record money you received." if is_income else "Record money you spent.",
    )
    options = INCOME_SOURCES if is_income else EXPENSE_CATEGORIES
    with st.form(f"{kind}_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        amount = c1.number_input(
            "Amount (Rs.)", min_value=0.01, value=None, step=100.0,
            format="%.2f", placeholder="e.g. 2500",
        )
        category = c2.selectbox("Income Source" if is_income else "Category", options)
        tx_date = c1.date_input("Date", value=date.today())
        description = c2.text_input(
            "Description (optional)" if is_income else "Description",
            max_chars=255,
            placeholder="What was this for?",
        )
        submitted = st.form_submit_button("Save Income" if is_income else "Save Expense")

    if submitted:
        if amount is None or amount <= 0:
            st.error("Please enter an amount greater than zero.")
        elif not is_income and not description.strip():
            st.error("Please add a short description for the expense.")
        else:
            try:
                db.add_transaction(kind, amount, category, tx_date, description)
                st.success(f"Saved {format_pkr(amount)} ({category}) on {tx_date:%d %b %Y}.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not save the transaction: {exc}")


# --------------------------------------------------------------------- budget
def page_budget():
    page_header("Budget Planner", "Plan each month and track your spending against it.")
    today = date.today()
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    years = list(range(today.year - 1, today.year + 3))

    c1, c2, _ = st.columns([1, 1, 2])
    sel_month = c1.selectbox("Month", months, index=today.month - 1)
    sel_year = c2.selectbox("Year", years, index=years.index(today.year))
    key = f"{sel_year}-{months.index(sel_month) + 1:02d}"

    budgets = db.get_budgets(key)

    st.subheader("Set Budgets")
    with st.form(f"budget_form_{key}"):
        total = st.number_input(
            "Overall monthly budget (Rs.)  -  set 0 to remove",
            min_value=0.0, value=float(budgets.get(db.TOTAL_KEY, 0.0)),
            step=1000.0, format="%.2f", key=f"tot_{key}",
        )
        st.markdown("**Category budgets** (set 0 to remove)")
        cols = st.columns(2)
        cat_values = {}
        for i, cat in enumerate(EXPENSE_CATEGORIES):
            cat_values[cat] = cols[i % 2].number_input(
                cat, min_value=0.0, value=float(budgets.get(cat, 0.0)),
                step=500.0, format="%.2f", key=f"cat_{key}_{cat}",
            )
        saved = st.form_submit_button("Save Budgets")

    if saved:
        try:
            db.set_budget(key, db.TOTAL_KEY, total)
            for cat, val in cat_values.items():
                db.set_budget(key, cat, val)
            st.success(f"Budgets saved for {month_label(key)}.")
            budgets = db.get_budgets(key)
        except Exception as exc:
            st.error(f"Could not save budgets: {exc}")

    # ---- progress
    st.subheader(f"Budget Progress - {month_label(key)}")
    df = load_df()
    m_exp = df[(df["month"] == key) & (df["type"] == "expense")] if not df.empty else df
    spent_by_cat = m_exp.groupby("category")["amount"].sum().to_dict() if not m_exp.empty else {}
    total_spent = float(m_exp["amount"].sum()) if not m_exp.empty else 0.0

    if not budgets:
        st.info("No budgets set for this month yet. Fill in the form above and save.")
        return

    def show_progress(name, spent, budget):
        pct, status = budget_status(spent, budget)
        left = budget - spent
        st.markdown(f"**{name}** - {format_pkr(spent)} of {format_pkr(budget)} ({pct:.0f}%)")
        st.progress(min(pct / 100, 1.0))
        if status == "over":
            st.error(f"Over budget by {format_pkr(-left)}.")
        elif status == "warning":
            st.warning(f"Approaching the limit - only {format_pkr(left)} left.")
        else:
            st.caption(f"{format_pkr(left)} remaining")

    if db.TOTAL_KEY in budgets:
        show_progress("Overall Budget", total_spent, budgets[db.TOTAL_KEY])
        st.divider()
    cat_budgets = {c: b for c, b in budgets.items() if c != db.TOTAL_KEY}
    if cat_budgets and db.TOTAL_KEY in budgets and sum(cat_budgets.values()) > budgets[db.TOTAL_KEY]:
        st.warning("Your category budgets add up to more than your overall budget.")
    for cat in EXPENSE_CATEGORIES:
        if cat in cat_budgets:
            show_progress(cat, float(spent_by_cat.get(cat, 0.0)), cat_budgets[cat])


# ---------------------------------------------------------------- transactions
def page_transactions():
    page_header("Transaction History", "Search, filter, edit and delete your records.")
    df = load_df()
    if df.empty:
        st.info("No transactions yet. Add income or an expense from the sidebar.")
        return

    st.subheader("Filters")
    f1, f2, f3 = st.columns(3)
    min_d, max_d = df["date"].min().date(), df["date"].max().date()
    rng = f1.date_input("Date range", value=(min_d, max_d), key="flt_date")
    t_type = f2.selectbox("Type", ["All", "Income", "Expense"])
    all_cats = sorted(df["category"].unique())
    cats = f3.multiselect("Category", all_cats)

    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        start, end = rng
    elif isinstance(rng, (tuple, list)) and len(rng) == 1:
        start = end = rng[0]
    else:
        start, end = min_d, max_d

    rows = db.get_transactions(
        start=start, end=end, categories=cats or None,
        t_type=None if t_type == "All" else t_type.lower(),
    )
    fdf = to_dataframe(rows)
    st.caption(f"{len(fdf)} transaction(s) found")
    show_table(fdf)

    if fdf.empty:
        return

    st.subheader("Edit or Delete")
    labels = {
        int(r.id): f"#{r.id} | {r.date:%d %b %Y} | {r.type.capitalize()} | {r.category} | {format_pkr(r.amount)}"
        for r in fdf.itertuples()
    }
    chosen = st.selectbox("Choose a transaction", list(labels.keys()), format_func=lambda i: labels[i])
    row = fdf[fdf["id"] == chosen].iloc[0]
    kind = row["type"]
    options = list(INCOME_SOURCES if kind == "income" else EXPENSE_CATEGORIES)
    if row["category"] not in options:
        options.append(row["category"])

    with st.form(f"edit_form_{chosen}"):
        st.caption(f"Editing a {kind} record")
        e1, e2 = st.columns(2)
        new_amount = e1.number_input("Amount (Rs.)", min_value=0.01, value=float(row["amount"]), step=100.0, format="%.2f")
        new_cat = e2.selectbox("Category / Source", options, index=options.index(row["category"]))
        new_date = e1.date_input("Date", value=row["date"].date())
        new_desc = e2.text_input("Description", value=row["description"] or "", max_chars=255)
        update_clicked = st.form_submit_button("Update Transaction")

    if update_clicked:
        try:
            db.update_transaction(chosen, kind, new_amount, new_cat, new_date, new_desc)
            st.success("Transaction updated.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.markdown("**Delete this transaction**")
    confirm = st.checkbox("Yes, I'm sure I want to delete it permanently", key=f"confirm_{chosen}")
    if st.button("Delete Transaction", disabled=not confirm):
        try:
            db.delete_transaction(chosen)
            st.success("Transaction deleted.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


# ------------------------------------------------------------------ analytics
def page_analytics():
    page_header("Analytics", "Understand where your money goes.")
    df = load_df()
    if df.empty:
        st.info("Add some transactions to unlock charts and trends.")
        return

    ms = monthly_summary(df)
    labels = [month_label(m) for m in ms["month"]]
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Income vs Expenses", "Category Breakdown", "Monthly Spending", "Trends"]
    )

    with tab1:
        fig = go.Figure()
        fig.add_bar(x=labels, y=ms["income"], name="Income", marker_color=GREEN)
        fig.add_bar(x=labels, y=ms["expense"], name="Expenses", marker_color=RED)
        fig.update_layout(barmode="group", title="Monthly Income vs Expenses", yaxis_title="PKR", **PLOT_LAYOUT)
        st.plotly_chart(fig)
        t_inc, t_exp = ms["income"].sum(), ms["expense"].sum()
        a, b, c = st.columns(3)
        a.metric("Total income", format_pkr(t_inc))
        b.metric("Total expenses", format_pkr(t_exp))
        c.metric("Net savings", format_pkr(t_inc - t_exp))

    with tab2:
        opts = ["All time"] + month_options(df)
        pick = st.selectbox("Period", opts, format_func=lambda m: m if m == "All time" else month_label(m))
        exp = df[df["type"] == "expense"]
        if pick != "All time":
            exp = exp[exp["month"] == pick]
        cat = exp.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
        if cat.empty:
            st.info("No expenses in this period.")
        else:
            fig = px.pie(cat, names="category", values="amount", hole=0.45,
                         title="Expenses by Category",
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(**PLOT_LAYOUT)
            st.plotly_chart(fig)
            cat["amount"] = cat["amount"].map(format_pkr)
            st.dataframe(cat.rename(columns={"category": "Category", "amount": "Spent"}), hide_index=True)

    with tab3:
        fig = go.Figure(go.Bar(x=labels, y=ms["expense"], marker_color=BLUE,
                               text=[format_pkr(v) for v in ms["expense"]], textposition="outside"))
        fig.update_layout(title="Monthly Spending", yaxis_title="PKR", **PLOT_LAYOUT)
        st.plotly_chart(fig)

    with tab4:
        fig = go.Figure()
        fig.add_scatter(x=labels, y=ms["expense"], name="Spending", mode="lines+markers",
                        line=dict(color=RED, width=3))
        fig.add_scatter(x=labels, y=ms["income"], name="Income", mode="lines+markers",
                        line=dict(color=GREEN, width=3))
        fig.add_scatter(x=labels, y=ms["savings"], name="Savings", mode="lines+markers",
                        line=dict(color=NAVY, width=3, dash="dot"))
        fig.update_layout(title="Spending, Income & Savings Trend", yaxis_title="PKR", **PLOT_LAYOUT)
        st.plotly_chart(fig)

        last30 = df[(df["type"] == "expense") & (df["date"] >= pd.Timestamp(date.today() - timedelta(days=29)))]
        if not last30.empty:
            daily = last30.groupby("date")["amount"].sum().reset_index()
            fig = px.area(daily, x="date", y="amount", title="Daily Spending - Last 30 Days")
            fig.update_traces(line_color=BLUE)
            fig.update_layout(yaxis_title="PKR", xaxis_title="", **PLOT_LAYOUT)
            st.plotly_chart(fig)

        if len(ms) >= 2:
            last, prev = ms["expense"].iloc[-1], ms["expense"].iloc[-2]
            if prev > 0:
                change = (last - prev) / prev * 100
                word = "up" if change > 0 else "down"
                st.info(f"Spending in {labels[-1]} is {word} {abs(change):.0f}% compared with {labels[-2]}.")


# -------------------------------------------------------------------- reports
def page_reports():
    page_header("Reports & Backup", "Download your data or restore it from a file.")
    df = load_df()

    st.subheader("Monthly Report")
    months = month_options(df)
    pick = st.selectbox("Choose a month", months, format_func=month_label)
    m = df[df["month"] == pick] if not df.empty else df
    inc = m.loc[m["type"] == "income", "amount"].sum()
    exp = m.loc[m["type"] == "expense", "amount"].sum()
    a, b, c = st.columns(3)
    a.metric("Income", format_pkr(inc))
    b.metric("Expenses", format_pkr(exp))
    c.metric("Savings", format_pkr(inc - exp))
    st.download_button(
        f"Download {month_label(pick)} report (CSV)",
        data=monthly_report_csv(df, pick),
        file_name=f"spendwise_report_{pick}.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("All Transactions")
    st.download_button(
        "Download all transactions (CSV)",
        data=transactions_csv(df),
        file_name=f"spendwise_transactions_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Restore from Backup")
    st.caption(
        "On Streamlit Community Cloud the database can be reset when the app restarts. "
        "Download your transactions regularly, and upload the file here to bring them back. "
        "Importing adds the rows to your existing data, so don't import the same file twice."
    )
    up = st.file_uploader("Upload a transactions CSV", type=["csv"])
    if up is not None:
        rows, errors = parse_import_csv(up)
        if rows:
            st.success(f"{len(rows)} valid row(s) ready to import.")
        for e in errors[:10]:
            st.warning(e)
        if len(errors) > 10:
            st.warning(f"...and {len(errors) - 10} more problem rows (they will be skipped).")
        if rows and st.button("Import these transactions"):
            try:
                n = db.add_transactions_bulk(rows)
                st.success(f"Imported {n} transaction(s).")
            except Exception as exc:
                st.error(f"Import failed: {exc}")


# ----------------------------------------------------------------- navigation
PAGES = {
    "📊  Dashboard": page_dashboard,
    "➕  Add Income": lambda: transaction_form("income"),
    "➖  Add Expense": lambda: transaction_form("expense"),
    "🎯  Budget Planner": page_budget,
    "🧾  Transactions": page_transactions,
    "📈  Analytics": page_analytics,
    "⬇️  Reports & Backup": page_reports,
}

with st.sidebar:
    st.markdown("## 💰 SpendWise")
    st.caption("Smart Expense Tracker")
    st.divider()
    choice = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption("Currency: Pakistani Rupee (PKR)")

try:
    PAGES[choice]()
except Exception as exc:  # last-resort safety net so users never see a raw crash
    st.error(f"Something went wrong: {exc}")
