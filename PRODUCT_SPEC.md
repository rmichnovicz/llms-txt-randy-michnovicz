# Brief — Product specification

This document describes Brief’s product goals, user experience, and design constraints. It covers both the current application and planned capabilities. See the [README](README.md) for setup and current features, and the [architecture](ARCHITECTURE.md) for technical decisions.

The current application supports guided generation, saved decisions, direct Markdown editing, version review, explicit publication, installation verification, and source monitoring. General conversational editing, automatic publication of refreshes, and browser rendering remain planned; the workflows below describe their intended behavior.

## 1. Product and user

Brief turns a public website into a useful `llms.txt` guide and maintains it as the website changes. A language model proposes sensible defaults from the captured website content. Users can refine the guide through optional questions, open text, or direct document editing.

Primary design audience: a technical marketer or software engineer responsible for a company website. The crawler and generator must also work on documentation sites, agencies, blogs, and other public websites.

Promise: **Create a clear guide to your website for AI assistants, shape it through conversation, and keep it current.**

The product improves the artifact and its freshness. It does not promise external AI rankings, citations, or universal adoption of the file.

### Core principles

- Generate a useful document before requiring any answers.
- Every interaction leaves a complete document available; informational replies need not create a new version.
- Ask about consequential choices, not details the model can reasonably infer.
- Offer recommendations, option cards, and free text together.
- Let users continue the interview voluntarily.
- Make remembered decisions visible, editable, and removable.
- Preserve explicit intent across website refreshes.
- Keep drafts separate from published output.

## 2. Scope

### Core experience

1. Public URL submission and bounded website crawl.
2. Site summary and valid `llms.txt` generation.
3. Workspace with conversation and document preview/editing.
4. Optional interview with recommended answers and open text.
5. Saved decisions and pending questions with edit/remove/dismiss controls.
6. Immutable document revisions and a simple text diff.
7. Download, explicit publication, a stable hosted file URL, and installation verification.
8. Private management link, without account signup.
9. Daily scheduled checks and a manual “Check now” action using the same pipeline.
10. Change detection, regeneration, update summary, and protection of the last good published output.
11. Deployment, setup documentation, and a reproducible demo.

### Further improvements

- Email when a meaningful update is published or review is needed.
- Select text in the preview to scope a conversational edit.
- Browser rendering fallback for sites with little extractable HTML.

### Deferred

Accounts, teams, billing, public directory, external publishing integrations, arbitrary uploads, general web research chat, `llms-full.txt`, agent answer benchmarks, per-field automatic merging of direct edits, and adaptive monitoring schedules.

## 3. Primary workflow

### A. Start

Landing page contains:

- Website URL input, accepting a domain or full public HTTP(S) URL.
- Optional “Anything we should know?” input.
- Primary action: **Create guide**.

No mandatory audience selector, crawl configuration, or interview.

Submitting creates a project, a durable crawl job, and a private management URL. The project is scoped to the submitted host and, when supplied, path. Related domains can appear as links; they are not automatically crawled without bounds.

### B. Discover and generate

Show actual phases: discovering pages, reading content, organizing the guide, ready.

Display factual counters when available: discovered, fetched, failed, and included. Do not show invented percentages. Work continues if the tab closes; reopening the management link resumes the status view.

The model produces:

- A short plain-language summary of the business or site.
- A structured document, rendered into `llms.txt` by code.
- Zero to three initial questions worth asking.
- Short explanations of important selection choices or limitations.

Output should use an H1, an optional summary/context area, and H2 link-list sections following the current specification. Validate actual requirements separately from recommended quality practices. Prefer verified Markdown alternatives when practical; never invent `.md` URLs.

### C. Review workspace

Desktop layout: conversation on the left, current document on the right. Narrow screens use Conversation / Document tabs.

Persistent header:

- Site identity and draft/published status.
- **Decisions** button with unresolved-item count.
- **Download** and **Publish latest**.
- Management-link copy action.

Document pane:

