"""Read IFS exports, validate them, and turn them into clean work order records."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pmtracker.rules import lookup_cell, parse_frequency, suggest_cell, week_number

REQUIRED_COLUMNS = [
    "WO No",
    "Object ID",
    "Object Description",
    "Directive",
    "Maint Org",
    "Status",
    "Planned Start",
]

MAINT_ORG = "MAINT" # HPDC Maintenance. Facilities is "FACILITY" and will be skipped for now.
FINISHED = "Finished"

class ImportValidationError(Exception):
    """Raised when a file cannot be imported at all (for example, missing columns)."""

@dataclass
class Issue:
    level: str # "error" = row left out, "warning" = row kept but worth checking
    wo_no: str
    message: str

def read_export(path):
    """Load an IFS export (.xlsx or .csv) and keep only the columns the app needs."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str)
    elif path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    else:
        raise ImportValidationError(f"{path.name}: unsupported file type {path.suffix}")
    
    df.columns = [str(c).strip() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ImportValidationError(f"{path.name}: missing columns {missing}")
    return df[REQUIRED_COLUMNS].copy()

def prepare(df, source, asset_map):
    """Validate and classify one export.
    
    source is "active" (open PMs) or "historical" (completed PMs).
    Returns (clean DataFrame, list of Issue).
    """
    if source not in ("active", "historical"):
        raise ValueError("source must be 'active' or 'historical'")
    
    issues = []
    records = []
    seen = set()
    
    for _, row in df.iterrows():
        wo_no = str(row["WO No"]).strip()
        object_id = str(row["Object ID"]).strip().upper()
        status = str(row["Status"]).strip()
        
        # 1. Only HPDC Maintenance work orders
        if str(row["Maint Org"]).strip().upper() != MAINT_ORG:
            continue
        
        # 2. Duplicate work order numbers.
        if wo_no in seen:
            issues.append(Issue("error", wo_no, "Duplicate WO Number; kept the first one"))
            continue
        seen.add(wo_no)
        
        # 3. Directive must be known PM frequency.
        frequency = parse_frequency(row["Directive"])
        if frequency is None:
            issues.append(Issue("error", wo_no, f"Directive '{row['Directive']}' is not a known PM"))
            continue
        
        # 4. ObjectID must be in the asset list
        cell = lookup_cell(object_id, asset_map)
        if cell is None:
            guess = suggest_cell(object_id)
            hint = f" (looks like {guess})" if guess else ""
            issues.append(Issue("error", wo_no, f"ObjectID {object_id} is not in assets.csv{hint}"))
            continue
        
        # 5. Planned Start must be a real date, e.g. "10/30/2026 20:30".
        planned = pd.to_datetime(row["Planned Start"], errors="coerce")
        if pd.isna(planned):
            issues.append(Issue("error", wo_no, f"Bad Planned Start '{row['Planned Start']}'"))
            continue
        
        # 6. Status checks.
        if source == "historical" and status != FINISHED:
            issues.append(Issue("error", wo_no, f"Historical row has status '{status}', expected Finished"))
            continue
        if source == "active" and status == "WorkDone":
            issues.append(Issue("warning", wo_no, "Status is WorkDone; move it to Finished in IFS"))
        
        records.append(
            {
                "wo_no": wo_no,
                "object_id": object_id,
                "object_description": str(row["Object Description"]).strip(),
                "directive": str(row["Directive"]).strip(),
                "status": status,
                "planned_start": planned.strftime("%Y-%m-%d %H:%M"),
                "cell": cell,
                "frequency": frequency,
                "month": planned.strftime("%Y-%m"),
                "week": week_number(planned.date()),
                "completed": 1 if source == "historical" else 0,
            }
        )
    return pd.DataFrame(records), issues