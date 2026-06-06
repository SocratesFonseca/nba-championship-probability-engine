FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY runtime_artifacts ./runtime_artifacts

RUN mkdir -p data/raw data/processed outputs logs

ENV NBA_MODEL_OUTPUT_DIR=/app/runtime_artifacts
ENV NBA_PREDICTION_DATA_PATH=/app/runtime_artifacts/prediction_features.csv

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
