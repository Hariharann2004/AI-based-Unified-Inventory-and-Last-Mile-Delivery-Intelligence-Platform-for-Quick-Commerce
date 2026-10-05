import { downloadReport } from "../api/client.js";
import { useTask } from "../hooks/useRemote.js";

export function ExportButtons({ path, filename }) {
  const task = useTask();
  return (
    <div className="surface">
      <h3>Download guide-review evidence</h3>
      <div className="toolbar">
        <button
          disabled={task.busy}
          onClick={() => task.run(() => downloadReport(path, "json", filename))}
        >
          Download JSON
        </button>
        <button
          disabled={task.busy}
          onClick={() => task.run(() => downloadReport(path, "html", filename))}
        >
          Download printable HTML
        </button>
      </div>
      <p className="muted">
        Includes all test windows, charts, complete metrics, source details and limitations. Open
        HTML in your browser to print or save as PDF. This is evidence, not the final project
        document.
      </p>
      {task.error && (
        <p className="error" role="alert">
          {task.error}
        </p>
      )}
    </div>
  );
}
