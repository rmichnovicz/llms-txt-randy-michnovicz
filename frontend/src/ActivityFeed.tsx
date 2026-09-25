import { useEffect, useState } from "react";
import type { Progress } from "./api";

export default function ActivityFeed({
  progress,
  kind,
  connected,
}: {
  progress?: Progress;
  kind: string;
  connected: boolean;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const elapsed = progress?.started_at
    ? Math.max(0, Math.floor((now - Date.parse(progress.started_at)) / 1000))
    : null;
  return (
    <section className="activity-feed" aria-label="Live activity">
      <div className="activity-heading">
        <strong>
          {kind === "generate" ? "Writing your guide" : "Reading your website"}
        </strong>
        {elapsed !== null && <span>{elapsed}s elapsed</span>}
      </div>
      <p aria-live="polite" aria-atomic="true">
        {progress?.message || "Queued. Starting soon…"}
      </p>
      {progress?.url && <p className="activity-url">{progress.url}</p>}
      {progress?.pages_read !== undefined && (
        <p>
          {progress.pages_read} readable pages
          {progress.pages_found !== undefined
            ? ` · ${progress.pages_found} links discovered`
            : ""}
        </p>
      )}
      {kind === "generate" && (
        <p className="activity-hint">
          Brief is choosing links and applying your saved decisions. Your draft
          will appear when it’s ready.
        </p>
      )}
      {!!progress?.recent?.length && (
        <details>
          <summary>Recent activity</summary>
          <ol>
            {progress.recent.map((item, index) => (
              <li key={index}>{item.message}</li>
            ))}
          </ol>
        </details>
      )}
      {!connected && (
        <p className="activity-hint">
          Connecting live updates. We’ll also check for completion
          automatically.
        </p>
      )}
    </section>
  );
}
