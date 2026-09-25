# Test this guide

The editor can test a saved draft or proposed update with a small reader model. Expand **Test this guide**, run suggested questions or enter a customer question, then inspect answers, quotations, and the pages the reader opened. After editing and saving, **Rerun same questions** compares the new document with an earlier run.

## What stays fixed

A question set freezes the document's captured source snapshot and the other guides' saved Markdown. Suggested questions are written from a sample of source content without showing the question writer the document being tested. Each suggestion must name a captured page and contain a verifiable supporting quote. Custom questions have no expected-source oracle.

Each run points to an immutable document version. Reusing a question set preserves questions, evidence, related guides, and reader model. It changes the entry document only. This isolates document revisions from later website changes; start a new question set when you want fresh evidence. The latest 20 runs are shown in the editor; older runs remain stored.

## Reader and checks

The reader defaults to `gpt-4.1-mini-2025-04-14`; `BRIEF_READER_MODEL` configures new question sets. It initially receives only the question and entry guide. It can open three links exposed by observed guides, including saved child guides. Reads use frozen captured pages, never the live network. Missing captures and invented links become explicit observations. Expected URLs and reference quotes are withheld from the reader.

Results distinguish:

- **Expected source cited:** the answer includes verified quotes and cites the question's expected page.
- **Quotes verified:** a custom-question answer quotes pages it opened.
- **Needs review:** missing or invalid quotations, or an unexpected cited page.
- **Could not answer:** the reader abstained or exhausted its browsing budget.

These are navigation and provenance checks, not proof that every claim is correct. An alternative source may answer a question legitimately. Suggested questions can be imperfect and favor material present in captured evidence. Question generation samples at most 12 pages, using 6,000 characters each; the reader sees at most 24,000 characters per guide and 12,000 per page. Following a related guide does not automatically make that guide's uncaptured pages available.

## Implementation and validation

Migration 007 adds immutable question sets and version-linked runs. Authenticated `POST /api/projects/{id}/tests` enqueues an idempotent durable `evaluate` job. The existing worker and SSE progress stream handle execution, retries, and updates. Testing does not modify the document. Reports retain the document hash, model metadata, actions, answers, and citation checks.

Backend tests cover evidence isolation, invented citations, missing pages, layered navigation, browsing budgets, validated suggestions, immutable comparisons, ownership, and idempotency. Browser tests cover suggested/custom questions, failed runs and retries, persisted results, regression comparison, unsaved-edit protection, and accessibility at 320px and 1280px.
