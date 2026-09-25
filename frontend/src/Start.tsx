import { useState, type FormEvent } from "react";
import { Check, FileText, Globe, LoaderCircle, Plus } from "lucide-react";
import SavedSessions from "./SavedSessions";
import { rememberSession, siteDocumentUrl } from "./sessions";
import Logo from "./Logo";
import { errorText } from "./errors";

export default function Start() {
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
