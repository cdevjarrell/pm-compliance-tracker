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
from pmtracker.report import GOAL, cell_compliance, monthly_summary
from pmtracker.rules import load_asset_map, to_db_month

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
    table, overall = monthly_summary(conn, month)
    if overall is None:
        print(f"No work orders found for {args.month}")
        return
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", 160):
        print(table)
        print()
        print(cell_compliance(conn, month).to_string(index=False))
    status  = "MEETS" if overall >= GOAL else "BELOW"
    print(f"\nOverall {args.month}: {overall:.1%} ({status} {GOAL:.0%} goal)")
    conn.close()

def main():
    parser = argparse.ArgumentParser(prog="pmtracker")
    parser.add_argument("--db", default="pm_tracker.db", help="SQLite database file")
    sub = parser.add_subparsers(dest="command", required=True)
    
    imp = sub.add_parser("import", help="Import IFS exports")
    imp.add_argument("--active", help="Active work orders export (.xlsx or .csv)")
    imp.add_argument("--historical", help="Historical work orders export (.xlsx or .csv)")
    imp.set_defaults(func=run_import)
    
    summ = sub.add_parser("summary", help="Show one month's complliance")
    summ.add_argument("--month", required=True, help="Month as MM/YYY, e.g. 10/2026")
    summ.set_defaults(func=run_summary)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()