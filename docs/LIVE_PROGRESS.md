# Live workspace progress

The private `/api/projects/{id}/events` endpoint streams lightweight Server-Sent
Events. It uses the existing project cookie/Bearer authorization and never puts
management tokens into stream URLs. Each payload contains a workspace version,
latest job status, and bounded progress metadata, not scraped page bodies or model
requests. Cache and reverse-proxy buffering are disabled.

The worker records actual crawler milestones, page titles/URLs, extracted page
counts, and generation/validation stages in `jobs.progress`. Six recent events
are retained, so refresh/reconnect restores useful context. Retry backoff replaces
old working messages. There are no invented percentages, simulated model reasoning,
or token-stream claims: generation remains one structured model request.

The API checks compact Postgres state once per second per stream, releases its DB
connection between reads, and sends only changes plus periodic heartbeats. Streams
close after one minute; native EventSource reconnects and re-authenticates. This is
SSE delivery with database polling, not Postgres LISTEN/NOTIFY. A production rollout
with many concurrent viewers should revisit connection capacity and fan-out.

The client refreshes the full workspace only on a version/status change. Progress
updates render independently, with elapsed time and an expandable recent-activity
list. A 15-second polling fallback also detects completion if streaming is blocked.
The stream is closed on unmount. The activity feed preserves the previous saved
preview while the next output is being produced.

Observed Tally run before this change: approximately 38 seconds for crawl/snapshot
work and 20 seconds for generation. This feature explains the wait; it does not
claim to speed those operations up.

Validation covers project authorization, reconnect state, stale-lease rejection,
real extraction milestones, retry messaging, worker persistence, browser reload,
completion without a manual refresh, and mobile overflow.

## Direct demo delivery (current optional mode)

Set `BRIEF_EMBEDDED_WORKER=true` and run a **single Uvicorn process**, without a separate `brief worker` process. FastAPI starts a worker on its own thread and event loop. Blocking worker code cannot block the HTTP event loop; model calls and extraction retain their thread offloading. This is event-loop isolation, not process isolation: CPU, memory and restarts are still shared.

Progress crosses to the API loop with `call_soon_threadsafe`, then wakes bounded one-slot subscriber queues. Slow viewers coalesce updates to the latest state and never block the crawler. The stream reads Postgres on connection and state invalidation (job completion/failure or API mutations), not on each page or heartbeat. Stage transitions checkpoint progress to Postgres; standalone workers retain per-event persistence and polling SSE. Job claims, idle checks, lease heartbeats, page caches and durable results still use Postgres.

The browser's 15-second fallback now fetches only when SSE is not open. Reconnects fetch the durable snapshot and overlay current in-memory progress. A process restart loses intermediate page events but retains job recovery through existing leases. A cancelled/finished job cannot be masked by a stale running-progress entry. In-memory progress is removed when a job exits, and queues are removed when viewers disconnect. Shutdown cancels the worker coroutine, with a bounded thread join; an already-running synchronous provider request may finish in its thread.

This mode needs no database migration, Redis or Postgres notifications. For multiple API processes or an external worker, leave it disabled and use the existing polling mode until cross-process transport is warranted.
