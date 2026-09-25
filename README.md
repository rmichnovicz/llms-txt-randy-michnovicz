# Brief

A guided llms.txt editor: crawl a website, generate a useful draft, refine it through optional questions, publish a stable file, and monitor changes.

The Python/FastAPI backend handles crawling, source snapshots, durable jobs, draft
generation, and scheduled refreshes. The React editor supports optional questions,
saved decisions, Markdown editing, version comparison, explicit publication, and
a source change inbox.

Cloud deployment is planned: Cloudflare Pages for the frontend and Railway for
the backend. The configured generation model is GPT-6 Sol with medium reasoning.

- [Product goals and design](PRODUCT_SPEC.md)
- [Architecture and tradeoffs](ARCHITECTURE.md)
- [Feature guides and verification notes](docs/README.md)
- [Evaluation commands and review rubric](evals/README.md)
- [Real-file evaluation study and results](evals/REPORT.md)

## Run locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker for Postgres.

```sh
uv sync
cp .env.example .env
docker compose up -d --wait
uv run --env-file .env brief migrate
uv run --env-file .env uvicorn brief.api:app --reload
```

Add `OPENAI_API_KEY` to the gitignored `.env` to enable generation (`OPENAI_MODEL` defaults to `gpt-6-sol`). Without a key, the worker runs the crawl-only pipeline. Run the worker in another terminal:

```sh
uv run --env-file .env brief worker
```

Start the frontend in another terminal (Node.js required):

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open http://localhost:5173. For local HTTP, set `BRIEF_SECURE_COOKIES=false` and `FRONTEND_ORIGINS=http://localhost:5173` in `.env`. The Vite server proxies `/api` to port 8000. Keep secure cookies enabled in production.

