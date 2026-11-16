from datetime import date

import pandas as pd
import pytest

from pmtracker.database import COLUMNS, connect, save_work_orders
from pmtracker.report import (
    finished_months,
    monthly_summary,
    quarter_of,
    quarter_to_date,
    weekly_summary,
    year_to_date,
)

NOV_15 = date(2026, 11, 15)

def add_pms(conn, month, cell, scheduled, completed, week=1):
    """Save 'scheduled' PMs for one cell and month, the first 'completed' of them Finished."""
    rows = []
    for i in range(scheduled):
        rows.append({
            "wo_no": f"{month}-{cell}-{week}-{i}",
            "object_id":"X1",
            "object_description": "",
            "directive": "Monthly PM",
            "status": "Finished" if i < completed else "WorkRequest",
            "planned_start": f"{month}-01 06:30",
            "cell": cell,
            "frequency": "Monthly",
            "month": month,
            "week": week,
            "completed": 1 if i < completed else 0,
        })
    save_work_orders(conn, pd.DataFrame(rows, columns=COLUMNS), "test", "test", 0)

@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test.db")
    yield c
    c.close()

def test_quarter_of():
    assert [quarter_of(m) for m in (1, 3, 4, 9, 10, 12)] == [1, 1, 2, 3, 4, 4]

def test_finished_months_leaves_out_current_and_future():
    months = ["2026-09", "2026-10", "2026-11", "2026-12"]
    assert finished_months(months, NOV_15) == ["2026-09", "2026-10"]

def test_year_to_date_average_vs_pooled(conn):
    add_pms(conn, "2026-01", "4400.4", 100, 100) # 100%
    add_pms(conn, "2026-02", "4400.4", 10, 5) # 50%
    result = year_to_date(conn, 2026, today=NOV_15)
    assert result["average"] == pytest.approx(0.75) # (100% + 50%) / 2
    assert result["pooled"] == pytest.approx(105 / 110) # every PM counted once
    assert result["months"] == ["2026-01", "2026-02"]

def test_current_month_is_not_in_year_to_date(conn):
    add_pms(conn, "2026-10", "4400.4", 10, 10)
    add_pms(conn, "2026-11", "4400.4", 10, 3) # in progress
    result = year_to_date(conn, 2026, today=NOV_15)
    assert result ["months"] == ["2026-10"]
    assert result ["average"] == pytest.approx(1.0)

def test_quarter_to_date_only_uses_its_quarter(conn):
    add_pms(conn, "2026-09", "4400.4", 10, 0) # Q3, should be ignored
    add_pms(conn, "2026-10", "4400.4", 10, 9)
    result = quarter_to_date(conn, 2026, 4, today=NOV_15)
    assert result["months"] == ["2026-10"]
    assert result["average"] == pytest.approx(0.9)

def test_quarter_with_no_finished_months_is_none(conn):
    add_pms(conn, "2026-11", "4400.4", 10, 5)
    assert quarter_to_date(conn, 2026, 4, today=date(2026, 10, 5)) is None

def test_untracked_cell_is_left_out(conn):
    add_pms(conn, "2026-10", "4400.4", 10, 10)
    add_pms(conn, "2026-10", "2200.1", 10, 0)
    scope = {("2026-10", "2200.1"): False}
    table, overall = monthly_summary(conn, "2026-10", scope)
    assert overall == pytest.approx(1.0)
    assert "2200.1" not in table.index.get_level_values(0)
    assert year_to_date(conn, 2026, today=NOV_15, scope=scope)["average"] == pytest.approx(1.0)

def test_weekly_summary_splits_by_week(conn):
    add_pms(conn, "2026-10", "4400.4", 4, 4, week=40)
    add_pms(conn, "2026-10", "4400.4", 4, 2, week=41)
    weeks  = weekly_summary(conn, "2026-10")
    assert list(weeks["week"]) == [40, 41]
    assert list(weeks["percent"]) == [1.0, 0.5]
    assert weeks["scheduled"].sum() == 8 # weekly totals add up to the month, like the Check column