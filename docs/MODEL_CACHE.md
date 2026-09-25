# Model request reuse

Production document and interview generation uses a Postgres result cache. It is
scoped to the private guide project, not shared across customers or sites. The key
hashes the complete request (system prompt, serialized evidence/decisions, output
schema and prompt version), provider endpoint, model name, reasoning effort, and
output budget. Different requests never receive approximate or semantic matches.

Only successful, source/decision-validated outputs are stored. Hits are validated
again against current contracts before use. The cache stores compressed JSON
outputs and original metadata, not API keys or another copy of the input prompt.
Entries are reusable for seven days; each write prunes expired entries and retains
at most 100 entries for that guide. Deleting the guide cascades to its cache.
Model aliases can change upstream during the seven-day window; set
`BRIEF_MODEL_CACHE=false` on the worker to bypass reuse when fresh sampling matters.

A hit reports `cache.status=hit`, zero new attempts, no new usage, and preserves
original metadata separately. Run details exposes these fields; job progress also
announces reuse. Normal immutable-version and job-lease checks still apply. This
cache begins empty: prior versions are not retroactively treated as cached results.
Concurrent identical calls are not globally coalesced; the existing per-project
job constraint serializes production generation jobs.

Reader test runs, eval CLIs, and crawl planning remain fresh calls. In particular,
repeating a reader test does not reuse its previous answer. The cache does not
resolve missing API credit for any new request.

## Less repeated input

Generation prompt v4 uses compact JSON and references identical historical decision
sources by `reviewSourceIds`, resolved against current sources. Historical sources
that differ remain in full `reviewSources`; source content is never summarized or
truncated by this optimization. Source evidence precedes changing decisions in the
serialized input, keeping a stable prefix for provider prompt caching. Actual
provider cached-token counts remain in the SDK usage metadata; a hit is not assumed.

Five recent persisted inputs shrank by 0.4–1.2% in character count because they had
little duplicated decision evidence. A regression fixture with a duplicated long
source shrank by more than 35%. These are character measurements, not token-cost
estimates. Live model quality and provider-cache savings have not been re-measured
because the configured API account exhausted its prepaid credits.

Billing-specific 429 errors now identify credit/quota problems and are not retried
automatically. Error bodies and credentials remain excluded from user-facing errors.
