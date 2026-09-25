import { useEffect, useState } from "react";
import { FlaskConical, ChevronDown } from "lucide-react";
import { api, date, type Project } from "./api";

export type ReaderResult = {
  question: string;
  expected_url: string | null;
  reference_quote: string | null;
  answer: string;
  outcome: string;
  expected_reached: boolean | null;
  expected_cited: boolean | null;
  reason: string;
  citations: { url: string; quote: string; verified: boolean }[];
  trace: {
    step: number;
    action: string;
    url: string | null;
    result?: string;
  }[];
};
export type TestRun = {
  id: string;
  suite_id: string;
  version_id: string;
  reader_model: string;
  created_at: string;
  version_created_at: string;
  evidence_frozen_at: string;
  status: string;
  error: string | null;
  progress?: { message?: string };
  questions: { question: string; expected_url: string | null }[];
  report: {
    results: ReaderResult[];
    limitations: string;
    guide_sha256: string;
  } | null;
};
const outcomeLabel = (value: string) =>
  ({
    evidence_matched: "Expected source cited",
    citations_verified: "Quotes verified",
    needs_review: "Needs review",
    abstained: "Could not answer",
  })[value] || value;
const short = (id: string) => id.slice(0, 8);
function SafeLink({ url }: { url: string }) {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol))
      return <span>{url}</span>;
  } catch {
    return <span>{url}</span>;
  }
  return (
    <a href={url} target="_blank" rel="noreferrer">
      {url}
    </a>
  );
}

