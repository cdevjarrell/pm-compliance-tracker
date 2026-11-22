"""PM compliance calculations from the databse.

Rules (matching the plant's Excel workbook):
- A PM counts in the month and week of its Planned Start (Sunday to Saturday weeks).
  A week that crosses two months is split, sso each month only counts its own days.
- Cells turned off on the scope settings for a month are left out of every total.
- Quarters are calnedar quarters (Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec).
- Quarter-to-date and year-to-date use finished months only. The official number is the
  average of the monthly percentages. The pooled number is shown next to it for comparison."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from pmtracker.rules import FREQUENCIES
from pmtracker.settings import is_tracked

GOAL = 0.95

def round_percent(value):
    """Round a fraction to the nearest whole percent, halves up like Excel's ROUND.
    0.9499 -> 0.95, 0.945 -> 0.95, 0.9449 -> 0.94. Returns None for a missing value.
    Rounding to 9 places first clears float noise, so 0.945 is neer read as 0.944999999.
    """
    
    if value is None or pd.isna(value):
        return None
    exact = Decimal(repr(round(float(value), 9)))
    return float(exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def format_percent(value, signed=False):
    """Whole-percent text: '95%', '+2%' / '-3%' when signed. Blank for a missing value."""
    rounded = round_percent(value)
    if rounded is None:
        return ""
    whole = int(round(rounded * 100))
    return f"{whole:+d}%" if signed else f"{whole}%"

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
    out["percent"] = [format_percent(c / s) for c, s in zip(out["completed"], out["scheduled"])]
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

WATCH_BAND = 0.10 # within 10 points under the goal is "Watch", the same band the workbook uses

def status_for(percent, goal=GOAL):
    """Dashboard status for one finished month, judged on the whole-percent value shown."""
    percent = round_percent(percent)
    if percent >= goal:
        return "On target"
    if percent >= round_percent(goal - WATCH_BAND):
        return "Watch"
    return "Below target"

def monthly_detail(conn, year, today=None, scope=None):
    """One row per month (Jan to Dec) for the dashboard table and chart.
    
    Only finished months get a percentage and a status, like "reported" months in the workbook.
    The current month shows "In progress" and months with no work orders show "No data".
    """
    
    today = today or date.today()
    results = month_results(conn, year, scope).set_index("month")
    done = finished_months([f"{year}-{m:02d}" for m in range(1, 13)], today)
    rows = []
    for m in range(1, 13):
        key = f"{year}-{m:02d}"
        scheduled = int(results.loc[key, "scheduled"]) if key in results.index else 0
        completed = int(results.loc[key, "completed"]) if key in results.index else 0
        percent = None
        if scheduled == 0:
            status = "No data"
        elif key in done:
            percent = round_percent(completed / scheduled)
            status = status_for(percent)
        else:
            status = "In progress"
        rows.append({
            "month": key,
            "scheduled": scheduled,
            "completed": completed,
            "percent": percent,
            "goal": GOAL,
            "vs_goal": None if percent is None else round_percent(percent - GOAL),
            "status": status,
        })
    return pd.DataFrame(rows)

def reported_months(conn, year, today=None, scope=None):
    """Finished months of the year that have at least one scheduled PM, oldest first."""
    today = today or date.today()
    results = month_results(conn, year, scope)
    with_data = list(results.loc[results["scheduled"] >0, "month"])
    return finished_months(with_data, today)

def ytd_by_cell(conn, year, today=None, scope=None, cells=()):
    """Year-to-date scheduled, completed and percent for each cell, pooled per cell.
    
    Matches the YEAR TO DATEBY CELL table in the workbook:
    - Only reported months count (finished months that have PMs).
    - months_tracked is how many of those months the cell is turned on in scope,
      whether or not it had PMs that month.
    - Every cell in `cells` is listed, even with 0 mnths tracked, plus any cell found in the data.
    Unlike the workbook, every cell is inclined, so the column totals equal to the pooled YTD.
    """
    
    months = reported_months(conn, year, today, scope)
    df = apply_scope(load_work_orders(conn, year=year), scope)
    df = df[df["month"].isin(months)]
    counts= df.groupby("cell")["completed"].agg(["count", "sum"])
    rows = []
    for cell in sorted(set(cells) | set(counts.index)):
        scheduled = int(counts.loc[cell, "count"]) if cell in counts.index else 0
        completed = int(counts.loc[cell, "sum"]) if cell in counts.index else 0
        rows.append({
            "cell": cell,
            "scheduled": scheduled,
            "completed": completed,
            "percent": completed / scheduled if scheduled else None,
            "months_tracked": sum(is_tracked(scope or {}, m, cell) for m in months),
        })
    return pd.DataFrame(rows, columns=["cell", "scheduled", "completed", "percent", "months_tracked"])