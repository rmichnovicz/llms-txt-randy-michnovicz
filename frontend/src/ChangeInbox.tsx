import { useState, type ReactNode } from "react";
import { date } from "./api";
import type { Project, Source } from "./api";
export type SourceChange = {
  id: string;
  url: string;
  title: string;
  kind: string;
  before: Source | null;
  after: Source | null;
  sections: string[];
  decision_ids: string[];
  diff: string;
};
export default function ChangeInbox({
  project,
  children,
  onCompare,
  onTest,
  blocked,
}: {
  project: Project;
  children: ReactNode;
  onCompare: () => void;
  onTest: () => void;
  blocked: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const changes = project.change_inbox || [];
  const visible = changes.filter(
    (c) =>
      filter === "all" ||
      (filter === "answers" ? c.decision_ids.length > 0 : c.kind === filter),
  );
  const reviews = project.decisions.filter((d) => d.active && d.needs_review);
  const ready =
    project.proposal &&
    project.proposal.decisions_revision === project.decisions_revision;
  if (!project.draft) return null;
  if (!changes.length && !reviews.length)
    return (
      <section className="change-inbox quiet-inbox" aria-label="Change inbox">
        <h2>
          Change inbox <span>No pending changes</span>
        </h2>
        <p>
          No source changes to review against the latest captured evidence. Last
          website check: {date(project.last_checked_at)}.
        </p>
      </section>
    );
  return (
    <section className="change-inbox" aria-label="Change inbox">
      <h2>Change inbox</h2>
      <p>
        {changes.length} source changes since this draft · {reviews.length}{" "}
        saved answers to review.
      </p>
      <p>
        “Removed” means a page left the captured evidence, not necessarily the
        website. “Added” means Brief read the page for the first time; it may
        already have been on your site. Review the changes and any flagged
        answers before accepting an update. Your current draft stays as it is.
      </p>
      {project.draft?.manually_edited && (
        <p>
          Section names come from the generated draft and may differ from your
          manual edits.
        </p>
      )}
      <p>Last website check: {date(project.last_checked_at)}.</p>
      <div className="inbox-filters" aria-label="Filter source changes">
        {(
          [
            ["all", "All"],
            ["added", "Added"],
            ["modified", "Modified"],
            ["removed", "Removed"],
            ["answers", "Flagged answers"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            aria-pressed={filter === value}
            onClick={() => setFilter(value)}
          >
            {label} (
            {value === "all"
              ? changes.length
              : changes.filter((c) =>
                  value === "answers"
                    ? c.decision_ids.length > 0
                    : c.kind === value,
                ).length}
            )
          </button>
        ))}
      </div>
      {!visible.length && <p>No source changes match this filter.</p>}
      {visible.map((c) => (
        <details key={c.id} className="source-change">
          <summary>
            {c.title} <span>{c.kind}</span>
          </summary>
          <a href={c.url} target="_blank" rel="noreferrer">
            {c.url}
          </a>
          <p>
            {c.sections.length
              ? `Linked from: ${c.sections.join(", ")}.`
              : "No section in the saved draft links to this page."}{" "}
            A link here doesn’t confirm which statements rely on this page.
          </p>
          <p>
            {c.decision_ids.length
              ? `${c.decision_ids.length} saved answer(s) refer to this page. Review them below.`
              : "No saved answer is flagged for this page."}
          </p>
          <p>
            <strong>Recommendation:</strong>{" "}
            {c.decision_ids.length
              ? "Check whether your answer still applies to the updated page."
              : c.kind === "added"
                ? "Check whether this page should be linked in your guide."
                : c.kind === "removed"
                  ? "Check the proposed update for outdated links or information."
                  : "Review the changes to sections that link to this page."}
          </p>
          <pre tabIndex={0} aria-label={`Source diff: ${c.title}`}>
            {c.diff}
          </pre>
        </details>
      ))}
      {children}
      <div className="inbox-actions">
        <button disabled={blocked || !ready} onClick={onCompare}>
          Inspect proposed edit
        </button>
        <button disabled={blocked || !ready} onClick={onTest}>
          Test proposed update
        </button>
      </div>
      {!ready && <p>The proposed update will appear when it’s ready.</p>}
      {reviews.length > 0 && (
        <p>Resolve flagged answers before accepting the proposal.</p>
      )}
    </section>
  );
}
