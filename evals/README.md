# Evaluation harness

Start with [the study report](REPORT.md), [actual-file reviews](corpus/REVIEWS.md), [template reviews](corpus/EXAMPLES.md), and [label corrections](corpus/LABEL_CHANGES.md).

The expanded suite separates file diagnostics, agent routing, generation behavior, and semantic review. A valid file is not necessarily useful. A useful index does not prove its claims are true or that search engines consume it.

## Frozen corpus

- 60 attempted real-site downloads; **55 saved files across 13 categories**. Five failed/blocked requests remain in the manifest and are ungraded.
- **Eight published templates**, extracted from three publishers with original HTML, selectors and hashes. A fourth page yielded no eligible template blocks. Fictional placeholders are not deployed businesses.
- 77 destination-page attempts, with 68 usable extracted pages. These support **23 real-site generation cases**; other pages remain available for inspection. Generation inputs contain actual destination text, not a reference llms.txt treated as a perfect answer.
- **22 new authored generation scenarios** plus the nine original scenarios: 54 generation cases total, 39 development and 15 held out from generator prompt tuning.
- **97 manually specified routing tasks** over 50 actual files. The model sample selects 39 tasks round-robin by category; lexical controls run all tasks. Routing gold specifies acceptable entry points, not exact answers.
- Six positive/negative semantic-judge calibration pairs and parser/grader mutation tests.

