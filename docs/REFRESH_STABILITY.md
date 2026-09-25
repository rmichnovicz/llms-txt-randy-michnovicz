# Minimal source-refresh edits

A Plausible docs refresh (project `066890a1-5aef-420a-adde-8b4614713994`) expanded captured evidence from 37 to 39 pages. Existing source objects were identical. The previous generator received no saved document, so it recomposed the guide: renaming sections, moving links, dropping a link and paraphrasing most descriptions.

Prompt v5 receives a frozen `refreshBaseline`: saved draft Markdown and source IDs added, changed or removed relative to that draft's generation evidence. It requests minimal maintenance edits, preserving unaffected wording and order, while allowing corrections when new evidence contradicts existing claims. Current evidence and unresolved-decision rules outrank baseline text. The output remains a complete, validated guide.

The baseline is included only for generation against a different source snapshot with the same decision revision. Initial generation, question-only requests and changed user decisions retain the clean-context behavior. This prevents removed answers from regaining authority through old drafts. The baseline is pinned in the durable job and included in the exact model-cache key; retries do not read a moving draft.

One live replay using the exact Plausible inputs produced just two inserted resource lines, with no existing lines removed or rewritten. The request, response, candidate and diff are retained under ignored `evals/results/refresh-stability/`. This is a targeted observed improvement, not a guarantee of deterministic outputs or a full quality re-evaluation. There is no rigid diff-size limit: substantive evidence changes may legitimately require broader edits.

Regression coverage in `tests/test_generation_jobs.py` verifies the pinned baseline, exact added-source IDs, no changed/removed sources for additions, question-only exclusion and decision-revision exclusion.

The original proposal changed 42 added / 39 removed lines. The v5 replay changed 2 added / 0 removed lines. The verified response was saved through the normal lease/revision-checked generation completion path as a new proposal, without accepting it or modifying the draft.
