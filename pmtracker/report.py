"""Monthly PM compliance summary built from the database"""

import pandas as pd

from pmtracker.rules import FREQUENCIES

GOAL = 0.95

def monthly_summary(conn, month):
    """Scheduled and completed counts by cell and frequency for one month ("YYYY-MM")."""
    df = pd.read_sql_query(
        "SELECT cell, frequency, completed FROM work_orders WHERE month = ?", conn, params=(month,)
    )
    if df.empty:
        return pd.DataFrame(), None
    
    scheduled = df.pivot_table(index="cell", columns="frequency", values="completed", aggfunc="count", fill_value=0)
    completed = df.pivot_table(index="cell", columns="frequency", values="completed", aggfunc="sum", fill_value=0)
    
    cols = [f for f in FREQUENCIES if f in scheduled.columns]
    table = pd.concat({"Scheduled": scheduled[cols], "Completed": completed[cols]}, names=["Metric"])
    table["Total"] = table.sum(axis=1)
    table = table.swaplevel().sort_index(level=0, sort_remaining=False) # group rows by cell
    
    overall = df["completed"].sum() / len(df)
    return table, overall

def cell_compliance(conn, month):
    """Completion percentage for each cell in one month."""
    df = pd.read_sql_query(
        "SELECT cell, COUNT(*) AS scheduled, SUM(completed) AS completed "
        "FROM work_orders WHERE month = ? GROUP BY cell ORDER BY cell",
        conn, params=(month,),
    )
    df["percet"] = (df["completed"] / df["scheduled"] * 100).round(1)
    return df