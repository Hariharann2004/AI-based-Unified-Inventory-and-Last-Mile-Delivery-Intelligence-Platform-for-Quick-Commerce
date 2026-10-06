import { useState } from "react";
import { API_BASE_URL } from "../../../shared/config/environment.js";
import { useRemote } from "../hooks/useRemote.js";

export function DatasetLibrary({ openResearch }) {
  const [datasetId, setDatasetId] = useState("porter-eta");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const catalog = useRemote("/datasets");
  const datasets = catalog.data?.datasets || [];
  const selected = datasets.find((item) => item.dataset_id === datasetId) || datasets[0];
  const preview = useRemote(
    previewOpen && selected?.available
      ? `/datasets/${encodeURIComponent(selected.dataset_id)}/preview?limit=10&offset=${offset}`
      : null,
  );
  const rows = preview.data?.records || [];
  const columns = preview.data?.dataset.columns || [];

  function changeDataset(value) {
    setDatasetId(value);
    setOffset(0);
  }

  return (
    <section className="surface dataset-library" aria-labelledby="dataset-library-title">
      <p className="eyebrow">Original source files / read-only</p>
      <h2 id="dataset-library-title">Project datasets · CSV preview & download</h2>
      <p className="muted">
        Inventory, legacy delivery and Porter are separate sources. Browse or download the original
        CSV here without importing it or changing a model.
      </p>
      {catalog.error && <p className="error">Dataset library: {catalog.error}</p>}
      {!catalog.data && !catalog.error && <p className="muted">Loading project datasets…</p>}
      {datasets.length > 0 && (
        <>
          <label>
            Project CSV dataset
            <select
              value={selected.dataset_id}
              onChange={(event) => changeDataset(event.target.value)}
            >
              {datasets.map((item) => (
                <option key={item.dataset_id} value={item.dataset_id}>
                  {item.title} ·{" "}
                  {item.available
                    ? `${item.row_count.toLocaleString("en-US")} rows`
                    : "unavailable"}
                </option>
              ))}
            </select>
          </label>
          <p>
            <strong>{selected.role}</strong> — {selected.purpose}
          </p>
          <p className="provenance">
            VS Code / Excel file: <code>{selected.relative_path}</code>
          </p>
          <p className="warning">{selected.warning}</p>
          {!selected.available ? (
            <p className="error">{selected.error}</p>
          ) : (
            <>
              <p className="provenance">
                {selected.row_count.toLocaleString("en-US")} original rows ·{" "}
                {selected.columns.length} columns ·{(selected.size_bytes / 1024 / 1024).toFixed(2)}{" "}
                MiB · source checksum verified
              </p>
              <div className="toolbar">
                <button onClick={() => setPreviewOpen(!previewOpen)}>
                  {previewOpen ? "Hide CSV preview" : "Preview original CSV"}
                </button>
                <a
                  className="dataset-download"
                  href={`${API_BASE_URL}/workbench/datasets/${encodeURIComponent(selected.dataset_id)}/download`}
                  download={selected.filename}
                >
                  Download original CSV
                </a>
                {selected.dataset_id === "porter-eta" && openResearch && (
                  <button className="primary" onClick={openResearch}>
                    View Porter ETA results
                  </button>
                )}
              </div>
              {previewOpen && (
                <div>
                  <h3>Original CSV preview · {selected.filename}</h3>
                  <p className="muted">
                    Recorded source values, not predictions. The download contains all original
                    rows. Empty values remain missing; no outcomes are filled or fabricated.
                  </p>
                  {preview.error && (
                    <p className="error" role="alert">
                      {preview.error}
                    </p>
                  )}
                  {!preview.data && !preview.error && <p className="muted">Loading CSV preview…</p>}
                  {preview.data && (
                    <>
                      <div
                        className="table-scroll dataset-preview"
                        tabIndex={0}
                        aria-label="Scrollable original CSV preview"
                      >
                        <table>
                          <thead>
                            <tr>
                              <th>CSV row</th>
                              {columns.map((column) => (
                                <th key={column}>{column}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row, index) => (
                              <tr key={offset + index}>
                                <td>{offset + index + 2}</td>
                                {columns.map((column) => (
                                  <td key={column}>
                                    {row[column] === "" || row[column] == null ? "—" : row[column]}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="pagination">
                        <span>
                          {rows.length ? `${offset + 1}–${offset + rows.length}` : "0"} of{" "}
                          {selected.row_count.toLocaleString("en-US")} source records
                        </span>
                        <button
                          disabled={!offset}
                          onClick={() => setOffset(Math.max(0, offset - 10))}
                        >
                          Previous CSV rows
                        </button>
                        <button
                          disabled={offset + 10 >= selected.row_count}
                          onClick={() => setOffset(offset + 10)}
                        >
                          Next CSV rows
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
