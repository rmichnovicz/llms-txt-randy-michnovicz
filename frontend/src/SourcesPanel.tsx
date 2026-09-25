import { FileText } from "lucide-react";
import type { Project } from "./api";

export default function SourcesPanel({ project }: { project: Project }) {
  return (
    <>
      <div className="panel-intro">
        <h2>Read from your website</h2>
        <p>
          {project.snapshot?.sources.length || 0} sources available.{" "}
          {project.snapshot?.coverage.stop_reason === "coverage_plan_finished"
            ? "Finished reading the selected pages. Other pages on your site may not have been read."
            : project.snapshot?.coverage.stop_reason === "time_budget"
              ? "Reached the time limit. Some pages haven’t been checked."
              : project.snapshot?.coverage.stop_reason === "download_budget"
                ? "Reached the download limit. Some pages haven’t been checked."
                : project.snapshot?.coverage.stop_reason === "text_budget"
                  ? "Reached the text limit. Some pages haven’t been checked."
                  : project.snapshot?.coverage.truncated
                    ? "Some pages were found but haven’t been read."
                    : ""}
        </p>
      </div>
      {project.snapshot?.coverage.assessment && (
        <div className="panel-intro">
          <p>{project.snapshot.coverage.assessment.reason}</p>
          {!!project.snapshot.coverage.assessment.gaps.length && (
            <details>
              <summary>Topics flagged during planning</summary>
              <p>
                Brief looked for pages on these topics. Some may still be
                missing from the sources.
              </p>
              <ul>
                {project.snapshot.coverage.assessment.gaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
      {project.snapshot?.sources.map((s) => (
        <a
          className="source"
          key={s.id}
          href={s.url}
          target="_blank"
          rel="noreferrer"
        >
          <FileText size={16} />
          <div>
            <strong>{s.title}</strong>
            <small>{new URL(s.url).pathname}</small>
          </div>
        </a>
      ))}
      {project.snapshot?.warnings.length ? (
        <details className="warnings">
          <summary>{project.snapshot.warnings.length} crawl notes</summary>
          {project.snapshot.warnings.map((w, i) => (
            <p key={i}>
              {w.url}: {w.reason}
            </p>
          ))}
        </details>
      ) : null}
    </>
  );
}

export function SourceCoverageSummary({
  snapshot,
  onInspect,
}: {
  snapshot: NonNullable<Project["snapshot"]>;
  onInspect: () => void;
}) {
  return (
    <section className="coverage-summary" aria-label="Latest crawl coverage">
      <p>
        <strong>Latest crawl:</strong> {snapshot.sources.length} sources
        available
        {snapshot.coverage.unread !== undefined &&
          ` · ${snapshot.coverage.unread} discovered pages unread`}
        . Brief reads selected pages; this does not establish full website
        coverage.
      </p>
      <button onClick={onInspect}>Inspect coverage</button>
    </section>
  );
}
