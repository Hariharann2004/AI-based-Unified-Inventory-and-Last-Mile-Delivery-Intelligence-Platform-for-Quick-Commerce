import { useEffect, useRef, useState } from "react";
import { request } from "../api/client.js";

export function useRemote(path, version = 0) {
  const [state, setState] = useState({ path: null, data: null, error: "" });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    request(path, { signal: controller.signal }).then(
      (data) => {
        if (!controller.signal.aborted) setState({ path, data, error: "" });
      },
      (error) => {
        if (!controller.signal.aborted) setState({ path, data: null, error: error.message });
      },
    );
    return () => controller.abort();
  }, [path, version]);
  return state.path === path ? state : { data: null, error: "" };
}

export function useTask() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function run(task) {
    setBusy(true);
    setError("");
    try {
      return await task();
    } catch (failure) {
      if (alive.current) setError(failure.message);
      return null;
    } finally {
      if (alive.current) setBusy(false);
    }
  }
  return { run, busy, error };
}
