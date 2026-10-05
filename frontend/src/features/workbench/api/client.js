import { API_BASE_URL } from "../../../shared/config/environment.js";

export async function request(path, { method = "GET", data, signal } = {}) {
  const form = data instanceof FormData;
  const response = await fetch(`${API_BASE_URL}/workbench${path}`, {
    method,
    signal,
    headers: data && !form ? { "Content-Type": "application/json" } : undefined,
    body: data ? (form ? data : JSON.stringify(data)) : undefined,
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(`API returned an unreadable response (${response.status}).`);
  }
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}

export async function downloadReport(path, format, filename) {
  const response = await fetch(`${API_BASE_URL}/workbench${path}/export?format=${format}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Export failed (${response.status}).`);
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${filename}.${format}`;
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(url);
  }
  return true;
}
