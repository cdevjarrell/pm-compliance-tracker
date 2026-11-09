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
```

Run tests with `pytest`.

## Data

The sample files in `data/sample/` are generated and contain no real plant data.
Real exports go in `data/real/`, which is excluded from Git.