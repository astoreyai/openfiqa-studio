import { useEffect, useRef, useState } from "react";
import { api, runEventSocket, type RunEvent, type RunSummary } from "./api";

/**
 * F10 — run log panel.
 *
 * Streams the control plane's real event feed over the WebSocket. Every line shown is a line the
 * child process actually wrote; there is no progress animation standing in for output the studio
 * does not have.
 */
export function LogPanel({
  runs,
  selectedRunId,
  onSelectRun,
  onRunsChanged,
}: {
  runs: RunSummary[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  onRunsChanged: () => void;
}) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [socketState, setSocketState] = useState<"idle" | "open" | "closed">("idle");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!selectedRunId) {
      setEvents([]);
      setSocketState("idle");
      return;
    }
    setEvents([]);
    const socket = runEventSocket(selectedRunId);
    socket.onopen = () => setSocketState("open");
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data as string) as RunEvent;
      setEvents((current) => [...current, event]);
      if (["completed", "failed", "cancelled"].includes(event.type)) onRunsChanged();
    };
    socket.onclose = () => setSocketState("closed");
    return () => socket.close();
  }, [selectedRunId, onRunsChanged]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [events.length]);

  const selected = runs.find((r) => r.run_id === selectedRunId) ?? null;

  return (
    <div className="logpanel">
      <div className="runlist">
        <h2>Runs ({runs.length})</h2>
        {runs.length === 0 && <p className="empty">No runs yet. Press ⌘K → Run health check.</p>}
        {runs.map((run) => (
          <button
            key={run.run_id}
            className={`row ${run.run_id === selectedRunId ? "sel" : ""}`}
            onClick={() => onSelectRun(run.run_id)}
          >
            <span className={`dot run-${run.status}`} title={run.status} />
            <span className="rowname">{run.label}</span>
            <span className="rowver">
              {run.exit_code === null ? run.status : `exit ${run.exit_code}`}
            </span>
          </button>
        ))}
      </div>

      <div className="logstream">
        <div className="loghead">
          <span>{selected ? selected.label : "Log"}</span>
          {selected && (
            <>
              <span className={`badge run-${selected.status}`}>{selected.status}</span>
              {!["completed", "failed", "cancelled"].includes(selected.status) && (
                <button
                  className="cancel"
                  onClick={async () => {
                    await api.cancelRun(selected.run_id);
                    onRunsChanged();
                  }}
                >
                  Cancel
                </button>
              )}
            </>
          )}
          <span className="sockstate">{socketState === "open" ? "streaming" : socketState}</span>
        </div>
        <pre className="logbody">
          {events.length === 0 && <span className="empty">Select a run to stream its output.</span>}
          {events.map((event, i) => (
            <span key={i} className={`ev ev-${event.type}`}>
              {formatEvent(event)}
              {"\n"}
            </span>
          ))}
          <div ref={bottomRef} />
        </pre>
      </div>
    </div>
  );
}

function formatEvent(event: RunEvent): string {
  switch (event.type) {
    case "stdout":
    case "stderr":
      return event.line ?? "";
    case "started":
      return `▸ started (pid ${event.pid})`;
    case "queued":
      return "▸ queued";
    case "completed":
      return `✓ completed (exit ${event.exit_code})`;
    case "failed":
      return `✗ failed (exit ${event.exit_code ?? "—"})${event.detail ? ` ${event.detail}` : ""}`;
    case "cancelled":
      return `■ cancelled (exit ${event.exit_code})`;
    case "error":
      return `✗ ${event.detail ?? "error"}`;
    default:
      return JSON.stringify(event);
  }
}
