import { useEffect, useMemo, useState } from "react";

import { getDataStatus, getHealth } from "./api";
import "./styles.css";

const navigationItems = ["Overview", "Predictions", "Models", "Data", "Roadmap"];

const fallbackPipelineItems = [
  {
    label: "Historical data ingestion",
    status: "Checking",
    detail: "Waiting for backend data status.",
  },
  {
    label: "Feature engineering",
    status: "Not started",
    detail: "Create training-ready team, season, and playoff features.",
  },
  {
    label: "Model training",
    status: "Not started",
    detail: "Train and evaluate the first championship probability model.",
  },
];

const roadmapItems = [
  "Build data ingestion workflow",
  "Add model training pipeline",
  "Store prediction outputs",
  "Connect dashboard visualizations to real data",
];

function getStatusTone(status) {
  const normalized = status.toLowerCase();

  if (normalized.includes("unavailable") || normalized.includes("missing")) {
    return "danger";
  }

  if (normalized.includes("checking") || normalized.includes("planned") || normalized.includes("waiting") || normalized.includes("not imported")) {
    return "pending";
  }

  if (normalized.includes("ready") || normalized.includes("imported") || normalized.includes("ok")) {
    return "success";
  }

  return "neutral";
}

function getPipelineItems(dataStatus) {
  if (!dataStatus) {
    return fallbackPipelineItems;
  }

  const ingestionStatus = dataStatus.database_has_import_metadata
    ? "Imported"
    : dataStatus.files_valid
      ? "Ready to import"
      : "Not imported";

  const ingestionDetail = dataStatus.messages?.[0] || "Download the Kaggle CSV files and run the backend ingestion command.";

  return [
    {
      label: "Kaggle dataset files",
      status: dataStatus.files_valid ? "Ready" : dataStatus.data_dir_exists ? "Missing files" : "Directory missing",
      detail: `${dataStatus.present_files?.length || 0} of ${dataStatus.expected_files?.length || 0} expected files found.`,
    },
    {
      label: "Dataset metadata import",
      status: ingestionStatus,
      detail: dataStatus.last_imported_at ? `Last imported ${new Date(dataStatus.last_imported_at).toLocaleString()}.` : ingestionDetail,
    },
    {
      label: "Model training",
      status: "Not started",
      detail: "Training will begin after raw stats tables and feature engineering are implemented.",
    },
  ];
}

function StatusPill({ label, tone = "neutral" }) {
  return <span className={`status-pill status-pill--${tone}`}>{label}</span>;
}

function DashboardCard({ title, eyebrow, children, action }) {
  return (
    <section className="dashboard-card">
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

function EmptyState({ title, description }) {
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
      </div>
    </div>
  );
}

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");
  const [dataStatus, setDataStatus] = useState(null);
  const [dataStatusLabel, setDataStatusLabel] = useState("Checking...");

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
          setDataStatusLabel(data.database_has_import_metadata ? "Imported" : "Not imported yet");
        }
      })
      .catch(() => {
        if (isMounted) {
          setDataStatusLabel("Unavailable");
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const backendTone = useMemo(() => getStatusTone(backendStatus), [backendStatus]);
  const dataTone = useMemo(() => getStatusTone(dataStatusLabel), [dataStatusLabel]);
  const pipelineItems = useMemo(() => getPipelineItems(dataStatus), [dataStatus]);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand-mark">NBA</div>
        <nav className="nav-list">
          {navigationItems.map((item) => (
            <a className={item === "Overview" ? "nav-item nav-item--active" : "nav-item"} href={`#${item.toLowerCase()}`} key={item}>
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
            <p className="subtitle">Machine learning forecasts built from historical NBA data.</p>
          </div>
          <div className="health-card" aria-label="Backend status">
            <span className="health-label">Backend</span>
            <StatusPill label={backendStatus} tone={backendTone} />
          </div>
        </header>

        <main className="dashboard-grid">
          <DashboardCard title="Overview" eyebrow="Project state">
            <div className="overview-layout">
              <div>
                <p className="body-copy">
                  The dashboard shell is ready for real NBA data, model outputs, and prediction history once ingestion and training are implemented.
                </p>
                <div className="overview-actions">
                  <StatusPill label="Prediction data pending" tone="pending" />
                  <StatusPill label={`Data ${dataStatusLabel.toLowerCase()}`} tone={dataTone} />
                  <StatusPill label="Backend health enabled" tone={backendTone} />
                </div>
              </div>
              <div className="readiness-list" aria-label="Readiness summary">
                <div>
                  <span>Interface</span>
                  <strong>Ready</strong>
                </div>
                <div>
                  <span>Data ingestion</span>
                  <strong>{dataStatusLabel}</strong>
                </div>
                <div>
                  <span>Model outputs</span>
                  <strong>Pending</strong>
                </div>
              </div>
            </div>
          </DashboardCard>

          <DashboardCard title="Prediction Workspace" eyebrow="Future outputs">
            <EmptyState
              title="No prediction data available yet"
              description="Championship probabilities will appear here after historical data ingestion, model training, and output storage are added."
            />
          </DashboardCard>

          <DashboardCard title="Model Status" eyebrow="Training">
            <div className="status-list">
              <div className="status-row">
                <div>
                  <h3>Baseline model</h3>
                  <p>No model has been trained yet.</p>
                </div>
                <StatusPill label="Not started" tone="neutral" />
              </div>
              <div className="status-row">
                <div>
                  <h3>Evaluation metrics</h3>
                  <p>Metrics will be shown after the first training run.</p>
                </div>
                <StatusPill label="Waiting" tone="pending" />
              </div>
            </div>
          </DashboardCard>

          <DashboardCard title="Data Pipeline Status" eyebrow="Data readiness">
            <div className="pipeline-list">
              {pipelineItems.map((item) => (
                <div className="pipeline-item" key={item.label}>
                  <div>
                    <h3>{item.label}</h3>
                    <p>{item.detail}</p>
                  </div>
                  <StatusPill label={item.status} tone={getStatusTone(item.status)} />
                </div>
              ))}
            </div>
          </DashboardCard>

          <DashboardCard title="Roadmap Progress" eyebrow="Next milestones">
            <ol className="roadmap-list">
              {roadmapItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
          </DashboardCard>
        </main>
      </div>
    </div>
  );
}

export default App;