# Archived website refresh fixtures

Seven downloaded HTML files, three before/after pairs, and one auxiliary page.
`manifest.json` records the original URL, immutable Git URL or release branch URL,
retrieval timestamp, and SHA-256 of each body. Tests verify hashes before parsing.
The files are unmodified downloads; the HTML belongs to its original authors.

## Provenance and expectations

| Site | Before → after | Why the change matters |
| --- | --- | --- |
| [jQuery](https://github.com/jquery/jquery.com) | Website source commits dated 2023-08-28 → 2026-01-28 | Related-project maintenance/deprecation notices appear. Extraction detects changed evidence. The notices must **not** be treated as saying jQuery itself is deprecated. |
| [HTML5 Boilerplate](https://github.com/h5bp/html5boilerplate.com) | Built homepage commits dated 2023-03-01 → 2025-04-09 | Normalize.css, optimized analytics, and Modernizr are no longer advertised among the included features. Old descriptions should be reviewed. |
| [Python tutorial](https://docs.python.org/3.13/tutorial/controlflow.html) | Python 3.10 → 3.13 documentation | Wording, examples, and section organization differ. A guide must receive the newly scraped evidence rather than the old snapshot. |

These are **not Wayback captures**. jQuery uses archived website source fragments;
HTML5 Boilerplate uses committed built HTML. Dates are Git commit dates, not proof
of when a deployment went live. Python is a comparison of maintained release
branches downloaded together, **not two dates of the same live page**. For replay,
both Python pages are served at the same logical tutorial URL. Its upstream release
URLs can change; the local checksummed bytes are the reproducible archive.

The jQuery browser-support page is an additional genuine 2023 source capture. It
stays frozen in synthetic availability scenarios. We do not pretend to have a
complete historical crawl of any site. Uncaptured links are unavailable, never
silently converted to 404s; the crawl records partial coverage. Robots and missing
sitemap responses are synthetic. Tests explicitly inject 404, 410, 503, robots
exclusion, and cosmetic HTML changes; none are claimed as historical events.

## Offline regression coverage

Run from the project root:

```sh
uv run pytest tests/test_refresh_replay.py -q
TEST_DATABASE_URL=postgresql://brief:brief-local-only@localhost:55432/brief \
  uv run pytest tests/test_refresh_replay.py -q
```

Without a test database, four extraction/integrity tests run and twelve integration
cases skip. With Postgres, all 16 run in individually isolated schemas. No model
credentials, live websites, or archive service are needed.

The tests exercise the production crawler and Trafilatura extraction, real snapshot
reconciliation, durable worker jobs, generation validation/storage, and editor
operations. They check:

- Each actual before/after pair changes extracted evidence.
- Identical checks and a synthetic HTML comment avoid another model call.
- Changed evidence and active owner direction reach generation together.
- A refresh creates a proposal without overwriting manual wording.
- Accepting a proposal keeps previous versions and owner decisions.
- Old snapshot content remains immutable.
- First 404/410 retains a page; the second removes it and excludes it from the proposal.
- A successful scrape between 404s resets the removal sequence.
- 503, robots exclusions, and uncaptured URLs retain old evidence.
- Returning pages are re-added after confirmed removal.
- Complete crawl failure retains the last usable snapshot and document.
- Generation failure retains the draft while keeping the new evidence for recovery.
- Cache corruption is rejected before extraction.

Generation is a deterministic evidence-consuming test double. Passing tests prove
workflow behavior, **not** an LLM's ability to interpret changes, resolve conflicting
claims, or ask good questions. Existing dialogue/conflict evals remain separate.
The current fixtures cover developer/community websites; retail, healthcare, and
policy changes are not represented by genuine historical pairs yet. No new browser
coverage is claimed by these backend integration tests.

## Adding or updating captures

Download another original HTML version into this directory and add its provenance,
SHA-256, and reviewed expected change to `manifest.json`. Use a commit-pinned URL
when available. Keep old bytes rather than replacing them when an upstream release
URL changes. Review the extracted text as well as the HTML: a raw byte change is
not automatically a meaningful content change. Add explicit source/claim assertions
for new scenarios instead of treating generated output as its own ground truth.
