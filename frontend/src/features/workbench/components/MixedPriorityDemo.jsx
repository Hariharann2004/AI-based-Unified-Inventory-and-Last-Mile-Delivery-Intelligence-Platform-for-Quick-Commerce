import { useState } from "react";
import { request } from "../api/client.js";
import { useTask } from "../hooks/useRemote.js";
import { ReplayEvents } from "./ReplayEvents.jsx";
import { SourcePicker } from "./SourcePicker.jsx";
import { PanelHeading } from "./WorkspacePrimitives.jsx";

export function MixedPriorityDemo({ imports, openCases }) {
  const [kind, setKind] = useState("inventory");
  const [importId, setImportId] = useState("");
  const [perPriority, setPerPriority] = useState("3");
  const [demonstration, setDemonstration] = useState(null);
  const task = useTask();
  const selected =
    imports.find((item) => item.kind === kind && item.import_id === importId) ||
    imports.find((item) => item.kind === kind);

  async function load() {
    const query = new URLSearchParams({
      kind,
      import_id: selected.import_id,
      per_priority: perPriority,
    });
    const result = await task.run(() => request(`/replay-demonstrations?${query}`));
    if (result) setDemonstration(result);
  }

  return (
    <section
      className="surface demonstration-panel"
      id="mixed-priority-demo"
      aria-labelledby="mixed-priority-title"
    >
      <PanelHeading
        icon="layers"
        eyebrow="02 / Deliberately selected cases"
        title="Mixed-priority demonstration"
        id="mixed-priority-title"
        description="See Critical, High and Normal assessments together without changing their predictions."
      />
      <p className="warning">
        Selected demonstration only — not a representative sample, chronological replay or accuracy
        evaluation. Uses genuine saved historical assessments without changing their predictions.
      </p>
      <fieldset className="replay-selection" disabled={task.busy}>
        <legend>Choose saved case sources</legend>
        <SourcePicker
          imports={imports}
          kind={kind}
          setKind={setKind}
          selected={selected}
          setSelected={setImportId}
        />
        <div className="toolbar">
          <label>
            Cases per priority
            <select value={perPriority} onChange={(event) => setPerPriority(event.target.value)}>
              {[1, 3, 5, 10].map((count) => (
                <option key={count} value={count}>
                  {count} per available priority
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={!selected || task.busy} onClick={load}>
            {task.busy ? "Loading saved cases…" : "Load mixed-priority demonstration"}
          </button>
        </div>
      </fieldset>
      <p className="muted">
        Selects up to the chosen number from each existing priority, spreading inventory cases
        across recorded dates where possible. Synthetic scenarios and replay copies are excluded.
        This does not process the whole dataset or execute any action. Source choices apply to the
        next load.
      </p>
      {task.error && (
        <p className="error" role="alert">
          {task.error}
        </p>
      )}
      {demonstration && (
        <>
          <p className="provenance">
            Loaded selection: {demonstration.kind} · {demonstration.source}
          </p>
          <p className="muted">
            Available genuine saved records:{" "}
            {Object.entries(demonstration.available_counts)
              .map(([priority, count]) => `${priority}: ${count}`)
              .join(" · ")}
            . These are saved assessment priorities; their original model identity and evidence are
            in each case.
          </p>
          {!!demonstration.missing_priorities.length && (
            <p className="warning">
              No eligible saved cases for: {demonstration.missing_priorities.join(", ")}. Process
              genuine source records in Operations to make more assessments available; missing
              priorities are not fabricated.
            </p>
          )}
          <ReplayEvents
            key={`${demonstration.kind}:${demonstration.import_id}:${demonstration.per_priority}`}
            events={demonstration.events}
            openCases={openCases}
            context="demonstration"
          />
        </>
      )}
    </section>
  );
}
