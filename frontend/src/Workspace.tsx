import type { Progress } from "./api";
import GuideTests from "./GuideTests";
import ChangeInbox from "./ChangeInbox";
import VersionReview from "./VersionReview";
import Publication from "./Publication";
import { rememberSession, savedSessions, siteDocumentUrl } from "./sessions";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import {
  ArrowUp,
  Check,
  ChevronDown,
  Copy,
  Download,
  FileText,
  Globe,
  History,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { api, date, type Decision, type Project, type Version } from "./api";

import Logo from "./Logo";
import Modal from "./Modal";
import RunDetails from "./RunDetails";
import SourcesPanel, { SourceCoverageSummary } from "./SourcesPanel";
import QuestionCard from "./QuestionCard";
import ActivityFeed from "./ActivityFeed";
import { errorText } from "./errors";

export default function Workspace({
  siteId,
  doc,
  navigate,
  canonicalize,
  canLeave,
}: {
  siteId: string;
  doc: string | null;
  navigate: (url: string) => void;
  canonicalize: (url: string) => void;
  canLeave: { current: () => boolean };
}) {
  const [project, setProject] = useState<Project | null>(null);
  const id = project?.id || siteId;
  const path = `/api/projects/${id}`;
  const siteApi = `/api/projects/${siteId}`;
  const documentApi =
    siteApi +
    "/document" +
    (doc === null ? "" : `?doc=${encodeURIComponent(doc)}`);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acting, setActing] = useState(false);
  const [tab, setTab] = useState<"guide" | "decisions" | "sources">("guide");
  const [view, setView] = useState<"preview" | "edit" | "history">("preview");
  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  useEffect(() => {
    canLeave.current = () =>
      !dirtyRef.current ||
      window.confirm("Discard your unsaved document changes?");
    return () => {
      canLeave.current = () => true;
    };
  }, [canLeave]);
  const loadedDraft = useRef("");
  const editRevision = useRef(0);
  const [direction, setDirection] = useState("");
  const [kind, setKind] = useState<"preference" | "fact">("preference");
  const [editing, setEditing] = useState<Decision | null>(null);
  const [testProposal, setTestProposal] = useState(0);
  const [review, setReview] = useState<Version | null>(null);
  const [restoreText, setRestoreText] = useState("");
  const [answer, setAnswer] = useState("");
  const [showRun, setShowRun] = useState(false);
  const [guideForm, setGuideForm] = useState({
    path: "/help/",
    name: "Help center",
    purpose: "Help readers use this part of the site.",
  });
  const [showStructure, setShowStructure] = useState(false);
  const [hideSuggestions, setHideSuggestions] = useState(false);
  const [liveProgress, setLiveProgress] = useState<{
    id: string;
    progress: Progress;
  } | null>(null);
  const [streamConnected, setStreamConnected] = useState(false);
  const [showRemoval, setShowRemoval] = useState<Decision | null>(null);
  const loadSequence = useRef(0);
  const rememberedVisit = useRef(false);
  async function load() {
    const sequence = ++loadSequence.current;
    const next = await api<Project>(documentApi);
    if (sequence !== loadSequence.current) return;
    setProject(next);
    if (
      !rememberedVisit.current ||
      savedSessions().some((s) => s.id === next.id)
    ) {
      rememberSession(next, undefined, !rememberedVisit.current);
    }
    rememberedVisit.current = true;
    if (next.draft?.id !== loadedDraft.current && !dirtyRef.current) {
      setText(next.draft?.markdown || "");
      loadedDraft.current = next.draft?.id || "";
      editRevision.current = next.revision;
    }
    return next;
  }
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let stream: EventSource | undefined;
    let version = "";
    async function init() {
      try {
        const token =
          new URLSearchParams(window.location.hash.slice(1)).get("key") ||
          savedSessions().find(
            (s) => (s.siteId === siteId || s.id === siteId) && s.token,
          )?.token;
        if (token) {
          await api(siteApi + "/session", "POST", { token });
        }
        const next = await poll();
        if (!active || !next) return;
        if (next) {
          canonicalize(siteDocumentUrl(next.site_id, next.guide_path));
          // Recover cookie-only visits too, so saved sessions survive cookie expiry.
          const access =
            token ||
            (await api<{ token: string }>(siteApi + "/access-token")).token;
          rememberSession(next, access);
        }
        if (!active) return;
        stream = new EventSource(
          (import.meta.env.VITE_API_BASE || "") +
            `/api/projects/${next.id}/events`,
          { withCredentials: true },
        );
        stream.onopen = () => {
          if (active) setStreamConnected(true);
        };
        stream.onerror = () => {
          if (active) setStreamConnected(false);
        };
        stream.onmessage = (event) => {
          if (!active) return;
          try {
            const data = JSON.parse(event.data);
            if (data.job)
              setLiveProgress({ id: data.job.id, progress: data.job.progress });
            const nextVersion = JSON.stringify(data.version);
            if (nextVersion !== version) {
              version = nextVersion;
              void load().catch((e) => {
                if (active) setError(errorText(e));
              });
            }
          } catch {
            setStreamConnected(false);
          }
        };
      } catch (e) {
        if (active) setError(errorText(e));
      }
    }
    async function poll() {
      try {
        if (active && stream?.readyState !== EventSource.OPEN)
          return await load();
      } catch (e) {
        if (active) setError(errorText(e));
      } finally {
        if (active) timer = setTimeout(poll, 15000);
      }
    }
    void init();
    return () => {
      active = false;
      loadSequence.current++;
      clearTimeout(timer);
      stream?.close();
    };
  }, [siteId, doc]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  const running = project?.jobs.find(
    (j) =>
      j.kind !== "evaluate" &&
      (j.status === "pending" || j.status === "running"),
  );
  const blocked =
    acting ||
    !!project?.jobs.some(
      (j) => j.status === "pending" || j.status === "running",
    ) ||
    dirty;
  const question = project?.questions.find((q) => q.status === "pending");
  const activeDecisions = project?.decisions.filter((d) => d.active) || [];
  const latestJob = project?.jobs.find((j) => j.kind !== "evaluate");
  const failed = latestJob?.status === "failed";
  async function action(fn: () => Promise<unknown>, message = "") {
    setActing(true);
    setError("");
    try {
      await fn();
      await load();
      setNotice(message);
      return true;
    } catch (e) {
      setError(errorText(e));
      await load().catch(() => {});
      return false;
    } finally {
      setActing(false);
    }
  }
  async function decide(
    statement: string,
    decision?: Decision,
    active = true,
    questionId?: string,
  ) {
    if (!project) return;
    const ok = await action(
      () =>
        api(
          path + "/decisions" + (decision ? "/" + decision.id : ""),
          decision ? "PATCH" : "POST",
          {
            revision: project.revision,
            statement,
            kind: decision?.kind || kind,
            active,
            question_id: questionId || null,
          },
        ),
      "Direction saved. Preparing an updated document.",
    );
    if (ok) {
      setDirection("");
      setEditing(null);
      setAnswer("");
      setShowRemoval(null);
    }
  }
  async function save() {
    if (!project) return;
    await action(async () => {
      await api(path + "/versions", "POST", {
        revision: editRevision.current,
        markdown: text,
      });
      dirtyRef.current = false;
      setDirty(false);
    }, "Changes saved as a new version.");
  }
  async function copyLink() {
    await action(async () => {
      const { token } = await api<{ token: string }>(path + "/access-token");
      await navigator.clipboard.writeText(
        `${window.location.origin}${siteDocumentUrl(siteId, project?.guide_path)}#key=${encodeURIComponent(token)}`,
      );
    }, "Private access link copied. Keep it somewhere safe.");
  }
  function download() {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "llms.txt";
    a.click();
    URL.revokeObjectURL(url);
  }
  function beginEdit() {
    if (!project) return;
    editRevision.current = project.revision;
    setView("edit");
  }
  function discard() {
    dirtyRef.current = false;
    setDirty(false);
    setText(project?.draft?.markdown || "");
    loadedDraft.current = project?.draft?.id || "";
    editRevision.current = project?.revision || 0;
  }
  const host = project ? new URL(project.site_url).hostname : "Your workspace";
  if (!project)
    return (
      <div className="opening">
        <Logo />
        {error ? (
          <>
            <h1>Open your workspace</h1>
            <p role="alert">{error}</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                try {
                  const link = new URL(restoreText);
                  if (
                    link.origin !== location.origin ||
                    !/^\/s\/[a-f0-9-]+$/.test(link.pathname)
                  )
                    throw Error();
                  if (link.pathname === location.pathname) {
                    history.replaceState(
                      null,
                      "",
                      link.pathname + link.search + link.hash,
                    );
                    location.reload();
                  } else {
                    location.assign(link.pathname + link.search + link.hash);
                  }
                } catch {
                  setError(
                    "Paste the full private access link for this workspace.",
                  );
                }
              }}
            >
              <input
                aria-label="Private access link"
                value={restoreText}
                onChange={(e) => setRestoreText(e.target.value)}
                placeholder="Paste your private access link"
              />
              <button className="primary">Open workspace</button>
            </form>
          </>
        ) : (
          <>
            <LoaderCircle className="spin" />
            <p>Opening your workspace…</p>
          </>
        )}
      </div>
    );
  return (
    <div className="workspace">
      <header className="topbar">
        <Logo />
        <div className="site-identity">
          <Globe size={15} />
          <span>{host}</span>
        </div>
        <div className="top-actions">
          <button aria-label="Run details" onClick={() => setShowRun(true)}>
            <FileText size={15} />
            <span>Run details</span>
          </button>
          <button
            onClick={copyLink}
            disabled={acting}
            aria-label="Copy private access link"
          >
            <Copy size={15} />
            <span>Private link</span>
          </button>
          <button
            className="primary"
            aria-label="Download llms.txt"
            onClick={download}
            disabled={!project.draft || dirty}
          >
            <Download size={16} />
            <span>Download file</span>
          </button>
        </div>
      </header>
      <nav className="workspace-jumps" aria-label="Jump to workspace section">
        <a href="#refine">Refine your guide</a>
        <a href="#document">View document</a>
      </nav>
      <div className="workspace-grid">
        <aside className="sidebar" id="refine" tabIndex={-1}>
          <section className="guide-switcher" aria-label="Site guides">
            <label htmlFor="guide-switch">Guide</label>
            <select
              id="guide-switch"
              value={id}
              disabled={dirty || acting}
              onChange={(e) => {
                const guide = project.guides.find(
                  (g) => g.id === e.target.value,
                );
                if (guide) navigate(siteDocumentUrl(siteId, guide.guide_path));
              }}
            >
              {(project.guides || []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.guide_name} · {g.guide_path}
                  {g.auto_cancelled
                    ? " · cancelled"
                    : g.reviews
                      ? " · needs review"
                      : ""}
                  {g.status === "running" || g.status === "pending"
                    ? " · updating"
                    : g.status === "failed"
                      ? " · check failed"
                      : ""}
                </option>
              ))}
            </select>
            <p>
              Publishing path: <code>{project.guide_path}llms.txt</code>
            </p>
            <button
              disabled={dirty || acting}
              onClick={() => setShowStructure(!showStructure)}
            >
              Guide structure
            </button>
            {showStructure && (
              <div>
                <p>
                  Create a separate guide for a section of your site, such as
                  /docs/. Each guide has its own saved decisions and history.
                </p>
                {!hideSuggestions &&
                  project.guide_suggestions?.map((suggestion) => (
                    <article className="guide-suggestion" key={suggestion.path}>
                      <strong>
                        {suggestion.name} · {suggestion.path}
                      </strong>
                      <p>{suggestion.reason}</p>
                      <button
                        onClick={() =>
                          setGuideForm({
                            path: suggestion.path,
                            name: suggestion.name,
                            purpose: suggestion.purpose,
                          })
                        }
                      >
                        Use suggestion
                      </button>
                    </article>
                  ))}
                {!hideSuggestions && !!project.guide_suggestions?.length && (
                  <button
                    onClick={() => {
                      setHideSuggestions(true);
                      setShowStructure(false);
                    }}
                  >
                    Keep current structure
                  </button>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () => {
                      await api<{ id: string }>(
                        path + "/guides",
                        "POST",
                        guideForm,
                      );
                      navigate(siteDocumentUrl(siteId, guideForm.path));
                    });
                  }}
                >
                  <label>
                    Guide name
                    <input
                      required
                      maxLength={100}
                      value={guideForm.name}
                      onChange={(e) =>
                        setGuideForm({ ...guideForm, name: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Path scope
                    <input
                      required
                      value={guideForm.path}
                      onChange={(e) =>
                        setGuideForm({ ...guideForm, path: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Guide purpose
                    <textarea
                      required
                      maxLength={2000}
                      value={guideForm.purpose}
                      onChange={(e) =>
                        setGuideForm({ ...guideForm, purpose: e.target.value })
                      }
                    />
                  </label>
                  <button disabled={dirty || acting} type="submit">
                    Create guide
                  </button>
                </form>
                <p>
                  These paths show where to publish each file on your website.
                  You’ll need to upload the files yourself.
                </p>
                <button
                  disabled={dirty || acting}
                  onClick={() =>
                    void action(
                      () => api(path + "/site-refresh", "POST"),
                      "Site check queued for every guide.",
                    )
                  }
                >
                  Check all guides
                </button>
                <button
                  disabled={dirty || acting}
                  onClick={() =>
                    void action(async () => {
                      const response = await fetch(
                        (import.meta.env.VITE_API_BASE || "") +
                          path +
                          "/bundle",
                        { credentials: "include" },
                      );
                      if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail);
                      }
                      const url = URL.createObjectURL(await response.blob());
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = "llms-guides.zip";
                      a.click();
                      URL.revokeObjectURL(url);
                    })
                  }
                >
                  Download all guides
                </button>
                <p>
                  The ZIP preserves paths and adds links from parent guides to
                  included children.
                </p>
              </div>
            )}
          </section>
          <div className="sidebar-heading">
            <span className="small-brand">Make it yours</span>
            <h1>What should readers know?</h1>
            <p>Add facts or preferences to help Brief write your guide.</p>
          </div>
          <div
            className="sidebar-tabs"
            role="tablist"
            aria-label="Workspace panels"
          >
            {(["guide", "decisions", "sources"] as const).map((t) => (
              <button
                role="tab"
                id={`tab-${t}`}
                aria-controls={`panel-${t}`}
                tabIndex={tab === t ? 0 : -1}
                onKeyDown={(event) => {
                  const tabs = ["guide", "decisions", "sources"] as const;
                  const index = tabs.indexOf(t);
                  const next =
                    event.key === "ArrowRight"
                      ? tabs[(index + 1) % 3]
                      : event.key === "ArrowLeft"
                        ? tabs[(index + 2) % 3]
                        : event.key === "Home"
                          ? tabs[0]
                          : event.key === "End"
                            ? tabs[2]
                            : null;
                  if (next) {
                    event.preventDefault();
                    setTab(next);
                    document.getElementById(`tab-${next}`)?.focus();
                  }
                }}
                aria-selected={tab === t}
                className={tab === t ? "selected" : ""}
                onClick={() => setTab(t)}
                key={t}
              >
                {t === "guide"
                  ? "Refine"
                  : t === "decisions"
                    ? `Decisions${activeDecisions.length ? " " + activeDecisions.length : ""}`
                    : "Sources"}
              </button>
            ))}
          </div>
          <div
            className="sidebar-body"
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
          >
            {tab === "guide" && (
              <>
                <div className="assistant-note">
                  <span className="note-mark">b.</span>
                  <div>
                    <strong>
                      {running
                        ? "Working on your brief"
                        : project.draft
                          ? "Your current draft"
                          : "Reading your website"}
                    </strong>
                    <p>
                      {running
                        ? running.kind === "generate"
                          ? "Writing a draft using your sources and saved decisions…"
                          : "Finding and reading pages on your site…"
                        : project.draft?.structured_result.explanation ||
                          "Your first draft will appear here when it’s ready."}
                    </p>
                  </div>
                </div>
                {running && (
                  <ActivityFeed
                    progress={
                      liveProgress?.id === running.id
                        ? liveProgress.progress
                        : running.progress
                    }
                    kind={running.kind}
                    connected={streamConnected}
                  />
                )}
                {question ? (
                  <QuestionCard
                    question={question}
                    sources={project.snapshot?.sources || []}
                    blocked={blocked}
                    answer={answer}
                    setAnswer={setAnswer}
                    onAnswer={(s) => decide(s, undefined, true, question.id)}
                    onDismiss={() =>
                      action(
                        () =>
                          api(
                            path + `/questions/${question.id}/dismiss`,
                            "POST",
                            { revision: project.revision },
                          ),
                        "Question dismissed. Your document is unchanged.",
                      )
                    }
                  />
                ) : (
                  project.draft &&
                  !running && (
                    <div className="quiet-note">
                      <Check size={17} />
                      <p>
                        No questions waiting. Add instructions below or ask for
                        another question.
                      </p>
                    </div>
                  )
                )}
                <button
                  className="interview-button"
                  disabled={blocked || !project.snapshot}
                  onClick={() =>
                    action(() =>
                      api(path + "/questions", "POST", {
                        revision: project.revision,
                      }),
                    )
                  }
                >
                  <Plus size={16} />
                  Ask me another question
                </button>
                {latestJob?.result?.question_count === 0 && !running && (
                  <p className="muted-note">{latestJob.result.explanation}</p>
                )}
                <div className="direction-composer">
                  <label htmlFor="direction">Add instructions</label>
                  <textarea
                    id="direction"
                    value={direction}
                    onChange={(e) => setDirection(e.target.value)}
                    placeholder="e.g. Focus on developers. Put the API docs first."
                    maxLength={4000}
                  />
                  <div className="composer-bottom">
                    <select
                      aria-label="Type of direction"
                      value={kind}
                      onChange={(e) => setKind(e.target.value as typeof kind)}
                    >
                      <option value="preference">Preference</option>
                      <option value="fact">A fact from me</option>
                    </select>
                    <button
                      className="send"
                      aria-label="Save direction"
                      disabled={
                        blocked || !direction.trim() || !project.snapshot
                      }
                      onClick={() => decide(direction.trim())}
                    >
                      <ArrowUp size={19} />
                    </button>
                  </div>
                  <p>
                    Saved for {project.guide_name || "this guide"}. Editable any
                    time.
                  </p>
                  {project.draft?.manually_edited && (
                    <p className="manual-note">
                      Changing direction regenerates the draft. Your manual
                      wording stays in version history.
                    </p>
                  )}
                </div>
              </>
            )}
            {tab === "decisions" && (
              <>
                <div className="panel-intro">
                  <h2>Saved decisions</h2>
                  <p>
                    Brief uses these facts and preferences when writing a draft.
                    Remove any you no longer want it to use.
                  </p>
                </div>
                {activeDecisions.length === 0 && (
                  <div className="empty-panel">
                    No saved direction yet. Answer a question or add a
                    preference in Refine.
                  </div>
                )}
                {project.decisions
                  .filter((d) => d.active)
                  .map((d) => (
                    <article className="decision" key={d.id}>
                      <span>
                        {d.kind === "fact" ? "Your fact" : "Your preference"}
                      </span>
                      {editing?.id === d.id ? (
                        <>
                          <textarea
                            aria-label="Edit decision"
                            value={editing.statement}
                            onChange={(e) =>
                              setEditing({
                                ...editing,
                                statement: e.target.value,
                              })
                            }
                          />
                          <div className="decision-actions">
                            <button
                              disabled={blocked || !editing.statement.trim()}
                              onClick={() => decide(editing.statement, editing)}
                            >
                              Save and update
                            </button>
                            <button onClick={() => setEditing(null)}>
                              Cancel
                            </button>
                          </div>
                        </>
                      ) : (
                        <>
                          <p>{d.statement}</p>
                          {d.needs_review && (
                            <p>
                              <strong>
                                Needs review: the source pages changed.
                              </strong>
                            </p>
                          )}
                          <div className="decision-actions">
                            <button
                              disabled={blocked}
                              onClick={() => setEditing({ ...d })}
                            >
                              <Pencil size={13} />
                              Edit
                            </button>
                            <button
                              disabled={blocked}
                              onClick={() => setShowRemoval(d)}
                            >
                              <Trash2 size={13} />
                              Remove
                            </button>
                          </div>
                        </>
                      )}
                    </article>
                  ))}
                {project.decisions.some((d) => !d.active) && (
                  <details className="removed">
                    <summary>Removed decisions</summary>
                    {project.decisions
                      .filter((d) => !d.active)
                      .map((d) => (
                        <article className="decision inactive" key={d.id}>
                          <p>{d.statement}</p>
                          <button
                            disabled={blocked}
                            onClick={() => decide(d.statement, d, true)}
                          >
                            Restore decision
                          </button>
                        </article>
                      ))}
                  </details>
                )}
              </>
            )}
            {tab === "sources" && <SourcesPanel project={project} />}
          </div>
          <div className="sidebar-footer">
            <div>
              <span className={`status-dot ${running ? "working" : ""}`} />
              {running ? "Updating your workspace" : "Private workspace"}
            </div>
            <p>Only people with your access link can edit.</p>
          </div>
        </aside>
        <main className="document-area" id="document" tabIndex={-1}>
          <div className="document-heading">
            <div>
              <h2>Your llms.txt</h2>
              <p>Review, edit, and download your guide.</p>
            </div>
            <span className="draft-badge">
              {running ? "Updating…" : "Draft"}
            </span>
          </div>
          {project.guides.some((g) => g.auto_reason) && (
            <section
              className="automatic-guides"
              aria-label="Automatic section guides"
            >
              <h3>Guides for sections of your site</h3>
              <p>
                Brief found enough pages in these sections to create separate
                guides. Each has its own saved decisions and history.
              </p>
              {project.guides
                .filter((g) => g.auto_reason)
                .map((g) => (
                  <article key={g.id}>
                    <strong>
                      {g.guide_name} · {g.guide_path}llms.txt
                    </strong>
                    <p>{g.auto_reason}</p>
                    <p>
                      {g.auto_cancelled
                        ? "Cancelled"
                        : g.draft_version_id
                          ? "Ready · available in the guide switcher"
                          : g.status === "failed"
                            ? "Could not finish. Open this guide to retry."
                            : g.status === "running"
                              ? "Building this guide…"
                              : "Queued after the main guide"}
                    </p>
                    {g.auto_cancelled && (
                      <button
                        disabled={acting}
                        onClick={() =>
                          action(() =>
                            api(`/api/projects/${g.id}/resume-guide`, "POST"),
                          )
                        }
                      >
                        Resume {g.guide_name}
                      </button>
                    )}
                    {!g.auto_cancelled && (
                      <a
                        href={siteDocumentUrl(siteId, g.guide_path)}
                        onClick={(event) => {
                          if (
                            event.button === 0 &&
                            !event.metaKey &&
                            !event.ctrlKey &&
                            !event.shiftKey &&
                            !event.altKey
                          ) {
                            event.preventDefault();
                            navigate(siteDocumentUrl(siteId, g.guide_path));
                          }
                        }}
                      >
                        Open {g.guide_name}
                      </a>
                    )}
                    {!g.draft_version_id && !g.auto_cancelled && (
                      <button
                        disabled={acting}
                        onClick={() =>
                          action(() =>
                            api(`/api/projects/${g.id}/cancel-guide`, "POST"),
                          )
                        }
                      >
                        Cancel {g.guide_name}
                      </button>
                    )}
                  </article>
                ))}
            </section>
          )}
          <ChangeInbox
            project={project}
            blocked={blocked}
            onCompare={() => setReview(project.proposal)}
            onTest={() => {
              setTestProposal((n) => n + 1);
              document
                .getElementById("guide-tests")
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          >
            {activeDecisions
              .filter((d) => d.needs_review)
              .map((d) => (
                <article
                  className="question-card decision-review"
                  key={d.id}
                  aria-label="Review saved answer"
                >
                  <span className="question-label">
                    Website evidence changed
                  </span>
                  <h2>Does your saved answer still apply?</h2>
                  <p>{d.statement}</p>
                  <p>
                    The source pages changed. Check whether your answer still
                    applies before accepting the update. Your current draft
                    stays as it is until you accept.
                  </p>
                  <details>
                    <summary>Compare the evidence</summary>
                    {d.evidence_basis.map((before) => {
                      const after = project.snapshot?.sources.find(
                        (s) => s.id === before.id,
                      );
                      if (
                        after &&
                        before.title === after.title &&
                        before.description === after.description &&
                        before.content === after.content
                      )
                        return null;
                      return (
                        <section className="review-evidence" key={before.id}>
                          <a href={before.url} target="_blank" rel="noreferrer">
                            {before.title}
                          </a>
                          <h3>When you answered</h3>
                          <p>{before.description}</p>
                          <pre
                            tabIndex={0}
                            aria-label="Previous source content"
                          >
                            {before.content}
                          </pre>
                          <h3>Latest website evidence</h3>
                          {after ? (
                            <>
                              <p>{after.description}</p>
                              <pre
                                tabIndex={0}
                                aria-label="Current source content"
                              >
                                {after.content}
                              </pre>
                            </>
                          ) : (
                            <p>
                              This page was removed after repeated not-found
                              responses.
                            </p>
                          )}
                        </section>
                      );
                    })}
                  </details>
                  <div className="decision-actions">
                    <button
                      disabled={blocked}
                      onClick={() => decide(d.statement, d)}
                    >
                      Keep my answer
                    </button>
                    <button
                      disabled={blocked}
                      onClick={() => {
                        setEditing({ ...d });
                        setTab("decisions");
                        document
                          .getElementById("refine")
                          ?.scrollIntoView({ behavior: "smooth" });
                      }}
                    >
                      Revise answer
                    </button>
                    <button
                      disabled={blocked}
                      onClick={() => decide(d.statement, d, false)}
                    >
                      Remove my override
                    </button>
                  </div>
                  <p className="muted">
                    Removing the override lets the proposed update use the
                    current website evidence. Keeping it confirms your answer
                    against these sources.
                  </p>
                </article>
              ))}
          </ChangeInbox>
          <Publication project={project} blocked={blocked} action={action} />
          {project.snapshot && (
            <SourceCoverageSummary
              snapshot={project.snapshot}
              onInspect={() => setShowRun(true)}
            />
          )}
          <GuideTests
            proposalRequest={testProposal}
            project={project}
            blocked={blocked}
            dirty={dirty}
            action={action}
          />
          {error && (
            <div className="banner error" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="banner notice" role="status">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {dirty && (
            <div className="banner">
              You have unsaved changes.
              <div>
                <button onClick={discard}>Discard</button>
                <button className="primary" disabled={acting} onClick={save}>
                  Save changes
                </button>
              </div>
            </div>
          )}
          {project.draft &&
            project.draft.decisions_revision !== project.decisions_revision && (
              <div className="banner warning">
                {running
                  ? "Preparing a document with your latest decisions. Your saved draft stays visible."
                  : "Your saved draft predates your latest decisions. Review the updated proposal when it is ready."}
                {!running && (
                  <button
                    disabled={acting}
                    onClick={() =>
                      action(() => api(path + "/generate", "POST"))
                    }
                  >
                    Retry generation
                  </button>
                )}
              </div>
            )}
          {failed && (
            <div className="banner error crawl-failure" role="alert">
              {latestJob?.error || "The update could not finish."}
              {!!latestJob?.result?.warnings?.length && (
                <ul className="crawl-warnings">
                  {latestJob.result.warnings
                    .slice(0, 5)
                    .map((warning, index) => (
                      <li key={index}>
                        <p>{warning.reason}</p>
                        <p>{warning.url}</p>
                        {warning.redirect_url && (
                          <p>
                            Redirect destination: {warning.redirect_url}{" "}
                            <a
                              href={`/?url=${encodeURIComponent(warning.redirect_url)}`}
                            >
                              Start a brief at this address
                            </a>
                          </p>
                        )}
                      </li>
                    ))}
                </ul>
              )}
              <button
                disabled={acting}
                onClick={() =>
                  action(() =>
                    api(
                      path +
                        (latestJob?.kind === "generate"
                          ? "/generate"
                          : "/refresh"),
                      "POST",
                    ),
                  )
                }
              >
                Retry
              </button>
            </div>
          )}
          {project.proposal &&
            !acting &&
            !running &&
            !failed &&
            project.proposal.decisions_revision ===
              project.decisions_revision && (
              <div className="banner proposal-banner">
                <div>
                  <strong>A new version is ready to review.</strong>
                  <span>Your current draft is unchanged.</span>
                </div>
                <button
                  disabled={dirty}
                  onClick={() => setReview(project.proposal)}
                >
                  Compare versions
                </button>
              </div>
            )}
          <div className="document-shell">
            <div className="document-toolbar">
              <div className="view-tabs">
                {(["preview", "edit", "history"] as const).map((v) => (
                  <button
                    key={v}
                    aria-pressed={view === v}
                    className={view === v ? "selected" : ""}
                    disabled={v === "edit" && (!project.draft || !!running)}
                    onClick={() => (v === "edit" ? beginEdit() : setView(v))}
                  >
                    {v === "history" ? (
                      <History size={14} />
                    ) : v === "edit" ? (
                      <Pencil size={14} />
                    ) : (
                      <FileText size={14} />
                    )}{" "}
                    {v === "edit"
                      ? "Markdown"
                      : v[0].toUpperCase() + v.slice(1)}
                  </button>
                ))}
              </div>
              <span className="file-name">llms.txt</span>
            </div>
            {!project.draft ? (
              <div className="draft-empty">
                <div className="paper-icon">
                  <FileText size={34} />
                </div>
                <h3>
                  {failed
                    ? "Couldn’t finish your draft"
                    : "Creating your first draft"}
                </h3>
                <p>
                  {failed
                    ? "Your saved sources are still available. Retry to continue."
                    : "Brief is reading your pages and writing a guide. You can edit it when it’s ready."}
                </p>
                {!failed && <LoaderCircle size={20} className="spin" />}
              </div>
            ) : view === "edit" ? (
              <textarea
                className="markdown-editor"
                aria-label="Document Markdown"
                value={text}
                spellCheck={false}
                onChange={(e) => {
                  if (!dirtyRef.current)
                    editRevision.current = project.revision;
                  setText(e.target.value);
                  dirtyRef.current = true;
                  setDirty(true);
                }}
              />
            ) : view === "history" ? (
              <div className="version-list">
                <h3>Version history</h3>
                <p>Restore a document without changing your saved decisions.</p>
                {project.versions.map((v, i) => (
                  <button
                    key={v.id}
                    disabled={dirty}
                    onClick={() =>
                      action(async () =>
                        setReview(
                          await api<Version>(path + "/versions/" + v.id),
                        ),
                      )
                    }
                  >
                    <span>
                      <FileText size={17} />
                      <strong>
                        {v.manually_edited
                          ? "Manual edit"
                          : v.kind === "proposal"
                            ? "Generated proposal"
                            : "Generated draft"}
                      </strong>
                    </span>
                    <span>
                      {date(v.created_at)}{" "}
                      {v.id === project.draft?.id ? (
                        <b>Current</b>
                      ) : (
                        <ChevronDown size={15} />
                      )}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <article className="document-preview">
                <Markdown
                  skipHtml
                  components={{
                    a: ({ children, href }) => (
                      <a href={href} target="_blank" rel="noreferrer">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {text}
                </Markdown>
              </article>
            )}
            <div className="document-foot">
              <span>
                {project.draft
                  ? `${text.trim().split(/\s+/).length} words`
                  : "Preparing your draft"}
              </span>
              <span>
                {project.draft
                  ? `Saved ${date(project.draft.created_at)}`
                  : "You can leave this page open."}
              </span>
            </div>
          </div>
          <div className="monitor">
            <div className="monitor-copy">
              <span className="monitor-icon">
                <RefreshCw size={19} />
              </span>
              <div>
                <h3>Keep an eye on your sources</h3>
                <p>
                  {project.last_checked_at
                    ? `Last checked ${date(project.last_checked_at)}${project.last_check_status === "partial" ? " · partial coverage" : ""}`
                    : "Check for changes without losing your work."}
                </p>
              </div>
            </div>
            <div className="monitor-actions">
              <label className="switch-label">
                <input
                  type="checkbox"
                  checked={project.monitor_enabled}
                  disabled={acting}
                  onChange={(e) => {
                    const enabled = e.target.checked;
                    setProject({ ...project, monitor_enabled: enabled });
                    void action(
                      () => api(path + "/monitoring", "PATCH", { enabled }),
                      "Daily check setting saved.",
                    );
                  }}
                />
                Daily checks
              </label>
              <button
                disabled={blocked}
                onClick={() => action(() => api(path + "/refresh", "POST"))}
              >
                <RefreshCw size={14} />
                Check now
              </button>
            </div>
          </div>
          <p className="local-note">
            Downloading gives you a copy. Changes here won’t update a file
            you’ve uploaded elsewhere.
          </p>
        </main>
      </div>
      {showRun && (
        <RunDetails project={project} onClose={() => setShowRun(false)} />
      )}
      {showRemoval && (
        <Modal
          label="remove-title"
          className="removal-modal"
          onClose={() => setShowRemoval(null)}
        >
          <div className="modal-heading">
            <h2 id="remove-title">Remove this decision?</h2>
            <button
              className="modal-close"
              aria-label="Close removal"
              onClick={() => setShowRemoval(null)}
            >
              <X size={20} />
            </button>
          </div>
          <div className="removal-body">
            <p>
              Brief will write a new draft using your website and the remaining
              decisions.
            </p>
            <blockquote>{showRemoval.statement}</blockquote>
            <p className="removal-note">
              You can restore this decision later. Previous drafts remain in
              version history.
            </p>
          </div>
          <div className="modal-actions">
            <button onClick={() => setShowRemoval(null)}>Keep decision</button>
            <button
              className="destructive"
              disabled={acting}
              onClick={() => decide(showRemoval.statement, showRemoval, false)}
            >
              Remove and regenerate
            </button>
          </div>
        </Modal>
      )}
      {review && (
        <Modal
          label="review-title"
          className="comparison review-modal"
          onClose={() => setReview(null)}
        >
          <div className="modal-heading">
            <h2 id="review-title">
              {review.id === project.proposal?.id
                ? "Review proposed changes"
                : "Review this version"}
            </h2>
            <button
              className="modal-close"
              aria-label="Close comparison"
              onClick={() => setReview(null)}
            >
              <X size={20} />
            </button>
          </div>
          <VersionReview key={review.id} project={project} version={review} />
          <p>
            Using this version changes the document. Your saved decisions stay
            as they are.
          </p>
          <div className="modal-actions">
            <button onClick={() => setReview(null)}>Keep current</button>
            <button
              className="primary"
              disabled={
                blocked ||
                review.id === project.draft?.id ||
                (review.id === project.proposal?.id &&
                  activeDecisions.some((d) => d.needs_review))
              }
              onClick={() =>
                action(async () => {
                  await api(path + `/versions/${review.id}/use`, "POST", {
                    revision: project.revision,
                  });
                  setReview(null);
                }, "Document version restored.")
              }
            >
              Use this version
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
