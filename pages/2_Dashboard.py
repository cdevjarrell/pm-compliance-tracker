"""Dashboard: year-to-date headline, monthly detail, monthly chart against goal, and cells.

Laid out like the Dashboard tab of the plant's Excel workbook.
"""

from datetime import date
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from pmtracker.database import connect
from pmtracker.report import GOAL, format_percent, monthly_detail, round_percent, year_to_date, ytd_by_cell
from pmtracker.settings import MONTH_NAMES, load_assets, load_scope

DB_PATH = Path("pm_tracker.db")
STATUS_COLORS = {"On target": "#1b7f3b", "Watch": "#b26a00", "Below target": "#b3261e"}

st.set_page_config(page_title="Dashboard", layout="wide")
st.title("Dashboard")

if not DB_PATH.exists():
    st.info("No data yet. Import exports with the command line first, then refresh this page.")
    st.stop()

today = date.today()
year = int(st.sidebar.number_input("Year", min_value=2020, max_value=2100, value=today.year, step=1))

conn = connect(DB_PATH)
scope = load_scope()
cells = load_assets()["cell"].unique()
ytd = year_to_date(conn, year, today, scope)
detail = monthly_detail(conn, year, today, scope)
by_cell = ytd_by_cell(conn, year, today, scope, cells)
conn.close()

def vs_goal(value):
    """Whole-percent gap to the goal, e.g. '+1%', using the rounded value that is shown."""
    return format_percent(round_percent(value) - GOAL, signed=True)

def as_text(df, *columns, signed=()):
    """Copy of df with the given fraction columns shown as whole percents ('95%')."""
    out = df.copy()
    for col in columns:
        out[col] = [format_percent(v, signed=col in signed) for v in out[col]]
    return out

# ----------- Year to date ----------
st.subheader(f"{year} year to date")
if ytd is None:
    st.write("No finished months yet.")
else:
    a, b, c = st.columns(3)
    a.metric("Average of months (official)", format_percent(ytd["average"]), f"{vs_goal(ytd['average'])} vs goal")
    b.metric("Pooled", format_percent(ytd["pooled"]), f"{vs_goal(ytd['pooled'])} vs goal")
    c.metric("Finished months", len(ytd["months"]))
    st.caption("Official is the average of monthly percentages. Pooled is total completed / total scheduled.")

# ---------- Monthly detail ----------
st.subheader("Monthly Detail")
table = as_text(detail, "percent", "goal", "vs_goal", signed=("vs_goal",))
table["month"] = [MONTH_NAMES[int(m[5:]) -1] for m in table ["month"]]
styled = table.style.map(lambda s: f"color: {STATUS_COLORS.get(s, 'gray')}; font-weight:  600", subset=["status"])
st.dataframe(
    styled,
    hide_index=True,
    width="stretch",
    column_config={
        "month": "Month",
        "scheduled": "Scheduled",
        "completed": "Completed",
        "status": "Status",
        "percent": "% Complete",
        "goal": "Goal",
        "vs_goal": "vs Goal",
    },
)
st.caption("Watch means within 10 points under the goal. The current month shows In progress until the date ends.")

# ---------- Chart ----------
st.subheader("Monthly PM completion against goal")
chart = detail.assign(month=table["month"]) # numbers, not text, for plotting
reported = chart[chart["percent"].notna()]
if reported.empty:
    st.write("No finished months to chart yet.")
else:
    low = min(0.80, float(reported["percent"].min()) - 0.05) # never cut off a bad month
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=reported["month"], y=reported["percent"], mode="lines+markers", name="% Complete",
        hovertemplate="%{x}: %{y:.0%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=MONTH_NAMES, y=[GOAL] * 12, mode="lines", name=f"Goal ({GOAL:.0%})",
        line=dict(dash="dash", color="firebrick"), hoverinfo="skip",
    ))
    fig.update_layout(
        yaxis=dict(tickformat=".0%", range=[max(low, 0), 1.02]),
        xaxis=dict(categoryorder="array", categoryarray=MONTH_NAMES),
        height=380,
        margin=dict(t=20),
    )
    st.plotly_chart(fig, width="stretch")

# ---------- By cell ----------
st.subheader("Year to date by cell")
st.dataframe(
    as_text(by_cell, "percent"),
    hide_index=True,
    width="stretch",
    column_config={
        "cell": "Cell",
        "scheduled": "Completed",
        "completed": "Completed",
        "months_tracked": "Months tracked",
        "percent": "% Complete",
    },
)
st.caption("Pooled per cell over finished months. Cells with 0 months tracked are turned off in Settings.")