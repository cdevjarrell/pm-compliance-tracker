from datetime import date

from pmtracker.rules import lookup_cell, parse_frequency, suggest_cell, week_number

def test_parse_frequency_known_values():
    assert parse_frequency("Weekly PM") == "Weekly"
    assert parse_frequency("Bi-Weekly PM") == "Bi-weekly"
    assert parse_frequency("6 Months PM") == "Semi-Annual"

def test_three_year_pm_counts_as_annual():
    assert parse_frequency("3 Years PM") == "Annual"

def test_parse_frequency_ignores_case_and_spaces():
    assert parse_frequency("  monthly   pm ") == "Monthly"

def test_parse_frequency_unknown_is_none():
    assert parse_frequency("Repair") is None
    assert parse_frequency(None) is None

def test_week_number_matches_plant_calendar():
    # Oct 4 to Oct 10, 2026 is Week 41 (Sunday to Saturday).
    assert week_number(date(2026, 10, 4)) == 41
    assert week_number(date(2026, 10, 10)) == 41
    assert week_number(date(2026, 10, 11)) == 42

def test_week_number_start_of_year():
    assert week_number(date(2026, 1, 1)) == 1 # Thursday
    assert week_number(date(2026, 1, 3)) == 1 # Saturday
    assert week_number(date(2026, 1, 4)) == 2 # Sunday starts week 2

def test_lookup_cell():
    asset_map = {"TP444": "4400.4", "SB441": "SBC"}
    assert lookup_cell("tp444", asset_map) == "4400.4"
    assert lookup_cell("XX999", asset_map) is None

def test_suggest_cell():
    assert suggest_cell("TP448") == "4400.8"
    assert suggest_cell("RB281E") == "2800.1"
    assert suggest_cell("SB441") == "SBC"
    assert suggest_cell("CRSBC") is None # Asset exists, but there are no digits to guess from; CRSBC is mapped in assets.csv