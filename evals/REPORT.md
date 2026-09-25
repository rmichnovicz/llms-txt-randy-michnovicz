# llms.txt evaluation study — September 24, 2026

The frozen v2 generator passed **162/162 deterministic checks across 54 cases, each run three times**, after one prompt revision and documented corrections to overly strict labels. These checks are regression evidence; they do not establish factual accuracy of every generated sentence. The most useful product finding is that **task routing, scope and source authority matter more than Markdown polish alone**.

## What was collected

- **55 actual llms.txt files** from 60 attempted websites, spanning **13 categories**.
- **Eight published example files** from three publishers; templates are distinguished from deployed files.
- **68 extracted destination pages** from 77 requests. These produced **23 frozen real-site generation cases**, supplemented by 22 new authored and nine existing cases.
- **97 routing questions across 50 actual files**; 39 were tested with a live model, stratified by category.
- Every file has its original URL, final URL, retrieval time, HTTP status and SHA-256 hash. Fetch failures remain visible and ungraded.

| Actual-file category | Successful downloads |
|---|---:|
| developer-docs | 8 |
| directory-travel | 4 |
| ecommerce | 3 |
| education | 4 |
| finance | 3 |
| health | 4 |
| hospitality | 5 |
| local-services | 4 |
| manufacturing | 3 |
| nonprofit-research | 4 |
| professional-services | 4 |
| publisher-personal | 4 |
| saas | 5 |

Read [all 60 file assessments](corpus/REVIEWS.md), [the download/format audit](corpus/AUDIT.md), and [all eight template assessments](corpus/EXAMPLES.md). Raw material is under `corpus/raw/`, templates under `corpus/examples/`, and fetched source evidence under `corpus/evidence/`.

## Which files work well, and for what

