# NBA Championship Probability Engine

A full-stack foundation for an NBA championship probability project.

## What It Does

This app has a FastAPI backend and a React frontend. It validates downloaded Kaggle CSV files, stores import metadata in a database, and reports backend and dataset status to the dashboard. It does not include predictions yet.

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
- Configurable Kaggle CSV validation
- Dataset import metadata stored in SQLite or PostgreSQL
- Focused backend tests

## Dataset

This project is intended to use the Kaggle NBA/ABA/BAA stats dataset:

https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats

Raw CSV files are not committed to GitHub. Download the dataset yourself, put the CSV files in `backend/data/raw`, then import dataset metadata into the database.

```bash
cd backend
python scripts/ingest_kaggle_dataset.py
```

You can also set `NBA_DATA_DIR` if the CSV files are somewhere else.

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

Do not put database credentials, Kaggle keys, or private values in frontend `VITE_` variables.

## Status

This is still a work in progress. The current data import only stores dataset metadata, not full stats tables or predictions.
