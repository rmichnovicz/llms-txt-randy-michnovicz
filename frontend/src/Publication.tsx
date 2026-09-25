import { useState } from "react";
import { api, date, type GuideCheck, type Project } from "./api";

type Props = {
  project: Project;
  blocked: boolean;
  action: (fn: () => Promise<unknown>, message?: string) => Promise<boolean>;
};

export default function Publication({ project, blocked, action }: Props) {
  const [verification, setVerification] = useState<
    | ({
        matches: boolean;
        version_id: string;
      } & GuideCheck)
    | null
  >(null);
  const path = `/api/projects/${project.id}`;
  const published = project.published_version_id;
  const current = published && published === project.draft?.id;
  const publicUrl = new URL(
    `${import.meta.env.VITE_API_BASE || ""}/api/published/${project.publication_id}/llms.txt`,
    window.location.origin,
  ).href;
  const siteUrl = new URL(project.site_url);
  const installUrl = `${siteUrl.origin}${project.guide_path}llms.txt`;
  const check = project.existing_guide_check;
  const needsReview =
    project.decisions.some((d) => d.active && d.needs_review) ||
    project.draft?.decisions_revision !== project.decisions_revision;

  return (
    <section
      className="publication"
      aria-label="Publishing and existing guides"
    >
      <details>
        <summary>
          Publish your guide{" "}
          <span>
            {published
              ? current
                ? "Published"
                : "Draft has changes"
              : "Private draft"}
          </span>
        </summary>
        <div className="publication-body">
          <p>
            Publishing makes this saved version available to anyone with its
            public URL. Future edits stay private until you publish again.
          </p>
          {published && (
            <>
              <p>
                Published {date(project.published_at || null)}.{" "}
                <a href={publicUrl} target="_blank" rel="noreferrer">
                  Open public llms.txt
                </a>
              </p>
              <div className="publication-actions">
                <button
                  onClick={() =>
                    action(
                      () => navigator.clipboard.writeText(publicUrl),
                      "Public file link copied.",
                    )
                  }
                >
                  Copy public URL
                </button>
                <button
                  disabled={blocked}
                  onClick={() =>
                    action(
                      () =>
                        api(path + "/publication", "POST", {
                          revision: project.revision,
                          version_id: null,
                        }),
                      "Guide unpublished. The public URL no longer serves a file.",
                    )
                  }
                >
                  Unpublish
                </button>
              </div>
            </>
          )}
          <button
            className="primary"
            disabled={blocked || !project.draft || !!current || needsReview}
            onClick={() =>
              action(
                () =>
                  api(path + "/publication", "POST", {
                    revision: project.revision,
                    version_id: project.draft?.id,
                  }),
                "Saved version published. Your private editor link stays private.",
              )
            }
          >
            {published ? "Publish updated draft" : "Publish saved draft"}
          </button>
          {project.draft && needsReview && (
            <p>
              Resolve flagged answers and bring the draft up to date with your
              decisions before publishing.
            </p>
          )}
          <h3>Install on your website</h3>
          <p>
            Download the published file and serve it as plain text at{" "}
            <a href={installUrl} target="_blank" rel="noreferrer">
              {installUrl}
            </a>
            . The hosted copy does not install it on your domain.
          </p>
          {published && (
            <>
              <a href={publicUrl + "?download=true"} download="llms.txt">
                Download published file
              </a>
              <div className="publication-actions">
                <button
                  disabled={blocked}
                  onClick={() =>
                    action(async () => {
                      setVerification(
                        await api(path + "/publication/verify", "POST"),
                      );
                    })
                  }
                >
                  Verify installation
                </button>
              </div>
            </>
          )}
          {published && verification?.version_id === published && (
            <p role="status">
              {verification.matches
                ? "Verified: your website serves the published text."
                : verification.guides.length
                  ? "The file on your website differs from this published version."
                  : "Could not verify a guide at the installation URL."}{" "}
              Checked {date(verification.checked_at)}. {verification.error}
            </p>
          )}
        </div>
      </details>
      <details>
        <summary>
          Existing website guide{" "}
          <span>
            {check?.guides.length
              ? `${check.guides.length} found`
              : check
                ? "Checked"
                : "Not checked yet"}
          </span>
        </summary>
        <div className="publication-body">
          <p>
            Check this guide’s path and its parent paths for an existing
            llms.txt. Compare it with your draft before deciding what to
            publish.
          </p>
          <button
            disabled={blocked}
            onClick={() => action(() => api(path + "/existing-guide", "POST"))}
          >
            {check ? "Check again" : "Find existing guide"}
          </button>
          {check && (
            <>
              <p>
                Checked {date(check.checked_at)}. {check.error}
              </p>
              {!check.guides.length && (
                <p>
                  {check.complete
                    ? "No usable Markdown guide found at the checked paths."
                    : "The check could not finish. Try again."}
                </p>
              )}
              {check.guides.map((guide) => (
                <details key={guide.requested_url}>
                  <summary>
                    Compare {new URL(guide.requested_url).pathname}
                  </summary>
                  <p>
                    <a href={guide.url} target="_blank" rel="noreferrer">
                      View source file
                    </a>
                    . This is a captured copy; its contents have not been
                    verified against your website.
                  </p>
                  <div className="guide-comparison">
                    <div>
                      <h3>Existing file</h3>
                      <pre tabIndex={0} aria-label="Existing guide text">
                        {guide.markdown}
                      </pre>
                    </div>
                    <div>
                      <h3>Current saved draft</h3>
                      <pre tabIndex={0} aria-label="Draft comparison text">
                        {project.draft?.markdown ||
                          "Your draft will appear when ready."}
                      </pre>
                    </div>
                  </div>
                </details>
              ))}
              <details>
                <summary>Checked URLs</summary>
                <ul>
                  {check.checks.map((c) => (
                    <li key={c.url}>
                      {c.url}: {c.status}
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </div>
      </details>
    </section>
  );
}