- Rendered preview by default; **Edit Markdown** toggle.
- Revision selector and **View changes** relative to the previous or published version.
- Generation warnings, such as incomplete crawl coverage.

Conversation pane:

- Site summary and brief generation result.
- One current question card, if useful.
- Recommended option, alternatives, and free-text response.
- Composer: “Ask a question, add context, or describe a change…”
- **Ask me another question** / **Keep grilling me** action.

Example question:

> Your website covers a software platform and consulting. I gave the platform priority. Should either lead?
>
> Software first — recommended / Equal emphasis / Consulting first

Example free-text answer:

> Software first, but consulting is how enterprise customers get started.

Example response:

> Updated the overview and retained consulting under enterprise onboarding. Saved this direction for future updates.

The new revision appears in the document pane. The user may download or publish at any time.

## 4. Interview and open conversation

### Interview behavior

- Initial round contains up to three material questions, presented one at a time.
- No fixed minimum: zero questions is valid when the site is straightforward.
- Every question offers a recommended answer where evidence supports one, plus free text.
- **Use recommendation** accepts and saves the recommendation.
- **Dismiss** leaves the current draft intact and suppresses that question under the current evidence.
- After the initial round, offer deeper questioning. Additional rounds are user-initiated and have no fixed product-level question cap; requests still have operational limits.
- Do not repeat answered or dismissed questions unless new evidence materially changes their premise.
- If no worthwhile question remains, say so rather than producing filler.
- Asking for another question alone does not mutate the document.

### Supported messages

- Answer a question or correct site understanding.
- Add a factual statement supplied by the user.
- Request a global or targeted document revision.
- Ask why a resource or claim is present.
- Ask for more questions or focus the interview on a topic.

The assistant can reply without changing the document. It does not need arbitrary tool access or an unrestricted browsing loop.

### Evidence and inference

The model may infer useful structure, audience, emphasis, and summaries from the site. Preserve the distinction between extracted source facts, user-provided facts, and uncertain inferences internally.

Accept user-supplied facts even when absent from the crawl, recording their origin. Do not fabricate concrete pricing, certifications, features, or URLs to fill a gap. Uncertainty can produce a question, omission, or appropriately qualified wording.

Source text is data, not instructions that can override the user's decisions or the generation rules.

## 5. Decisions drawer

Two sections: **Needs attention** and **Saved decisions**.

### Needs attention

Contains unanswered questions and detected website changes that conflict with explicit decisions. Routine site changes belong in the update summary and do not all require review.

Question actions: answer, use recommendation, dismiss.

Conflict example:

> **Review suggested: Free plan**
>
> You said Acme offers a free plan. The pricing page now describes a trial.
>
> Compare sources / Update my answer / Keep my answer / Remove my answer

Keeping an answer acknowledges this evidence; the identical issue should not reappear on every scheduled check.

### Saved decisions

Each item displays:

- A concise statement of the preference or user-supplied fact.
- Originating question or message.
- Active/inactive status and whether it is included in the published policy.
- Edit and remove actions.

Examples:

- Prioritize developers.
- Treat consulting as enterprise onboarding.
- Exclude recruiting content.
- User-provided fact: Enterprise onboarding includes a migration assessment.

### Edit/remove semantics

1. Edit or deactivate the decision immediately in the draft policy.
2. Generate a new draft from current source evidence and the remaining active decisions.
3. Show the document diff and offer undo.
4. Preserve the published document until explicit publication.

Removing a decision means “return this topic to the model's judgment based on the site,” not “always exclude this topic.” The resulting wording may remain if current source evidence independently supports it.

The originating chat message remains visible with “No longer applied.” Historical messages are not authoritative generation instructions. Superseded or inactive answers must not regain influence when constructing model context.

If regeneration fails, retain the previous document and mark it as not yet reflecting the updated decisions; offer retry. Never imply that a failed revision succeeded.

## 6. Direct editing

The editor uses a Markdown textarea with preview and validation.

