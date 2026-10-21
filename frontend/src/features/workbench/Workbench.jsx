import { useCallback, useState } from "react";
import { useRemote } from "./hooks/useRemote.js";
import { WorkbenchIcon } from "./components/WorkbenchIcon.jsx";
import { CasesPage } from "./pages/CasesPage.jsx";
import { EvaluationPage } from "./pages/EvaluationPage.jsx";
import { OperationsPage } from "./pages/OperationsPage.jsx";
import { ReplayPage } from "./pages/ReplayPage.jsx";
import "./workbench.css";
import "./workspace-layouts.css";

const NAVIGATION = [
  { id: "operations", label: "Operations", detail: "Import & analyze" },
  { id: "cases", label: "Cases & actions", detail: "Evidence & decisions" },
  { id: "replay", label: "Replay & scenarios", detail: "Explore & demonstrate" },
  { id: "evaluation", label: "Model evaluation", detail: "Measure & compare" },
];

export function Workbench() {
  const [page, setPage] = useState("operations");
  const [version, setVersion] = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [evaluationMode, setEvaluationMode] = useState("operational");
  const refresh = useCallback(() => setVersion((value) => value + 1), []);
  const remote = useRemote("/imports", version);
  const imports = remote.data || [];
  const currentSection = NAVIGATION.find((item) => item.id === page);
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
            <WorkbenchIcon name="brand" />
          </span>
          <div>
            <strong>Unified Intelligence</strong>
            <small>Operations workbench</small>
          </div>
        </div>
        <p className="nav-heading">WORKSPACE</p>
        <nav aria-label="Workbench navigation">
          {NAVIGATION.map(({ id, label, detail }, index) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              aria-current={page === id ? "page" : undefined}
              aria-label={label}
              onClick={() => {
                if (id === "evaluation") setEvaluationMode("operational");
                setPage(id);
              }}
            >
              <span className="nav-icon" aria-hidden="true">
                <WorkbenchIcon name={id} />
              </span>
              <span className="nav-copy">
                {label}
                <small aria-hidden="true">{detail}</small>
              </span>
              <span className="nav-index" aria-hidden="true">
                0{index + 1}
              </span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="sidebar-environment">
            <WorkbenchIcon name="shield" />
            Local research environment
          </div>
          <p>Dataset-backed · assigned warehouse only</p>
          <small>Actions remain internal drafts.</small>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <div className="header-breadcrumb" role="group" aria-label="Current section">
            <span>Workspace</span>
            <WorkbenchIcon name="chevron" />
            <strong>{currentSection.label}</strong>
          </div>
          <div className="header-context">
            <span className="header-source">
              <WorkbenchIcon name="database" />
              Historical data
            </span>
            <span className="header-tag">LightGBM only</span>
          </div>
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
          <WorkbenchIcon name="shield" />
          <span>
            Decision support, not autonomous execution. Historical data and synthetic scenarios are
            labelled explicitly.
          </span>
        </footer>
      </div>
    </div>
  );
}
