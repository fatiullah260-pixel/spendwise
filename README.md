# 💰 SpendWise – Smart Expense Tracker

A personal expense tracker built with **Streamlit**, **SQLite**, **Pandas** and **Plotly**.
Track income and expenses, plan budgets, explore charts and download reports. Amounts are in Pakistani Rupees (Rs.).

## Features

- **Dashboard** – total income, expenses, balance, monthly savings, recent transactions, monthly overview
- **Add Income / Add Expense** – with validation (amounts must be greater than zero)
- **Budget Planner** – overall and per-category monthly budgets with progress bars and warnings (80% and over 100%)
- **Transactions** – filter by date, category and type; edit; delete with confirmation
- **Analytics** – income vs expenses, category pie chart, monthly spending bars, trends
- **Reports & Backup** – CSV export, monthly report, and CSV import to restore data

## Project structure

```
spendwise/
├── app.py            # Streamlit user interface (all pages)
├── database.py       # SQLite tables and queries
├── utils.py          # Formatting, calculations, CSV helpers, styling
├── requirements.txt  # Python packages
├── .gitignore        # Files Git should ignore
├── README.md         # This file
└── .streamlit/
    └── config.toml   # Theme colours
```

## Run locally

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The database is created automatically at `data/spendwise.db` the first time you run the app.
Your records stay saved when you restart the app.

## Deploy on Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, choose your repository, branch `main` and main file `app.py`.
4. Click **Deploy**.

## ⚠️ Data persistence on the cloud

Streamlit Community Cloud does not guarantee permanent disk storage. The SQLite file can be reset when the app
restarts, is updated, or goes to sleep. To protect your data:

- Use **Reports & Backup → Download all transactions** regularly.
- After a reset, upload that CSV in **Restore from Backup** to bring your data back.
- For permanent online storage, switch to a hosted database (for example Supabase or Neon, both with free plans).
- Never commit `data/` or `*.db` files to GitHub (they are already in `.gitignore`).

## Notes

No API keys, passwords or paid services are used.