Open [API docs](http://localhost:8000/docs). `POST /api/projects` accepts `{"url":"https://example.com/"}` and returns a project ID, job ID, and one-time management token. Use the token as `Authorization: Bearer <token>` on project routes. It is stored only as a hash. The frontend exchanges a private link fragment for a site-scoped HttpOnly cookie, then removes the fragment from the address bar.

Workspace URLs use one site UUID: `/s/{site_id}` opens the site's original document, and `/s/{site_id}?doc=/docs/` selects a document by scope. All documents share site access; their internal IDs still keep edits and version history independent. `GET /api/projects/{site_id}/document?doc=/docs/` resolves and loads a document within the authenticated site.

`GET /api/projects/{id}` returns recent job status and the latest usable snapshot, including source titles, descriptions, URLs, main content, coverage, warnings, and added/modified/removed URLs. Completed attempts remain readable at `GET /api/projects/{id}/snapshots/{snapshot_id}`, including failed attempts whose snapshot ID is in the job result.

`POST /api/projects/{id}/refresh` requires an `Idempotency-Key` header. Refresh requests reuse an active project job; completed manually created refresh keys are deduplicated. A changed source produces a new snapshot; a failed crawl preserves the previous usable snapshot. With a configured model, changed sources queue generation as a separate durable job. The first generated document becomes a draft; later generations become proposals, preserving the current draft. Publication is explicit: only a saved version selected by the owner becomes public.

`GET /api/projects/{id}` also returns `draft` and `proposal`, including Markdown, structured questions, pinned source snapshot, and model usage metadata. `POST /api/projects/{id}/generate` with an `Idempotency-Key` queues generation from the latest usable snapshot without recrawling. Generation freezes the active decisions with its source snapshot. Decision changes replace the draft; source refreshes create a proposal for review. Model failures leave source snapshots and previous documents intact.

Enable source monitoring with `PATCH /api/projects/{id}/monitoring` and `{"enabled":true}`. Run the scheduler hourly; it enqueues projects due for their daily check, then exits:

```sh
uv run --env-file .env brief schedule
```

A database-free crawler is also available:

```sh
uv run brief crawl https://llmstxt.org/ --max-pages 5 --out evals/results/crawl.json
```

## Verify

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
TEST_DATABASE_URL=postgresql://brief:brief-local-only@localhost:55432/brief uv run pytest
uv run brief-eval --export evals/results/requests
# Optional paid model run:
uv run --env-file .env brief-eval --openai --out evals/results/live
```

Python checks cover `src`, `tests`, `evals`, and `scripts`. Every function requires parameter and return annotations, and mypy checks function bodies and generic type arguments. Heterogeneous SQL rows and JSON payloads use explicit `dict[str, Any]` types; injected services and callbacks use structural protocols.

Without `TEST_DATABASE_URL`, tests requiring Postgres explicitly skip. Integration tests create and remove a unique schema per test; they do not reset the database's existing tables. They cover concurrent claims, lease expiry, retries, atomic enqueue, snapshot preservation, authorization, scheduling, and API-to-extraction-to-refresh behavior. Synthetic HTML fixtures cover documentation, a service business, policies, and a product catalog.

The eval harness accepts any model through an executable adapter or saved JSON responses. `uv run brief-eval --baseline` is a deliberately weak metadata control and is expected to return a failing exit code. See [the eval guide](evals/README.md) for interpretation.

## Crawl boundaries

Uses Trafilatura for extraction and aiohttp for controlled fetching. There is no default page-count limit. Production crawls use a ranked initial sample and one model-guided coverage assessment, followed by targeted reading. Safeguards: 10 seconds and 4 MB for sitemap discovery, a 120-second crawl deadline, 50 MB aggregate downloads, 300,000 extracted evidence characters, 12-second request timeout, 2 MB per response, and 12,000 content characters per source. See [coverage-driven reading](docs/CRAWL_COVERAGE.md). Requests run in batches of four with at least 250 ms between starts, increased by robots crawl delay. Discovery retains a compact URL inventory (4 MB of new URLs and 1 MB of sitemap URLs), with unfinished work saved per project. Initial reading and the model’s 24 KB candidate shortlist are balanced across sections; refreshes reuse the saved page selection while owner direction is unchanged and recheck existing sources. Newly discovered URLs remain in the inventory. Unchanged content with an existing draft skips guide generation. See [saved discovery](docs/DISCOVERY_INVENTORY.md).

The crawler checks robots per origin, keeps redirects in the submitted hostname/`www` alias and path scope, and checks destination IPs during DNS resolution and socket creation. Environment proxies and cookies are disabled. It reports missing content and partial coverage. It does not render JavaScript, bypass bot protection, process PDFs, or verify Markdown alternatives yet. Subdomain documentation sites need their own submitted URL. Known resources are removed only after two explicit 404/410 observations in usable crawls; a timeout or an omitted page never means deletion.

## Backend deployment commands

Use one repository with separate Railway services for API and worker, plus managed Postgres. Use the same `DATABASE_URL` on both. Run migrations once as a pre-deploy command.

| Process | Command |
| --- | --- |
| Migrations | `uv run brief migrate` |
| API | `uv run uvicorn brief.api:app --host 0.0.0.0 --port "$PORT"` |
| Worker | `uv run brief worker` |
| Hourly cron | `uv run brief schedule` |

The cron must exit after dispatch; the worker stays running. Set `FRONTEND_ORIGINS` to exact frontend origins. Set `BRIEF_CREATION_KEY` for a private demo before exposing project creation publicly; send it via `X-Creation-Key`. This gate is not a production user quota system. Public rollout still needs per-user/project quotas and deployment-specific origin configuration. The default Compose password is for loopback-only local development.

## Frontend build and browser checks

`npm --prefix frontend run build` produces `frontend/dist` for Cloudflare Pages. Set `VITE_API_BASE` to the API origin at build time when using a separate API host. Use HTTPS sibling custom domains for frontend and API so SameSite cookies work; an unrelated `pages.dev` / Railway domain pair needs a same-origin API proxy or a different cookie strategy before deployment.

Run `npm --prefix frontend run test:e2e` with the local Postgres container running. The suite starts an isolated API on 8001 and Vite on 5175, creates the dedicated `brief_browser` database, and uses deterministic crawl/model fixtures. Your development API and worker can keep running. Chrome is required. Tests cover the full editing/review flow at four viewport widths, keyboard navigation, long-content scaling, accessibility checks, authentication recovery, and failure/retry states. See [browser QA notes](docs/BROWSER_QA.md).

Path-scoped guides share a site cache while keeping independent decisions and document history. The sidebar provides guide structure, switching, checks, and a ZIP export; the top bar's **Run details** exposes recorded crawl selection, fetch outcomes, cache behavior, and model usage. See [the demo and implementation notes](docs/GUIDES_AND_RUN_DETAILS.md) and [the frozen real hierarchy fixtures](evals/corpus/hierarchies/README.md).

## Publish, discover existing guides, and review changes

Run `uv run --env-file .env brief migrate` after updating to apply pending migrations.
In the editor, expand **Publish your guide** to publish the current saved draft.
The stable `/api/published/{publication_id}/llms.txt` URL serves only that version as
plain text without authentication. Editing, regeneration, and refresh proposals do
not change the published file. **Publish updated draft** updates the same URL;
**Unpublish** makes it return 404. Publication requires a current project revision,
no pending crawl/generation, and resolved source/decision conflicts.

The panel shows the exact installation URL on the owner's domain. Download the
published file, install it there, then use **Verify installation** to compare the
served text with the selected publication (ignoring leading/trailing whitespace).
Hosting a copy in Brief does not install it on another domain. Verification follows
same-origin redirects and reports the checked version and time.

The first normal worker crawl also checks for an existing `llms.txt` at the guide's
path and every ancestor through the origin root. **Existing website guide** can
repeat the check and compare captured files beside the saved draft. Checks use
public-address validation, same-origin redirects, robots rules, a 100 KB response
limit, and a 20-second request budget. HTML/error pages are rejected; a Markdown
title is required. This is discovery, not full llms.txt conformance or content
verification. Results retain the source URL, retrieval time, and content hash.

The **Change inbox** compares saved draft evidence with the latest captured sources.
Filter added, modified, removed, or answer-related changes while keeping flagged
answers available for review. An empty inbox does not prove the live website is
unchanged; check outcomes and crawl coverage still matter.

## Saved browser sessions

The home page lists projects created or successfully opened in this browser,
ordered by the most recent visit. Local storage keeps each project's URL, guide
name/path, last-opened time, and private access token. Reopening a saved session
restores its cookie automatically. Cookie-only visits are remembered too. **Remove**
forgets the list entry and saved token without deleting the server-side project.
Clearing browser storage removes this history; it is not synced between devices.
Sessions visited before this feature are added when reopened.

## Single-process demo runtime

Start the API with `BRIEF_EMBEDDED_WORKER=true uv run --env-file .env uvicorn brief.api:app --host 127.0.0.1 --port 8000` and **do not start a separate worker**. Use one API process. The worker runs on its own thread/event loop; live progress flows through bounded memory queues instead of Postgres polling. Durable jobs, evidence and documents remain in Postgres. See [live progress](docs/LIVE_PROGRESS.md) for recovery and deployment limits. Leave the flag off to retain the separate-worker deployment.
