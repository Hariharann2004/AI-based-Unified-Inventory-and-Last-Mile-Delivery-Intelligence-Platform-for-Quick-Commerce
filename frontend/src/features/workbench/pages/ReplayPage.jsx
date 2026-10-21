import { useEffect, useRef, useState } from "react";
import { request } from "../api/client.js";
import { MixedPriorityDemo } from "../components/MixedPriorityDemo.jsx";
import { ReplayEvents } from "../components/ReplayEvents.jsx";
import { SourcePicker } from "../components/SourcePicker.jsx";
import { useRemote, useTask } from "../hooks/useRemote.js";
import { PageIntro, PanelHeading, WorkflowGuide } from "../components/WorkspacePrimitives.jsx";

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
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const invalidDates = kind === "inventory" && startDate && endDate && startDate > endDate;
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
        data: {
          kind,
          import_id: selected.import_id,
          limit: 100,
          ...(kind === "inventory" && startDate ? { start_date: startDate } : {}),
          ...(kind === "inventory" && endDate ? { end_date: endDate } : {}),
        },
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
    <section className="replay-page">
      <PageIntro
        eyebrow="03 / Reproducible operational sequences"
        title="Replay & scenarios"
        description="Explore what happened. Compare saved priorities. Test what could happen next."
        icon="replay"
        mode="Simulation environment"
        context="Recorded sequences and labelled stress tests. No live feeds or accuracy claims."
      />
      <WorkflowGuide
        label="Replay and scenario modes"
        steps={[
          {
            title: "Historical replay",
            description: "Follow recorded source order",
            href: "#historical-replay",
          },
          {
            title: "Selected demonstration",
            description: "Explore genuine saved priorities",
            href: "#mixed-priority-demo",
          },
          {
            title: "Scenario laboratory",
            description: "Test copies, not the original data",
            href: "#scenario-laboratory",
          },
        ]}
      />
      {(task.error || replayError || scenarios.error || inventories.error || deliveries.error) && (
        <p className="error" role="alert">
          {task.error || replayError || scenarios.error || inventories.error || deliveries.error}
        </p>
      )}
      <section
        className="surface replay-panel"
        id="historical-replay"
        aria-labelledby="historical-replay-title"
      >
        <PanelHeading
          icon="replay"
          eyebrow="01 / Recorded sequence"
          title="Historical replay"
          id="historical-replay-title"
          description="Choose a period and follow how recorded operations are assessed."
        />
        <div className="replay-configuration">
          <div className="replay-source">
            <SourcePicker
              imports={imports}
              kind={kind}
              setKind={setKind}
              selected={selected}
              setSelected={setImportId}
            />
            {kind === "inventory" ? (
              <>
                <div className="toolbar">
                  <label>
                    Replay start date (optional)
                    <input
                      type="date"
                      value={startDate}
                      onChange={(event) => setStartDate(event.target.value)}
                      disabled={task.busy || advancing || (automatic && !completed)}
                    />
                  </label>
                  <label>
                    Replay end date (optional)
                    <input
                      type="date"
                      value={endDate}
                      onChange={(event) => setEndDate(event.target.value)}
                      disabled={task.busy || advancing || (automatic && !completed)}
                    />
                  </label>
                </div>
                <p className="muted">
                  Dates apply to the next replay, including both boundary dates. Leave either blank
                  for an open-ended range. Each run uses up to the first 100 matching records in
                  chronological order.
                </p>
                {invalidDates && (
                  <p className="error" role="alert">
                    Start date must be on or before end date.
                  </p>
                )}
              </>
            ) : (
              <p className="muted">
                Delivery replay uses source-row order. Date filtering is unavailable because
                verified delivery timestamps are absent from this operational dataset.
              </p>
            )}
          </div>
          <div className="toolbar replay-actions">
            <p className="option-label">Choose how to run</p>
            <button
              className="primary"
              disabled={
                !selected || !!invalidDates || task.busy || advancing || (automatic && !completed)
              }
              onClick={() => start(true)}
            >
              Start automatic replay
            </button>
            <button
              disabled={
                !selected || !!invalidDates || task.busy || advancing || (automatic && !completed)
              }
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
            {run.date_range && (
              <p className="provenance">
                Requested range: {run.date_range.start_date || "beginning"} to{" "}
                {run.date_range.end_date || "latest"}. This run selects {run.total} of{" "}
                {run.eligible_records} eligible records.
                {run.selected_dates?.first && (
                  <>
                    {" "}
                    Recorded dates: {run.selected_dates.first.slice(0, 10)} to{" "}
                    {run.selected_dates.last.slice(0, 10)}.
                  </>
                )}
              </p>
            )}
            <ReplayEvents key={run.run_id} events={run.events} openCases={openCases} />
          </>
        ) : (
          <p className="empty">
            Choose a dataset and start a sequence of up to 100 stored records.
          </p>
        )}
      </section>
      <MixedPriorityDemo imports={imports} openCases={openCases} />
      <div className="surface scenario-panel" id="scenario-laboratory">
        <PanelHeading
          icon="experiment"
          eyebrow="03 / Controlled what-if test"
          title="Scenario laboratory"
          description="Presets modify copies of source records. Model outputs are measured, never forced to match a preferred result."
        />
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
