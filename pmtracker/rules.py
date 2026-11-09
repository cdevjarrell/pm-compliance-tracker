"""Business Rules: Pm frequency, Sundary-start week numbers, and ObjectID-to_cell mapping"""

import csv
import re
from datetime import date

# Directive test from IFS -> frequency catgory used in the report.
# "3 Years PM" is counted with Annual, the same way the current Excel workbook does  it.
FREQUENCY_MAP = {
    "weekly pm": "Weekly",
    "bi-weekly pm": "Bi-weekly",
    "monthly pm": "Monthly",
    "quarterly pm": "Quarterly",
    "6 months pm": "Semi-Annual",
    "annual pm": "Annual",
    "3 years pm": "Annual",
}

# Report column order
FREQUENCIES = ["Weekly", "Bi-weekly", "Monthly", "Quarterly", "Semi-Annual", "Annual"]

# Three-digit codes that do not follow the normal "cell digits" pattern
SPECIAL_CODES = {"441": "SBC"}

def parse_frequency(directive):
    """Return the frequency catgory for a Directive value, or None if it is not a PM."""
    if directive is None:
        return None
    key = " ".join(str(directive).split()).lower() # Trims and collapses extra spaces
    return FREQUENCY_MAP.get(key)

def week_number(day):
    """Week of the year with weeks running Sunday to Saturday (same as Excel WEEKNUM(date, 1)).
    
    Week 1 is the week that containts January 1.
    """
    jan1 = date(day.year, 1, 1)
    days_before_jan1 = (jan1.weekday() + 1) % 7 # Python lists Monday as 0. This shifts Sunday to 0 instead.
    day_of_year = day.timetuple().tm_yday
    return (day_of_year - 1 + days_before_jan1) // 7 + 1

def load_asset_map(path):
    """Read config/assets.csv into a dictionary of {OBJECT_ID: cell}."""
    asset_map = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            object_id = row["object_id"].strip().upper()
            if object_id:
                asset_map[object_id] = row["cell"].strip()
    return asset_map

def lookup_cell(object_id, asset_map):
    """Return the cell for an ObjectID, or None if it is not in th asset list."""
    if object_id is None:
        return None
    return asset_map.get(str(object_id).strip().upper())

def suggest_cell(object_id):
    """Guess a cell from the digits in an unknown ObjectID, e.g. TP444 -> 4400.4.
    
    Used only to hlep when an import flags an unmapped ObjectID. Returns None if no guess.
    """
    match = re.match(r"^[A-Z]+(\d{3})", str(object_id).strip().upper())
    if not match:
        return None
    code = match.group(1)
    if code in SPECIAL_CODES:
        return SPECIAL_CODES[code]
    return f"{code[:2]}00.{code[2]}"

def to_db_month(text):
    """Convert a US month like "10/2026" to the stored form "2026-10"."""
    match = re.fullmatch(r"\s*(\d{1,2})/(\d{4})\s*", str(text))
    if not match or not 1 <= int(match.group(1)) <= 12:
        raise ValueError(f"Month must look like MM/YYYY, for example 10/2026 (got '{text}')")
    return f"{match.group(2)}-{int(match.group(1)):02d}"

def to_us_month(db_month):
    """Conver the stored form "2026-10" back to the "10/2026" for display."""
    year, month = db_month.split("-")
    return f"{month}/{year}"