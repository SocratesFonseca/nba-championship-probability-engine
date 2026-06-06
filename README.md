# NBA Championship Probability Engine

A full-stack foundation for an NBA championship probability project.

## What It Does

This app has a FastAPI backend and a React frontend. It collects NBA team-season statistics, builds a validated training table, and evaluates a logistic regression championship baseline on unseen seasons.

## Tech Stack

- React and Vite
- FastAPI
- SQLAlchemy
- SQLite for local development
- PostgreSQL through `DATABASE_URL`
- Docker Compose

## Current Features

- Responsive dashboard with backend and dataset status
- FastAPI health and data status endpoints
- Cached and resumable NBA.com data collection through `nba_api`
- Validated team-season training CSV with a champion target
- Chronological logistic regression baseline with held-out evaluation
- Focused backend tests

## Dataset

The primary data workflow uses NBA.com statistics through the Python `nba_api` package. It collects regular-season team statistics and uses a separate playoff response to identify each season's champion.

Raw API responses and processed datasets are not committed to GitHub.

```bash
cd backend
python -m app.scripts.collect_nba_data
```

The default range is `1984-85` through `2010-11`. Seasons from `2011-12` onward are left available for future model evaluation. You can override the range with `--start-season` and `--end-season`.

The older Kaggle metadata command remains optional at `python scripts/ingest_kaggle_dataset.py`.

Train and evaluate the logistic regression baseline:

```bash
python -m app.scripts.train_baseline
```

The model trains through `2006-07`, validates on `2007-08` through `2010-11`, and uses `2011-12` onward as the final test period. Model artifacts are written to the ignored `backend/outputs` directory.

## Run It Locally

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Docker:

```bash
docker compose up --build
```

Run backend tests:

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Deployment Notes

Frontend: deploy the `frontend` folder to Vercel.

Backend: deploy the `backend` folder to Railway and use a Railway PostgreSQL database.

Environment variables:

- `DATABASE_URL` for PostgreSQL
- `FRONTEND_URL` for the deployed frontend URL
- `ENVIRONMENT=production` in production
- `NBA_DATA_DIR` if raw CSV files are not in `backend/data/raw`
- `NBA_API_RAW_DIR` to override the raw API cache directory
- `NBA_PROCESSED_DIR` to override the processed dataset directory

Do not put database credentials, Kaggle keys, or private values in frontend `VITE_` variables.

## Status

This is still a work in progress. The baseline is evaluated offline; predictions are not exposed through the API or dashboard.
