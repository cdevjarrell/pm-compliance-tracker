"""PM compliance calculations from the databse.

Rules (matching the plant's Excel workbook):
- A PM counts in the month and week of its Planned Start (Sunday to Saturday weeks).
  A week that crosses two months is split, sso each month only counts its own days.
- Cells turned off on the scope settings for a month are left out of every total.
- Quarters are calnedar quarters (Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec).
- Quarter-to-date and year-to-date use finished months only. The official number is the
  average of the monthly percentages. The pooled number is shown next to it for comparison."""

from datetime import date

import pandas as pd

from pmtracker.rules import FREQUENCIES
from pmtracker.settings import is_tracked

GOAL = 0.95

def load_work_orders(conn, month=None, year=None):
    """Read work orders for one month("YYYY-MM"), one year, or everything."""
    sql = "SELECT cell, frequency, month, week, completed FROM work_orders"
    params = ()
    if month:
        sql += " WHERE month = ?"
        params = (month,)
    elif year:
        sql += " WHERE month LIKE ?"
        params = (f"{year}-%",)
    return pd.read_sql_query(sql, conn, params=params)

def apply_scope(df, scope):
    """Drop rows for cells that are not tracked in their month."""
    if not scope or df.empty:
        return df
    keep = [is_tracked(scope, m, c) for m, c in zip(df["month"], df["cell"])]
    return df[keep]

def monthly_summary(conn, month, scope=None):
    """Scheduled and completed counts by cell and frequency for one month ("YYYY-MM")."""
    df = apply_scope(load_work_orders(conn, month=month), scope)
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

def cell_compliance(conn, month, scope=None):
    """Completion percentage for each cell in one month."""
    df = apply_scope(load_work_orders(conn, month=month), scope)
    out = df.groupby("cell").agg(scheduled=("completed", "count"), completed=("completed", "sum")).reset_index()
    out["percent"] = (out["completed"] / out["scheduled"] * 100).round(1)
    return out

def weekly_summary(conn, month, scope=None):
    """Scheduled, completed and percent for each week of one month, plant-wide."""
    df = apply_scope(load_work_orders(conn, month=month), scope)
    out = df.groupby("week").agg(scheduled=("completed", "count"), completed=("completed", "sum")).reset_index()
    out["percent"] = out["completed"] / out["scheduled"]
    return out

def month_results(conn, year, scope=None):
    """One row per month that has data: scheduled, completed and percent."""
    df = apply_scope(load_work_orders(conn, year=year), scope)
    out = df.groupby("month").agg(scheduled=("completed", "count"), completed=("completed", "sum")).reset_index()
    out["percent"] = out["completed"] / out["scheduled"]
    return out

def finished_months(months, today):
    """Keep only the months ("YYYY-MM") that ended before today."""
    current = f"{today.year}-{today.month:02d}"
    return [m for m in months if m < current]

def period_compliance(results, months):
    """Average-of-months and pooled compliance for a list of months.
    
    results in the DataFrame from months_results. Months with no scheduled PMs are skipped.
    Returns a dict, or None if none of the months have data.
    """
    rows = results[results["month"].isin(months) & (results["scheduled"] > 0)]
    if rows.empty:
        return None
    return {
        "average": rows["percent"].mean(),
        "pooled": rows["completed"].sum() / rows["scheduled"].sum(),
        "months": list(rows["month"]),
    }

def quarter_of(month_number):
    """Calendar quarter (1-4) for a month number (1-12)."""
    return (month_number - 1) // 3 + 1

def year_to_date(conn, year, today=None, scope=None):
    """Year-to-date compliance using finished months only."""
    today = today or date.today()
    months = [f"{year}-{m:02d}" for m in range(1,13)]
    return period_compliance(month_results(conn, year, scope), finished_months(months, today))

def quarter_to_date(conn, year, quarter, today=None, scope=None):
    """Quarter-to-date compliance using finished months only."""
    today = today or date.today()
    first = (quarter - 1) * 3 + 1
    months = [f"{year}-{m:02d}" for m in range(first, first + 3)]
    return period_compliance(month_results(conn, year, scope), finished_months(months, today))