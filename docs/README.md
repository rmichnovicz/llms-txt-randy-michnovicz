# Documentation

Start with the [project README](../README.md) for setup, verification, and deployment
commands. The [architecture](../ARCHITECTURE.md) explains implementation decisions
and planned behavior. The [product specification](../PRODUCT_SPEC.md) describes
the user experience and development priorities.

## Editor and review

- [Guides and run details](GUIDES_AND_RUN_DETAILS.md): document scopes, navigation, exports, and crawl diagnostics.
- [Decision review](DECISION_REVIEW.md): evidence, saved answers, and conflict handling.
- [Guide tests](GUIDE_TESTS.md): versioned reader tests and their limits.
- [Live progress](LIVE_PROGRESS.md): event delivery, recovery, and the optional embedded worker.

## Crawling and refreshes

- [Crawl coverage](CRAWL_COVERAGE.md): reading budgets and source selection.
- [Discovery inventory](DISCOVERY_INVENTORY.md): saved URLs and continued discovery.
- [Refresh stability](REFRESH_STABILITY.md): stable reading plans and change detection.
- [Model cache](MODEL_CACHE.md): reuse boundaries and invalidation.

## Verification and evidence

- [Browser QA](BROWSER_QA.md): editor flows, accessibility, and failure states.
- [Evaluation guide](../evals/README.md): commands, grading, and interpretation.
- [Real-file study](../evals/REPORT.md): evaluation results and limitations.
- [Sitemap study](../evals/reports/sitemap-study/README.md): measured discovery behavior.
- [Refresh fixtures](../tests/fixtures/refresh/README.md): archived sources and capture provenance.
- [Hierarchy fixtures](../evals/corpus/hierarchies/README.md): frozen examples of scoped guides.
