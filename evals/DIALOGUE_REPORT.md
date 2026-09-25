# Clarification questions and responses

The harness now saves ambiguous first-pass drafts and questions, then tests the actual option cards and custom answers against the production generator. The [example gallery](DIALOGUE_EXAMPLES.md) is the most useful place to inspect what the product would show.

## Pilot

Eight scenarios: five meaningful ambiguities and three no-filler controls. Seven are authored. One uses real captured WE IN STYLE pages whose delivery terms differ. All simulated owner updates are fictional test data, including the €450 threshold, Alameda-only service, and 4.25% interest rate. These are not claims about current businesses.

Using the existing configured generator and production `brief-generation-v2` prompt:

| Check | Result |
|---|---:|
| Ambiguous scenarios asked the relevant question | 5/5 |
| No-filler scenarios avoided questions | 3/3 |
| Ambiguous scenarios supplied a recommendation | 3/5 |
| First passes met all mechanical checks | 6/8 |
| Generated follow-ups met mechanical checks | 28/28 |
| Advisory review calibration controls | 3/3 after quote-validator correction |

The 28 follow-ups comprise three recommended-card selections, five alternative selections, five custom answers, five removals, five dismissals, and five extra-question requests. Two recommended-card branches were unavailable because no recommendation existed; they were not fabricated or counted as passes. Three negative controls have no answer branches and are excluded from the follow-up denominator.

This is a small development pilot with one sample per branch. Mechanical passes do not establish semantic correctness.

## Concrete examples

**Shelter with a one-link limit:** the assistant asks whether to serve people seeking a bed or potential donors. It recommends bed seekers and explains that selecting donors would replace the intake link with the donation page. Both options and the custom recipient-first answer changed the actual selected resource correctly. This is a strong question: the site supplies both resources, but cannot tell us the owner's priority under the link limit.

**Conflicting undated interest rates:** the assistant asks which rate, if either, is verified. It recommends leaving the rate unconfirmed. A fictional owner correction appears in the new draft with decision provenance; removing that answer removes the owner-provided value. This is a strong recommendation because it offers a useful action without guessing a fact.

**Actual shipping-page ambiguity:** the assistant identifies €300 in the captured policy and €600 in the homepage, cites both, and asks which terms to use. Its third option says, “These are distinct offers; clarify which services and destinations each covers.” That wording prematurely asserts the explanation for the discrepancy. A better card would say, “They may apply to different offers; leave the threshold unspecified until we clarify the scope.” A reversible suggestion could link the policy without repeating a numeric threshold.

**API implementers versus buyers:** with a one-link limit, the question correctly identifies the unresolved audience and offers distinct choices. It provides no recommendation. That is transparent uncertainty, but falls short of the pilot's desired recommendation requirement. Prefer a clearly tentative editorial default and explain the tradeoff; do not invent evidence that the business favors that audience.

**Clear portfolio and local services:** no questions are necessary. The generator produces useful drafts from the evidence. A question-only scenario with previously dismissed topics likewise returns no filler.

## Semantic review and interpretation

The advisory reviewer flagged issues in three of eight trajectories, with literal output anchors:

- Shipping: premature “distinct offers” assertion; no reversible recommendation; a concern about losing the visible conflict after selecting the policy.
- Software audience: no tentative recommendation or evidence-based explanation for its provisional resource selection.
- Service area: after deleting an owner correction, the renewed question had yes/no options without an “unconfirmed” option.

These are review suggestions, not established failures. The shipping source-priority branch explicitly follows the user's chosen policy preference and attributes the policy's claim; omitting the superseded conflict may be acceptable. The service-area user can still type a custom answer, so the missing defer card is a usability opportunity rather than an inability to express uncertainty. The premature assertion in the shipping option is the clearest improvement target.

The same model family generated and reviewed the outputs. Reviewer independence is therefore limited. Scores on dimensions not exercised by no-question controls are not evidence of successful answer handling.

## Harness iteration

The original reviewer anchor validator accepted string values but rejected real JSON fragments such as `"recommendedOption": null` and duplicate option arrays. That incorrectly rejected one negative calibration control and two review anchors. The revised validator accepts actual JSON structure as well as literal text, while still rejecting fabricated fragments. Original judgments and anchor failures remain intact; corrected anchor checks are in separate `anchors-reviewed.json` reports. No model outputs were rewritten, and all three calibration controls pass after that correction.

Artifacts:

- [Frozen first-pass requests and outputs](corpus/dialogue-first-v1/report.json)
- [Scenario definitions and rubrics](corpus/dialogue-cases.json)
- [All 28 follow-up outputs, mechanically regraded](reports/dialogue-follow-v1/report.json)
- [Advisory review with corrected anchor checks](reports/dialogue-review-v1/anchors-reviewed.json)
- [Reviewer controls with original candidate outputs](reports/dialogue-review-controls-v1/anchors-reviewed.json)

The first-pass directory contains the generated llms.txt drafts alongside JSON outputs. Each follow-up records its parent response hash and exact active context. Removing an answer removes it from the next model request; older generated text cannot silently restore it.

## Product implication

A good card should explain **what is uncertain, why it matters to this document, and what the recommendation would change**. Factual conflicts need a defer or omit option; editorial choices can usually have tentative defaults. A custom answer must override suggestions, carry its provenance where it supplies a fact, and be removable without leaving hidden influence.

The harness is ready for more saved first passes, including real sites with ambiguous product versions, region-specific policies, and competing audiences. Current limits: only one real-site ambiguity, no repeated trials, no open-chat answer-extraction test, no source-refresh trajectory in this suite, and no claim of calibrated semantic accuracy. Production prompts were not changed based on this small pilot.

Validation: six new harness tests; full suite **124 passed**. Ruff passes. The tests cover question checks, real-card branch selection, missing recommendations, custom facts and removal, question-only behavior, and reviewer quote anchors.
