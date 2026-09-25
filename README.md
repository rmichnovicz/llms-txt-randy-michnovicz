# Brief

Turn a website into an `llms.txt` guide you can review, test, and keep up to date.

[Open the live app](https://brief-llms-txt.pages.dev/). Project creation requires
a private demo creation key.

Give Brief a URL and it reads the site, picks useful pages, and writes a draft.
You can answer follow-up questions to shape it, edit the Markdown yourself, or
try visitor questions to see whether the guide leads to the right sources.
When you're happy with it, download the file or publish a hosted copy.

Brief also checks for website changes. Updates arrive as proposals for you to
review, so a background crawl won't overwrite your published guide.

The app uses React, Python/FastAPI, and Postgres. The frontend runs on Cloudflare
Pages and the backend on Railway. Generation uses GPT-6 Sol with medium reasoning.
See [deployment instructions](docs/DEPLOYMENT.md) for setup and redeploys.

<details>
<summary>See the editor</summary>

![Brief editor showing a generated guide, source coverage, and reader tests](docs/images/editor-demo.png)

This screenshot uses the browser tests' sample site.

</details>

## Run locally

You'll need Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22.12+,
and Docker Compose with Docker running. Generating guides and running reader
tests requires an OpenAI API key and incurs API charges. You can crawl sites and
inspect their sources without a key.

Install dependencies and start Postgres:

```sh
uv sync
npm --prefix frontend ci
cp .env.example .env
docker compose up -d --wait
uv run --env-file .env brief migrate
```

Add `OPENAI_API_KEY` to `.env`, which is excluded from Git. The example file
already has the cookie and origin settings for local development.
`OPENAI_MODEL` defaults to `gpt-6-sol`.

Start the API with its embedded worker:

```sh
BRIEF_EMBEDDED_WORKER=true uv run --env-file .env uvicorn brief.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend:

```sh
npm --prefix frontend run dev
```

Open [Brief at localhost:5173](http://localhost:5173).

The embedded worker handles crawl and generation jobs inside the API process.
Use one API process with this setup, and don't start another worker. To run the
API and worker separately, leave `BRIEF_EMBEDDED_WORKER=false` and run these in
separate terminals:

```sh
uv run --env-file .env uvicorn brief.api:app --reload
uv run --env-file .env brief worker
```

Jobs and documents stay in Postgres in either mode. The embedded worker uses its
own thread and event loop, with in-memory queues for live progress. See
[live progress](docs/LIVE_PROGRESS.md) for recovery behavior and deployment limits.

<a id="five-minute-reviewer-walkthrough"></a>

### Try it out

Start with a small site that serves HTML, such as `https://llmstxt.org/`.

1. **Create a draft.** Enter the URL and let Brief read the site. Check the
   resulting summary, sections, and links against the original pages.
2. **See what it read.** Open **Run details** for page selection, crawl warnings,
   and model usage. Brief may finish its selected pages without reading the
   whole site.
3. **Ask a visitor question.** Expand **Test this guide** and choose **Run
   suggested tests**, or write your own question. You can inspect the answer,
   the pages the reader opened, and its source quotes. These tests use saved
   page content.
4. **Refine the guide.** Answer an optional question or edit and save the
   Markdown. **Rerun same questions** lets you compare the two versions against
   the same sources.
5. **Download or publish.** Choose **Download file** to get the Markdown, or
   expand **Publish your guide** to host a saved version at a stable URL.
   To put it on your own domain, download it and upload it there.

You can also watch the browser tests exercise the flow using fixed sample data:
run `npm --prefix frontend run test:e2e` with Postgres and Chrome available.
This doesn't need a model key. See [browser QA](docs/BROWSER_QA.md) for details.

### Troubleshooting

| Problem | What to try |
| --- | --- |
| Can't connect to Postgres | Run `docker compose ps`. The local database uses port `55432`. Run migrations once it's ready. |
| Sources appear, but there's no draft | Add `OPENAI_API_KEY` and restart the worker or embedded API. Choose **Check now** after a crawl-only run, or **Retry** after a failed generation. |
| Jobs stay queued | Check that a worker is running and uses the same `DATABASE_URL` as the API. |
| Can't open a project in the browser | Use `http://localhost:5173`, set `BRIEF_SECURE_COOKIES=false` locally, and check `FRONTEND_ORIGINS`. |
| Very little content was found | Read the crawl warnings. JavaScript-only pages, PDFs, and bot challenges aren't supported yet. Try an HTML section of the site. |

## Working with guides

You can create separate guides for different parts of a site, such as `/docs/`
and `/help/`. They share a page cache, but each has its own decisions and version
history. Use the sidebar to switch guides, check their structure, or download
all of them as a ZIP. [Guide details](docs/GUIDES_AND_RUN_DETAILS.md) covers this
workflow.

### Publishing and installation

**Publish your guide** makes a saved version available as plain text at
`/api/published/{publication_id}/llms.txt`. Anyone with that URL can read it.
Further edits and generated proposals stay private until you choose **Publish
updated draft**. The URL stays the same. **Unpublish** makes it return 404.

Before publishing, finish any pending crawl or generation and resolve source or
decision conflicts. Publication checks the project revision to avoid publishing
from stale editor state.

The panel shows where to install the file on your domain. After uploading it,
choose **Verify installation** to compare the served file with your published
version. The check follows same-origin redirects, ignores surrounding whitespace,
and records the version and time checked. Brief's hosted copy and the file on
your domain are separate; updating one won't update the other.

<a id="publish-discover-existing-guides-and-review-changes"></a>

### Existing files and website changes

On the first worker crawl, Brief looks for an existing `llms.txt` at the guide's
path and each parent path up to the site root. **Existing website guide** lets
you repeat that check and compare what it found with your draft.

Discovery respects robots rules, validates public addresses, follows only
same-origin redirects, and allows up to 100 KB per response within a 20-second
budget. It rejects HTML and error pages and requires a Markdown title. Finding a
file doesn't establish that its contents are accurate or fully conform to the
format. Brief saves its URL, retrieval time, and content hash for reference.

The **Change inbox** compares the sources behind your saved draft with the latest
captured pages. Filter by added, changed, removed, or answer-related content, then
review any saved answers affected by those changes. Check crawl coverage too:
an empty inbox only means no changes were found in the captured evidence.

### Returning to a project

The home page remembers projects you've created or opened in this browser.
Local storage holds the URL, guide name and path, last visit, and private access
token. Opening a saved project restores its session cookie when a token is
available. Cookie-only visits appear in the list too.

**Remove** forgets the local entry and token; it doesn't delete the project.
Clearing browser storage clears the list, and it doesn't sync between devices.
Older projects appear there the next time you open them.

## What the crawler can read

Brief uses Trafilatura to extract content and aiohttp to fetch pages. It starts
with a ranked sample, asks the model which areas need more coverage, and reads
those pages next. There's no default page-count cap, but each crawl has limits:

| Resource | Limit |
| --- | --- |
| Sitemap discovery | 10 seconds and 4 MB |
| Whole crawl | 120 seconds and 50 MB of downloads |
| Extracted evidence | 300,000 characters total; 12,000 content characters per source |
| Each request | 12 seconds and 2 MB per response |
| Discovery inventory | 4 MB of new page URLs and 1 MB of sitemap URLs |

Requests run in batches of four, at least 250 ms apart, with longer delays when
robots rules require them. The initial sample and the model's 24 KB URL shortlist
include pages from different sections. Unfinished discovery is saved for later.

Refreshes reuse the selected pages while your instructions stay the same and
recheck existing sources. New URLs stay in the discovery inventory. If the
content hasn't changed and a draft already exists, Brief skips generation.
See [crawl coverage](docs/CRAWL_COVERAGE.md) and
[saved discovery](docs/DISCOVERY_INVENTORY.md) for the details.

The crawler stays within the submitted hostname, its `www` alias, and the chosen
path. It checks robots rules per origin and validates destination IPs during DNS
resolution and socket creation. Environment proxies and cookies are disabled.
Submit documentation on another subdomain as its own URL.

JavaScript rendering, PDFs, bot-protection bypasses, and verified Markdown
alternatives aren't supported yet. Missing content and partial coverage appear
in crawl notes. Brief only removes a known resource after two explicit 404/410
responses in usable crawls; a timeout or an unread page doesn't count as deletion.

To try the crawler without Postgres:

```sh
uv run brief crawl https://llmstxt.org/ --max-pages 5 --out evals/results/crawl.json
```

## API and scheduled checks

The running API has [interactive docs](http://localhost:8000/docs).
`POST /api/projects` accepts `{"url":"https://example.com/"}` and returns a
project ID, job ID, and one-time management token. Send that token as
`Authorization: Bearer <token>` on project routes. The server stores its hash.
In the browser, a private link exchanges the token in its URL fragment for a
site-scoped HttpOnly cookie, then clears the fragment from the address bar.

| Endpoint | Use |
| --- | --- |
| `GET /api/projects/{id}` | Read job status, the latest usable source snapshot, draft, and proposal. |
| `GET /api/projects/{id}/snapshots/{snapshot_id}` | Inspect a saved crawl attempt, including failed attempts with a snapshot ID in the job result. |
| `POST /api/projects/{id}/refresh` | Check the website again. Requires `Idempotency-Key`; active jobs are reused and repeated completed manual requests are deduplicated. |
| `POST /api/projects/{id}/generate` | Generate from the latest usable snapshot without recrawling. Requires `Idempotency-Key`. |
| `PATCH /api/projects/{id}/monitoring` | Enable daily checks with `{"enabled":true}`. |

Snapshots include source text and metadata, coverage, warnings, and URL changes.
Drafts and proposals include Markdown, questions, their source snapshot, and model
usage. Generation captures the active decisions along with its source snapshot.
Decision changes rebuild the draft; source refreshes produce proposals. Failed
crawls and model calls preserve the previous usable sources and documents.

In the UI, `/s/{site_id}` opens the original guide and
`/s/{site_id}?doc=/docs/` opens a guide for that path. All guides share site
access while keeping their edits and history separate.
`GET /api/projects/{site_id}/document?doc=/docs/` resolves the corresponding document.

Run the scheduler hourly to queue projects due for their daily check:

```sh
uv run --env-file .env brief schedule
```

The scheduler exits after adding jobs. A running worker picks them up.

## Tests and evaluations

[CI](.github/workflows/ci.yml) installs locked dependencies and runs Python
checks, Postgres integration tests, the frozen benchmark, the frontend build,
and Chrome browser tests. Benchmark results and browser artifacts are saved
with the run.

Run the Python checks locally:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
TEST_DATABASE_URL=postgresql://brief:brief-local-only@localhost:55432/brief uv run pytest
```

Without `TEST_DATABASE_URL`, Postgres tests are skipped. Each integration test
creates and removes its own schema, leaving existing tables alone. Tests cover
job claiming and recovery, retries, authorization, scheduling, snapshot
preservation, and the crawl-to-refresh flow. Python lint and type checks cover
`src`, `tests`, `evals`, and `scripts`.

Build the frontend and run browser checks with:

```sh
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Browser tests need Chrome and the local Postgres container. They start a separate
API on port 8001 and Vite on 5175, using the `brief_browser` database and fixed
crawl/model data. Your development API and worker can keep running. The suite
covers editing and review at four viewport widths, keyboard navigation,
accessibility, long content, session recovery, and failure/retry flows.
See [browser QA notes](docs/BROWSER_QA.md).

For generation and crawl evaluations:

```sh
uv run brief-eval --export evals/results/requests
uv run python evals/end_to_end.py --baseline --out evals/results/end-to-end-review
# Optional paid model run:
uv run --env-file .env brief-eval --openai --out evals/results/live
```

The [URL-to-file benchmark](evals/end_to_end.md) replays 12 authored sites through
crawling, extraction, validation, and rendering. Its baseline simply links every
extracted source. It helps catch coverage regressions, but doesn't measure model
quality or success on live websites. Give each run a fresh output directory.

The generation harness also accepts executable model adapters and saved JSON
responses. Its separate `uv run brief-eval --baseline` command runs a deliberately
weak metadata control and is expected to fail some checks. The
[evaluation guide](evals/README.md) explains how to interpret the results, and the
[real-file study](evals/REPORT.md) records the historical model runs and their limits.

## Deployment

See [deployment and redeploy instructions](docs/DEPLOYMENT.md) for the full setup.
Run the API and worker as separate Railway services sharing a managed Postgres
database and the same `DATABASE_URL`. Apply migrations before deploying updated
code.

| Process | Command |
| --- | --- |
| Migrations | `uv run brief migrate` |
| API | `uv run uvicorn brief.api:app --host 0.0.0.0 --port "$PORT"` |
| Worker | `uv run brief worker` |
| Hourly cron | `uv run brief schedule` |

The worker stays running; the cron exits after dispatch. Set `FRONTEND_ORIGINS`
to the exact frontend origins. For a private demo, set `BRIEF_CREATION_KEY` and
send it through `X-Creation-Key`. Public access still needs per-user/project
quotas. The Compose password is only for local development on the loopback interface.

The frontend build produces `frontend/dist` for Cloudflare Pages. The Pages
worker proxies `/api/*` to its `API_ORIGIN` binding, keeping browser sessions on
the same origin. Leave `VITE_API_BASE` unset for that setup. If browsers connect
directly to a separate API host, set `VITE_API_BASE` at build time and use HTTPS
sibling custom domains so SameSite cookies work.

## More about the project

- [Product goals and design](PRODUCT_SPEC.md)
- [Architecture and tradeoffs](ARCHITECTURE.md)
- [Feature guides](docs/README.md)
- [Frozen examples of hierarchical guides](evals/corpus/hierarchies/README.md)