Saving creates a manual revision. Subsequent conversational revisions use the current document and active decisions, preserving unrelated manual text where possible; users can inspect the diff and restore an earlier version.

Exact automatic merging of arbitrary manual edits is out of scope. Once a manually edited document is published, scheduled refreshes continue generating proposed drafts but require review before replacing that published version. Explain this beside the update setting. Users can explicitly re-enable automatic replacement after reviewing the generated draft.

Publishing always identifies the precise document revision being published.

## 7. Publication and access

### Access

- Separate unguessable private management token and public file identifier.
- Management access permits editing, publication, and monitoring controls; public access only reads the published file.
- Store a hash of the management token; do not expose it in public output or routine logs.
- Explain that anyone with the management link can edit and that losing it means losing access in the first release.
- No public directory or domain-global ownership: unrelated users submitting the same domain get separate projects.

### Publishing

Before first publication, the user can preview and download, but no draft is exposed at the public endpoint.

**Publish latest** atomically records the chosen revision and snapshots its active decisions as the published policy. The public URL remains stable across publications. Failed validation leaves the previous published revision intact.

Suggested route: `/p/{publicId}/llms.txt`, served as UTF-8 plain text with an ETag derived from content and cache revalidation.

Hosting here does not install the file on the customer's domain. Provide a short explanation and a copyable command to pull it into their site's public directory. Downloaded/uploaded copies remain static unless the user integrates a refresh mechanism.

## 8. Automated updates

Monitoring becomes available after publication, with a clearly labeled daily schedule and pause control. **Check now** invokes the same work as the scheduler. One active crawl per project; overlapping triggers reuse or skip the active job.

### Refresh pipeline

1. Discover URLs again within the same scope and budgets.
2. Fetch pages and compare normalized main content and metadata with stored observations.
3. Distinguish added, modified, confirmed removed, unchanged, and unavailable pages.
4. If relevant evidence is unchanged, update `last_checked_at` only and avoid a generation call.
5. On change, generate using the published decision snapshot, not unpublished conversation edits.
6. Validate the result. If output is identical, do not create a duplicate published version.
7. Publish automatically when enabled and there is no material conflict or unsafe crawl degradation.
8. Otherwise retain the current public file and put the proposed revision or conflict into review.

A timeout, crawl budget cutoff, or a page missing from one discovered sample is not proof of deletion. Retain prior evidence for transient failures; retry suspected removal and require repeated not-found evidence before automatic removal.

### Draft conflicts

If an unpublished user draft exists, a scheduled check must not overwrite it. Store the new crawl and update proposal separately, mark review needed, and pause automatic replacement for that check. The user can refresh their draft from latest sources using their draft decisions before publishing.

### User-visible status

Example:

> Hosted version updated today at 9:14 AM
> Added the Salesforce guide and refreshed the pricing description.
> View changes · Download latest
> Last checked: 9:14 AM · Next check: tomorrow

Keep last checked, last published, and last check outcome separate. Show “Hosted version updated,” not “Your website is up to date.” Email notifications are planned.

## 9. Logical implementation

The implementation uses a React frontend, a Python/FastAPI backend, and Postgres. Its main components are:

- Web UI and API.
- Persisted background crawl/generation jobs that survive closing a tab.
- Database for projects, source snapshots, conversations, decisions, and document revisions.
- Scheduled trigger for due projects.

Keep deployment small and give each service a clear responsibility. Reuse the same crawler, generator, and validator for initial creation, manual refresh, and scheduled refresh.

### Minimal records

| Record | Essential contents |
| --- | --- |
| Project | Input URL/scope, management-token hash, public ID, draft and published revision pointers, schedule/status |
| Crawl run | Trigger, state, timestamps, counters, limits reached, errors |
| Page observation | Crawl ID, canonical URL, fetch outcome, title, description, normalized content/hash |
| Message | Role, text/card response, related question and revision |
| Decision | Type, statement, source message, active state; immutable snapshots on document revisions |
| Review item | Question or source conflict, evidence references, status, resolution |
| Document revision | Markdown, content hash, source crawl, decision snapshot, origin, change summary |

