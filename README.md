# NBA Championship Probability Engine

A simple project for estimating NBA championship probabilities.

## What It Does

This app has a FastAPI backend and a React frontend. It is set up for future NBA data ingestion and model training, but it does not include predictions yet.

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