# Site guides, cache, and run details

A site workspace owns its canonical origin and extracted-page cache. Each path-scoped guide has independent purpose, owner answers, snapshots, proposed/draft documents, history, and review state. Existing projects migrate into one-guide sites without losing their drafts or answers.

## Demo flow

1. Open **Run details** in the top bar. Inspect the selected/skipped URL list, individual fetch status and bytes, cache validation counts, duration, stop reason, model usage, and recent job milestones.
2. Open **Guide structure** in the sidebar. Suggestions are transparent rules: captured pages grouped into common path sections (at least three pages), not a model pretending to know the site's information architecture. Choose a suggestion or edit a guide's name, scope, and purpose before creation.
3. Create a guide such as `/help/`. Its purpose enters the generation context. Switch guides with the labelled dropdown; answers and history stay with their guide. No external publishing occurs.
4. **Check all guides** queues checks independently. A single worker processes them sequentially. Review counts appear in the switcher. Cache evidence is shared within this workspace, while source differences and decision reviews remain guide-specific.
5. **Download all guides** produces a ZIP preserving publishing paths. Parent exports gain relative links to included descendants. This does not mutate saved drafts. Every guide must have a draft first.

The scope is a proposed file location and crawl boundary, not a claim that downstream LLMs universally implement path inheritance. Existing guides cannot yet be moved, merged, or deleted in the UI. “Keep current structure” dismisses suggestions for the current screen; it does not create a persistent preference.

## What is recorded

Run details shows structured outputs and measured events, not private model reasoning. Page selection starts with URL-priority rules; one model assessment can choose any number of additional discovered URLs and supply a short selection reason. The source snapshot records that plan, skipped candidates, page responses, and aggregate metrics. Recent jobs retain the latest progress and a bounded recent-event list, rather than a permanent full event log. Older snapshots lack the new trace fields; refresh them to populate details.

No default page-count cap applies. Time, download bytes, extracted-text size, and discovery bounds remain explicit resource limits. A completed selection plan does not prove exhaustive coverage. See `CRAWL_COVERAGE.md` for exact limits and fallback behavior.

## Cache behavior

The cache stores extracted source JSON and discovered links in Postgres, using its native storage compression; it does not archive raw HTML. It is keyed by workspace site and exact URL, with an extraction-version check. Separate users creating the same public URL do not share private workspace data.

Robots rules are checked before using cached content. Requests prefer `If-None-Match`, falling back to `If-Modified-Since`. A 304 reuses extracted content and links; a 200 extracts and replaces them. Without validators, the crawler downloads again. Redirects drop request validators. Responses marked `no-store` or `private`, or with unsupported `Vary` fields, are not cached. A 404/410 evicts the cache; immutable source snapshots still drive conservative removal detection.

There is no freshness TTL that bypasses HTTP validation, no persistent robots/sitemap cache, and no guarantee that a site supports useful validators. Refresh can therefore still take time. Overlapping guides reuse extraction after validation, but each still performs its own coverage assessment and scoped crawl.

## Verification

Backend tests cover frozen real parent/child files, scope boundaries, shared authorization with cross-site isolation, independent answers and drafts, ZIP links, cache revalidation, storage restrictions, and extraction-version changes. Browser checks cover create/switch, bundle download, checking all guides, and the details modal at 320px and 1280px, including accessibility checks. Frozen fixture provenance and qualitative notes are in `evals/corpus/hierarchies/README.md`.

## Live Tally smoke run (2026-09-25 UTC)

An isolated demo generated both a root overview and a `/help/` guide. The initial root crawl captured 28 pages in 45 seconds; the focused help guide captured 40. This demonstrates why scope and purpose can justify different reading depths without a fixed page quota.

A repeat root crawl sent two conditional requests, both returning full 200 responses, so there were **zero 304 cache hits**. It also skipped cache storage for 31 responses with private/no-store directives. Do not present Tally as a proven cache-speedup example. Cache reuse is verified deterministically with a 304 fixture, and Run details exposes actual response and storage decisions. The root's first generated draft detected conflicting prices among the supplied pages and asked whether to omit exact prices—useful real ambiguity for the interview demo. Machine-readable smoke metrics are in `evals/reports/guide-live-smoke.json`.

## Automatic section guides

After a root document is generated successfully, the same transaction plans its
section guides once. The current rule uses at least three captured pages under
`/docs/`, `/help/`, `/support/`, `/developers/`, or `/learn/`. At most three suggested
sections are queued; ordinary blog and product folders are not automatically split.
This is a transparent path-and-coverage heuristic, not a semantic model assessment.
Existing guide paths are skipped, cancelled paths stay reserved, and child guides
never recursively create more guides. Existing workspaces become eligible on their
next explicit generation; installing the migration itself starts no model calls.

The root draft is available before section crawling starts. Child jobs reuse the
site's extracted-text/HTTP cache through the normal crawler, with the same robots,
validation, scope, and coverage rules. That does not guarantee a cache hit: private
or no-store pages and fresh server responses still require reading.

A visible status panel shows each automatic guide's reason and progress. Cancel
invalidates the active job lease and excludes the unfinished guide from bundles
and refresh-all; Resume explicitly queues it again. Individual model/network calls
already in flight may finish, but their results cannot be committed after cancellation.

Once a child draft exists, its absolute llms.txt link is appended to root draft and
proposal copies as new immutable versions. Existing text and historical versions
are preserved. If root generation is already queued/running, that generation adds
ready child links when it completes. Parent SSE also observes sibling job status,
so switching guides or refreshing the browser is unnecessary to see completion.
These files remain local drafts until the user exports and hosts them.

Tests cover root-first scheduling, duplicate prevention, cancelled lease writes,
immutable parent linking, no recursive creation, cancellation/resume, site-cookie
navigation, and accessibility at mobile and desktop widths.
