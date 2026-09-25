import { useEffect, useState } from "react";
import { date } from "./api";
import { forgetSession, savedSessions, siteDocumentUrl } from "./sessions";

export default function SavedSessions() {
  const [sessions, setSessions] = useState(savedSessions);
  useEffect(() => {
    const refresh = () => setSessions(savedSessions());
    window.addEventListener("storage", refresh);
    window.addEventListener("brief:sessions", refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      window.removeEventListener("brief:sessions", refresh);
    };
  }, []);
  if (!sessions.length) return null;
  return (
    <section className="saved-sessions" aria-labelledby="saved-sessions-title">
      <h2 id="saved-sessions-title">Your saved sessions</h2>
      <p>
        Stored in this browser, including private access. Removing a session
        from this list does not delete its project.
      </p>
      <ul>
        {sessions.map((session) => (
          <li key={session.id}>
            <a href={siteDocumentUrl(session.siteId || session.id, session.guidePath)}>
              <strong>{session.siteUrl}</strong>
              <span>
                {session.guideName} · {session.guidePath}
              </span>
              <small>Last opened {date(session.lastVisited)}</small>
            </a>
            <button
              type="button"
              aria-label={`Remove saved session for ${session.siteUrl} ${session.guidePath}`}
              onClick={() => forgetSession(session.id)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
