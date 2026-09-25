# Sitemap discovery study

Captured September 24, 2026 (America/Los_Angeles). No model calls or page-body
crawls were made. The production replay permits one page attempt, served locally
as unavailable, so it isolates sitemap discovery.

| Scope | Old discovered URLs | New production replay | Old/new sitemap requests | Old/new MB |
| --- | ---: | ---: | ---: | ---: |
| Plausible `/docs/` | 1 | 1 | 1 / 1 | .018 / .018 |
| Tally `/help/` | 199 | 199 | 1 / 1 | .074 / .074 |
| Vercel `/docs/` | 305 | 1,000 | 1 / 1 | 1.031 / 1.031 |
| Shopify `/blog/` | 9 | 1,000 | 3 / 4 | .156 / 1.415 |

Counts include the submitted entry URL for comparability. The study strategy
reports also retain sitemap-only counts, which exclude that additional entry.
Discovered is not fetched, extracted, or proven useful. The 1,000 URL discovery
budget remains; there is still no default page-count crawl limit.

## Findings and implementation

The three-request sitemap cap misses useful sections in large indexes. Keyword
ranking alone was wasteful: on Shopify it visited other locales' blogs first.
Exact scope-path priority plus shallower-path ordering finds the intended section
sooner. A second issue was more directly fixable: slicing the first 1,000 `loc`
elements **before** applying path scope discarded Vercel docs entries later in the
same response. Applying the discovery cap after filtering improves coverage with
no additional network request there.

Production now scans indexes under a 10-second discovery deadline and 4 MB body
budget, within the existing overall crawl budgets. A response can cross the byte
threshold by up to the normal 2 MB response cap; no further sitemap is started.
Sitemap references are deduplicated, same-site validated, and bounded to 10,000
known sitemap URLs. Page robots checks, request pacing, private-IP protections,
and hardened XML parsing remain. Discovery stats appear in Run details.

Plausible's captured sitemap has no docs URLs: expanding traversal cannot create
missing entries. Normal HTML-link discovery remains necessary. Tally's single
sitemap already works. This supports shipping the narrow discovery fixes, not
claiming a universal speedup or better model answers.

## Reproducibility and limits

`evals/study_sitemaps.py` records the old algorithm and two prototypes. It reuses
saved responses when available, avoiding repeated downloads during iteration.
`evals/replay_sitemap_study.py` runs the actual production crawler against only
recorded responses; it cannot access the network. Reports map source URLs to
compressed capture files. Compression here is archive storage, not evidence that
the origin serves `.xml.gz` sitemaps.

Recorded fetch time sums were about 0.51 seconds for Vercel in both strategies and
0.57 versus 2.51 seconds for Shopify. These reuse first-observed request durations,
including fetcher pacing; they are not independent repeated wall-clock benchmarks.
The production replay uses immediate local responses, so it verifies selection
and byte counts, not real timeout behavior. Four selected sites are not a
representative benchmark. No downstream guide quality or token-cost benefit was
measured. Sitemap response caching, `lastmod` scheduling, and gzip-origin support
remain deferred.
