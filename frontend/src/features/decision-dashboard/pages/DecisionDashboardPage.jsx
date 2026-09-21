import { MetricCard } from "../components/MetricCard.jsx";
import { useDecision } from "../hooks/useDecision.js";
import { deliveryExample, inventoryExample } from "../model/demoRecords.js";

export function DecisionDashboardPage() {
  const { result, error, loading, execute } = useDecision();

  function runDemo() {
    execute({ inventory: inventoryExample, delivery: deliveryExample });
  }

  return (
    <main>
      <header>
        <p className="eyebrow">LIGHTGBM-POWERED CAPSTONE</p>
        <h1>Unified Operations Dashboard</h1>
        <p>Inventory and last-mile delivery decisions for the assigned dark store.</p>
      </header>
      <button type="button" onClick={runDemo} disabled={loading}>
        {loading ? "Analysing…" : "Run demo decision"}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
      {result && (
        <section className="grid" aria-label="Decision results">
          <MetricCard title="Inventory" values={result.inventory} />
          <MetricCard title="Delivery" values={result.delivery} />
          <MetricCard
            title={`Priority: ${result.decision.operational_priority}`}
            values={{
              actions: result.decision.actions.join(" • "),
              warehouse_policy: "Assigned warehouse only",
            }}
          />
        </section>
      )}
    </main>
  );
}
