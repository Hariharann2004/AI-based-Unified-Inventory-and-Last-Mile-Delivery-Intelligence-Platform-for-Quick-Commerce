import { useCallback, useState } from "react";
import { useRemote } from "./hooks/useRemote.js";
import { CasesPage } from "./pages/CasesPage.jsx";
import { EvaluationPage } from "./pages/EvaluationPage.jsx";
import { OperationsPage } from "./pages/OperationsPage.jsx";
import { ReplayPage } from "./pages/ReplayPage.jsx";
import "./workbench.css";

export function Workbench() {
  const [page, setPage] = useState("operations");
  const [version, setVersion] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [evaluationMode, setEvaluationMode] = useState("operational");
  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  const remote = useRemote("/imports", version);
  const imports = remote.data || [];
  function openCases(id) {
    setSelectedId(id);
    setPage("cases");
  }
  function openResearch() {
    setEvaluationMode("research");
    setPage("evaluation");
  }
  const shared = { imports, version, refresh, openCases, openResearch };
  return (
    <div className="workbench">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="app-sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            U
          </span>
          <div>
            <strong>Unified Intelligence</strong>
            <small>Quick-commerce operations</small>
          </div>
        </div>
        <p className="nav-heading">WORKSPACE</p>
        <nav aria-label="Workbench navigation">
          {[
            ["operations", "Operations"],
            ["cases", "Cases & actions"],
            ["replay", "Replay & scenarios"],
            ["evaluation", "Model evaluation"],
          ].map(([id, label], index) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              aria-current={page === id ? "page" : undefined}
              onClick={() => {
                if (id === "evaluation") setEvaluationMode("operational");
                setPage(id);
              }}
            >
              <span aria-hidden="true">0{index + 1}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" aria-hidden="true" /> Local research environment
          <p>Dataset-backed · assigned warehouse only</p>
          <small>Actions remain internal drafts.</small>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <span>Inventory + last-mile delivery</span>
          <span className="header-tag">LightGBM / research workbench</span>
        </header>
        <main id="workspace" className="workspace">
          {remote.error && (
            <p className="error" role="alert">
              {remote.error} Start the Flask API using the README instructions.
            </p>
          )}
          {page === "operations" && <OperationsPage {...shared} />}
          {page === "cases" && (
            <CasesPage
              version={version}
              refresh={refresh}
              selectedId={selectedId}
              setSelectedId={setSelectedId}
            />
          )}
          {page === "replay" && <ReplayPage {...shared} />}
          {page === "evaluation" && <EvaluationPage {...shared} initialMode={evaluationMode} />}
        </main>
        <footer>
          Decision support, not autonomous execution. Historical data and synthetic scenarios are
          labelled explicitly.
        </footer>
      </div>
    </div>
  );
}
