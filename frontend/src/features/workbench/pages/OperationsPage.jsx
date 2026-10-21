import { useState } from "react";
import { request } from "../api/client.js";
import { DatasetLibrary } from "../components/DatasetLibrary.jsx";
import { ProcessingJobs } from "../components/ProcessingJobs.jsx";
import { SourcePicker } from "../components/SourcePicker.jsx";
import { PageIntro, PanelHeading, WorkflowGuide } from "../components/WorkspacePrimitives.jsx";
import { WorkbenchIcon } from "../components/WorkbenchIcon.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";

export function OperationsPage({ imports, version, refresh, openCases, openResearch }) {
  const [kind, setKind] = useState("inventory");
  const [importId, setImportId] = useState("");
  const [offset, setOffset] = useState(0);
  const [file, setFile] = useState(null);
  const [notice, setNotice] = useState("");
  const [warehouse, setWarehouse] = useState("");
  const [sku, setSku] = useState("");
  const selected =
    imports.find((item) => item.kind === kind && item.import_id === importId) ||
    imports.find((item) => item.kind === kind);
  const query = new URLSearchParams({
    import_id: selected?.import_id || "",
    limit: 20,
    offset,
    warehouse,
    sku,
  });
  const remote = useRemote(selected ? `/records/${kind}?${query}` : null, version);
  const task = useTask();
  const rows = remote.data?.records || [];
  function changeKind(value) {
    setKind(value);
    setOffset(0);
    setWarehouse("");
    setSku("");
  }
  async function ingest(upload = false) {
    const data = upload ? new FormData() : undefined;
    if (upload) data.append("file", file);
    const result = await task.run(() => request(`/imports/${kind}`, { method: "POST", data }));
    if (result) {
      setNotice(
        `${result.duplicate ? "Existing import reused" : "Import complete"}: ${result.accepted_rows.toLocaleString()} accepted, ${result.rejected_rows} rejected.`,
      );
      setImportId(result.import_id);
      setOffset(0);
      refresh();
    }
  }
  async function process(ids) {
    const result = await task.run(() =>
      request("/batches", { method: "POST", data: { record_ids: ids } }),
    );
    if (result) {
      setNotice(
        `${result.processed} processed, ${result.failed} failed. ${result.failures.map((failure) => failure.error).join("; ")}`,
      );
      refresh();
      if (result.results.length) openCases(result.results[0].case_id);
    }
  }
  return (
    <section className="operations-page">
      <PageIntro
        eyebrow="01 / Automated record processing"
        title="Operations"
        description="From recorded data to a decision you can explain. Choose a source, analyze records and review the evidence."
        icon="operations"
        mode="Historical data · not live"
        context="Dataset-backed inputs. Human-reviewed decisions."
      />
      <WorkflowGuide
        label="Operations workflow"
        steps={[
          {
            title: "Connect your data",
            description: "Choose an import or add a CSV",
            href: "#operations-import",
          },
          {
            title: "Explore the source",
            description: "Inspect records before analysis",
            href: "#operations-records",
          },
          {
            title: "Analyze records",
            description: "Process a page or the full import",
            href: "#operations-processing",
          },
        ]}
      />
      <div className="operations-launchpad">
        <div className="operations-main-column">
          <div className="surface import-panel" id="operations-import">
            <PanelHeading
              icon="upload"
              eyebrow="01 / Input workspace"
              title="Choose your working data"
              description="Use a stored import, the local dataset or your own CSV."
            />
            <SourcePicker
              imports={imports}
              kind={kind}
              setKind={changeKind}
              selected={selected}
              setSelected={(value) => {
                setImportId(value);
                setOffset(0);
              }}
            />
            <div className="import-options">
              <div className="import-local">
                <span className="option-label">Use the project file</span>
                <button disabled={task.busy} onClick={() => ingest()}>
                  <WorkbenchIcon name="database" />
                  Import local {kind} dataset
                </button>
              </div>
              <div className="import-upload">
                <label className="file-field">
                  New CSV
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => setFile(event.target.files[0] || null)}
                  />
                </label>
                <button disabled={task.busy || !file} onClick={() => ingest(true)}>
                  Import selected CSV
                </button>
              </div>
            </div>
            {selected && (
              <p className="provenance import-provenance">
                <WorkbenchIcon name="shield" />
                {selected.accepted_rows.toLocaleString()} accepted · {selected.rejected_rows}{" "}
                rejected · SHA-256 {selected.fingerprint.slice(0, 12)}… · independent dataset
              </p>
            )}
            {(task.error || remote.error) && (
              <p className="error" role="alert">
                {task.error || remote.error}
              </p>
            )}
            {notice && (
              <p className="notice" role="status">
                {notice}
              </p>
            )}
          </div>
          <ProcessingJobs
            key={selected?.import_id || "empty"}
            selected={selected}
            openCases={openCases}
          />
        </div>
        <DatasetLibrary openResearch={openResearch} />
      </div>
      <section
        className="surface records-panel"
        id="operations-records"
        aria-labelledby="source-records-title"
      >
        <div className="section-heading records-heading">
          <PanelHeading
            icon="package"
            eyebrow="02 / Record explorer"
            title="Source records"
            id="source-records-title"
            description="Inputs come from storage; no feature-by-feature entry is required."
          />
          <button
            className="primary"
            disabled={task.busy || !rows.length}
            onClick={() => process(rows.map((row) => row.record_id))}
          >
            {task.busy ? "Processing…" : `Process these ${rows.length} records`}
          </button>
        </div>
        {kind === "inventory" && (
          <div className="toolbar record-filters">
            <label>
              Warehouse filter
              <input
                value={warehouse}
                placeholder="All warehouses"
                onChange={(event) => {
                  setWarehouse(event.target.value);
                  setOffset(0);
                }}
              />
            </label>
            <label>
              SKU filter
              <input
                value={sku}
                placeholder="All SKUs"
                onChange={(event) => {
                  setSku(event.target.value);
                  setOffset(0);
                }}
              />
            </label>
          </div>
        )}
        <div className="table-scroll records-table">
          <table>
            <thead>
              <tr>
                <th>{kind === "inventory" ? "Product / warehouse" : "Delivery / partner"}</th>
                <th>{kind === "inventory" ? "Recorded date" : "Traffic"}</th>
                <th>{kind === "inventory" ? "Available stock" : "Distance"}</th>
                <th>Process</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.record_id}>
                  <td>
                    <strong>
                      {row.inputs.SKU_ID || row.inputs.delivery_id || "Unidentified delivery"}
                    </strong>
                    <small>{row.inputs.Warehouse_ID || row.inputs.delivery_partner}</small>
                  </td>
                  <td>{row.inputs.Date || row.inputs.Traffic_Level}</td>
                  <td>
                    {kind === "inventory"
                      ? `${row.inputs.Inventory_Level} units`
                      : `${row.inputs.distance_km} km`}
                  </td>
                  <td>
                    <button
                      className="text-button"
                      disabled={task.busy}
                      onClick={() => process([row.record_id])}
                    >
                      Analyze case →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <p className="empty">
              {selected
                ? "No matching records, or records are loading."
                : "Import a dataset to populate the workbench."}
            </p>
          )}
        </div>
        <div className="pagination">
          <span>{remote.data?.total.toLocaleString() || "0"} matching records</span>
          <button
            disabled={!offset || task.busy}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Previous
          </button>
          <button
            disabled={task.busy || offset + 20 >= (remote.data?.total || 0)}
            onClick={() => setOffset(offset + 20)}
          >
            Next
          </button>
        </div>
      </section>
    </section>
  );
}
