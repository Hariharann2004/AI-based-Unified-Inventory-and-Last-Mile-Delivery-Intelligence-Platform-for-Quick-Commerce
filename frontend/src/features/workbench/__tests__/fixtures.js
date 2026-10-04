export const imports = [
  {
    import_id: "i1",
    kind: "inventory",
    source: "inventory.csv",
    accepted_rows: 40,
    rejected_rows: 1,
    fingerprint: "a".repeat(64),
  },
  {
    import_id: "d1",
    kind: "delivery",
    source: "delivery.csv",
    accepted_rows: 25,
    rejected_rows: 0,
    fingerprint: "b".repeat(64),
  },
];
export const inventory = {
  record_id: "i1:0",
  position: 0,
  import_id: "i1",
  inputs: { SKU_ID: "SKU_1", Warehouse_ID: "WH_1", Date: "2024-01-01", Inventory_Level: 100 },
};
export const delivery = {
  record_id: "d1:0",
  position: 0,
  import_id: "d1",
  inputs: {
    delivery_id: "DEL_1",
    delivery_partner: "partner",
    Traffic_Level: "High",
    distance_km: 4,
  },
};
export const assessment = {
  sku_id: "SKU_1",
  warehouse_id: "WH_1",
  predicted_daily_demand: 20,
  stockout_probability: 0.8,
  stockout_risk: "High",
  inventory_health_score: 40,
  delivery_intelligence_score: 60,
  delay_probability: 0.8,
  delay_risk: "High",
  predicted_eta_minutes: 25,
};
export const explanation = {
  available: true,
  scale: "log_odds",
  baseline: -0.5,
  factors: [
    { feature: "Inventory_Level", contribution: 0.3 },
    { feature: "Region", contribution: -0.1 },
  ],
  unknown_encoded_categories: ["Region_new"],
  note: "Model influence, not causation.",
};
export const caseRecord = {
  case_id: "c1",
  kind: "inventory",
  priority: "Critical",
  status: "open",
  evidence: {
    provenance: "historical_dataset",
    kind: "inventory",
    inputs: inventory.inputs,
    assessment,
    decision: { actions: ["Review inventory and replenish"] },
    calculations: {
      current_stock: 100,
      required_stock: 230,
      reorder_point: 120,
      formula: "demand × lead time × 1.15",
      expected_minutes: 20,
      predicted_minutes: 25,
    },
    explanations: {
      stockout: explanation,
      demand: { available: false, reason: "Not available for stub" },
    },
    models: { algorithm: "LightGBM" },
    warnings: ["Derived stockout label."],
  },
  drafts: [{ type: "replenishment", quantity: 130, warehouse: "WH_1", status: "pending" }],
  audit: [
    {
      event: "created",
      actor: "system",
      reason: "historical_dataset",
      occurred_at: "2024-01-01T00:00:00Z",
    },
  ],
};
export const scenarios = [
  {
    id: "depleted_stock",
    kind: "inventory",
    label: "Depleted stock",
    overrides: { Inventory_Level: 0 },
  },
  {
    id: "traffic_pressure",
    kind: "delivery",
    label: "Traffic pressure",
    overrides: { Traffic_Level: "High" },
  },
  { id: "combined_pressure", kind: "unified", label: "Combined pressure", overrides: {} },
];
export const windowReport = {
  window: 1,
  counts: { train: 60, validation: 20, test: 20 },
  regression: { mae: 3.2, rmse: 4 },
  constant_baseline: { mae: 6 },
  classification: {
    threshold: 0.5,
    metrics: { precision: 0.5, recall: 0.7, f1: 0.58 },
    confusion_matrix: [
      [10, 3],
      [2, 5],
    ],
    precision_recall: [
      { recall: 0, precision: 1 },
      { recall: 1, precision: 0.5 },
    ],
    calibration: [
      { predicted: 0.3, observed: 0.2 },
      { predicted: 0.8, observed: 0.7 },
    ],
  },
  action_threshold: { threshold: 0.7 },
  samples: [
    { actual: 10, predicted: 12 },
    { actual: 20, predicted: 19 },
  ],
  segments: [{ segment: "WH_1", count: 20, mae: 3.2, rmse: 4 }],
};
export const evaluation = {
  evaluation_id: "e1",
  import_id: "i1",
  status: "completed",
  report: {
    protocol: "Date-isolated testing",
    windows: [windowReport, { ...windowReport, window: 2 }, { ...windowReport, window: 3 }],
    warnings: ["Derived risk label"],
    features: ["Inventory_Level"],
    library_versions: {},
    note: "Not promoted",
  },
};
