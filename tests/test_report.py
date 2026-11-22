from datetime import date

import pandas as pd
import pytest

from pmtracker.database import COLUMNS, connect, save_work_orders
from pmtracker.report import (
    finished_months,
    format_percent,
    monthly_detail,
    monthly_summary,
    quarter_of,
    quarter_to_date,
    round_percent,
    status_for,
    weekly_summary,
    year_to_date,
    ytd_by_cell,
)

NOV_15 = date(2026, 11, 15)


def add_pms(conn, month, cell, scheduled, completed, week=1):
    """Save 'scheduled' PMs for one cell and month, the first 'completed' of them Finished."""
    rows = []
    for i in range(scheduled):
        rows.append({
            "wo_no": f"{month}-{cell}-{week}-{i}",
            "object_id": "X1",
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


# ---------- Quarters and year to date ----------

def test_quarter_of():
    assert [quarter_of(m) for m in (1, 3, 4, 9, 10, 12)] == [1, 1, 2, 3, 4, 4]


def test_finished_months_leaves_out_current_and_future():
    months = ["2026-09", "2026-10", "2026-11", "2026-12"]
    assert finished_months(months, NOV_15) == ["2026-09", "2026-10"]


def test_year_to_date_average_vs_pooled(conn):
    add_pms(conn, "2026-01", "4400.4", 100, 100)  # 100%
    add_pms(conn, "2026-02", "4400.4", 10, 5)  # 50%
    result = year_to_date(conn, 2026, today=NOV_15)
    assert result["average"] == pytest.approx(0.75)  # (100% + 50%) / 2
    assert result["pooled"] == pytest.approx(105 / 110)  # every PM counted once
    assert result["months"] == ["2026-01", "2026-02"]


def test_current_month_is_not_in_year_to_date(conn):
    add_pms(conn, "2026-10", "4400.4", 10, 10)
    add_pms(conn, "2026-11", "4400.4", 10, 3)  # in progress
    result = year_to_date(conn, 2026, today=NOV_15)
    assert result["months"] == ["2026-10"]
    assert result["average"] == pytest.approx(1.0)


def test_quarter_to_date_only_uses_its_quarter(conn):
    add_pms(conn, "2026-09", "4400.4", 10, 0)  # Q3, should be ignored
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
    weeks = weekly_summary(conn, "2026-10")
    assert list(weeks["week"]) == [40, 41]
    assert list(weeks["percent"]) == [1.0, 0.5]
    assert weeks["scheduled"].sum() == 8  # weekly totals add up to the month, like the Check column


# ---------- Whole-percent rounding ----------

def test_round_percent_halves_up_like_excel():
    assert round_percent(0.9499) == 0.95
    assert round_percent(189 / 200) == 0.95  # 94.5% rounds up
    assert round_percent(0.9449) == 0.94
    assert round_percent(None) is None


def test_format_percent_is_whole_numbers():
    assert format_percent(0.958) == "96%"
    assert format_percent(0.012, signed=True) == "+1%"
    assert format_percent(-0.026, signed=True) == "-3%"
    assert format_percent(None) == ""


def test_status_uses_rounded_percent():
    assert status_for(0.9499) == "On target"  # shows as 95%
    assert status_for(0.945) == "On target"
    assert status_for(0.9449) == "Watch"  # shows as 94%
    assert status_for(0.845) == "Watch"  # shows as 85%
    assert status_for(0.8449) == "Below target"


# ---------- Dashboard ----------

def test_monthly_detail_statuses(conn):
    add_pms(conn, "2026-01", "4400.4", 100, 96)  # 96%
    add_pms(conn, "2026-02", "4400.4", 100, 90)  # 90%
    add_pms(conn, "2026-03", "4400.4", 100, 50)  # 50%
    add_pms(conn, "2026-04", "4400.4", 200, 189)  # 94.5% shows as 95%
    add_pms(conn, "2026-11", "4400.4", 10, 3)  # current month
    detail = monthly_detail(conn, 2026, today=NOV_15).set_index("month")
    assert len(detail) == 12
    assert detail.loc["2026-01", "status"] == "On target"
    assert detail.loc["2026-02", "status"] == "Watch"
    assert detail.loc["2026-03", "status"] == "Below target"
    assert detail.loc["2026-04", "percent"] == 0.95
    assert detail.loc["2026-04", "status"] == "On target"
    assert detail.loc["2026-05", "status"] == "No data"
    assert detail.loc["2026-11", "status"] == "In progress"
    assert pd.isna(detail.loc["2026-11", "percent"])
    assert detail.loc["2026-02", "vs_goal"] == pytest.approx(-0.05)


def test_ytd_by_cell_is_pooled_and_skips_current_month(conn):
    add_pms(conn, "2026-01", "4400.4", 10, 10)
    add_pms(conn, "2026-02", "4400.4", 30, 15)
    add_pms(conn, "2026-01", "2200.1", 10, 9)
    add_pms(conn, "2026-11", "2200.1", 50, 0)  # in progress, left out
    table = ytd_by_cell(conn, 2026, today=NOV_15).set_index("cell")
    assert table.loc["4400.4", "scheduled"] == 40
    assert table.loc["4400.4", "percent"] == pytest.approx(25 / 40)
    assert table.loc["2200.1", "scheduled"] == 10
    # months_tracked counts reported months the cell is on, even with no PMs (like the workbook)
    assert table.loc["2200.1", "months_tracked"] == 2


def test_ytd_by_cell_respects_scope(conn):
    add_pms(conn, "2026-01", "4400.4", 10, 10)
    add_pms(conn, "2026-02", "4400.4", 10, 0)
    scope = {("2026-02", "4400.4"): False}
    table = ytd_by_cell(conn, 2026, today=NOV_15, scope=scope).set_index("cell")
    assert table.loc["4400.4", "months_tracked"] == 1
    assert table.loc["4400.4", "percent"] == pytest.approx(1.0)


def test_ytd_by_cell_lists_unused_cells(conn):
    add_pms(conn, "2026-01", "4400.4", 10, 10)
    scope = {("2026-01", "4400.1"): False}
    table = ytd_by_cell(conn, 2026, today=NOV_15, scope=scope, cells=["4400.1", "4400.4"]).set_index("cell")
    assert table.loc["4400.1", "scheduled"] == 0
    assert table.loc["4400.1", "months_tracked"] == 0
    assert pd.isna(table.loc["4400.1", "percent"])


def test_ytd_by_cell_totals_match_pooled_ytd(conn):
    add_pms(conn, "2026-01", "4400.4", 20, 19)
    add_pms(conn, "2026-02", "2200.1", 10, 7)
    add_pms(conn, "2026-02", "Waste Water", 5, 5)
    table = ytd_by_cell(conn, 2026, today=NOV_15)
    ytd = year_to_date(conn, 2026, today=NOV_15)
    assert table["completed"].sum() / table["scheduled"].sum() == pytest.approx(ytd["pooled"])