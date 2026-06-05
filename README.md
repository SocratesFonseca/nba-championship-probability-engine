# NBA Championship Probability Engine

## Overview

NBA Championship Probability Engine is a foundation for predicting NBA championship probabilities from historical NBA data. This initial version focuses on project structure, configuration, deployment readiness, and a small health-check interface.

Machine learning models, NBA data ingestion, prediction outputs, and analytics dashboards are intentionally not included yet.

## Architecture

The repository is split into two deployable services:

- `backend`: FastAPI application with environment-driven settings, SQLAlchemy database setup, logging, CORS, and a health endpoint.
- `frontend`: React and Vite application with a minimal dark interface that checks backend availability.

Local development can use SQLite automatically when no `DATABASE_URL` is provided. Production is designed for PostgreSQL.

## Tech Stack

- Frontend: React, Vite, JavaScript, Recharts
- Backend: Python 3.11, FastAPI, SQLAlchemy
- Database: SQLite for local development, PostgreSQL for production
- Deployment: Vercel for frontend, Render Web Service and Render PostgreSQL for backend and database

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

If `DATABASE_URL` is unset, the backend uses:

```text
sqlite:///nba_local.db
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Docker Setup

```bash
docker compose up --build
```

This starts:

- PostgreSQL at `localhost:5432`
- FastAPI backend at `localhost:8000`
- Vite frontend at `localhost:5173`

The Docker setup uses service-level environment variables and does not require local environment files.

## Vercel Deployment

Deploy the `frontend` directory as a Vercel project.

Set the following environment variable in Vercel:

```text
VITE_API_URL=<render-backend-url>
```

Build settings:

- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

## Render Deployment

Create a Render PostgreSQL database first, then create a Render Web Service for the `backend` directory.

Set the following backend environment variables in Render:

```text
DATABASE_URL=<render-postgresql-internal-url>
FRONTEND_URL=<vercel-frontend-url>
ENVIRONMENT=production
```

Use the Dockerfile in `backend` for deployment.

## Roadmap

1. NBA Stats API integration
2. Historical playoff and regular season data collection
3. Data caching
4. Feature engineering
5. Logistic Regression baseline
6. Random Forest model
7. XGBoost model
8. Model evaluation
9. Feature importance analysis
10. Championship probability dashboard
11. Historical season comparisons
