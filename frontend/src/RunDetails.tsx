import { X } from "lucide-react";
import type { Project } from "./api";
import Modal from "./Modal";

export default function RunDetails({
  project,
  onClose,
}: {
  project: Project;
  onClose: () => void;
}) {
  return (
    <Modal label="run-details-title" onClose={onClose} className="run-details">
      <header className="run-details-header">
        <div>
          <h2 id="run-details-title">Run details</h2>
          <p>How Brief explored your site and built this guide.</p>
        </div>
        <button
          className="modal-close"
          aria-label="Close run details"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </header>
      <div className="run-details-body">
        <dl className="run-context">
          <div>
            <dt>Website</dt>
            <dd>{project.site_url}</dd>
          </div>
          <div>
            <dt>Purpose</dt>
            <dd>
              {project.guide_purpose || "Create an overview of the website."}
            </dd>
          </div>
        </dl>
        <section className="run-section" aria-labelledby="run-snapshot-title">
          <h3 id="run-snapshot-title">Latest source snapshot</h3>
          <dl className="run-stats">
            <div>
              <dt>Pages read</dt>
              <dd>{project.snapshot?.coverage.fresh_sources ?? "—"}</dd>
            </div>
            <div>
              <dt>Discovered</dt>
              <dd>{project.snapshot?.coverage.discovered ?? "—"}</dd>
            </div>
            <div>
              <dt>Unread</dt>
              <dd>{project.snapshot?.coverage.unread ?? "—"}</dd>
            </div>
          </dl>
          <p>
            Brief reads selected pages, so this may not cover your entire site.
          </p>
          {project.snapshot ? (
            <>
              <dl className="run-metadata">
                <div>
                  <dt>Crawl result</dt>
                  <dd>
                    {project.snapshot.coverage.stop_reason?.replaceAll(
                      "_",
                      " ",
                    ) || "Not recorded"}
                  </dd>
                </div>
                <div>
                  <dt>Duration</dt>
                  <dd>
                    {(
                      (project.snapshot.coverage.duration_ms || 0) / 1000
                    ).toFixed(1)}{" "}
                    s
                  </dd>
                </div>
                <div>
                  <dt>Downloaded</dt>
                  <dd>
                    {(
                      (project.snapshot.coverage.downloaded_bytes || 0) /
                      1_000_000
                    ).toFixed(2)}{" "}
                    MB
                  </dd>
                </div>
              </dl>
              <p className="run-cache-note">
                {project.snapshot.coverage.cache_hits || 0} pages reused after
                HTTP validation from{" "}
                {project.snapshot.coverage.conditional_requests || 0}{" "}
                conditional requests.
              </p>
            </>
          ) : (
            <p>No crawl result yet.</p>
          )}
        </section>
        <section className="run-section" aria-labelledby="run-selection-title">
          <h3 id="run-selection-title">Page selection</h3>
          <p>
            {project.snapshot?.coverage.assessment?.reused
              ? "Reused the saved page selection and checked those pages for changes. No new planning call was needed."
              : "URL rules prioritize entry pages. One model assessment then selects additional discovered URLs."}
          </p>
          <p>
            {project.snapshot?.coverage.assessment?.reason ||
              "No model assessment recorded for this snapshot."}
          </p>
        </section>
        <section
          className="run-section run-diagnostics"
          aria-labelledby="run-diagnostics-title"
        >
          <h3 id="run-diagnostics-title">Technical details</h3>
          {project.snapshot?.coverage.sitemap_discovery && (
            <details>
              <summary>Sitemap discovery</summary>
              <p>
                {project.snapshot.coverage.sitemap_discovery.fetches} sitemap
                requests ·{" "}
                {(
                  project.snapshot.coverage.sitemap_discovery.bytes / 1_000_000
                ).toFixed(2)}{" "}
                MB · {project.snapshot.coverage.sitemap_discovery.stop_reason}
              </p>
              <p>
                {(
                  (project.snapshot.coverage.sitemap_discovery
                    .inventory_bytes || 0) / 1_000_000
                ).toFixed(2)}{" "}
                MB URL inventory ·{" "}
                {project.snapshot.coverage.sitemap_discovery.resumed_urls || 0}{" "}
                saved URLs resumed ·{" "}
                {project.snapshot.coverage.sitemap_discovery.remaining_indexes}{" "}
                sitemap files pending
              </p>
              <pre tabIndex={0} aria-label="Sitemap discovery trace">
                {JSON.stringify(
                  project.snapshot.coverage.sitemap_discovery,
                  null,
                  2,
                )}
              </pre>
            </details>
          )}
          <details>
            <summary>Selected and skipped URLs</summary>
            <pre tabIndex={0} aria-label="Selection details">
              {JSON.stringify(
                {
                  selected: project.snapshot?.coverage.assessment?.urls,
                  skipped: project.snapshot?.coverage.assessment?.skipped_urls,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <details>
            <summary>Fetch results</summary>
            <pre tabIndex={0} aria-label="Fetch results">
              {JSON.stringify(project.snapshot?.coverage.trace || [], null, 2)}
            </pre>
          </details>
          <details>
            <summary>Model usage and settings</summary>
            <pre tabIndex={0} aria-label="Model metadata">
              {JSON.stringify(
                {
                  planning: project.snapshot?.coverage.assessment?.metadata,
                  document: (project.proposal || project.draft)?.model_metadata,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <details>
            <summary>Recent jobs</summary>
            <pre tabIndex={0} aria-label="Recent jobs">
              {JSON.stringify(
                project.jobs.map((j) => ({
                  kind: j.kind,
                  status: j.status,
                  error: j.error,
                  progress: j.progress,
                })),
                null,
                2,
              )}
            </pre>
          </details>
        </section>
      </div>
    </Modal>
  );
}
