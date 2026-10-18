# Sciencia AI Review Intelligence Sandbox

A small, self-contained review-ingestion and analysis application used for the Cyber Security Internship project.

## What the system does

The application simulates a lightweight internal data workflow:

1. A user selects an App and triggers an ingestion run.
2. The backend loads review records from a mock external provider (`data/provider_reviews.json`).
3. Reviews are normalized and stored in SQLite.
4. Users can search stored reviews, inspect ingestion runs, export data, and view a simple sentiment summary.

The sandbox is intentionally small so that the architecture, data flow, and security posture can be understood end to end.

## Components

- Flask web application
- SQLite database
- Mock external review provider
- Local application logs
- Simple HTML interface
- CSV/database export endpoints

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app/app.py
```

Then open: `http://127.0.0.1:5000`

The database is created automatically at `data/reviews.db`.

## Internship scope

This repository is a **local security sandbox**. It should be reviewed and tested only on your own local copy.

Please read `SECURITY_SCOPE.md` before beginning any active security testing.

For the first module, focus on understanding the architecture, assets, data flow, access points, trust boundaries, and areas that may deserve deeper security review. Do not begin active exploitation or scanning until specifically instructed.
