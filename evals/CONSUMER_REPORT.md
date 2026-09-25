# Can a smaller model use the guide to answer real questions?

Yes: the harness now follows links, reads actual captured destination pages, and answers questions with citations. This tests usefulness beyond syntax and URL selection. The first pilot suggests curated guides can help, but it does **not** establish that llms.txt generally improves website visibility or every model's answers.

## Setup

- Reader: pinned `gpt-4.1-mini-2025-04-14`, a smaller non-reasoning model with structured-output support ([official model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini)). Generator remains separate.
- 12 questions, nine websites, three entry conditions: homepage, published llms.txt, Brief-generated llms.txt. One trial per condition per prompt; 72 trials across two prompts, plus three initial smoke trials.
- Three additional page opens; only URLs discovered in visible observations can be opened. Same extraction and presentation limits across arms. No gold facts or gold URLs in model inputs.
- Initial pilot records missing public pages through the safe crawler. Second prompt uses the frozen cache and explicitly reports misses. Every observation/action is saved, alongside usage, hashes, final answers, and grades.
- Known-fact coverage checks required answer patterns and forbidden claims. Strict success additionally checks supporting quotes against pages actually read. A guide cannot serve as destination evidence. This is deliberately stricter than judging whether an answer sounds right.

## Results

Reviewed v1 scores include one documented evidence-URL correction described below. Counts include the abstention task.

| Entry | v1 fact coverage | v1 strict success | v2 fact coverage | v2 strict success |
|---|---:|---:|---:|---:|
| Homepage | 7/12 | 5/12 | 7/12 | 4/12 |
| Published guide | 11/12 | 6/12 | 10/12 | 7/12 |
| Generated guide | 12/12 | 7/12 | 11/12 | 7/12 |

| Entry | v1 page opens | v1 input tokens | v2 page opens | v2 input tokens |
|---|---:|---:|---:|---:|
| Homepage | 19 | 114,883 | 14 | 91,534 |
| Published guide | 19 | 115,020 | 20 | 124,648 |
| Generated guide | 13 | 45,252 | 14 | 46,937 |

Opens and tokens are totals across 12 tasks. Tokens include repeated conversation evidence at each step; they exclude guide generation. Lower browsing cost can also result from premature stopping, so it must be read alongside answer quality.

v2 adds explicit destination verification and short verbatim quotation instructions. It fixed some cases, but did not produce a clear overall win. Do not promote it as a proven improvement from this sample. The v2 homepage arm encountered two previously uncaptured URLs; all misses remain failures, rather than being silently dropped. This further limits any causal prompt comparison.

## What failed, and why it matters

- **PackMojo:** v1 guide readers answered the 500-unit sample reimbursement question without opening its source. The fact was right, but the verification requirement failed. In v2 the generated-guide reader opened the right page yet also cited llms.txt; the extra invalid citation still failed strict grading.
- **MOLLIE dining:** the guide readers found breakfast/dinner hours in one open. v1 combined nonadjacent source lines without marking omissions, failing quote provenance. v2 quoted them correctly. Homepage navigation spent its budget without finding the hours.
- **WE IN STYLE:** the captured homepage advertises a €600 home-delivery threshold while the shipping policy says €300. This is a genuine source conflict, not evidence that the homepage reader invented €600. Our task's gold is scoped to the policy; a better product should surface the contradiction for a decision instead of silently choosing one. Some model quotes also corrupted currency characters.
- **DocPP privacy:** a homepage reader inferred a marketing-sharing answer from generic security text. Required-word coverage alone can reward this. Citation support correctly prevented a strict pass.
- **FastHTML:** correct instructions sometimes came with reconstructed Markdown rather than authentic quotations. One authentic HTML citation initially failed because gold listed only the Markdown counterpart; that grader error was corrected for both runs.
- **Future hotel rate:** v1 abstained appropriately across all arms. In v2 one model gave a sensible uncertainty statement with the wrong action enum; another returned an empty abstention. These are protocol/usefulness failures, not fabricated prices. Keep the trace visible when interpreting aggregate scores.

## Calibration and provenance

Smoke testing revealed that the original grader rejected explicit ellipsis omissions and prices written before plan names. The grader now accepts ordered exact quote segments separated by ellipses, and Framer's price patterns accept either ordering. It still rejects invented or reordered segments. Original smoke task labels are preserved in `corpus/revisions/consumer-smoke-tasks.json`.

The pilot's FastHTML HTML evidence was inspected and verified against the captured page, then added as an acceptable source alongside its Markdown version. Original pilot labels remain in `corpus/revisions/consumer-pilot-tasks.json`. Raw pilot outputs are unchanged; reviewed reports recompute grades separately. That correction moves the v1 homepage strict score from 4/12 to 5/12.

Reports with saved observations, actions, original grades, and reviewed grades:

- [Reviewed v1](reports/consumer-v1-reviewed.json)
- [Reviewed v2](reports/consumer-v2-reviewed.json)
- [Question definitions](corpus/consumer-tasks.json)
- [Runner](../src/brief/consumer_eval.py)
- [Offline regrader](report_consumer.py)

Ten new tests cover quote provenance, missing/unvisited citations, redirect aliases, abstention, withheld gold labels, URL-discovery restrictions, browsing budgets, and offline cache misses. Full suite: 118 passed. Ruff passes.

## Product recommendation and limits

Use this as a **reader test** in the product: show the question, path taken, answer, source evidence, and any unanswered or conflicting facts. Feed those failures into editable decision points: add/reorder a useful link, resolve a policy conflict, clarify scope, or leave an uncertainty explicit. Re-run the same questions after each document revision. A smaller reader makes expensive or ambiguous navigation easier to expose.

Do not use only this model as the universal judge. The generator's guides were built from a small curated source set that overlaps the questions; they have a favorable coverage advantage over a large published guide truncated at the entry budget. This is an engineering pilot, not a blind benchmark or a statistically reliable ranking. There is only one sample per cell, one small reader, one abstention case, and no semantic judge in this layer. Pattern matching does not understand all negation or validate extra claims; exact-quote grading can reject substantively correct paraphrases. HTML/Markdown equivalence is only allowed where reviewed. Capture gaps and truncation also affect results.

Before making a public efficacy claim, add independently authored held-out questions, repeat trials, capture all discovered routes before a paired frozen comparison, and run a stronger reader control. Keep guide quality, crawler/extraction failures, reader mistakes, and grader mistakes distinct.
