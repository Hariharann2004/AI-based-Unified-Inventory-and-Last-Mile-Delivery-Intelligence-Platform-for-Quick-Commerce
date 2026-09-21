import { useState } from "react";

const inventoryExample = {
  Date: "2024-01-01", SKU_ID: "SKU_1", Warehouse_ID: "WH_1", Supplier_ID: "SUP_8",
  Region: "West", Inventory_Level: 592, Supplier_Lead_Time_Days: 14, Reorder_Point: 379,
  Order_Quantity: 0, Unit_Cost: 13.95, Unit_Price: 20.48, Promotion_Flag: 0,
};
const deliveryExample = {
  delivery_id: "DEMO-1", delivery_partner: "delhivery", package_type: "grocery",
  vehicle_type: "Bike", delivery_mode: "Instant", region: "west", weather_condition: "clear",
  distance_km: 4, package_weight_kg: 2, expected_time_minutes: 20, delivery_rating: 4,
  Traffic_Level: "Medium", Peak_Hour: "No", Rider_Workload: 1,
};

function App() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function runDecision() {
    setLoading(true); setError("");
    try {
      const response = await fetch("http://127.0.0.1:5000/api/decision/unified", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ inventory: inventoryExample, delivery: deliveryExample }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Prediction failed");
      setResult(data);
    } catch (err) { setError(`${err.message}. Start the Flask API and train the models first.`); }
    finally { setLoading(false); }
  }

  return <main>
    <header><p className="eyebrow">LIGHTGBM-POWERED CAPSTONE</p><h1>Unified Operations Dashboard</h1><p>Inventory and last-mile delivery decisions for the assigned dark store.</p></header>
    <button onClick={runDecision} disabled={loading}>{loading ? "Analysing…" : "Run demo decision"}</button>
    {error && <p className="error">{error}</p>}
    {result && <section className="grid">
      <Card title="Inventory" values={result.inventory} />
      <Card title="Delivery" values={result.delivery} />
      <Card title={`Priority: ${result.decision.operational_priority}`} values={{ actions: result.decision.actions.join(" • "), warehouse_policy: "Assigned warehouse only" }} />
    </section>}
  </main>;
}

function Card({ title, values }) {
  return <article><h2>{title}</h2>{Object.entries(values).map(([key, value]) => <p key={key}><span>{key.replaceAll("_", " ")}</span><strong>{String(value)}</strong></p>)}</article>;
}
export default App;
