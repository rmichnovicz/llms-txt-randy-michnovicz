# Real Wayback refresh demo

This experiment is isolated from Brief's application code. It serves **one actual archived homepage**, not a complete historical website.

Replay URL: https://brief-history-demo.pages.dev/site/

- Before: HTML5 Boilerplate, **2022-12-31 20:29:13 UTC**.
- After: HTML5 Boilerplate, **2025-05-31 19:48:32 UTC**.
- Original capture URLs, retrieval timestamps and SHA-256 hashes: `manifest.json`.
- Original decompressed response bodies are kept in `captures/`. These are Wayback downloads, not our older Git-source fixtures.

The older homepage advertises Normalize.css, an optimized analytics snippet and Modernizr. Those descriptions are absent from the newer homepage. This demonstrates changed website evidence, not independent proof that every underlying feature was removed.

## Present the demo

Run commands from the repository root. The installed Wrangler CLI uses your existing Cloudflare login.

1. Reset the public replay to the older capture:
   ```sh
   uv run python scripts/wayback_demo.py before --deploy
   ```
2. Submit `https://brief-history-demo.pages.dev/site/` to Brief and wait for its draft.
3. Add a saved **fact**: `The starter template includes Modernizr and an optimized Google Analytics snippet.` Wait for regeneration. It is supported by the old captured page.
4. Show the source website changing, at the exact same URL:
   ```sh
   uv run python scripts/wayback_demo.py after --deploy
   ```
   Wait for deployment completion. Check https://brief-history-demo.pages.dev/provenance.json says `after` before refreshing Brief.
5. Click **Check now**. Explain: the crawler reads a real public website; this is not an injected snapshot. The source changes and the saved fact should need review. Inspect before/after evidence and the proposed document. A pending fact review prevents acceptance.
6. Choose **Remove my override** to let current captured evidence determine wording, wait for the proposal, inspect and accept it. An unchanged check should reuse the content and avoid another generation.

The provider may phrase the draft and questions differently. The captured website inputs and HTTP responses are repeatable. Allow time for model generation and Pages deployment. No Wayback access is needed during the presentation.

## Serving details

`wayback_demo.py` verifies source hashes, strips executable/embedded content and external stylesheet references, resolves archive links against the original origin, and adds a visible historical-replay banner. Captured prose is not rewritten. The site is labeled as an independent demo, not an official mirror. An explicit CSP prevents scripts, forms and external asset loading.

Robots and the sitemap are synthetic replay infrastructure. Only `/site/` is in the sitemap; uncaptured resources return 503, not a misleading deletion. Strong ETags are derived from served bytes: same capture yields 304 with its validator, switching captures yields 200 and a new ETag. Metadata and provenance remain separate from the crawled scope. Deploying either version affects this shared demo site, so coordinate concurrent demos.

## Verify

```sh
node --test demos/wayback/replay.test.mjs
uv run ruff check scripts/wayback_demo.py
```

Live run evidence and private project credentials are in gitignored `evals/results/wayback-demo/`. Do not publish those files. Captures and the build script contain no credentials.

## Revert

No app code, database schema or fetch security exceptions were introduced. Delete only the dedicated **brief-history-demo** Pages project in Cloudflare and remove `demos/wayback/` plus `scripts/wayback_demo.py` if abandoning the experiment. Existing Brief deployments are independent. The test project can be removed separately through the normal application workflow. Do not use a broad git reset; the workspace contains other ongoing work.
