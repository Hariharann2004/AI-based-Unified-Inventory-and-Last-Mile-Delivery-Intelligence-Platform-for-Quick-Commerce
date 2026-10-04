import { useEffect, useRef, useState } from "react";
import { request } from "../api/client.js";
import { SourcePicker } from "../components/SourcePicker.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";

export function ReplayPage({ imports, version, refresh, openCases }) {
  const [kind, setKind] = useState("inventory");
  const [importId, setImportId] = useState("");
  const [run, setRun] = useState(null);
  const [automatic, setAutomatic] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [replayError, setReplayError] = useState("");
  const [scenario, setScenario] = useState("depleted_stock");
  const [inventoryId, setInventoryId] = useState("");
  const [deliveryId, setDeliveryId] = useState("");
  const [mappingReason, setMappingReason] = useState("");
  const selected =
    imports.find((item) => item.kind === kind && item.import_id === importId) ||
    imports.find((item) => item.kind === kind);
  const scenarios = useRemote("/scenarios", version);
  const inventories = useRemote(
    imports.some((item) => item.kind === "inventory") ? "/records/inventory?limit=20" : null,
    version,
  );
  const deliveries = useRemote(
    imports.some((item) => item.kind === "delivery") ? "/records/delivery?limit=20" : null,
    version,
  );
  const task = useTask();
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const completed = run && run.cursor >= run.total;
  const actualInventoryId = inventoryId || inventories.data?.records[0]?.record_id;
  const actualDeliveryId = deliveryId || deliveries.data?.records[0]?.record_id;

  useEffect(() => {
    if (!automatic || !run || run.cursor >= run.total) return;
    const timer = setTimeout(async () => {
      setAdvancing(true);
      try {
        const next = await request(`/replays/${run.run_id}/steps`, {
          method: "POST",
          data: { expected_cursor: run.cursor, count: 5 },
        });
        if (alive.current) {
          setRun(next);
          refresh();
        }
      } catch (error) {
        if (alive.current) {
          setReplayError(error.message);
          setAutomatic(false);
        }
      } finally {
        if (alive.current) setAdvancing(false);
      }
    }, 1000);
    return () => {
      clearTimeout(timer);
    };
  }, [automatic, run, refresh]);

  async function start(auto) {
    const next = await task.run(() =>
      request("/replays", {
        method: "POST",
        data: { kind, import_id: selected.import_id, limit: 100 },
      }),
    );
    if (next) {
      setRun(next);
      setAutomatic(auto);
      setReplayError("");
    }
  }
  async function step() {
    const next = await task.run(() =>
      request(`/replays/${run.run_id}/steps`, {
        method: "POST",
        data: { expected_cursor: run.cursor, count: 5 },
      }),
    );
    if (next) {
      setRun(next);
      refresh();
    }
  }
  async function simulate() {
    const result = await task.run(() =>
      request("/scenarios", {
        method: "POST",
        data: {
          scenario_id: scenario,
          inventory_id: actualInventoryId,
          delivery_id: actualDeliveryId,
          mapping_reason: mappingReason,
        },
      }),
    );
    if (result) {
      refresh();
      openCases(result.case_id);
    }
  }
  const selectedScenario = (scenarios.data || []).find((item) => item.id === scenario);
  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">03 / Reproducible operational sequences</p>
          <h1>Replay & scenarios</h1>
          <p className="muted">
            Recorded sequences and labelled stress tests. No live feeds or accuracy claims.
          </p>
        </div>
        <span className="mode-label">Simulation environment</span>
      </div>
      {(task.error || replayError || scenarios.error || inventories.error || deliveries.error) && (
        <p className="error" role="alert">
          {task.error || replayError || scenarios.error || inventories.error || deliveries.error}
        </p>
      )}
      <div className="surface">
        <h2>Historical replay</h2>
        <SourcePicker
          imports={imports}
          kind={kind}
          setKind={setKind}
          selected={selected}
          setSelected={setImportId}
        />
        <div className="toolbar">
          <button
            className="primary"
            disabled={!selected || task.busy || advancing || (automatic && !completed)}
            onClick={() => start(true)}
          >
            Start automatic replay
          </button>
          <button
            disabled={!selected || task.busy || advancing || (automatic && !completed)}
            onClick={() => start(false)}
          >
            Prepare step-by-step replay
          </button>
          {run && (
            <>
              <button disabled={task.busy || advancing || completed || automatic} onClick={step}>
                Advance 5 records
              </button>
              {automatic && !completed && (
                <button onClick={() => setAutomatic(false)}>Pause replay</button>
              )}
              {!automatic && !completed && (
                <button disabled={advancing} onClick={() => setAutomatic(true)}>
                  Continue automatically
                </button>
              )}
            </>
          )}
        </div>
        {run ? (
          <>
            <div className="replay-progress">
              <strong>
                {run.cursor} / {run.total} records
              </strong>
              <span>{run.status.replaceAll("_", " ")}</span>
            </div>
            <progress value={run.cursor} max={run.total} aria-label="Replay progress" />
            <p className="provenance">
              {run.sequence_note} · recorded data · model checksums pinned for this run
            </p>
            <ol className="timeline" aria-label="Replay events">
              {run.events.slice(-10).map((event, index) => (
                <li key={index}>
                  <strong>
                    {event.status === "failed" ? "Processing failed" : `${event.priority} priority`}
                  </strong>
                  <span>{event.error || event.record_id}</span>
                  {event.case_id && (
                    <button className="text-button" onClick={() => openCases(event.case_id)}>
                      Open replay case →
                    </button>
                  )}
                </li>
              ))}
            </ol>
          </>
        ) : (
          <p className="empty">
            Choose a dataset and start a sequence of up to 100 stored records.
          </p>
        )}
      </div>
      <div className="surface">
        <h2>Scenario laboratory</h2>
        <p className="muted">
          Presets modify copies of source records. Model outputs are measured, never forced to match
          a preferred result.
        </p>
        <div className="source-picker">
          <label>
            Stress scenario
            <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
              {(scenarios.data || []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          {(selectedScenario?.kind === "inventory" || selectedScenario?.kind === "unified") && (
            <label>
              Inventory source
              <select
                value={actualInventoryId || ""}
                onChange={(event) => setInventoryId(event.target.value)}
              >
                <option value="" disabled>
                  Select a stored source
                </option>
                {(inventories.data?.records || []).map((row) => (
                  <option key={row.record_id} value={row.record_id}>
                    {row.inputs.SKU_ID} · {row.inputs.Warehouse_ID} · row {row.position + 1}
                  </option>
                ))}
              </select>
            </label>
          )}
          {(selectedScenario?.kind === "delivery" || selectedScenario?.kind === "unified") && (
            <label>
              Delivery source
              <select
                value={actualDeliveryId || ""}
                onChange={(event) => setDeliveryId(event.target.value)}
              >
                <option value="" disabled>
                  Select a stored source
                </option>
                {(deliveries.data?.records || []).map((row) => (
                  <option key={row.record_id} value={row.record_id}>
                    {row.inputs.delivery_id || `Source row ${row.position + 1}`}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {selectedScenario?.kind === "unified" && (
          <>
            <p className="warning">
              Independent datasets: this mapping represents a simulated case, not a verified real
              order.
            </p>
            <label>
              Why these records are being mapped
              <input
                value={mappingReason}
                maxLength={500}
                onChange={(event) => setMappingReason(event.target.value)}
              />
            </label>
          </>
        )}
        <p className="formula">
          Overrides: {JSON.stringify(selectedScenario?.overrides || {})}
          {scenario === "combined_pressure" && " · depleted stock + peak-hour traffic pressure"}
        </p>
        <button
          className="primary"
          disabled={
            task.busy ||
            !selectedScenario ||
            (selectedScenario.kind !== "delivery" && !actualInventoryId) ||
            (selectedScenario.kind !== "inventory" && !actualDeliveryId) ||
            (selectedScenario.kind === "unified" && !mappingReason.trim())
          }
          onClick={simulate}
        >
          Analyze stress scenario
        </button>
      </div>
    </section>
  );
}
