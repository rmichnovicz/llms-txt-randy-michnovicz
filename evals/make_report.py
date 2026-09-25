"""Build the research report from saved runs; no network/model calls."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from brief.corpus import write_json

BASE = Path("evals/results")


def read(name: str) -> dict[str, Any]:
    return json.loads((BASE / name / "report.json").read_text())


v1 = read("corpus-v1-regraded")
v1_more = read("corpus-v1-repeat-check")
v2 = read("corpus-v2-development")
hold = read("corpus-v2-holdout")
control = read("corpus-metadata-control-fixed")
router = read("routing-model-16k-reviewed")
lexical = read("routing-bm25-16k-reviewed")
full = read("routing-bm25-full-reviewed")
labels = read("routing-labels-16k-reviewed")
iteration = read("routing-order-iteration")
calibration = read("judge-calibration-review")
expected = {r["id"]: r for r in json.loads(Path("evals/corpus/judge-calibration-labels.json").read_text())}
cal_pass = sum(
    r.get("anchors_valid", False)
    and ((r["judgment"]["scores"][expected[r["id"]]["dimension"]] < 2) == expected[r["id"]]["has_known_defect"])
    for r in calibration["results"]
)
ids = {r["id"] for r in router["results"]}
matched = {
    name: sum(r["result"]["passed"] for r in report["results"] if r["id"] in ids)
    for name, report in [("model", router), ("bm25", lexical), ("bm25_full", full), ("labels", labels)]
}
v1_pass = v1["summary"]["passed"] + v1_more["summary"]["passed"]
v1_n = v1["summary"]["attempts"] + v1_more["summary"]["attempts"]
corpus = json.loads(Path("evals/corpus/manifest.json").read_text())
category = Counter(m["category"] for m in corpus if m["accepted"])
files = [m for m in corpus if m["accepted"]]
judges = {name: read(name) for name in ["corpus-v1-semantic", "corpus-v2-semantic"]}
semantic = {
    name: {
        "reviewed": len(r["results"]),
        "with_issues": sum(bool(x.get("judgment", {}).get("issues")) for x in r["results"]),
        "invalid_anchors": sum(not x.get("anchors_valid", False) for x in r["results"]),
    }
    for name, r in judges.items()
}
usage = []
for name in ["corpus-v1-development", "corpus-v1-repeat-check", "corpus-v2-development", "corpus-v2-holdout"]:
    usage += [r["modelMetadata"]["usage"] for r in read(name)["results"] if r.get("modelMetadata")]
usage += [r["modelMetadata"]["usage"] for r in router["results"] if r.get("modelMetadata")]
usage += [r["metadata"]["usage"] for r in iteration["results"]]
for report in [*judges.values(), calibration]:
    usage += [r["usage"] for r in report["results"] if r.get("usage")]
summary: dict[str, Any] = {
    "snapshot_date": "2026-09-24",
    "actual_files": len(files),
    "attempted_files": len(corpus),
    "categories": dict(category),
    "published_templates": 8,
    "generation_cases": 54,
    "routing_tasks": 97,
    "model": "gpt-6-sol",
    "reasoning": "medium",
    "generation_v1_reviewed": {"passed": v1_pass, "attempts": v1_n},
    "generation_v2_development": v2["summary"],
    "generation_v2_holdout": hold["summary"],
    "metadata_control": control["summary"],
    "routing_matched_39": matched,
    "routing_all_97": {
        name: r["summary"] for name, r in [("bm25_16k", lexical), ("bm25_full", full), ("labels_16k", labels)]
    },
    "semantic_review": semantic,
    "judge_calibration": {"correct": cal_pass, "total": len(calibration["results"])},
    "live_calls_with_usage": len(usage),
    "total_input_tokens": sum(u.get("input_tokens", 0) for u in usage),
    "total_output_tokens": sum(u.get("output_tokens", 0) for u in usage),
    "limitations": [
        "Convenience sample",
        "Small frozen source slices",
        "Same-model advisory reviewer",
        "No independent human factual review",
        "No search ranking/adoption experiment",
    ],
}
write_json(Path("evals/reports/study-2026-09-24.json"), summary)
category_table = "\n".join(f"| {k} | {v} |" for k, v in sorted(category.items()))
report_markdown = f"""# llms.txt evaluation study — September 24, 2026

The generator passed **{v2["summary"]["passed"] + hold["summary"]["passed"]}/162 deterministic checks across 54 cases, each run three times**, after one prompt revision and documented corrections to overly strict labels. These checks are regression evidence; they do not establish factual accuracy of every generated sentence. The most useful product finding is that **task routing, scope and source authority matter more than Markdown polish alone**.

## What was collected

- **55 actual llms.txt files** from 60 attempted websites, spanning **13 categories**.
- **Eight published example files** from three publishers; templates are distinguished from deployed files.
- **68 extracted destination pages** from 77 requests. These produced **23 frozen real-site generation cases**, supplemented by 22 new authored and nine existing cases.
- **97 routing questions across 50 actual files**; 39 were tested with a live model, stratified by category.
- Every file has its original URL, final URL, retrieval time, HTTP status and SHA-256 hash. Fetch failures remain visible and ungraded.

