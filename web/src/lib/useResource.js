import { useCallback, useEffect, useState } from "react";

/**
 * Loads a resource once on mount and exposes reload().
 * `load` must be a stable function (defined outside the component).
 * While reloading, the previous data stays available so panels don't flash.
 *
 * @returns {{ data: any, status: "loading" | "ready" | "error", error: Error | null, reload: () => Promise<void> }}
 */
export function useResource(load) {
  // Starts as "loading": the first fetch begins on mount.
  const [state, setState] = useState({ data: null, status: "loading", error: null });

  const onReady = (data) => setState({ data, status: "ready", error: null });
  const onError = (error) => setState((s) => ({ ...s, status: "error", error }));

  useEffect(() => {
    let cancelled = false; // ignore the answer if the component went away
    load().then(
      (data) => !cancelled && onReady(data),
      (error) => !cancelled && onError(error),
    );
    return () => {
      cancelled = true;
    };
  }, [load]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, status: "loading", error: null }));
    return load().then(onReady, onError);
  }, [load]);

  return { ...state, reload };
}
