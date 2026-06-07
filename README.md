# NBA Championship Probability Engine

This is a full-stack project that uses historical NBA data to estimate each
team's chance of winning the championship.

Live site: https://nba-championship-probability-engine.vercel.app

## Built With

- React and Vite
- FastAPI
- Python and scikit-learn
- `nba_api`
- PostgreSQL
- Docker

## How It Works

The project collects real NBA regular-season data and uses a logistic
regression model to rank teams for each season.

The model was trained on seasons from 1984-85 through 2006-07. Seasons from
2007-08 through 2010-11 were used for validation, and seasons from 2011-12
through 2024-25 were used for testing.

Test results:

- Log loss: 1.740
- Brier score: 0.767
- Top predicted team won 50% of the test seasons
- The real champion was in the top three 85.7% of the time

The predictions are based on historical data and are not guaranteed.

## Run With Docker

```powershell
docker compose up --build
```

The frontend will run at `http://localhost:5173` and the backend will run at
`http://localhost:8000`.

## Run Without Docker

Backend:

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Deployment Variables

Railway:

- `DATABASE_URL`
- `FRONTEND_URL`
- `ENVIRONMENT=production`

Vercel:

- `VITE_API_URL`

## Current Limitations

The app currently shows predictions for completed seasons through 2024-25.
The model does not include injuries, trades, roster changes, or other
in-season information.
