import { useState } from "react";
import type { Project, Version } from "./api";

export default function VersionReview({
  project,
  version,
}: {
  project: Project;
  version: Version;
}) {
  const proposal = version.id === project.proposal?.id;
  const refinement = proposal ? undefined : version.refinement;
  const [view, setView] = useState(
    proposal || refinement ? "changes" : "documents",
  );
  const lines = ((refinement ? refinement.diff : project.proposal_diff) || "")
    .split("\n")
    .filter((line) => !line.startsWith("---") && !line.startsWith("+++"));
  const additions = lines.filter((line) => line.startsWith("+")).length;
  const removals = lines.filter((line) => line.startsWith("-")).length;
  const changes = project.change_inbox || [];
  const unresolved = project.decisions.filter(
    (d) => d.active && d.needs_review,
  ).length;
  return (
    <div className="review-body">
      <p className="review-intro">
        {proposal
          ? "Review the suggested edits to your saved draft. Nothing changes until you use this version."
          : refinement
            ? "These changes are already saved in this version. Compare it with the draft it replaced."
            : "Compare this saved version with your current draft before restoring it."}
      </p>
      {(proposal || refinement) && (
        <>
          <div
            className="review-summary"
            role="group"
            aria-label="Change summary"
          >
            <strong>
              {additions + removals
                ? `${additions} added ${additions === 1 ? "line" : "lines"}, ${removals} removed`
                : "No document wording changes"}
            </strong>
            {proposal && (
              <span>
                {changes.length}{" "}
                {changes.length === 1
                  ? "source page differs"
                  : "source pages differ"}{" "}
                from your draft’s evidence
              </span>
            )}
          </div>
          {version.structured_result?.explanation && (
            <p className="review-rationale">
              <strong>
                {refinement ? "About this refinement" : "Why this update"}
              </strong>
              {version.structured_result.explanation}
            </p>
          )}
          {refinement && refinement.directions.length > 0 && (
            <details className="review-evidence" open>
              <summary>
                Directions behind this refinement (
                {refinement.directions.length})
              </summary>
              <ul>
                {refinement.directions.map((direction, i) => (
                  <li key={i}>
                    <span className="review-change-kind">
                      {direction.kind === "added"
                        ? "Added"
                        : direction.kind === "removed"
                          ? "Removed"
                          : "Updated"}
                    </span>
                    <span>
                      {direction.before && <del>{direction.before}</del>}
                      {direction.before && direction.after && <br />}
                      {direction.after}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {proposal && changes.length > 0 && (
            <details className="review-evidence">
              <summary>
                Website evidence behind this update ({changes.length})
              </summary>
              <p>Newly read pages may already have existed on your website.</p>
              <ul>
                {changes.map((change) => (
                  <li key={change.id}>
                    <span className="review-change-kind">
                      {change.kind === "added"
                        ? "Newly read"
                        : change.kind === "removed"
                          ? "Removed from evidence"
                          : "Content changed"}
                    </span>
                    <a href={change.url} target="_blank" rel="noreferrer">
                      {change.title || change.url}
                    </a>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {proposal && unresolved > 0 && (
            <p className="review-blocker" role="status">
              Resolve {unresolved} flagged{" "}
              {unresolved === 1 ? "answer" : "answers"} in the Change inbox
              before using this proposal. Close this comparison to review them.
            </p>
          )}
          <div
            className="review-view-switch"
            role="group"
            aria-label="Comparison view"
          >
            <button
              aria-pressed={view === "changes"}
              onClick={() => setView("changes")}
            >
              Changes only
            </button>
            <button
              aria-pressed={view === "documents"}
              onClick={() => setView("documents")}
            >
              Full documents
            </button>
          </div>
        </>
      )}
      {view === "changes" ? (
        <section
          className="review-diff"
          aria-label={
            refinement ? "Refinement document diff" : "Proposed document diff"
          }
          tabIndex={0}
        >
          <div className="review-diff-legend">
            <span>
              {refinement ? "+ Added in this version" : "+ Added to your draft"}
            </span>
            <span>
              {refinement
                ? "− Removed in this version"
                : "− Removed from your draft"}
            </span>
          </div>
          {!additions && !removals ? (
            <p className="review-empty">
              Your document’s wording is unchanged.
            </p>
          ) : (
            lines.map((line, i) =>
              line.startsWith("@@") ? (
                <div className="review-diff-break" key={i}>
                  Changed passage
                </div>
              ) : (
                <div
                  className={`review-diff-line ${line.startsWith("+") ? "is-added" : line.startsWith("-") ? "is-removed" : "is-context"}`}
                  key={i}
                >
                  <span
                    className="review-diff-sign"
                    role="img"
                    aria-label={
                      line.startsWith("+")
                        ? "Added"
                        : line.startsWith("-")
                          ? "Removed"
                          : "Unchanged"
                    }
                  >
                    {line[0] || " "}
                  </span>
                  <code>{line.slice(1) || " "}</code>
                </div>
              ),
            )
          )}
        </section>
      ) : (
        <div className="compare-columns">
          <div>
            <h3>{refinement ? "Before refinement" : "Current draft"}</h3>
            <pre
              tabIndex={0}
              aria-label={
                refinement ? "Before refinement text" : "Current draft text"
              }
            >
              {refinement
                ? refinement.before_markdown
                : project.draft?.markdown}
            </pre>
          </div>
          <div>
            <h3>
              {proposal
                ? "Proposed update"
                : refinement
                  ? "After refinement"
                  : "Selected version"}
            </h3>
            <pre tabIndex={0} aria-label="Selected version text">
              {version.markdown}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