export default function GuideTests({
  project,
  proposalRequest = 0,
  blocked,
  dirty,
  action,
}: {
  project: Project;
  proposalRequest?: number;
  blocked: boolean;
  dirty: boolean;
  action: (fn: () => Promise<unknown>, message?: string) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [target, setTarget] = useState("draft");
  useEffect(() => {
    if (proposalRequest) {
      setOpen(true);
      setTarget("proposal");
    }
  }, [proposalRequest]);
  const [selected, setSelected] = useState("");
  const runs = project.test_runs || [];
  const current = runs.find((r) => r.id === selected) || runs[0];
  const effectiveTarget =
    target === "proposal" && project.proposal ? "proposal" : "draft";
  const version =
    effectiveTarget === "proposal" ? project.proposal : project.draft;
  const previous =
    current &&
    runs.find(
      (r) =>
        r.id !== current.id &&
        r.suite_id === current.suite_id &&
        r.report &&
        r.reader_model === current.reader_model &&
        new Date(r.created_at) < new Date(current.created_at),
    );
  const active = runs.find((r) => ["pending", "running"].includes(r.status));
  async function start(suite?: string, custom?: string) {
    if (!version) return;
    const ok = await action(async () => {
      const result = await api<{ id: string }>(
        `/api/projects/${project.id}/tests`,
        "POST",
        {
          version_id: version.id,
          suite_id: suite || null,
          questions: custom ? [custom] : [],
        },
      );
      setSelected(result.id);
    });
    if (ok && custom) setQuestion("");
  }
  return (
    <section id="guide-tests" className="guide-tests" aria-label="Guide tests">
      <button
        className="test-toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <FlaskConical size={18} />
        <span>Test this guide</span>
        <ChevronDown size={16} />
        {active && <span className="test-state">Running</span>}
      </button>
      {open && (
        <div className="test-content">
          <h3>Can a reader find the answer?</h3>
          <p>
            An AI reader uses your guide to find answers in saved copies of
            your pages. It quotes the pages it reads. Rerun the same questions
            to compare guide versions using the same source material.
          </p>
          {dirty && (
            <p className="test-warning">
              Save your document changes before testing.
            </p>
          )}
          <label htmlFor="test-version">Version to test</label>
          <select
            id="test-version"
            value={effectiveTarget}
            onChange={(e) => setTarget(e.target.value)}
            disabled={blocked}
          >
            <option value="draft">
              Saved draft
              {project.draft ? ` · ${short(project.draft.id)}` : " · not ready"}
            </option>
            {project.proposal && (
              <option value="proposal">
                Proposed update · {short(project.proposal.id)}
              </option>
            )}
          </select>
          <button
            className="primary"
            disabled={blocked || !version}
            onClick={() => void start()}
          >
            Run suggested tests
          </button>
          <p className="test-hint">
            Creates up to three questions from your source pages, then checks
            whether an AI reader can answer them using your guide.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void start(undefined, question.trim());
            }}
          >
            <label htmlFor="reader-question">Or test a customer question</label>
            <textarea
              id="reader-question"
              maxLength={500}
              minLength={8}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Can I accept recurring payments on the free plan?"
            />
            <button
              disabled={blocked || !version || question.trim().length < 8}
            >
              Test my question
            </button>
          </form>
          {!!runs.length && (
            <>
              <label htmlFor="test-run">Saved test runs</label>
              <select
                id="test-run"
                value={current?.id || ""}
                onChange={(e) => setSelected(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {date(r.created_at)} · {short(r.version_id)} · {r.status}
                  </option>
                ))}
              </select>
            </>
          )}
          {current && (
            <article className="test-report" aria-label="Reader test results">
              <p>
                <strong>Version {short(current.version_id)}</strong> · Sources
                saved {date(current.evidence_frozen_at)}
                <br />
                Reader: {current.reader_model}
              </p>
              {version && current.version_id !== version.id && (
                <p className="test-warning">
                  These results belong to a different version. Rerun the same
                  questions to compare.
                </p>
              )}
              {["pending", "running"].includes(current.status) && (
                <p role="status">
                  {current.progress?.message || "Reader test queued…"}
                </p>
              )}
              {current.status === "failed" && (
                <p role="alert">
                  {current.error || "The reader test could not finish."}
                </p>
              )}
              {current.status === "superseded" && (
                <p>
                  The test was interrupted by a workspace change. Run it again
                  when ready.
                </p>
              )}
              {current.questions.length > 0 && (
                <button
                  disabled={blocked || !version}
                  onClick={() => void start(current.suite_id)}
                >
                  Rerun same questions
                </button>
              )}
              {current.status === "failed" && !current.questions.length && (
                <button
                  disabled={blocked || !version}
                  onClick={() => void start()}
                >
                  Retry suggested tests
                </button>
              )}
              {current.report && (
                <>
                  <p className="test-hint">{current.report.limitations}</p>
                  {previous && (
                    <p className="test-comparison">
                      Comparing with version {short(previous.version_id)} using
                      the same questions, evidence, and reader model. Individual
                      runs can vary.
                    </p>
                  )}
                  {current.report.results.map((result, index) => {
                    const before = previous?.report?.results[index];
                    return (
                      <details
                        className="test-result"
                        key={index}
                        open={
                          current.report!.results.length === 1
                            ? true
                            : undefined
                        }
                      >
                        <summary>
                          <strong>{result.question}</strong>
                          <span className={`test-outcome ${result.outcome}`}>
                            {outcomeLabel(result.outcome)}
                          </span>
                        </summary>
                        {before && (
                          <p>
                            Previous: {outcomeLabel(before.outcome)} → Now:{" "}
                            {outcomeLabel(result.outcome)}
                          </p>
                        )}
                        <p className="reader-answer">
                          {result.answer || "No answer returned."}
                        </p>
                        <p>{result.reason}</p>
                        {result.expected_url && (
                          <p>
                            Expected source:{" "}
                            <SafeLink url={result.expected_url} />
                            <br />
                            {result.expected_reached
                              ? "Reader reached this page."
                              : "Reader did not reach this page."}
                          </p>
                        )}
                        {result.reference_quote && (
                          <details>
                            <summary>
                              Source passage for this question
                            </summary>
                            <blockquote>{result.reference_quote}</blockquote>
                          </details>
                        )}
                        {result.citations.map((citation, i) => (
                          <div className="test-citation" key={i}>
                            <SafeLink url={citation.url} />
                            <blockquote>{citation.quote}</blockquote>
                            <span>
                              {citation.verified
                                ? "Quote verified in an opened page"
                                : "Quote could not be verified"}
                            </span>
                          </div>
                        ))}
                        <details>
                          <summary>Pages and steps</summary>
                          <ol>
                            {result.trace.map((step) => (
                              <li key={step.step}>
                                <strong>{step.action}</strong>
                                {step.url && (
                                  <>
                                    {" "}
                                    · <SafeLink url={step.url} />
                                  </>
                                )}
                                <p>{step.result}</p>
                              </li>
                            ))}
                          </ol>
                        </details>
                      </details>
                    );
                  })}
                </>
              )}
            </article>
          )}
        </div>
      )}
    </section>
  );
}
