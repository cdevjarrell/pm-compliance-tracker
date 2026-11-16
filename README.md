# PM Compliance Tracker

Automates preventive maintenance (PM) compliance reporting from IFS CMMS exports.
Reads active and historical work order exports, assigns each PM to a production cell,
frequency, and Sunday-to-Saturday week, and reports completion against a 95% goal.

CS 4960 Senior Project, Indiana Institute of Technology.

## Setup

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```
python -m pmtracker.generate_sample
python -m pmtracker.cli import --active data/sample/ActiveWorkOrders_sample.xlsx --historical data/sample/HistoricalWorkOrders_sample.xlsx
python -m pmtracker.cli summary --month 10/2026
streamlit run Home.py
```

The Settings page in the browser app edits `config/assets.csv` (which cell each ObjectID belongs to)
and `config/scope.csv` (which cells count toward totals each month).

Run tests with `pytest`.

## How compliance is calculated

- Each PM counts in the month and week of its Planned Start. Weeks run Sunday to Saturday,
  and a week that crosses two months is split between them.
- Cells turned off for a month on the Settings page are left out of every total.
- Quarter-to-date and year-to-date use finished months only. The official number is the
  average of the monthly percentages; the pooled number (total completed / total scheduled)
  is shown next to it for comparison.

## Data

The sample files in `data/sample/` are generated and contain no real plant data.
Real exports go in `data/real/`, which is excluded from Git.