# Evidence-aware answer review

Saved answers now retain their source basis and snapshot ID. On a usable refresh,
Brief compares normalized extracted title, description, and content against that
basis. A changed or confirmed-removed source marks the active decision `needs_review`.
This is a source-change signal, not a claim that the owner is wrong.

Question answers track the question's cited source IDs. Manually added facts track
all currently known sources because they have no narrower source attribution.
Standalone editorial preferences do not expire on website changes. Legacy facts
and question answers are conservatively baselined against the latest snapshot at
migration time; their original historical basis cannot be reconstructed reliably.

Unavailable pages retain their previous evidence. A first 404/410, robots exclusion,
failed request, or incomplete crawl does not by itself reopen a decision. Confirmed
removal after two not-found observations does. Cosmetic HTML outside extraction,
normalized whitespace, and changes to other pages do not reopen an answer.

## Review experience

The Refine tab shows the saved answer and expandable before/after evidence, with
three actions:

- **Keep my answer** re-confirms the same decision against the current evidence.
- **Revise answer** opens the existing decision for editing; it does not create a
  second contradictory active answer.
- **Remove my override** deactivates that decision and generates from the remaining
  decisions and current website evidence.

Existing snapshots and decision events remain available for audit. Review status
is sticky until the owner resolves it. The current draft stays in place during
refresh; a model-generated revision is a proposal. An explicit owner resolution
regenerates the draft, following the existing decision-edit behavior.

Generation receives `needsReview` and the prior `reviewSources`. Prompt v3 instructs
it to omit disputed assertions, retain useful links, and explain the uncertainty.
The UI supplies the review card, so the model should not duplicate it as another
question. Answered question topics no longer suppress reconsideration when their
associated decision needs review. Validation rejects factual claims that cite an
unreviewed decision ID.

## Limits

Tracking is at the **source-page level**, not individual claim excerpts. An unrelated
change in the same page's extracted content may trigger review. A manually added
fact may trigger on any known page. Confirming an answer records owner authority;
it does not verify the fact externally. Validation checks provenance IDs, not
semantic entailment: it cannot mechanically prevent every disputed statement cited
against a source or written into an unstructured link description. Prompt behavior
still needs live evals. Version histories retain past wording intentionally.

## Demo

The opened local demo is fictional. Its initial website threshold is €300; the owner
says €450 “until the website is corrected”; the refreshed website says €600. The live
model omitted the threshold in its proposal and left the owner draft intact.
The initial draft and website captures are fixtures; the post-refresh proposal used
the configured live OpenAI model. Input/output metadata is saved under
`evals/results/conflict-demo/generation.json` (ignored by Git).

To create another demo, stop the local crawl worker, run
`uv run --env-file .env python scripts/demo_conflict.py`, then restart the worker.
The script creates a new project and prints its private management link. Do not use
“Check now” on the demo: its example.com subdomain is fictional, not a live store.
Keep, revise, and remove use the real application and running generation worker.

## Validation

- Seven Postgres regressions cover reopening, narrowed source scope, unchanged
  preferences, transient versus confirmed removal, provenance rejection, and all
  three resolution paths.
- Three browser tests cover keep/revise/remove with before/after evidence, retained
  draft, mobile width, and Axe accessibility checks.
- Existing archive refresh tests remain in the full backend suite.
- The live shipping demo checks that the proposal states none of the disputed amounts.

## Live model checks (September 24, 2026)

The first v3 prompt passed 11/13 original pilot checks. Both previous refresh
failures passed, but it over-revalidated an existing owner correction against
undated pages. A second apparent failure was a strict document regex: the model
correctly omitted the disputed amounts and explained uncertainty outside the
document, where that regex did not look. We did not silently relabel that run.

The final prompt explicitly distinguishes existing disagreement from changed
evidence. The owner-resolution case and both refresh/revalidation cases then
passed twice each: **6/6 targeted attempts**. This is a small regression check,
not a broad accuracy estimate or a full re-run of the corpus after the refinement.
Frozen requests/responses and the live workflow response are in
[conflict-review-v3](../evals/corpus/conflict-review-v3/).

## Change inbox (current behavior)

The document area now groups source diffs and flagged answers in a Change inbox.
Changes are computed against the saved draft's frozen generation sources, so a
later unchanged crawl does not hide an unaccepted update. Each item shows added,
modified, or removed evidence, saved guide sections that link to that page, and
whether a saved answer needs review. Recommendations are conservative rules based
on change type and evidence references, not model claims of semantic impact.
Manually edited wording may no longer match the original structured section map.

For source refreshes, resolving an answer now generates a **proposal** instead of
replacing the draft; this supersedes the earlier behavior described above. Retries
preserve that separation. The proposal comparison includes a unified document diff.
Flagged answers must be resolved before accepting a current proposal (enforced by
both API and UI). Ordinary direction edits against the draft's current snapshot
still regenerate the draft directly.

**Test proposed update** opens the existing reader panel with the proposal selected.
Choose an existing run and **Rerun same questions** for a frozen-evidence comparison,
or run new suggested/custom questions. Testing remains optional. Accepting the
proposal advances the evidence baseline and clears reviewed changes from the inbox.
There is no separate dismiss action that silently discards source changes.
