import type { Project } from "./api";

const key = "brief.sessions.v1";
export type SavedSession = {
  id: string;
  siteUrl: string;
  siteId?: string;
  guideName: string;
  guidePath: string;
  lastVisited: string;
  token?: string;
};

export function savedSessions(): SavedSession[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || "[]");
    if (!Array.isArray(value)) return [];
    return value
      .filter(
        (entry): entry is SavedSession =>
          entry &&
          typeof entry.id === "string" &&
          /^[a-f0-9-]{36}$/.test(entry.id) &&
          typeof entry.siteUrl === "string" &&
          /^https?:\/\//.test(entry.siteUrl) &&
          typeof entry.guideName === "string" &&
          typeof entry.guidePath === "string" &&
          typeof entry.lastVisited === "string" &&
          Number.isFinite(Date.parse(entry.lastVisited)) &&
          (entry.token === undefined || typeof entry.token === "string"),
      )
      .sort((a, b) => b.lastVisited.localeCompare(a.lastVisited));
  } catch {
    return [];
  }
}

function save(sessions: SavedSession[]) {
  try {
    localStorage.setItem(key, JSON.stringify(sessions));
    window.dispatchEvent(new Event("brief:sessions"));
  } catch {
    // A blocked or full browser store must not prevent opening a workspace.
  }
}

export function rememberSession(
  project: Project,
  token?: string,
  visited = false,
) {
  const sessions = savedSessions();
  const previous = sessions.find((s) => s.id === project.id);
  save([
    {
      id: project.id,
      siteUrl: project.site_url,
      siteId: project.site_id,
      guideName: project.guide_name || "Site overview",
      guidePath: project.guide_path || "/",
      lastVisited:
        visited || !previous ? new Date().toISOString() : previous.lastVisited,
      token: token || previous?.token,
    },
    ...sessions.filter((s) => s.id !== project.id),
  ]);
}

export function forgetSession(id: string) {
  save(savedSessions().filter((s) => s.id !== id));
}

export function siteDocumentUrl(siteId: string, guidePath = "/") {
  return `/s/${siteId}` + (guidePath === "/" ? "" : `?doc=${encodeURIComponent(guidePath)}`);
}
