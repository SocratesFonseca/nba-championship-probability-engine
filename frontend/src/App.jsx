import { useEffect, useState } from "react";

import { getHealth } from "./api";
import "./styles.css";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");

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

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="intro">
        <p className="eyebrow">Project foundation</p>
        <h1>NBA Championship Probability Engine</h1>
        <p className="subtitle">
          Machine learning forecasts built from historical NBA data.
        </p>
      </section>

      <section className="status-panel" aria-label="Backend status">
        <span className="status-label">Backend Status:</span>
        <span className="status-value">{backendStatus}</span>
      </section>
    </main>
  );
}

export default App;
