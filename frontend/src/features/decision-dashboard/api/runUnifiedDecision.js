import { API_BASE_URL } from "../../../shared/config/environment.js";

export async function runUnifiedDecision(payload, { signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/decision/unified`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Prediction failed with status ${response.status}`);
  }
  return data;
}
