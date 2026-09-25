# Owner-question flow: Tally live-model check

Tested 2026-09-25 using the configured `gpt-6-sol` adapter and production generation
prompt. Website evidence was replayed from saved captures: 48 Tally root pages and
40 help-center pages. These were fresh model calls, not fresh crawls.

## What happened

The v5 prompt returned no questions for both the broad Tally guide and the help
section with a saved form-builder purpose. The first prompt revision asked a
useful workflow question on one attempt but skipped it on the repeat. Both
outcomes are retained in `reports/owner-priority-initial/`.

The final v6 prompt distinguishes a provisional balanced draft from a known owner
priority. It asks about materially different evidenced starting workflows when
priority is unresolved, and excludes already-scoped guides and simple sites.

| Final prompt case | Observed result |
| --- | --- |
| Tally root, two independent calls | Both asked which starting path should lead: new forms, existing forms, or product evaluation. Both produced complete drafts. |
| Tally help with saved purpose | No questions. |
| Simple portfolio | No questions. |
| Captured shipping-policy conflict | Asked which conflicting threshold applies; did not recommend either factual value. |

The existing mechanical grader passes 4/5 final samples. The shipping-conflict
sample fails its requirement for a recommended option (`recommendedOption` was
null, which the product contract permits). Its conflict question is present;
this remains an option-quality limitation, not a missing-question failure.

## Answering the real question

An isolated Postgres project received the actual generated question. A simulated
owner answer selecting existing-form migration was posted to the production
`/decisions` API, then processed by the real worker and model. The check verifies a
new saved draft, an answered question, suppression of its topic, and no pending
repeat question. See `reports/owner-priority-v6/answer-followup.json` for the
before/after first section and model metadata.

The browser suite separately uses deterministic fixtures: all five editor tests
passed, including answer, edit, remove, and dismiss flows. The backend editor,
generation-job, dialogue-evaluation, and model suites passed 36 tests. These
browser checks establish UI wiring, not live model quality.

## Reproduce

The frozen cases include the captured inputs, saved purpose, and evaluation
rubrics. This command makes paid model calls; use a fresh output directory:

```sh
uv run --env-file .env python -m brief.dialogue_eval \
  --cases evals/corpus/owner-priority-cases.json \
  --out evals/results/owner-priority-check
```

Two successful Tally samples demonstrate the behavior, not a reliability rate.
The proposed owner answer is a test preference, not a statement of Tally's intent.
