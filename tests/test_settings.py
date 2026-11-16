import pandas as pd

from pmtracker.settings import (
    is_tracked,
    load_scope,
    save_scope,
    scope_grid,
    update_scope_year,
    validate_assets,
)

def test_validate_assets_cleans_and_finds_problems():
    df = pd.DataFrame({
        "object_id": [" tp444 ", "TP444", "DC221", "", ""],
        "description": ["Trim Press", "Copy", "Die Cast", "", "No ID"],
        "cell": ["4400.4", "4400.4", "", "", "2200.1"],
    })
    clean, errors = validate_assets(df)
    assert clean.loc[0, "object_id"] == "TP444"  # Trimmed and uppercased
    assert len(clean) == 4  # The fully blank row is dropped
    assert any("TP444 is listed more than once" in e for e in errors)
    assert any("cell is blank for DC221" in e for e in errors)
    assert any("ObjectID is blank" in e for e in errors)

def test_cells_are_tracked_by_default():
    assert is_tracked({}, "2026-10", "4400.4") is True

def test_scope_round_trip(tmp_path):
    path = tmp_path / "scope.csv"
    grid = scope_grid({}, 2026, ["2200.1", "4400.4"])
    grid.loc["2200.1", "Oct"] = False
    scope = update_scope_year({}, 2026, grid)
    save_scope(scope, path)
    
    loaded = load_scope(path)
    assert is_tracked(loaded, "2026-10", "2200.1") is False
    assert is_tracked(loaded, "2026-11", "2200.1") is True
    assert is_tracked(loaded, "2026-10", "4400.4") is True
    assert len(pd.read_csv(path)) == 1  # Only the turned-off entry is written

def test_update_scope_year_leaves_other_years_alone():
    scope = {("2025-03", "SBC"): False}
    grid = scope_grid(scope, 2026, ["SBC"])
    new_scope = update_scope_year(scope, 2026, grid)
    assert new_scope[("2025-03", "SBC")] is False