| Actual-file category | Successful downloads |
|---|---:|
{category_table}

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
| Labels-only lexical control | {matched["labels"]}/39 |
| BM25 over labels, descriptions and URLs | {matched["bm25"]}/39 |
| BM25 over the full file | {matched["bm25_full"]}/39 |
| Thinking-model router | {matched["model"]}/39 |

On all 97 tasks, the controls scored {labels["summary"]["passed"]}/97 (labels), {lexical["summary"]["passed"]}/97 (16k BM25) and {full["summary"]["passed"]}/97 (full-file BM25). The full file was not automatically better: extra matching material can distract a lexical ranker. These are results on authored tasks, not estimated population rates.

The model originally graded 35/39. Inspection identified three incomplete gold URL sets; **the same responses regraded to 38/39**. This is a grading correction, not a model improvement. Details and original labels are preserved in [LABEL_CHANGES.md](corpus/LABEL_CHANGES.md).

The remaining failure was Wheelhouse's contact link, beyond the supplied context. A controlled variant moved only that existing link into an early section, preserving its wording and the other entries. With the same model and reading budget, it succeeded **3/3** times. The variant is explicitly marked analyst-derived under `corpus/variants/`; it is not represented as the live site's file.

## Generator iteration

The 54-case suite contains 39 development cases and 15 held-out cases. Domain splits were set before generator runs. Held-out outputs were opened only after freezing v2; file discovery and broad corpus reviews were not held out.

| Run | Deterministic result | Interpretation |
|---|---:|---|
| Metadata-only control, all cases | {control["summary"]["passed"]}/54 | Copying metadata is sufficient on several small evidence slices; it fails important editorial/decision behaviors. |
| Original prompt, first development pass, original gold | 36/39 | One actual output-contract error and two debatable gold expectations. |
| Original prompt, reviewed gold, three trials per development case | {v1_pass}/{v1_n} | Includes the regraded original trial and two additional live trials. |
| Revised prompt, three trials per development case | {v2["summary"]["passed"]}/117 | All 39 cases passed every repetition. |
| Revised prompt, three trials per held-out case | {hold["summary"]["passed"]}/45 | All 15 cases passed every repetition. |

The model-facing inputs were unchanged for the v1/v2 comparisons. The new prompt:

1. Returns a schema-valid empty draft when source evidence is absent, with an explicit explanation.
2. Avoids promising search, filters, instructions or guarantees merely because a page title makes them plausible.
3. Distinguishes a user's positioning preference from evidence of a certification or other factual claim.
4. Preserves version, locale, geographic scope and policy exceptions; permits clearly labeled archive material when useful.

Prompts are frozen in `prompts/generation-v1.json` and `prompts/generation-v2.json`; v2 is now used by the application. Original requests, outputs, failures and usage remain under `results/`.

## Semantic review and its limits

A separate same-model review of the first response per development case scored grounding, usefulness, decision fidelity, question value and concision. It flagged **{semantic["corpus-v1-semantic"]["with_issues"]} of 39** initial responses and **{semantic["corpus-v2-semantic"]["with_issues"]} of 39** revised responses. Every cited issue had mechanically valid evidence anchors. Some initial flags were minor or debatable; read the adjudication notes before treating them as errors. The reviewer does not see deterministic gold labels or prompt version.

Calibration paired six unchanged outputs with six deliberately corrupted summaries: invented certifications, unsupported client names, wrong service region, false allergy guarantees, incorrect returns and mixed-up technical specifications. It classified **{cal_pass}/12** correctly, with exact quote checks. These obvious controls establish basic sensitivity, not broad reviewer reliability. No external human has independently reviewed the corpus or outputs.

## Product implications

- Default to a concise task guide with an optional deeper index. Preserve hierarchical documentation structures when a site already provides them.
- Show the user a few realistic visitor questions and the source each question routes to. This is more actionable than a single quality score.
- Prioritize contact, eligibility, policies, setup or other core tasks early enough to survive a limited reading budget.
- Ask for decisions where site evidence cannot settle audience, scope or conflicting facts. Avoid asking users to repeat obvious site information.
- Keep facts, preferences and source evidence distinct. Removed answers must stop influencing regeneration; certifications and guarantees need actual evidence.
- During refresh, flag changes to policy, scope, versions and authoritative sources. A changed word count alone is not the important event.

## Reproducibility and remaining work

See [commands and evaluation contracts](README.md). The study made {summary["live_calls_with_usage"]} live model calls with reported usage: {summary["total_input_tokens"]:,} input and {summary["total_output_tokens"]:,} output tokens, including generation, routing, semantic review and calibration. Regrading and lexical controls made no model calls. Dollar cost was not inferred from unverified account pricing.

The suite remains limited by convenience sampling, small two/three-page real-site inputs, incomplete gold URL alternatives, one model family, one snapshot date and same-model review. Passing 162 repeated assertions is not 162 independent websites. Full-site crawl coverage, more difficult multistep model trajectories, independent human calibration and other providers should be evaluated separately. No measurement here establishes search ranking gains or actual adoption of a site's llms.txt by answer engines.

Machine-readable totals: [study summary](reports/study-2026-09-24.json).
"""
Path("evals/REPORT.md").write_text(report_markdown)
print("Wrote evals/REPORT.md and reproducible summary")
