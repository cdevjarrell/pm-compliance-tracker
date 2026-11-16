"""PM Compliance Tracker: browser app.

Run from the project folder:
    streamlit run Home.py
"""

from datetime import date
from pathlib import Path

import streamlit as st

from pmtracker.database import connect
from pmtracker.report import GOAL, quarter_of, quarter_to_date, year_to_date
from pmtracker.settings import load_scope

DB_PATH = Path("pm_tracker.db")

st.set_page_config(page_title="PM Compliance Tracker", layout="wide")
st.title("PM Compliance Tracker")
st.write("Preventive maintenance completion against the plant's 95% goal.")

if not DB_PATH.exists():
    st.info("No data yet. Import exports with the command lind first, then refresh this page.")
    st.stop()

today = date.today()
quarter = quarter_of(today.month)
conn = connect(DB_PATH)
scope = load_scope()
qtd = quarter_to_date(conn, today.year, quarter, today, scope)
ytd = year_to_date(conn, today.year, today, scope)
conn.close()

def show(column, label, result):
    """One metric title: official average, with the pooled number underneath."""
    if result is None:
        column.metric(label, "No finished months")
        return
    gap = result["average"] - GOAL
    column.metric(label, f"{result['average']:.1%}", f"{gap:+.1%} vs goal")
    column.caption(f"Pooled: {result['pooled']:.1%} over {len(result['months'])} finished month(s)")

left, right = st.columns(2)
show(left, f"Q{quarter} {today.year} to date", qtd)
show(right, f"{today.year} year to date", ytd)
st.caption("Official numbers are the average of monthly percentages. The current month is not included until it ends.")