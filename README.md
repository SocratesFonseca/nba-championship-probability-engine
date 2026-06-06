# NBA Championship Probability Engine

A React and FastAPI application that collects real NBA team-season data,
evaluates a logistic regression baseline, and serves historical championship
probabilities through an API and dashboard.

## Technology

- React and Vite
- FastAPI and SQLAlchemy
- scikit-learn
- `nba_api`
- SQLite locally and PostgreSQL through `DATABASE_URL`
- Docker Compose

## Model

The baseline uses regular-season statistics only. It trains on 1984-85 through
2006-07, validates on 2007-08 through 2010-11, and tests on 2011-12 through
2024-25.

Final test results:

- Log loss: 1.740
- Brier score: 0.767
- Top-1 champion accuracy: 50.0%
- Top-3 champion inclusion: 85.7%

These are historical holdout results, not future guarantees or betting advice.

## Run Locally

```powershell
docker compose up --build
```

Or run each service:

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Backend tests:

```powershell
cd backend
pip install -r requirements-dev.txt
pytest
```

## Deployment

Deploy `backend` to Railway and `frontend` to Vercel.

Railway variables:

- `DATABASE_URL`
- `FRONTEND_URL`
- `ENVIRONMENT=production`

Vercel variable:

- `VITE_API_URL`

The backend Docker image includes only the small model and prediction files
needed at runtime. Raw API responses, generated training datasets, databases,
credentials, and local environment files are not committed.

## Limitations

Predictions cover completed historical seasons through 2024-25. The model uses
a small regular-season feature set and does not account for injuries, roster
changes, transactions, or in-season context.