| Example | Assessment | Concrete reason |
|---|---|---|
| [Svelte](https://svelte.dev/llms.txt) | Strong documentation router | Seven links distinguish compact, complete and package-specific documentation. Readers can choose scope and budget. |
| [Cloudflare](https://developers.cloudflare.com/llms.txt) | Strong platform router | Product descriptions lead to smaller product indexes instead of flattening all documentation into one list. |
| [FastHTML](https://www.fastht.ml/docs/llms.txt) | Strong technical guide | Specific framework distinctions prevent likely implementation mistakes; introductory and reference resources have distinct roles. |
| [Framer](https://www.framer.com/llms.txt) | Strong product guide | Separates pricing authority, product resources and the external-agent workflow. |
| [UAMS Health](https://uamshealth.com/llms.txt) | Strong patient-navigation guide | Provider, location and patient-logistics routes have explicit scope. This does not validate medical claims. |
| [Terminal Trove](https://terminaltrove.com/llms.txt) | Strong plain-URL guide | A compact catalogue/category map works despite using plain URLs instead of Markdown links. |
| [CarParts](https://www.carparts.com/llms.txt) | Mixed: useful shopping front matter, huge catalogue | Policy links appear early, but thousands of entries make loading the entire index costly. |
| [Mailmodo](https://www.mailmodo.com/llms.txt) | Weak as a first-read guide | More than 1,000 entries under one Docs section mix product and article content; no direct pricing destination was found. |
| [After Hours Plumbing](https://afterhoursplumbing.com.au/llms.txt) | Weak as a first-read guide | Tens of thousands of words concatenate full pages, making it closer to a content archive than an entry guide. |
| [Backpack Bed](https://backpackbed.org/llms.txt) | Weak navigation | Many donation/help actions are named, but the main linked destination is a single homepage. |
| [John Mueller](https://johnmu.com/llms.txt) | Poor descriptive labels for technical routing | Playful labels do not describe the linked articles; correct syntax does not make the labels useful. |
| [Proposal restaurant template](https://llmstxt.org/domains.html) | Mixed, with a concrete copied-content defect | Its dessert link describes software documentation; every-day menu wording also conflicts with Sunday closure. |

These are Codex editorial assessments based on sampled openings, headings and link entries, with limited destination checks. They are neither exhaustive fact checks nor rankings of the organizations. Long files can be useful searchable references; plain URLs and intentionally repeated categories can be useful too.

## Measured routing results

All live routing calls used GPT-6 Sol, medium reasoning, a **16,000-character** file budget and at most three destination URLs. No search tool or external knowledge was provided. The budget is characters, not tokens. Grading accepts several appropriate entry points where labeled.

| Method, same 39 tasks | Correct destination in top three |
|---|---:|
| Labels-only lexical control | 21/39 |
| BM25 over labels, descriptions and URLs | 25/39 |
| BM25 over the full file | 23/39 |
| Thinking-model router | 38/39 |

On all 97 tasks, the controls scored 55/97 (labels), 67/97 (16k BM25) and 64/97 (full-file BM25). The full file was not automatically better: extra matching material can distract a lexical ranker. These are results on authored tasks, not estimated population rates.

The model originally graded 35/39. Inspection identified three incomplete gold URL sets; **the same responses regraded to 38/39**. This is a grading correction, not a model improvement. Details and original labels are preserved in [LABEL_CHANGES.md](corpus/LABEL_CHANGES.md).

The remaining failure was Wheelhouse's contact link, beyond the supplied context. A controlled variant moved only that existing link into an early section, preserving its wording and the other entries. With the same model and reading budget, it succeeded **3/3** times. The variant is explicitly marked analyst-derived under `corpus/variants/`; it is not represented as the live site's file.

## Generator iteration

The 54-case suite contains 39 development cases and 15 held-out cases. Domain splits were set before generator runs. Held-out outputs were opened only after freezing v2; file discovery and broad corpus reviews were not held out.

| Run | Deterministic result | Interpretation |
|---|---:|---|
| Metadata-only control, all cases | 35/54 | Copying metadata is sufficient on several small evidence slices; it fails important editorial/decision behaviors. |
| Original prompt, first development pass, original gold | 36/39 | One actual output-contract error and two debatable gold expectations. |
| Original prompt, reviewed gold, three trials per development case | 114/117 | Includes the regraded original trial and two additional live trials. |
| Revised prompt, three trials per development case | 117/117 | All 39 cases passed every repetition. |
| Revised prompt, three trials per held-out case | 45/45 | All 15 cases passed every repetition. |

The model-facing inputs were unchanged for the v1/v2 comparisons. The new prompt:

1. Returns a schema-valid empty draft when source evidence is absent, with an explicit explanation.
2. Avoids promising search, filters, instructions or guarantees merely because a page title makes them plausible.
3. Distinguishes a user's positioning preference from evidence of a certification or other factual claim.
4. Preserves version, locale, geographic scope and policy exceptions; permits clearly labeled archive material when useful.

Prompts are frozen in `prompts/generation-v1.json` and `prompts/generation-v2.json`. These are historical v1/v2 results. The application now identifies its prompt as `brief-generation-v5` in [generation.py](../src/brief/generation.py); the scores above do not establish v5 performance. Original requests, outputs, failures and usage remain under `results/`.

## Semantic review and its limits

A separate same-model review of the first response per development case scored grounding, usefulness, decision fidelity, question value and concision. It flagged **5 of 39** initial responses and **0 of 39** revised responses. Every cited issue had mechanically valid evidence anchors. Some initial flags were minor or debatable; read the adjudication notes before treating them as errors. The reviewer does not see deterministic gold labels or prompt version.

Calibration paired six unchanged outputs with six deliberately corrupted summaries: invented certifications, unsupported client names, wrong service region, false allergy guarantees, incorrect returns and mixed-up technical specifications. It classified **12/12** correctly, with exact quote checks. These obvious controls establish basic sensitivity, not broad reviewer reliability. No external human has independently reviewed the corpus or outputs.

## Product implications

- Default to a concise task guide with an optional deeper index. Preserve hierarchical documentation structures when a site already provides them.
- Show the user a few realistic visitor questions and the source each question routes to. This is more actionable than a single quality score.
- Prioritize contact, eligibility, policies, setup or other core tasks early enough to survive a limited reading budget.
- Ask for decisions where site evidence cannot settle audience, scope or conflicting facts. Avoid asking users to repeat obvious site information.
- Keep facts, preferences and source evidence distinct. Removed answers must stop influencing regeneration; certifications and guarantees need actual evidence.
- During refresh, flag changes to policy, scope, versions and authoritative sources. A changed word count alone is not the important event.

## Reproducibility and remaining work

See [commands and evaluation contracts](README.md). The study made 411 live model calls with reported usage: 783,840 input and 122,686 output tokens, including generation, routing, semantic review and calibration. Regrading and lexical controls made no model calls. Dollar cost was not inferred from unverified account pricing.

The suite remains limited by convenience sampling, small two/three-page real-site inputs, incomplete gold URL alternatives, one model family, one snapshot date and same-model review. Passing 162 repeated assertions is not 162 independent websites. Full-site crawl coverage, more difficult multistep model trajectories, independent human calibration and other providers should be evaluated separately. No measurement here establishes search ranking gains or actual adoption of a site's llms.txt by answer engines.

Machine-readable totals: [study summary](reports/study-2026-09-24.json).


Follow-up: [consumer navigation and answer evaluation](CONSUMER_REPORT.md) tests a smaller reader against actual destination pages.
