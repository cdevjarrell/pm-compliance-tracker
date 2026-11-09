"""Generate fake IFS exports that match the real export format.

Run: python -m pmtracker.generate_sample
Creates data/sample/ActiveWorkORders_sample.xlsx and HistoricalWorkOrders_sample.xlsx.
No real plant data is used; the public repo only ever contains these  files.
"""

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from pmtracker.importer import REQUIRED_COLUMNS

START = date(2024, 1, 1)
OUT_DIR = Path("data/sample")

# Directive text -> (days between PMs, share of sassets that have this PM)
SCHEDULES = {
    "Weekly PM": (7, 0.15),
    "Bi-Weekly PM": (14, 0.20),
    "Monthly PM": (30, 0.80),
    "Quarterly PM": (91, 0.50),
    "6 Months PM": (182, 0.30),
    "Annual PM": (365, 0.50),
    "3 Years PM": (1095, 0.05),
}

def month_end(day):
    nxt = date(day.year + (day.month // 12), day.month % 12 + 1, 1)
    return nxt - timedelta(days=1)

def build_rows(assets, today, rng):
    rows = []
    wo_no = 500000
    month_rate = {} # Each month gets its own plant-wide completion rate
    last_day = month_end(today)
    
    for asset in assets:
        cell_shift = rng.uniform(-0.03, 0.02)
        for directive, (interval, share) in SCHEDULES.items():
            if rng.random() > share:
                continue
            day = START + timedelta(days=rng.randrange(interval))
            while day <= last_day:
                key = (day.year, day.month)
                if key not in month_rate:
                    month_rate[key] = rng.uniform(0.90, 0.99)
                planned = datetime(day.year, day.month, day.day, rng.choice([6, 14, 20]), 30)
                
                if key == (today.year, today.month):
                    finished = day <= today and rng.random() < 0.80
                else:
                    finished = day < today and rng.random() < month_rate[key] + cell_shift
                
                if finished:
                    status = "Finished"
                else:
                    status = rng.choice(["WorkRequest", "WorkRequest", "Started"])
                
                rows.append({
                    "WO No": str(wo_no),
                    "Object ID": asset["object_id"],
                    "Object Description": asset["description"],
                    "Directive": directive,
                    "Maint Org": "MAINT",
                    "Status": status,
                    "Planned Start": planned.strftime("%m/%d/%Y %H:%M"),
                })
                wo_no += 1
                day += timedelta(days=interval)
    return rows

def add_problem_rows(active):
    """A few bad rows so the validator has something to catch."""
    base = {"Object Description": "Test", "Maint Org": "MAINT", "Status": "WorkRequest", "Planned Start": active[0]["Planned Start"], "Directive": "Monthly PM"}
    active.append({**base, "WO No": "900001", "Object ID": "TP448"}) # Unknown ObjectID
    active.append({**base, "WO No": "900002", "Object ID": "HV100", "Maint Org": "FACILITY"})
    active.append({**base, "WO No": "900003", "Object ID": "DC221", "Directive": "Repair"})
    active.append({**base, "WO No": "900004", "Object ID": "DC222", "Status": "WorkDone"})
    active.append(dict(active[0])) # Duplicate WO No

def main(today=None, seed=42):
    today = today or date.today()
    rng = random.Random(seed)
    with open("config/assets.csv", newline="", encoding="utf-8") as f:
        assets = list(csv.DictReader(f))
    
    rows = build_rows(assets, today, rng)
    historical = [r for r in rows if r["Status"] == "Finished"]
    active = [r for r in rows if r["Status"] != "Finished"]
    add_problem_rows(active)
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(active, columns=REQUIRED_COLUMNS).to_excel(
        OUT_DIR / "ActiveWorkOrders_sample.xlsx", index=False)
    pd.DataFrame(historical, columns=REQUIRED_COLUMNS).to_excel(
        OUT_DIR / "HistoricalWorkOrders_sample.xlsx", index=False)
    print(f"Wrote {len(active)} active and {len(historical)} historical rows to {OUT_DIR}")


if __name__ == "__main__":
    main()