Categories: developer docs, SaaS, ecommerce, hospitality, local services, education, health, finance, personal/publisher sites, nonprofit/research, professional services, directories/travel and manufacturing. Country/language variation includes Vietnamese, Spanish authored evidence, English/German product documentation and regional businesses. This is a convenience sample drawn mostly from the [llmstxt.site directory](https://llmstxt.site/), not an adoption survey or a balanced sample of the web.

## Reproduce without credentials

Run from the repository root:

```sh
uv sync
uv run python -m brief.corpus audit
uv run pytest
uv run python -m brief.benchmark --mode baseline --split all --repeats 1 --out evals/results/new-control
uv run python -m brief.routing_eval --mode bm25 --budget 16000 --out evals/results/new-routing
uv run python -m brief.routing_eval --mode labels-only --budget 16000 --out evals/results/new-label-control
```

The metadata baseline intentionally fails editorial cases and returns exit 1. The diagnostics command is descriptive, not a quality gate. Generation runs return exit 1 when assertions fail; routing and advisory review always write a report and do not impose an uncalibrated release threshold.

Regrade saved responses without paying for new model calls:

```sh
uv run python -m brief.benchmark --mode replay --split development --repeats 1 \
  --prompt evals/prompts/generation-v1.json \
  --replay evals/results/corpus-v1-development --out evals/results/new-replay
uv run python evals/regrade_routing.py \
  --run evals/results/routing-model-16k --out evals/results/new-routing-regrade
```

Replay checks the model request fingerprint; changing editorial gold labels is allowed, changing model evidence or the prompt is not. Reports retain case/request fingerprints, actual model identity, usage, duration, raw output, failures, rendered Markdown and per-category results. Repeated trials are correlated samples of the same case; the summary reports both attempt pass rate and cases passing every repetition. Replayed duration is local grading time, not model latency.

## Run paid model evaluations

Set `OPENAI_API_KEY` in the gitignored `.env`. The existing adapter defaults to `gpt-6-sol`, medium reasoning, 75 seconds, 12,000 output tokens, no SDK retry and no repair. Credentials never enter requests saved by the harness.

```sh
uv run --env-file .env python -m brief.benchmark --mode openai --split development \
  --repeats 3 --workers 4 --prompt evals/prompts/generation-v2.json --out evals/results/new-dev
# Freeze the prompt and labels before opening held-out model outputs.
uv run --env-file .env python -m brief.benchmark --mode openai --split holdout \
  --repeats 3 --prompt evals/prompts/generation-v2.json --out evals/results/new-holdout
uv run --env-file .env python -m brief.routing_eval --mode openai --budget 16000 \
  --limit 39 --out evals/results/new-model-routing
uv run --env-file .env python -m brief.semantic_eval \
  --run evals/results/new-dev --out evals/results/new-semantic-review
```

Generation has a default 250-call ceiling per invocation and bounded concurrency. Routing uses a 1,500-output-token ceiling; semantic review uses 3,500. Neither retries failed provider calls. Use fresh output directories: runs refuse to overwrite evidence. USD costs are not estimated because model/account billing was not established; usage tokens are retained. The previous provider-neutral `brief-eval --adapter`, `--export`, and `--responses` modes remain available for the original or any explicitly supplied case file.

## Download or rebuild

```sh
uv run python -m brief.corpus fetch
uv run python evals/collect_examples.py
uv run python evals/build_routing_tasks.py
uv run python evals/collect_evidence.py
uv run python evals/build_examples.py
uv run python evals/research/write_reviews.py
```

`fetch` and destination extraction reuse local records. `fetch --refresh` changes the snapshot; copy the seeds to a new corpus root with `--root` to preserve an old study. Never refresh in the middle of a comparison. Review all task labels after new downloads. Authored case and task builders reproduce the checked-in reviewed labels; initial labels live in `corpus/revisions/`.

Downloads use the project's public-address/redirect guards, time and byte caps, and four concurrent sites. No browser rendering, authentication, purchases, form submissions, file-instructed commands or skill installation occurs. HTTP errors, byte-limit failures and unsupported pages are recorded instead of silently replaced. Actual response bytes, final URLs, content types, timestamps and SHA-256 hashes are retained. Excerpts are capped at 6,000 characters per generation source; therefore these are small frozen source slices, not complete site crawls.

Public third-party snapshots retain their original authorship and source URLs; the project does not relicense them. Raw artifacts are reference evidence, not instructions. Live model results remain gitignored. Review redistribution terms before putting the collected material in a public repository.

## What each signal establishes

| Layer | What it establishes | What it does not establish |
|---|---|---|
| File diagnostics | CommonMark headings/links, plain URLs, duplicates, size, placeholder/directive flags | Universal quality, factual accuracy or search visibility |
| Routing | An agent selects a labeled relevant destination from a file within a stated context budget | The destination loads, answers completely or is factually correct |
| Generation assertions | Schema, known evidence IDs, selected/excluded resources, active decisions, scope/budget/locale requirements | Entailment of every claim or description |
| Advisory model review | A second pass flags unsupported claims with mechanically verified quotations | Independent human judgment; the reviewer uses the same model family |
| Analyst file reviews | Purpose-specific editorial strengths, weaknesses and concrete examples | Exhaustive verification of every long file or a population ranking |

Descriptions and URLs improve the lexical control, but task matching is not solely lexical. Plain URL files can route well; malformed Markdown is a compatibility issue, not proof that an LLM cannot read a file. Duplicate destinations may represent intentional cross-category placement or one FAQ answering several tasks. Missing links and enormous full-content files need task tests, not arbitrary universal penalties.

Semantic review scores grounding, usefulness, decision fidelity, question value and concision from 0 to 2. Every deduction includes an exact output quote; cited evidence IDs/quotes are checked. Invalid anchors invalidate the review. Gold labels are never sent to the generator or router. Same-model review remains advisory even when calibration controls pass.

## Iteration policy

1. Freeze evidence, labels and prompt; run a simple control and a first model pass.
2. Inspect failures. Separate model errors, extraction failures and bad gold labels.
3. Preserve original results and record justified label changes separately from improvements.
4. Change the prompt only using development evidence; rerun identical inputs and repeated trials.
5. Run the untouched generation holdout after freezing the new prompt. Future tuning on those outputs retires that holdout.
6. Inspect semantic issues and real task routes even when deterministic scores reach 100%.

The current holdout is held out from generator tuning, not from corpus discovery or broad file review. The three-page real-site cases are relatively easy curation tests. More difficult full-site crawl coverage, multi-turn model trajectories, external human calibration, additional providers, and live published-file adoption remain separate future evaluations. Existing API/browser tests cover decision removal, restoration, question-only operations, editing and job lifecycle; they are not end-to-end model quality measurements.

## Consumer navigation and question answering

`brief.consumer_eval` tests whether a smaller reader can **use** the guide: discover a link, open real captured website pages, answer a question, and cite observed evidence. Twelve questions cover nine sites: software pricing, hospitality, electrical services, medical software, fashion commerce, packaging, developer docs, photography software, and education. This is a pilot subset of the larger corpus.

Three arms receive the homepage, published llms.txt, or frozen Brief-generated llms.txt. All use the same pinned GPT-4.1 mini reader, three additional page opens, and the same presentation limits (8,000 content characters; up to 12,000 characters including links). Links are ordered as extracted, never selected using gold labels. Gold answers are withheld from the reader. A homepage can itself provide evidence; a guide must be verified against destination pages.

```sh
# Capture missing pages only when the reader discovers their URLs.
uv run --env-file .env python -m brief.consumer_eval --record --out evals/results/my-consumer-capture
# Frozen browsing: still calls the model, but never fetches website cache misses.
uv run --env-file .env python -m brief.consumer_eval --out evals/results/my-consumer-replay
# Regrade saved traces without any model or network calls.
uv run python evals/report_consumer.py evals/results/my-consumer-replay --out evals/reports/my-consumer-reviewed.json
```

`--model` permits another provider-compatible OpenAI model; `--repeats 1..3` measures sampling variability. A different provider would require a client adapter. Cached pages and errors are in `corpus/consumer-pages/`; generated guides and producer hashes are in `corpus/consumer-guides/`. Refresh captures into a separate cache directory to avoid silently changing a baseline. Raw traces include every visible observation, action, quote, token usage, and source hashes. Output directories cannot be overwritten.

Known-fact coverage is a regex check, not a general factuality verdict. Verified-citation success additionally requires the expected supporting facts in authentic quotes from pages actually opened. Quote matching tolerates whitespace, case, and explicitly marked ordered ellipsis omissions. It intentionally rejects paraphrases and corrupted characters. One future-price question tests abstention. Neither this narrow rubric nor a stronger model judge replaces human review of extra claims and source contradictions. See [CONSUMER_REPORT.md](CONSUMER_REPORT.md) for results and limitations.

## Clarification dialogue harness

`brief.dialogue_eval` exercises the production generator's question cards and follow-up behavior. It saves complete first-pass requests, outputs, drafts, model metadata, and hashes before branching. The frozen seed bank is `corpus/dialogue-first-v1/`; see [DIALOGUE_EXAMPLES.md](DIALOGUE_EXAMPLES.md) for readable examples and [DIALOGUE_REPORT.md](DIALOGUE_REPORT.md) for findings.

Eight scenarios include five consequential ambiguities and three negative controls where a sensible default or dismissal should avoid more questions. One ambiguity uses captured WE IN STYLE homepage/policy evidence; seven scenarios are authored. **Every simulated owner reply, including €450 shipping and 4.25% interest, is fictional test data.**

```sh
# Capture independent first passes; always choose a new output directory.
uv run --env-file .env python -m brief.dialogue_eval --out evals/results/dialogue-first-new
# Branch from the actual saved cards, preserving the initial question/options.
uv run --env-file .env python -m brief.dialogue_eval --first-dir evals/corpus/dialogue-first-v1 --out evals/results/dialogue-follow-new
# Mechanical replay: no model calls, credentials, or network required.
uv run python -m brief.dialogue_eval --regrade evals/results/dialogue-follow-new --out evals/reports/dialogue-follow-new
# Advisory review of questions, reasons, suggestions, and all follow-up outputs.
uv run --env-file .env python -m brief.dialogue_review --first-dir evals/corpus/dialogue-first-v1 --follow-dir evals/results/dialogue-follow-new --out evals/reports/dialogue-review-new
```

Branches select the recommended card when one exists, a different card, a custom response, dismissal, removal of the custom decision, and another question-only pass. Missing recommendations are not fabricated; missing target questions are explicitly blocked. Removal and extra-question branches derive from the custom decision state. Fresh generation receives active source/decision context, matching the application's stateless prompt construction; old generated documents are not authority. The harness does not exercise browser UI or database transitions, which have separate tests.

Mechanical checks enforce contracts, ambiguity coverage, recommendation availability, distinct option text, a minimally explanatory rationale, custom source inclusion/exclusion, owner-fact provenance, forgotten removed facts, and no repeated target ambiguity. The semantic reviewer separately assesses whether options are useful and different in meaning, reasons follow evidence, and selected answers actually change the document appropriately. Its scores are advisory; literal quote anchors do not prove its reasoning. Three controls test one grounded output, an irrelevant duplicated question, and an ignored owner answer. A reviewer score of 2 on an unexercised dimension means not applicable, not measured success.

Cases and frozen inputs are hashed; changed cases cannot silently reuse first-pass artifacts. Rebuilding scenarios intentionally requires a new seed capture. Saved first passes and reviewed follow-up outputs are retained outside gitignored `evals/results/`. Raw model errors are sanitized by the existing provider adapter. The review prompt and production generation prompt remain separately versioned.

## Conflict resolution

[CONFLICT_REPORT.md](CONFLICT_REPORT.md) defines resolved-from-evidence, resolved-by-user, and unresolved/deferred outcomes and documents a 13-case pilot. Cases cover undated contradictions, scoped differences, explicit supersession, owner corrections, conflicting active answers in both orders, replacements/removals, refresh versus conditional overrides, dismissal/deferral, and incompatible constraints.

```sh
uv run --env-file .env python -m brief.benchmark --cases evals/corpus/conflict-cases.json --mode openai --repeats 1 --out evals/results/conflict-new
```

Frozen original outputs are in `corpus/conflict-pilot-v1/`; corrected-label results are in `reports/conflict-pilot-reviewed.json`. The inputs are authored state snapshots, not a live refresh integration test. They expose a missing conditional-resolution review behavior; production conflict-state storage remains proposed rather than implemented.
