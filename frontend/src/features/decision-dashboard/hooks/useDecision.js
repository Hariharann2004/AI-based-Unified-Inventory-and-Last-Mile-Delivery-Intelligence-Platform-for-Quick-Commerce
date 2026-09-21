import { useEffect, useRef, useState } from "react";

import { runUnifiedDecision } from "../api/runUnifiedDecision.js";

export function useDecision() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const activeRequest = useRef(null);

  useEffect(() => () => activeRequest.current?.abort(), []);

  async function execute(payload) {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setLoading(true);
    setError("");
    try {
      setResult(await runUnifiedDecision(payload, { signal: controller.signal }));
    } catch (requestError) {
      if (requestError.name !== "AbortError") {
        setError(`${requestError.message}. Start the Flask API and train the models first.`);
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setLoading(false);
      }
    }
  }

  return { result, error, loading, execute };
}
