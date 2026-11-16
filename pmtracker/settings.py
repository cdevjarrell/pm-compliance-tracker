"""Read and save the editable settings: the asset list and the monthly cell scope."""

from pathlib import Path

import pandas as pd

ASSETS_PATH = Path("config/assets.csv")
SCOPE_PATH = Path("config/scope.csv")
ASSET_COLUMNS = ["object_id", "description", "cell"]
SCOPE_COLUMNS = ["month", "cell", "tracked"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ---------- Assets ----------

def load_assets(path=ASSETS_PATH):
    """Return the asset list as a DataFrame with columns object_id, description, cell."""
    df = pd.read_csv(path, dtype=str).fillna("")
    return df[ASSET_COLUMNS]

def validate_assets(df):
    """Check an edited asset table. Returns (clean DataFrame, list of error messages)."""
    df = df.copy().fillna("")
    for col in ASSET_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    df["object_id"] = df["object_id"].str.upper()
    df = df[(df != "").any(axis=1)] # drop rows left completely blank
    
    errors = []
    for i, row in df.iterrows():
        if not row["object_id"]:
            errors.append(f"Row {i + 1}: ObjectID is blank")
        if not row["cell"]:
            errors.append(f"Row {i + 1}: cell is blank for {row['object_id'] or 'this row'}")
    dupes = df.loc[df["object_id"].duplicated() & (df["object_id"] != ""), "object_id"]
    for object_id in sorted(set(dupes)):
        errors.append(f"ObjectID {object_id} is listed more than once")
    return df.reset_index(drop=True), errors

def save_assets(df, path=ASSETS_PATH):
    """Write the asset list back to CSV, sorted by cell then ObjectID."""
    df.sort_values(["cell", "object_id"]).to_csv(path, index=False, columns=ASSET_COLUMNS)

# ---------- Scope ----------
# scope.csv only needs rows for cells that were turned off.
# A cell with no row for a month is tracked, so new months work without any setup.

def load_scope(path=SCOPE_PATH):    
    """Return {(month, cell): tracked} where month is "YYYY-MM" and tracked True/False."""
    path = Path(path)
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str)
    return {(r.month, r.cell): r.tracked.strip() == "1" for r in df.itertuples()}

def is_tracked(scope, month, cell):
    """True if the cell counts toward totals in that month. Default is tracked."""
    return scope.get((month, cell), True)

def scope_grid(scope, year, cells):
    """Build a cells x months table of True/False for one year, like the Scope tab."""
    data = {
        name: [is_tracked(scope, f"{year}-{m:02d}", cell) for cell in cells]
        for m, name in enumerate(MONTH_NAMES, start=1)
    }
    return pd.DataFrame(data, index=pd.Index(cells, name="Cell"))

def update_scope_year(scope, year, grid):
    """Return a new scope dict with one year replaced by the edited grid."""
    new_scope = {k: v for k, v in scope.items() if not k[0].startswith(f"{year}-")}
    for cell, row in grid.iterrows():
        for m, name in enumerate(MONTH_NAMES, start=1):
            new_scope[(f"{year}-{m:02d}", cell)] = bool(row[name])
    return new_scope

def save_scope(scope, path=SCOPE_PATH):
    """Write the scope to CSV. Only untracked entries are saved."""
    rows = [
        {"month": month, "cell": cell, "tracked": 0}
        for (month, cell), tracked in sorted(scope.items())
        if not tracked
    ]
    pd.DataFrame(rows, columns=SCOPE_COLUMNS).to_csv(path, index=False)