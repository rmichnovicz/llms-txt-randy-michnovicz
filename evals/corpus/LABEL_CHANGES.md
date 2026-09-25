# Label and grader change log

All original response artifacts are retained. The first label sets are frozen in `revisions/`. Corrections below do not count as model improvements. Model-facing generation evidence was unchanged by these corrections.

## Generation labels, v1 → reviewed

- `docs-version-separation`: the initial gold excluded the archived v1 page unconditionally. The actual task included migration, and the response explicitly marked the archive. Revised expectation allows the link only with a version/archive qualifier. Current v3 and migration resources remain required. This is a rubric correction, not evidence that the model learned to omit archives.
- `real-lowellbooks`: the initial gold required the programming category based on the index label. Its fetched body showed an unrelated-looking title. The model's omission was defensible, so that category is no longer required. Search remains required. We did not relabel the mismatched book as a programming book.
- `preference-is-not-fact`: forbidden certification language applies to the **document**, not explanations that correctly say certification is unverified. This was corrected before the initial model run.
- Metadata control: empty source descriptions were emitted as empty strings, which violate the existing output schema. Changed the baseline to emit `null` instead, then reran it. Its initial score is not used for comparisons.

## Routing labels, v1 → reviewed

- CarParts headlights: accept the direct headlight-components category as well as the larger lighting category.
- Giles Thomas AI usage: accept the explicitly titled current AI-use article, not just an older URL matching an overly narrow pattern.
- After Hours Plumbing contact: accept the emergency-service page because its supplied body includes contact instructions, as well as the contact page.

The same saved model responses were regraded: 35/39 became 38/39. No routing model behavior changed. The remaining failure was a contact link outside the 16,000-character context budget. The label refinements also apply to all lexical controls.

## Analyst review of the advisory judge

The same-model reviewer flagged five small grounding issues in the initial 39 generation outputs. Its quotes were mechanically verified against the supplied evidence. That does **not** establish that its judgments are correct:

- “With the team” and an unsupported “featured” category are avoidable additions, but low-impact.
- The UAMS provider description promised search/filter behavior more specific than the extracted page established; worth tightening.
- The request-estimate and sizing-guide issues are debatable: titles support the general purpose, but the extracts do not prove detailed instructions exist. Preserve these as review notes, not hard factual-error labels.
- The judge gave the missing-evidence null document a good semantic score, while the schema checker correctly failed it. Both signals are needed.

No external human has calibrated these judgments. Do not call the reviewer score factual accuracy or claim an independent evaluation.
