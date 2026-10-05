import { useState } from "react";
import { request } from "../api/client.js";
import { ProcessingJobs } from "../components/ProcessingJobs.jsx";
import { SourcePicker } from "../components/SourcePicker.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";

export function OperationsPage({ imports, version, refresh, openCases }) {
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
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">01 / Automated record processing</p>
          <h1>Operations</h1>
          <p className="muted">
            Load recorded operations. Let the system retrieve inputs and identify cases.
          </p>
        </div>
        <span className="mode-label">Historical data · not live</span>
      </div>
      <div className="surface">
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
        <div className="toolbar">
          <button disabled={task.busy} onClick={() => ingest()}>
            Import local {kind} dataset
          </button>
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
        {selected && (
          <p className="provenance">
            {selected.accepted_rows.toLocaleString()} accepted · {selected.rejected_rows} rejected ·
            SHA-256 {selected.fingerprint.slice(0, 12)}… · independent dataset
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
      <div className="section-heading">
        <div>
          <h2>Source records</h2>
          <p className="muted">
            Inputs come from storage; no feature-by-feature entry is required.
          </p>
        </div>
        <button
          className="primary"
          disabled={task.busy || !rows.length}
          onClick={() => process(rows.map((row) => row.record_id))}
        >
          {task.busy ? "Processing…" : `Process these ${rows.length} records`}
        </button>
      </div>
      {kind === "inventory" && (
        <div className="toolbar">
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
      <div className="surface table-scroll">
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
        <button disabled={!offset || task.busy} onClick={() => setOffset(Math.max(0, offset - 20))}>
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
  );
}
