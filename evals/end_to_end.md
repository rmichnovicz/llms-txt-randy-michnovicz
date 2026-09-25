# URL-to-file frozen replay

This offline regression benchmark connects the production crawler, HTML extraction, generation contract validation, and `llms.txt` rendering. It complements the existing frozen-evidence generation evaluations: those start with extracted sources; this starts with a URL and authored HTTP responses.

## Reproduce without an API key

From the repository root after `uv sync --group dev`:

```sh
uv run python evals/end_to_end.py --baseline --out evals/results/end-to-end-review
uv run pytest tests/test_end_to_end_eval.py -q
```

Use a fresh output directory for every run; existing evidence is never overwritten. The required `--baseline` flag selects the existing metadata-only control. There are no network or model calls, and no database is needed. The control links every extracted source; perfect usable-source coverage is expected by construction and does **not** demonstrate good editorial judgment.

To evaluate a model separately, replace `--baseline` with `--adapter /absolute/path/to/adapter`. This uses the existing `brief-eval` executable protocol: one generation request JSON on stdin, one generation-result JSON on stdout, bounded to 90 seconds and 1 MB output per case. An adapter can incur API charges; no model adapter was run for the checked-in baseline report. Adapter failures produce an error row and missing-link metrics, preserve available artifacts, and make the command exit nonzero after remaining cases finish.

## Corpus and scope

[end_to_end_sites.json](end_to_end_sites.json) contains twelve synthetic, authored sites with predetermined `important_paths`. These labels are supplied to grading only; neither the generator nor crawler sees them. The fixtures are illustrative regression cases, not a random sample of real websites or evidence of broad real-world accuracy. Changes to labels or HTTP bodies change the report's corpus SHA-256.

| Scenario | Important URLs extracted / expected | Purpose |
|---|---:|---|
| Developer documentation | 3 / 3 | Quickstart and authentication |
| Retail shop | 3 / 3 | Product and returns policy |
| Local services | 3 / 3 | Service details and appointment steps |
| News publication | 3 / 3 | Article and editorial policy |
| Multilingual library | 3 / 3 | Spanish and English text |
| Sitemap discovery | 2 / 2 | Important page without a homepage link |
| Path-scoped documentation | 2 / 2 | Exclude an archive outside the entry path |
| Robots-blocked archive | 1 / 2 | Retain blocked important page as missing |
| Transient HTTP failure | 1 / 2 | Retain unavailable 503 page as missing |
| JavaScript-only application | 0 / 1 | Empty HTML shell is not evidence |
| PDF resource | 1 / 2 | Unsupported MIME type; no PDF extraction |
| Bounded crawl | 1 / 4 | Page budget exposes incomplete coverage |

The crawler runs with a frozen transport and a maximum of 12 pages per case (one for the budget case). Unknown URLs return 404. Sitemap discovery, robots checks, scope decisions, extraction, and the normal crawl budget logic are exercised. This is **not** a complete product end-to-end test: real HTTP/DNS and redirect transport, live availability, JavaScript rendering, model-guided coverage assessment and planning, durable jobs, persistence, and browser flows are outside scope. The PDF fixture is a MIME gate probe, not a full PDF document.

## What the metrics mean

Each report separates:

- **Crawl important-page coverage:** important URLs extracted / all labelled important URLs. Blocked, failed, unsupported, and unread pages remain in the denominator.
- **Generated important-page coverage:** important URLs linked in the rendered file / all labelled important URLs. Comparing this with crawl coverage helps locate generation-stage omissions.
- **Generated usable-source coverage:** extracted source URLs linked / all extracted source URLs. This diagnoses omission; maximizing it is not an editorial goal because useful guides can omit irrelevant sources.
- **Generated link precision:** rendered link destinations matching extracted source URLs / all unique rendered link destinations. This verifies destination provenance, not live reachability or factual accuracy.

Metrics use unique URL sets and micro-averages across cases; empty denominators are `null`, not a perfect score. Unknown destinations are listed explicitly. Schema validation and source provenance cannot establish factual entailment, useful descriptions, locale-aware curation, or visitor task success. Use the existing generation and consumer evaluations for those additional questions.

## Measured baseline and evidence

The checked-in [baseline report](reports/end-to-end-baseline.json) records **23/30 important URLs extracted and linked (76.7%)**, **23/23 extracted sources linked**, and **zero generation errors**. The seven missing URLs are deliberate probes of robots restrictions, HTTP failure, JavaScript shells, PDF extraction, and a page budget. They are retained as limitations, not removed to improve the score. Tests assert the per-case counts so a coverage collapse cannot pass merely by producing valid JSON.

Every run saves a copy of the corpus plus `report.json`, with corpus and system-prompt hashes, prompt version, Git revision, dirty-worktree status, and SHA-256 hashes of the runner, Python source files, and lockfile. A dirty worktree means the revision alone does not reproduce the run; use the hashes to verify the code. Per-case directories contain:

- `requests.json` and `crawl.json`: requested URLs, sources, observations, warnings, budget state, and extraction version.
- `request.json` and `response.json`: generation input and returned output, including an invalid response when one was returned.
- `llms.txt`: the actual rendered file, only when validation and rendering succeeded.
- `result.json`: metrics, missing URLs, errors, and diagnostic timing.

Replay timing is not a live-site performance estimate. Full local artifacts are under the ignored output directory; the checked-in report is a compact result snapshot. Re-run the command to inspect complete evidence.
