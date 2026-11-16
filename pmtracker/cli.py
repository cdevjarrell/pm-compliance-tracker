"""Command line entry point.

Import exports:
    python -m pmtracker.cli import --active PATH --historical PATH
Show a month:
    python -m pmtracker.cli summary --month 10/2026
"""

import argparse
from pathlib import Path

import pandas as pd

from pmtracker.database import connect, save_work_orders
from pmtracker.importer import ImportValidationError, prepare, read_export
from pmtracker.report import (
    GOAL,
    cell_compliance,
    monthly_summary,
    quarter_of,
    quarter_to_date,
    weekly_summary,
    year_to_date,
)
from pmtracker.rules import load_asset_map, to_db_month, to_us_month
from pmtracker.settings import load_scope

ASSETS = "config/assets.csv"

def run_import(args):
    asset_map = load_asset_map(ASSETS)
    conn = connect(args.db)
    # Historical first, then active, so open PMs reflect the latest status.
    for source, path in (("historical", args.historical), ("active", args.active)):
        if not path:
            continue
        try:
            raw = read_export(path)
        except ImportValidationError as err:
            print(f"ERROR: {err}")
            continue
        clean, issues = prepare(raw, source, asset_map)
        save_work_orders(conn, clean, source, Path(path).name, len(issues))
        print(f"{source}: read {len(raw)} rows, saved {len(clean)}, {len(issues)} issues")
        for issue in issues[:20]:
            print(f"  [{issue.level}] WO {issue.wo_no}: {issue.message}")
        if len(issues) > 20:
            print(f"  ...and {len(issues) - 20} more")
    conn.close()

def run_summary(args):
    try:
        month = to_db_month(args.month)
    except ValueError as err:
        print(f"Error: {err}")
        return
    conn = connect(args.db)
    scope = load_scope()
    table, overall = monthly_summary(conn, month, scope)
    if overall is None:
        print(f"No work orders found for {args.month}")
        conn.close()
        return
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 160):
        print(table)
        print()
        print(cell_compliance(conn, month, scope).to_string(index=False))
        print()
        weeks = weekly_summary(conn, month, scope)
        weeks["percent"] = (weeks["percent"] * 100).round(1)
        print(weeks.to_string(index=False))
    status = "MEETS" if overall >= GOAL else "BELOW"
    print(f"\nOverall {args.month}: {overall:.1%} ({status} {GOAL:.0%} goal)")
    
    year, month_number = int(month[:4]), int(month[5:])
    quarter = quarter_of(month_number)
    print_period(f"Q{quarter} {year} to date", quarter_to_date(conn, year, quarter, scope=scope))
    print_period(f"{year} year to date", year_to_date(conn, year, scope=scope))
    conn.close()

def print_period(label, result):
    """Print one quarter-to-date or year-to-date line."""
    if result is None:
        print(f"{label}: no finished months yet")
        return
    months = ", ".join(to_us_month(m) for m in result["months"])
    print(f"{label}: {result['average']:.1%} average of months (official), "
          f"{result['pooled']:.1%} pooled [{months}]")
    

def main():
    parser = argparse.ArgumentParser(prog="pmtracker")
    parser.add_argument("--db", default="pm_tracker.db", help="SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)
    
    imp = sub.add_parser("import", help="Import IFS exports")
    imp.add_argument("--active", help="Active work orders export (.xlsx or .csv)")
    imp.add_argument("--historical", help="Historical work orders export (.xlsx or .csv)")
    imp.set_defaults(func=run_import)
    
    summ = sub.add_parser("summary", help="Show one month's compliance")
    summ.add_argument("--month", required=True, help="Month as MM/YYYY, e.g. 10/2026")
    summ.set_defaults(func=run_summary)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()