Version chat-driven writes against the current revision so a stale response cannot overwrite a newer edit. Process one mutation at a time per project in the first release.

### Model responsibilities

- Infer identity, audience, useful grouping, selection, and summaries.
- Propose material questions and recommended options.
- Interpret answers into visible saved decisions.
- Produce revised document structure and a brief change explanation.
- Identify possible conflicts between changed sources and explicit decisions.

### Code responsibilities

- Crawl budgets, URL normalization, fetch safety, persistence, scheduling, and access control.
- Hashing and factual change counts.
- Schema validation, deterministic Markdown rendering, and URL membership checks.
- Versioning, publication, and enforcement of active decision state.

Use source IDs in generated link selections so the model cannot accidentally invent destinations. User-added URLs must pass the same URL validation and fetch checks.

## 10. Crawler boundaries and failure UX

Crawls use bounded concurrency, a 120-second deadline, a 50 MB download budget, and a 300,000-character evidence budget, with no default page-count limit. Make limits visible and keep selection stable where possible. Use robots/sitemaps and internal links, extracting main content and metadata rather than only titles.

Public HTTP(S) targets only. Block private/internal network destinations and recheck redirects. Apply request/body limits, rate limiting, robots rules, and bounded sitemap traversal.

- Invalid or blocked target: actionable error, no fabricated output.
- Some failed pages: usable partial result with coverage warning.
- Thin JavaScript shell: explicitly state limited extraction; browser rendering is planned.
- LLM failure: retain prior draft/published file and allow retry; initial generation shows a recoverable failure.
- Failed scheduled run: preserve published output and expose the failed check status.
- Confirmed source/decision conflict: retain publication and request review.

## 11. Acceptance criteria

### Generation and refinement

- A URL produces a downloadable, validated file without any interview answers.
- Output links correspond to known resources; unavailable Markdown alternatives are not invented.
- A question-card answer and a free-text answer both update the document and saved direction.
- Users can request further questions after the initial round or stop at any point.
- An explanatory chat message can leave the document unchanged.
- Removing an answer produces a new draft without treating that answer as active guidance; the historical message remains marked inactive.
- A removed instruction does not reappear because it was present in chat history.

### Publication and monitoring

- Public URLs reveal only the published document and never grant editing access.
- Publishing a new version preserves the same public URL.
- An unchanged check does not create a new document version or publication timestamp.
- A body-content change with unchanged metadata is detected.
- A new relevant page can be included on refresh using saved published preferences.
- A transient fetch failure does not delete a previously included resource.
- Scheduled work does not overwrite an unpublished draft or publish unpublished decisions.
- Manual document edits follow the explicit review-before-replacement behavior.

### Demonstration

Use a controlled public fixture website with two content states and several real sites of different types. Show:

1. Generate from state A.
2. Answer a question to prioritize developers; publish.
3. Remove a decision, inspect the revision, then restore it.
4. Change fixture to state B: add an integration page and change existing body content.
5. Run Check now and show the update respecting published preferences.
6. Run an unchanged check; show no new version.
7. Demonstrate a failed fetch preserving the last good output.

## 12. Development priorities

- Deploy and verify the complete generation, review, publication, and monitoring workflow.
- Improve conversational editing while preserving explicit decisions and manual revisions.
- Add selective browser rendering and verified Markdown alternatives for difficult sources.
- Expand evaluation across website types, with held-out evidence and repeatable refresh scenarios.

Crawl reliability and evidence quality take priority over additional interface features. New automation should preserve the last usable draft and published version when a step fails.

## 13. Reference material

- [llms.txt format and intent](https://llmstxt.org/)
- [Artifacts: conversation and versions](https://support.anthropic.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)
- [Chat and document editing](https://help.gamma.app/en/articles/8033284-how-do-i-edit-my-content-with-ai)
- [Guided creation with optional questions](https://help.gamma.app/en/articles/15002203-how-do-i-create-with-agent-in-gamma)
