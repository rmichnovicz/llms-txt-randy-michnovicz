# Coverage-driven reading

Production crawls no longer default to 50 page attempts. The worker ranks discovered
URLs, reads an initial sample of eight usable pages, then makes one structured model
request to assess coverage against active saved owner direction. Eight is a planning
checkpoint, not a maximum or a claim that every site needs eight pages. Small sites
can exhaust discovery earlier.

The model selects exact discovered URLs in priority order, explains why they matter,
and identifies topics missing from the initial excerpts. The crawler reads that
selection in order. There is no fixed number of selected pages: tests exercise a
66-page plan. Previously known sources are always retained in the refresh reading
queue, even if the model omits them. Unvisited sources are not treated as removed.

Refreshes reuse the saved selection while owner direction is unchanged, rechecking
its selected URLs and previously saved sources without another planning call. New
URLs remain in the discovery inventory rather than expanding the guide on every
refresh. Changing owner direction triggers a fresh assessment. With an existing
draft, unchanged source content does not enqueue guide generation. Reused plans
are labeled in run details and do not report the original model usage as new usage.

Discovery uses robots-declared sitemaps (or the conventional `/sitemap.xml` path
when none are declared), HTML links, and the saved discovery frontier. The initial
reading sample is balanced across path sections. The assessment receives a
section-balanced shortlist within 24 KB of serialized URL text, rather than the
entire URL inventory. See [saved discovery](DISCOVERY_INVENTORY.md).

The surrounding application also implements existing `llms.txt` discovery,
path-scoped guides, and persistent page caching. The first normal worker crawl
checks for an existing guide at the submitted path and its ancestors. Scoped
guides share a site cache while retaining independent decisions and history.
Cached pages are revalidated with ETag or Last-Modified headers; a 304 reuses
extracted content, while pages without validators are downloaded again. Robots
and sitemap responses do not have a persistent conditional cache. See [guide and
cache behavior](GUIDES_AND_RUN_DETAILS.md) and [existing-guide checks](../README.md#publish-discover-existing-guides-and-review-changes).

## Safeguards and failure behavior

- 120 seconds overall, including the assessment call.
- 50 MB aggregate returned bodies, including robots/sitemaps. This is checked after
  each response; up to four page responses may already be in flight when it is reached.
- 300,000 characters of newly extracted source text/title/description, bounding the
  evidence supplied downstream.
- Existing per-request timeout, 2 MB response limit, robots checks, public-address
  validation, and site/path scope restrictions remain in effect.
- New page URL inventory is bounded by 4 MB of compact JSON URL bytes per pass;
  sitemap URL bookkeeping has a separate 1 MB allowance. Existing source URLs
  and the entry URL are restored separately. There is no fixed 1,000-URL or
  three-sitemap cap.
- Sitemap discovery has a 10-second deadline and 4 MB soft download budget;
  the last response can cross that byte budget. Unread URLs, pending sitemap
  files, and partial XML offsets are saved per project for subsequent crawls.
  These are safety constraints, not a target site coverage claim.
- An explicitly supplied `--max-pages` remains available for diagnostics/tests;
  its default is now unset and values greater than 50 are accepted.

Unknown model-selected URLs are rejected. An unavailable/invalid assessment falls
back to ranked discovery under the resource budgets; it does not pretend that
coverage was judged sufficient. Without a configured provider, that same ranked
fallback applies. The diagnostic CLI does not invoke the model.

One planning request means one additional model cost and potential latency. It
reuses the configured provider/model, persists model usage metadata, and does not
run an open-ended planning loop. The assessment sees bounded excerpts, not whole
pages, and the selected reading pass is not followed by a second assessment.
Consequently, “coverage plan finished” means its selected URLs were attempted, not
proof that every information need was resolved. Unusable pages remain crawl notes.

## Visible results

SSE announces the coverage checkpoint and the planner's explanation. Snapshot
coverage records stop reason, bytes downloaded, unvisited discovered URLs, the
assessment rationale, planning-time gaps, selected URLs, and model metadata. The
Sources tab explains a finished curated pass versus a time/download/evidence
safeguard. Planning gaps are explicitly labeled as observations from the checkpoint,
not claims about final completeness.

## Validation

Regressions cover >50-page default and planned crawls, targeted expansion, model
reading order, retention of previously known URLs, specific entry pages ahead of
generic help articles, invalid/invented URLs, budget stops, structured model output,
and the worker's use of saved owner direction.

During the original coverage-planner implementation, a live Tally smoke test with no owner direction read 26 pages in 36.3 seconds,
including planning, and downloaded 13.3 MB. It finished the selected coverage pass.
An earlier iteration chose 32 additional pages and hit a 20 MB safeguard; its
initial sample included low-value template articles. That exposed a ranking issue,
which was corrected, and the aggregate safeguard was set to 50 MB. Both outputs
remain in `evals/results/coverage-tally/`; they are not additions to the eval corpus.
These are historical functional smoke runs, not measurements of the current
crawler's speed or quality. The [saved-discovery replay](DISCOVERY_INVENTORY.md#verification)
separately compares old and current discovery limits against recorded XML;
discovered URL counts do not measure pages read or generated-guide quality.
