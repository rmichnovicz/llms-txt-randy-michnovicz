import type { Progress } from "./api";
import GuideTests from "./GuideTests";
import ChangeInbox from "./ChangeInbox";
import VersionReview from "./VersionReview";
import Publication from "./Publication";
import SavedSessions from "./SavedSessions";
import { rememberSession, savedSessions, siteDocumentUrl } from "./sessions";
import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
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
import {
  api,
  date,
  type Decision,
  type Project,
  type Version,
  type Question,
} from "./api";

const currentRoute = () => window.location.pathname + window.location.search;
const Logo = () => (
  <a className="logo" href="/" aria-label="Brief home">
    <span className="logo-mark">b.</span>brief
    <span className="logo-dot">/</span>
  </a>
);
const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";

export default function App() {
  const [route, setRoute] = useState(currentRoute);
  const currentUrl = useRef(route);
  const canLeave = useRef(() => true);
  useEffect(() => {
    const update = () => {
      if (canLeave.current()) {
        currentUrl.current = currentRoute();
        setRoute(currentUrl.current);
      } else history.pushState(null, "", currentUrl.current);
    };
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  function navigate(url: string) {
    if (!canLeave.current()) return;
    history.pushState(null, "", url);
    currentUrl.current = url;
    setRoute(url);
  }
  function canonicalize(url: string) {
    history.replaceState(null, "", url);
    currentUrl.current = url;
  }
  const url = new URL(route, window.location.origin);
  const siteId = url.pathname.match(/^\/s\/([a-f0-9-]+)$/)?.[1];
  return siteId ? <Workspace key={route} siteId={siteId} doc={url.searchParams.get("doc")} navigate={navigate} canonicalize={canonicalize} canLeave={canLeave} /> : <Start />;
}

function Modal({
  label,
  onClose,
  className = "",
  children,
}: {
  label: string;
  onClose: () => void;
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const backdropPressed = useRef(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${className}`}
      aria-labelledby={label}
      onPointerDown={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        backdropPressed.current =
          event.target === event.currentTarget &&
          (event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom);
      }}
      onClick={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          backdropPressed.current &&
          event.target === event.currentTarget &&
          (event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom)
        )
          onClose();
        backdropPressed.current = false;
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const targets = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex="0"]',
          ),
        ).filter((element) => element.getClientRects().length > 0);
        const first = targets[0];
        const last = targets[targets.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      {children}
    </dialog>
  );
}
function Start() {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [creationKey, setCreationKey] = useState("");
  async function start(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        (import.meta.env.VITE_API_BASE || "") + "/api/projects",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(creationKey ? { "X-Creation-Key": creationKey } : {}),
          },
          body: JSON.stringify({
            url: url.includes("://") ? url : "https://" + url,
          }),
        },
      );
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Enter a public website URL.",
        );
      rememberSession(result.project, result.management_token, true);
      window.location.assign(
        `${siteDocumentUrl(result.project.site_id, result.project.guide_path)}#key=${encodeURIComponent(result.management_token)}`,
      );
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }
  return (
    <div className="start">
      <header className="start-header">
        <Logo />
        <span>An llms.txt editor for your website.</span>
      </header>
      <main className="intro">
        <div className="intro-copy">
          <div className="intro-symbol" aria-hidden="true">
            <FileText size={32} />
            <span>llms.txt</span>
          </div>
          <h1>
            Your website,
            <br />
            ready for AI readers.
          </h1>
          <p>
            Create an llms.txt file with links and summaries from your website.
            Review the draft, add context, and download it when you’re ready.
          </p>
          <form onSubmit={start} className="url-form">
            <label htmlFor="site-url">Website URL</label>
            <div className="url-entry">
              <Globe size={20} />
              <input
                id="site-url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="your-website.com"
                required
                autoComplete="url"
                disabled={busy}
              />
              <button className="primary" disabled={busy}>
                {busy ? (
                  <>
                    <LoaderCircle className="spin" size={18} /> Creating brief…
                  </>
                ) : (
                  <>
                    Create a brief <Plus size={17} />
                  </>
                )}
              </button>
            </div>
            <details>
              <summary>Private demo access</summary>
              <input
                aria-label="Creation key"
                type="password"
                placeholder="Creation key, if required"
                value={creationKey}
                onChange={(e) => setCreationKey(e.target.value)}
              />
            </details>
          </form>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="intro-note">
            <Check size={16} />
            Edit the draft or answer questions to update it.
          </div>
        </div>
        <div className="sample-sheet" aria-label="Example llms.txt document">
          <div className="sheet-meta">
            <FileText size={16} />
            llms.txt<span>Example</span>
          </div>
          <div className="sheet-content">
            <h2>
              A guide to
              <br />
              your website.
            </h2>
            <blockquote>
              A short overview with links to your product, documentation, and
              support pages.
            </blockquote>
            <h3>Start here</h3>
            <p>
              <span className="sample-link">Your product</span>
              <br />
              What your product does and who it’s for.
            </p>
            <p>
              <span className="sample-link">Useful resources</span>
              <br />
              Documentation, common questions, and support.
            </p>
            <h3>When your site changes</h3>
            <p>Check for updates and review the suggested edits.</p>
          </div>
          <div className="sheet-foot">
            A plain text file you can edit and publish.
          </div>
        </div>
      </main>
      <SavedSessions />
      <footer className="start-footer">
        A workspace for llms.txt{" "}
        <span>Create and maintain your website’s AI guide.</span>
      </footer>
    </div>
  );
}

function Workspace({ siteId, doc, navigate, canonicalize, canLeave }: {
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
  const documentApi = siteApi + "/document" + (doc === null ? "" : `?doc=${encodeURIComponent(doc)}`);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acting, setActing] = useState(false);
  const [tab, setTab] = useState<"guide" | "decisions" | "sources">("guide");
  const [view, setView] = useState<"preview" | "edit" | "history">("preview");
  const [text, setText] = useState("");
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  useEffect(() => {
    canLeave.current = () => !dirtyRef.current || window.confirm("Discard your unsaved document changes?");
    return () => { canLeave.current = () => true; };
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
    if (!rememberedVisit.current || savedSessions().some((s) => s.id === next.id)) {
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
          savedSessions().find((s) => (s.siteId === siteId || s.id === siteId) && s.token)?.token;
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
          (import.meta.env.VITE_API_BASE || "") + `/api/projects/${next.id}/events`,
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
        if (active && stream?.readyState !== EventSource.OPEN) return await load();
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
                    history.replaceState(null, "", link.pathname + link.search + link.hash);
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
                const guide = project.guides.find((g) => g.id === e.target.value);
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
            {tab === "sources" && (
              <>
                <div className="panel-intro">
                  <h2>Read from your website</h2>
                  <p>
                    {project.snapshot?.sources.length || 0} sources available.{" "}
                    {project.snapshot?.coverage.stop_reason ===
                    "coverage_plan_finished"
                      ? "Finished reading the selected pages. Other pages on your site may not have been read."
                      : project.snapshot?.coverage.stop_reason === "time_budget"
                        ? "Reached the time limit. Some pages haven’t been checked."
                        : project.snapshot?.coverage.stop_reason ===
                            "download_budget"
                          ? "Reached the download limit. Some pages haven’t been checked."
                          : project.snapshot?.coverage.stop_reason ===
                              "text_budget"
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
                          Brief looked for pages on these topics. Some may still
                          be missing from the sources.
                        </p>
                        <ul>
                          {project.snapshot.coverage.assessment.gaps.map(
                            (gap) => (
                              <li key={gap}>{gap}</li>
                            ),
                          )}
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
                    <summary>
                      {project.snapshot.warnings.length} crawl notes
                    </summary>
                    {project.snapshot.warnings.map((w, i) => (
                      <p key={i}>
                        {w.url}: {w.reason}
                      </p>
                    ))}
                  </details>
                ) : null}
              </>
            )}
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
                      <a href={siteDocumentUrl(siteId, g.guide_path)} onClick={(event) => {
                        if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
                          event.preventDefault();
                          navigate(siteDocumentUrl(siteId, g.guide_path));
                        }
                      }}>Open {g.guide_name}</a>
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
            <div className="banner error" role="alert">
              {latestJob?.error || "The update could not finish."}
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
        <Modal
          label="run-details-title"
          onClose={() => setShowRun(false)}
          className="run-details"
        >
          <header className="run-details-header">
            <div>
              <h2 id="run-details-title">Run details</h2>
              <p>How Brief explored your site and built this guide.</p>
            </div>
            <button
              className="modal-close"
              aria-label="Close run details"
              onClick={() => setShowRun(false)}
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
                  {project.guide_purpose ||
                    "Create an overview of the website."}
                </dd>
              </div>
            </dl>
            <section
              className="run-section"
              aria-labelledby="run-snapshot-title"
            >
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
                Brief reads selected pages, so this may not cover your entire
                site.
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
                    {project.snapshot.coverage.cache_hits || 0} pages reused
                    after HTTP validation from{" "}
                    {project.snapshot.coverage.conditional_requests || 0}{" "}
                    conditional requests.
                  </p>
                </>
              ) : (
                <p>No crawl result yet.</p>
              )}
            </section>
            <section
              className="run-section"
              aria-labelledby="run-selection-title"
            >
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
                    {project.snapshot.coverage.sitemap_discovery.fetches}{" "}
                    sitemap requests ·{" "}
                    {(
                      project.snapshot.coverage.sitemap_discovery.bytes /
                      1_000_000
                    ).toFixed(2)}{" "}
                    MB ·{" "}
                    {project.snapshot.coverage.sitemap_discovery.stop_reason}
                  </p>
                  <p>
                    {(
                      (project.snapshot.coverage.sitemap_discovery
                        .inventory_bytes || 0) / 1_000_000
                    ).toFixed(2)}{" "}
                    MB URL inventory ·{" "}
                    {project.snapshot.coverage.sitemap_discovery.resumed_urls ||
                      0}{" "}
                    saved URLs resumed ·{" "}
                    {
                      project.snapshot.coverage.sitemap_discovery
                        .remaining_indexes
                    }{" "}
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
                      skipped:
                        project.snapshot?.coverage.assessment?.skipped_urls,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
              <details>
                <summary>Fetch results</summary>
                <pre tabIndex={0} aria-label="Fetch results">
                  {JSON.stringify(
                    project.snapshot?.coverage.trace || [],
                    null,
                    2,
                  )}
                </pre>
              </details>
              <details>
                <summary>Model usage and settings</summary>
                <pre tabIndex={0} aria-label="Model metadata">
                  {JSON.stringify(
                    {
                      planning: project.snapshot?.coverage.assessment?.metadata,
                      document: (project.proposal || project.draft)
                        ?.model_metadata,
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
function QuestionCard({
  question,
  sources,
  blocked,
  answer,
  setAnswer,
  onAnswer,
  onDismiss,
}: {
  question: Question;
  sources: NonNullable<Project["snapshot"]>["sources"];
  blocked: boolean;
  answer: string;
  setAnswer: (s: string) => void;
  onAnswer: (s: string) => void;
  onDismiss: () => void;
}) {
  return (
    <section className="question-card">
      <span className="question-label">A question for you</span>
      <h2>{question.data.question}</h2>
      <p>{question.data.rationale}</p>
      <div className="options">
        {question.data.options.map((option, index) => (
          <button
            key={option}
            disabled={blocked}
            onClick={() => onAnswer(option)}
          >
            <span>{option}</span>
            {question.data.recommended_option === index && (
              <small>Recommended</small>
            )}
          </button>
        ))}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onAnswer(answer.trim());
        }}
      >
        <label htmlFor="answer">Or answer in your own words</label>
        <div className="answer-entry">
          <textarea
            rows={2}
            id="answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            maxLength={2500}
            placeholder="Here’s what I have in mind…"
          />
          <button aria-label="Save answer" disabled={blocked || !answer.trim()}>
            <ArrowUp size={16} />
          </button>
        </div>
      </form>
      <div className="question-footer">
        <details>
          <summary>Why this came up</summary>
          {question.data.evidence_ids.map((id) => {
            const s = sources.find((s) => s.id === id);
            return s ? (
              <a key={id} href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            ) : (
              <span key={id}>Your saved direction</span>
            );
          })}
        </details>
        <button disabled={blocked} onClick={onDismiss}>
          Dismiss
        </button>
      </div>
    </section>
  );
}

function ActivityFeed({
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
