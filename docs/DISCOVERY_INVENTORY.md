# Saved discovery and balanced reading

The crawler no longer stops discovering at 1,000 URLs. Discovery and reading have separate budgets:

- New page URLs occupy up to 4 MB of compact JSON URL bytes per pass. Existing snapshot sources and the entry URL are restored separately and do not consume that allowance.
- Sitemap URL bookkeeping has a separate 1 MB allowance. XML downloading retains a 10-second deadline and a 4 MB soft budget (the final response can cross it).
- Initial page reading rotates across scope-relative first-path sections, ranking useful entry pages within each section. One coverage assessment receives a deterministic, section-balanced shortlist within 24 KB of serialized URL text. The full inventory is never dumped into the model prompt.
- The existing reading deadline, download budget and extracted-text budget still apply. The model may decide that only a handful of pages need reading.

Unread URLs, pending sitemap files and offsets within partially processed XML files are compressed in Postgres per project. Saving is atomic with the crawl result, after job lease and project revision validation. They cascade on project deletion. The next crawl restores this frontier; it does not autonomously schedule extra paid model calls. Snapshot source URLs are restored separately for refresh checks.

Run details shows URL inventory bytes, restored URL count, pending sitemap count, the discovery trace and the coverage assessment. The assessment records full candidate count versus the model shortlist count. Unread pages remain explicitly reported as incomplete coverage.

## Verification

`tests/test_coverage_crawl.py` covers discovery beyond 1,000 URLs, section balance in the model shortlist, its byte bound, resuming within XML, and private persistent storage with deletion cleanup. Existing crawl tests cover request protections, sitemap cycles, scope filtering and reading after discovery budgets expire.

Frozen real-world replay: `uv run python evals/replay_sitemap_study.py inventory-replay.json`.

| Site scope | Previous discovered URLs | New discovered URLs |
| --- | ---: | ---: |
| Plausible docs | 1 | 1 |
| Tally help | 199 | 199 |
| Vercel docs | 1,000 | 2,002 |
| Shopify blog | 1,000 | 6,858 |

Counts include entry URLs. These are discovery results from recorded XML, not pages fetched or model-quality scores. Shopify stops on its XML download budget with 558 sitemap files pending. Plausible’s recorded sitemap does not enumerate its docs. The original replay report is preserved separately.

## Limits

This is bounded incremental discovery, not exhaustive indexing. The shortlist can miss useful deep pages, and path segments are a heuristic for site sections. HTML links rejected when the inventory is full are rediscovered when their source pages are read again; they do not have a saved HTML cursor. Sitemap offsets are positional, so edits to a sitemap between passes can shift entries; subsequent fresh discovery is still necessary. Sitemap response caching and last-modified-based skipping are not implemented here.
