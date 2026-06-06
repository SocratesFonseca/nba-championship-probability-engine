const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(
  /\/+$/,
  "",
);

async function request(path, errorMessage) {
  const response = await fetch(`${API_URL}${path}`);

  if (!response.ok) {
    throw new Error(errorMessage);
  }

  return response.json();
}

export async function getHealth() {
  return request("/health", "Backend health check failed");
}

export async function getDataStatus() {
  return request("/data/status", "Data status check failed");
}

export async function getModelStatus() {
  return request("/models/status", "Model status check failed");
}

export async function getLatestPredictions() {
  return request("/predictions/latest", "Latest predictions could not be loaded");
}

export async function getPredictions(season) {
  return request(
    `/predictions/${encodeURIComponent(season)}`,
    `Predictions for ${season} could not be loaded`,
  );
}
