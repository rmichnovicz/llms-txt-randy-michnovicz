export type Progress = {
  stage?: string;
  message?: string;
  url?: string;
  pages_read?: number;
  pages_found?: number;
  started_at?: string;
  recent?: { message: string; url?: string; at: string }[];
};
export type Source = {
  id: string;
  url: string;
  title: string;
  description: string;
  content: string;
};
export type Decision = {
  id: string;
  statement: string;
  kind: "preference" | "fact";
  active: boolean;
  revision: number;
  needs_review: boolean;
  evidence_basis: Source[];
};
export type Question = {
  id: string;
  status: string;
  topic: string;
  data: {
    question: string;
    rationale: string;
    options: string[];
    recommended_option: number | null;
    evidence_ids: string[];
  };
};
export type Version = {
  refined_from_version_id?: string | null;
  refinement?: {
    before_version_id: string;
    before_markdown: string;
    diff: string;
    directions: {
      kind: "added" | "removed" | "updated";
      before: string | null;
      after: string | null;
    }[];
  };
  id: string;
  kind: string;
  manually_edited: boolean;
  created_at: string;
  markdown: string;
  decisions_revision: number;
  structured_result: { explanation: string };
  model_metadata?: Record<string, unknown>;
  generation_input: { decisions: Decision[] };
};
export type GuideCheck = {
  checked_at: string;
  complete: boolean;
  error?: string;
  guides: {url: string; requested_url: string; markdown: string; sha256: string}[];
  checks: {url: string; status: string}[];
};
export type Project = {
  publication_id?: string;
  published_version_id?: string | null;
  published_at?: string | null;
  existing_guide_check?: GuideCheck | null;
  proposal_diff?: string | null;
  change_inbox?: import("./ChangeInbox").SourceChange[];
  test_runs?: import("./GuideTests").TestRun[];
  id: string;
  site_url: string;
  site_id: string;
  guide_path: string;
  guide_name: string;
  guide_purpose: string;
  guides: {
    id: string;
    guide_path: string;
    auto_reason: string | null;
    auto_cancelled: boolean;
    draft_version_id: string | null;
    guide_name: string;
    status: string;
    reviews: number;
  }[];
  guide_suggestions: {
    path: string;
    name: string;
    purpose: string;
    reason: string;
  }[];
  revision: number;
  decisions_revision: number;
  draft: Version | null;
  proposal: Version | null;
  monitor_enabled: boolean;
  last_checked_at: string | null;
  last_check_status: string | null;
  decisions: Decision[];
  questions: Question[];
  versions: Version[];
  snapshot: {
    sources: Source[];
    warnings: { url: string; reason: string }[];
    coverage: {
      sitemap_discovery?: {inventory_bytes?: number; resumed_urls?: number; resumed_indexes?: number; fetches: number; bytes: number; stop_reason: string; remaining_indexes: number; trace: {url: string; status: number; bytes: number}[]};
      attempted: number;
      discovered?: number;
      fresh_sources: number;
      truncated: boolean;
      stop_reason?: string;
      duration_ms?: number;
      downloaded_bytes?: number;
      cache_hits?: number;
      conditional_requests?: number;
      trace?: {
        url: string;
        status: string | number;
        cache: string;
        bytes: number;
        storage?: string;
      }[];
      unread?: number;
      assessment?: {
        reused?: boolean;
        reason: string;
        gaps: string[];
        urls?: string[];
        skipped_urls?: string[];
        metadata?: Record<string, unknown>;
      } | null;
    };
    changes: { added: string[]; modified: string[]; removed: string[] };
  } | null;
  jobs: {
    id: string;
    kind: string;
    progress?: Progress;
    status: string;
    error: string | null;
    result: {
      explanation?: string;
      question_count?: number;
      warnings?: { url: string; reason: string; redirect_url?: string }[];
    } | null;
  }[];
};
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch((import.meta.env.VITE_API_BASE || "") + path, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check your input and try again.",
    );
  return data as T;
}
export function date(value: string | null) {
  return value
    ? new Date(value).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : "Not checked yet";
}
