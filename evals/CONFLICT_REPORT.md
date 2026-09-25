# Conflict resolution: evidence, user decisions, and changed sources

Conflict handling needs its own regression suite. Detecting a contradiction is not the same as resolving it. A user dismissing a question is not evidence that either claim is true.

## Recommended product behavior

Use explicit outcomes:

1. **Resolved from evidence:** the claims concern different regions, versions, delivery methods, or dates; or an authoritative document explicitly supersedes the other. Explain the distinction. A page being crawled later is not sufficient evidence of factual recency.
2. **Resolved by the user:** the owner confirms a fact, selects an authoritative source, narrows the applicable scope, or explicitly replaces an earlier answer. Keep the decision ID and its authority/scope. A preference to emphasize a claim is not verification of the claim.
3. **Unresolved or deferred:** neither source wins. Omit the disputed assertion, qualify the uncertainty, or link the sources while continuing to produce a useful draft. Offer confirmation, scope clarification, and defer/omit options. Do not recommend a factual winner merely to populate a recommended card.

For incompatible active answers, ask which to keep or whether they apply to different scopes. Do not infer “latest wins” from list order. An explicit edit/replacement can retire the older answer. Removing a resolution should recompute from remaining active decisions and current evidence; it should not restore an old draft as factual authority.

A conflict card should show the two claims and excerpts, their source/decision provenance, why they appear incompatible, the affected document text, and what each resolution changes. When the evidence clearly settles a conflict, this can be a reviewable explanation rather than another mandatory question.

## The missing lifecycle concept

A resolution should record **the evidence it was based on**, not just the question topic. Proposed fields:

- Stable issue ID plus claim scope (product/version/region/effective period where known).
- Source IDs and hashes of the relevant claim excerpts; full source snapshot IDs for audit.
- Resolution type, chosen fact/source/scope, associated active decision ID, and any expiry condition.
- Status: unresolved, resolved, deferred, or needs review.

On refresh, compare the relevant claim evidence against that basis. A changed footer should not reopen shipping policy. A materially changed policy should trigger review if it challenges the resolution. A transient fetch failure is unavailable evidence, not a retraction. “Needs review” must not silently remove an owner override or assert the new source is true. Preserve the last accepted document while presenting a candidate revision.

This was a proposed extension at the time of the v1 pilot. **Source-page-level evidence tracking and automatic review are now implemented**; see [decision review](../docs/DECISION_REVIEW.md). Claim-excerpt tracking and semantic conflict adjudication remain unimplemented. The following describes the pre-v3 application: Current generation receives sources, active decisions, and dismissed topic strings; it lacks structured conflict status and the evidence basis of each resolution. The application has separate snapshot/decision history, but the generator does not receive that history in a form that supports this comparison.

## Pilot results

Thirteen authored state-based cases ran through the existing production generator (`brief-generation-v2`) using the configured model. All amounts and owner statements are fictional. Inputs and raw outputs are frozen in [conflict-pilot-v1](corpus/conflict-pilot-v1/report.json).

| Behavior | Reviewed mechanical outcome |
|---|---:|
| Ask about undated source disagreement | Pass |
| Distinguish compatible region/delivery scopes | Pass |
| Respect explicit dated supersession without asking | Pass |
| Apply owner correction with decision provenance | Pass |
| Ask about conflicting active owner facts, both orderings | 2/2 pass |
| Apply explicit replacement; forget removed values | Pass |
| Reopen source disagreement after removing all overrides | Pass |
| Defer or dismiss without adopting a disputed value | 2/2 pass |
| Ask which incompatible editorial constraint to relax | Pass |
| Revalidate a conditional owner override against a dated differing site policy | **Fail** |
| Revalidate that same condition with the topic previously dismissed | **Fail** |

**11/13 passed after label correction.** This is one trial per state, not a measured accuracy rate or a complete end-to-end state transition test. Related cases share authored evidence; they are not independent samples. Checks cover expected questions, obvious claim/provenance constraints, and safe omission; they do not prove all semantic details. An assistant inspection of the saved outputs supports the specific observations below, not broad production reliability.

### Important failure

The owner correction says €450 “until the website is corrected.” The current homepage and dated policy say €600. The generator acknowledges the discrepancy but keeps presenting €450 as owner-confirmed and asks no question. It does the same with a dismissed shipping topic.

It should ask whether the conditional override is still valid; it should **not** simply switch to €600. The supplied evidence does not prove that the source update fulfills the owner's condition. This is an unresolved authority/expiry question, not a rule that newer pages always win.

### Good behavior

Reversing the order of two conflicting owner answers does not make the generator pick a different winner. Both outputs ask which owner correction remains authoritative. Explicitly deactivating one answer resolves the question. Removing both makes the original source conflict visible again.

A dismissed or deferred issue does not cause the generator to invent a settled threshold. The guide remains useful by linking the policy while omitting amounts. Different country/delivery scopes are correctly treated as compatible, and explicitly superseded terms do not prompt unnecessary questions.

### Grader correction

Initial labels unnecessarily required both homepage and policy links in every draft. That penalized good curation even when conflict handling was correct, including the one-link constraint scenario. The requirement was removed; original labels remain in `corpus/revisions/conflict-initial-labels.json`. Original outputs and grades were preserved. The original report shows 6/13; [the reviewed report](reports/conflict-pilot-reviewed.json) shows 11/13 under the corrected labels. The two revalidation failures are unchanged.

## Running and extending

```sh
uv run --env-file .env python -m brief.benchmark --cases evals/corpus/conflict-cases.json --mode openai --repeats 1 --out evals/results/conflict-new
```

Use more repetitions and independently authored scenarios before comparing prompts. Future additions should include effective dates versus crawl timestamps, changed claim excerpts versus unrelated page edits, deleted/unavailable sources, user-selected source authority, resolution scope, and conflicting locales/versions. Test the actual refresh/decision storage path once structured conflict tracking exists.

Four new tests cover conflict questions versus false positives, decision provenance, removal, deferral, hidden gold labels, and the decision-order permutation. No production prompt was changed merely to pass this small suite.
