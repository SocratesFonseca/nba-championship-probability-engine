import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getDataStatus,
  getHealth,
  getLatestPredictions,
  getModelStatus,
  getPredictions,
} from "./api";
import "./styles.css";

const navigationItems = ["Overview", "Predictions", "Models", "Data", "Status"];
const predictionSeasons = Array.from(
  { length: 14 },
  (_, index) => `${2011 + index}-${String(12 + index).slice(-2)}`,
).reverse();

function getStatusTone(status) {
  const normalized = String(status).toLowerCase();

  if (
    normalized.includes("unavailable") ||
    normalized.includes("missing") ||
    normalized.includes("error")
  ) {
    return "danger";
  }

  if (
    normalized.includes("checking") ||
    normalized.includes("loading") ||
    normalized.includes("not collected")
  ) {
    return "pending";
  }

  if (
    normalized.includes("ready") ||
    normalized.includes("available") ||
    normalized.includes("ok")
  ) {
    return "success";
  }

  return "neutral";
}

function formatPercent(value, digits = 1) {
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

function formatMetric(value, type) {
  if (value === null || value === undefined) {
    return "Unavailable";
  }

  return type === "rate" ? formatPercent(value) : Number(value).toFixed(3);
}

function StatusPill({ label, tone = "neutral" }) {
  return <span className={`status-pill status-pill--${tone}`}>{label}</span>;
}

function DashboardCard({ id, title, eyebrow, children, action, className = "" }) {
  return (
    <section className={`dashboard-card ${className}`} id={id}>
      <div className="card-header">
        <div>
          {eyebrow ? <p className="card-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        {action ? <div className="card-action">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ title, description, action }) {
  return (
    <div className="empty-state">
      <div className="empty-state__surface" aria-hidden="true">
        <div className="empty-state__line empty-state__line--wide" />
        <div className="empty-state__line" />
        <div className="empty-state__line empty-state__line--short" />
      </div>
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
        {action ? <div className="empty-state__action">{action}</div> : null}
      </div>
    </div>
  );
}

function PredictionChart({ teams }) {
  const chartTeams = teams.slice(0, 8);
  const maximum = chartTeams[0]?.championship_probability || 1;

  return (
    <div className="probability-chart" aria-label="Top championship probabilities">
      {chartTeams.map((team) => (
        <div className="probability-row" key={team.team_id}>
          <span className="probability-team">{team.team_name}</span>
          <div className="probability-track">
            <span
              className="probability-bar"
              style={{
                width: `${(team.championship_probability / maximum) * 100}%`,
              }}
            />
          </div>
          <strong>{formatPercent(team.championship_probability, 2)}</strong>
        </div>
      ))}
    </div>
  );
}

function PredictionTable({ teams }) {
  return (
    <div className="table-scroll">
      <table className="prediction-table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Team</th>
            <th scope="col">Probability</th>
            <th scope="col">Result</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => (
            <tr key={team.team_id}>
              <td>{team.rank}</td>
              <td>{team.team_name}</td>
              <td>{formatPercent(team.championship_probability, 2)}</td>
              <td>
                {team.actual_champion ? (
                  <StatusPill label="Champion" tone="success" />
                ) : (
                  <span className="muted-cell">Not champion</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [dataStatus, setDataStatus] = useState(null);
  const [dataStatusLabel, setDataStatusLabel] = useState("Checking...");
  const [modelStatus, setModelStatus] = useState(null);
  const [modelStatusLabel, setModelStatusLabel] = useState("Checking...");
  const [prediction, setPrediction] = useState(null);
  const [selectedSeason, setSelectedSeason] = useState("latest");
  const [predictionLoading, setPredictionLoading] = useState(true);
  const [predictionError, setPredictionError] = useState("");

  const loadPrediction = useCallback(async (season) => {
    setPredictionLoading(true);
    setPredictionError("");

    try {
      const result =
        season === "latest"
          ? await getLatestPredictions()
          : await getPredictions(season);
      setPrediction(result);
    } catch (error) {
      setPrediction(null);
      setPredictionError(error.message);
    } finally {
      setPredictionLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    getHealth()
      .then((data) => {
        if (isMounted) {
          setBackendStatus(`${data.status} (${data.environment})`);
        }
      })
      .catch(() => {
        if (isMounted) {
          setBackendStatus("Unavailable");
        }
      });

    getDataStatus()
      .then((data) => {
        if (isMounted) {
          setDataStatus(data);
          setDataStatusLabel(
            data.training_dataset_available ? "Ready" : "Not collected",
          );
        }
      })
      .catch(() => {
        if (isMounted) {
          setDataStatusLabel("Unavailable");
        }
      });

    getModelStatus()
      .then((data) => {
        if (isMounted) {
          setModelStatus(data);
          setModelStatusLabel(data.available ? "Available" : "Unavailable");
        }
      })
      .catch(() => {
        if (isMounted) {
          setModelStatusLabel("Unavailable");
        }
      });

    loadPrediction("latest");

    return () => {
      isMounted = false;
    };
  }, [loadPrediction]);

  const handleSeasonChange = (event) => {
    const season = event.target.value;
    setSelectedSeason(season);
    loadPrediction(season);
  };

  const backendTone = useMemo(
    () => getStatusTone(backendStatus),
    [backendStatus],
  );
  const dataTone = useMemo(
    () => getStatusTone(dataStatusLabel),
    [dataStatusLabel],
  );
  const modelTone = useMemo(
    () => getStatusTone(modelStatusLabel),
    [modelStatusLabel],
  );
  const validationMetrics = modelStatus?.evaluation_metrics?.validation;
  const testMetrics = modelStatus?.evaluation_metrics?.test;

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand-mark">NBA</div>
        <nav className="nav-list">
          {navigationItems.map((item) => (
            <a
              className={
                item === "Overview" ? "nav-item nav-item--active" : "nav-item"
              }
              href={`#${item.toLowerCase()}`}
              key={item}
            >
              {item}
            </a>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="top-header">
          <div>
            <p className="eyebrow">Analytics dashboard</p>
            <h1>NBA Championship Probability Engine</h1>
            <p className="subtitle">
              Machine learning forecasts built from historical NBA data.
            </p>
          </div>
          <div className="health-card" aria-label="Backend status">
            <span className="health-label">Backend</span>
            <StatusPill label={backendStatus} tone={backendTone} />
          </div>
        </header>

        <main className="dashboard-grid">
          <DashboardCard id="overview" title="Overview" eyebrow="Project state">
            <div className="overview-layout">
              <div>
                <p className="body-copy">
                  Historical team seasons are scored by a logistic regression
                  baseline trained only on regular-season statistics.
                </p>
                <div className="overview-actions">
                  <StatusPill
                    label={`Model ${modelStatusLabel.toLowerCase()}`}
                    tone={modelTone}
                  />
                  <StatusPill
                    label={`Data ${dataStatusLabel.toLowerCase()}`}
                    tone={dataTone}
                  />
                  <StatusPill
                    label="Historical predictions"
                    tone="success"
                  />
                </div>
              </div>
              <div className="readiness-list" aria-label="Readiness summary">
                <div>
                  <span>Latest season</span>
                  <strong>{prediction?.season || "Loading"}</strong>
                </div>
                <div>
                  <span>Training cutoff</span>
                  <strong>{modelStatus?.training_cutoff || "Loading"}</strong>
                </div>
                <div>
                  <span>Model version</span>
                  <strong>{modelStatus?.model_version || "Loading"}</strong>
                </div>
              </div>
            </div>
          </DashboardCard>

          <DashboardCard
            id="predictions"
            title="Prediction Workspace"
            eyebrow="Historical output"
            className="prediction-card"
            action={
              <label className="season-control">
                <span>Season</span>
                <select
                  aria-label="Prediction season"
                  value={selectedSeason}
                  onChange={handleSeasonChange}
                >
                  <option value="latest">Latest available</option>
                  {predictionSeasons.map((season) => (
                    <option value={season} key={season}>
                      {season}
                    </option>
                  ))}
                </select>
              </label>
            }
          >
            {predictionLoading ? (
              <div className="loading-state" role="status">
                Loading real model predictions...
              </div>
            ) : predictionError ? (
              <EmptyState
                title="Prediction data could not be loaded"
                description={predictionError}
                action={
                  <button
                    className="button"
                    type="button"
                    onClick={() => loadPrediction(selectedSeason)}
                  >
                    Retry
                  </button>
                }
              />
            ) : prediction?.teams?.length ? (
              <div className="prediction-content">
                <div className="prediction-summary">
                  <div>
                    <p className="prediction-season">{prediction.season}</p>
                    <p>{prediction.data_type}</p>
                  </div>
                  <StatusPill
                    label={`${prediction.teams.length} teams`}
                    tone="neutral"
                  />
                </div>
                <PredictionChart teams={prediction.teams} />
                <PredictionTable teams={prediction.teams} />
              </div>
            ) : (
              <EmptyState
                title="No prediction data available"
                description="The API returned no team predictions for this season."
              />
            )}
          </DashboardCard>

          <DashboardCard id="models" title="Model Status" eyebrow="Evaluation">
            <div className="status-list">
              <div className="status-row">
                <div>
                  <h3>{modelStatus?.model_type || "Baseline model"}</h3>
                  <p>
                    {modelStatus?.available
                      ? `${modelStatus.model_version}, trained through ${modelStatus.training_cutoff}.`
                      : modelStatus?.message || "Model status is unavailable."}
                  </p>
                </div>
                <StatusPill label={modelStatusLabel} tone={modelTone} />
              </div>
              <div className="metric-grid">
                <div>
                  <span>Validation log loss</span>
                  <strong>{formatMetric(validationMetrics?.log_loss)}</strong>
                </div>
                <div>
                  <span>Test log loss</span>
                  <strong>{formatMetric(testMetrics?.log_loss)}</strong>
                </div>
                <div>
                  <span>Test top-1 accuracy</span>
                  <strong>
                    {formatMetric(
                      testMetrics?.top_1_champion_accuracy,
                      "rate",
                    )}
                  </strong>
                </div>
                <div>
                  <span>Test top-3 inclusion</span>
                  <strong>
                    {formatMetric(
                      testMetrics?.top_3_champion_inclusion_rate,
                      "rate",
                    )}
                  </strong>
                </div>
              </div>
            </div>
          </DashboardCard>

          <DashboardCard id="data" title="Data Pipeline Status" eyebrow="Data readiness">
            <div className="pipeline-list">
              <div className="pipeline-item">
                <div>
                  <h3>NBA API collection</h3>
                  <p>
                    {dataStatus?.season_range
                      ? `${dataStatus.season_range.start} through ${dataStatus.season_range.end}.`
                      : dataStatus?.messages?.[0] || "Checking collected data."}
                  </p>
                </div>
                <StatusPill
                  label={dataStatusLabel}
                  tone={dataTone}
                />
              </div>
              <div className="pipeline-item">
                <div>
                  <h3>Validated team seasons</h3>
                  <p>
                    {dataStatus?.row_count
                      ? `${dataStatus.row_count} rows reported by the data pipeline.`
                      : "Prediction-ready rows are loaded separately at runtime."}
                  </p>
                </div>
                <StatusPill
                  label={prediction ? "Available" : "Checking"}
                  tone={prediction ? "success" : "pending"}
                />
              </div>
              <div className="pipeline-item">
                <div>
                  <h3>Prediction service</h3>
                  <p>
                    Uses the saved feature allowlist and normalizes every
                    season to a total probability of 100%.
                  </p>
                </div>
                <StatusPill label={modelStatusLabel} tone={modelTone} />
              </div>
            </div>
          </DashboardCard>

          <DashboardCard id="status" title="Runtime Status" eyebrow="Verification">
            <div className="status-list">
              <div className="status-row">
                <div>
                  <h3>Prediction type</h3>
                  <p>{prediction?.data_type || "Waiting for prediction data."}</p>
                </div>
                <StatusPill
                  label={prediction ? "Loaded" : "Waiting"}
                  tone={prediction ? "success" : "pending"}
                />
              </div>
              <div className="status-row">
                <div>
                  <h3>Generated</h3>
                  <p>
                    {modelStatus?.generated_at
                      ? new Date(modelStatus.generated_at).toLocaleString()
                      : "Waiting for model metadata."}
                  </p>
                </div>
              </div>
            </div>
          </DashboardCard>
        </main>
      </div>
    </div>
  );
}

export default App;
