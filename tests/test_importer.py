import pandas as pd
import pytest

from pmtracker.database import connect, save_work_orders
from pmtracker.importer import prepare
from pmtracker.report import monthly_summary

ASSETS = {"TP444": "4400.4", "DC221": "2200.1"}

def make_rows(*rows):
    cols = ["WO No", "Object ID", "Object Description", "Directive", "Maint Org", "Status", "Planned Start"]
    return pd.DataFrame(rows, columns=cols)

def test_good_row_is_classified():
    df = make_rows(("1", "TP444", "Trim Press", "Monthly PM", "MAINT", "Finished", "10/30/2026 20:30"))
    clean, issues = prepare(df, "historical", ASSETS)
    assert issues == []
    row = clean.iloc[0]
    assert row["cell"] == "4400.4"
    assert row["frequency"] == "Monthly"
    assert row["month"] == "2026-10"
    assert row["week"] == 44
    assert row["completed"] == 1

def test_facility_rows_are_skipped():
    df = make_rows(("1", "TP444", "x", "Monthly PM", "FACILITY", "WorkRequest", "10/30/2026 20:30"))
    clean, issues = prepare(df, "active", ASSETS)
    assert clean.empty and issues == []

def test_bad_rows_are_flagged():
    df = make_rows(
        ("1", "TP444", "x", "Monthly PM", "MAINT", "WorkRequest", "10/30/2026 20:30"),
        ("1", "TP444", "x", "Monthly PM", "MAINT", "WorkRequest", "10/30/2026 20:30"),  # duplicate
        ("2", "TP448", "x", "Monthly PM", "MAINT", "WorkRequest", "10/30/2026 20:30"),  # unknown asset
        ("3", "DC221", "x", "Repair", "MAINT", "WorkRequest", "10/30/2026 20:30"),      # not a PM
        ("4", "DC221", "x", "Weekly PM", "MAINT", "WorkRequest", "not a date"),         # bad date
    )
    clean, issues = prepare(df, "active", ASSETS)
    assert len(clean) == 1
    assert len(issues) == 4
    assert "looks like 4400.8" in issues[1].message

def test_historical_must_be_finished():
    df = make_rows(("1", "TP444", "x", "Monthly PM", "MAINT", "Started", "10/30/2026 20:30"))
    clean, issues = prepare(df, "historical", ASSETS)
    assert clean.empty
    assert issues[0].level == "error"

def test_workdone_is_kept_with_warning():
    df = make_rows(("1", "TP444", "x", "Monthly PM", "MAINT", "WorkDone", "10/30/2026 20:30"))
    clean, issues = prepare(df, "active", ASSETS)
    assert len(clean) == 1
    assert issues[0].level == "warning"

def test_summary_counts_and_overall(tmp_path):
    hist = make_rows(
        ("1", "TP444", "x", "Monthly PM", "MAINT", "Finished", "10/05/2026 06:30"),
        ("2", "TP444", "x", "Weekly PM", "MAINT", "Finished", "10/12/2026 06:30"),
        ("3", "DC221", "x", "Monthly PM", "MAINT", "Finished", "10/20/2026 06:30"),
    )
    active = make_rows(("4", "DC221", "x", "Weekly PM", "MAINT", "WorkRequest", "10/27/2026 06:30"))
    conn = connect(tmp_path / "test.db")
    for source, df in (("historical", hist), ("active", active)):
        clean, issues = prepare(df, source, ASSETS)
        save_work_orders(conn, clean, source, "test", len(issues))
    
    table, overall = monthly_summary(conn, "2026-10")
    assert overall == pytest.approx(0.75)
    assert table.loc[("2200.1", "Scheduled"), "Total"] == 2
    assert table.loc[("2200.1", "Completed"), "Total"] == 1