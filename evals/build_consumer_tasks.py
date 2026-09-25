"""Questions and frozen answer evidence, authored before consumer runs."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from brief.corpus import write_json

ROOT = Path("evals/corpus")
cases = {c["reference_file"]: c for c in json.loads((ROOT / "real-generation-cases.json").read_text())}
tasks = []


def add(
    site: str,
    id: str,
    question: str,
    specs: list[tuple[str, tuple[list[str], list[str]], str]],
    expect_abstain: bool = False,
    forbidden: Sequence[str] = (),
) -> None:
    case = cases[site]
    facts = []
    for fid, pattern, url_part in specs:
        sources = [s for s in case["input"]["sources"] if url_part in s["url"]]
        assert sources, (site, url_part)
        import re

        assert any(all(re.search(p, s["content"], re.IGNORECASE) for p in pattern[1]) for s in sources), (site, fid)
        # Include other frozen pages when their extracted text contains the same fact anchors.
        urls = [
            s["url"]
            for s in case["input"]["sources"]
            if all(re.search(p, s["content"], re.IGNORECASE) for p in pattern[1])
        ]
        facts.append({"id": fid, "answer_patterns": pattern[0], "quote_patterns": pattern[1], "evidence_urls": urls})
    tasks.append(
        {
            "id": id,
            "site_id": site,
            "category": case["category"],
            "site_url": case["input"]["siteUrl"],
            "question": question,
            "facts": facts,
            "expect_abstain": expect_abstain,
            "forbidden_patterns": list(forbidden),
            "generated_file": f"evals/results/corpus-v2-{case['split']}/{case['id']}--r1.llms.txt",
            "gold_scope": "Frozen source extracts, not independent verification of business claims.",
        }
    )


add(
    "framer",
    "framer-plan-prices",
    "On the pricing page, what monthly prices are displayed for Basic and Pro under yearly billing? Make the billing basis clear.",
    [
        ("basic", ([r"Basic[^\n.;]{0,70}10\b|10\b[^\n.;]{0,40}Basic"], [r"Basic", r"\$10"]), "/pricing"),
        ("pro", ([r"Pro[^\n.;]{0,70}30\b|30\b[^\n.;]{0,40}Pro"], [r"Pro", r"\$30"]), "/pricing"),
        ("billing", ([r"yearly|annual"], [r"Yearly billing"]), "/pricing"),
    ],
)
add(
    "mollieaspen",
    "mollie-dining-hours",
    "At MOLLIE Aspen, when are breakfast and dinner served?",
    [
        (
            "breakfast",
            ([r"7(?::00)?\s*(?:AM|a\.m\.)", r"11(?::00)?\s*(?:AM|a\.m\.)"], [r"BREAKFAST", r"7:00AM", r"11:00AM"]),
            "/dine-drink/",
        ),
        (
            "dinner",
            ([r"5(?::00)?\s*(?:PM|p\.m\.)", r"9(?::00)?\s*(?:PM|p\.m\.)"], [r"DINNER", r"5:00PM", r"9:00PM"]),
            "/dine-drink/",
        ),
    ],
)
add(
    "neonelectrical",
    "neon-guarantee",
    "What workmanship guarantee does Neon Electrical describe, and how long does its issue-remediation period last?",
    [
        ("amount", ([r"20[, ]?000"], [r"20,000", r"Workmanship Guarantee"]), "/qualifications/"),
        ("period", ([r"12\s*months|one\s*year|a\s*year"], [r"12 months"]), "/qualifications/"),
    ],
)
add(
    "healthcare-lk",
    "docpp-demo",
    "How long is the DocPP free demo, and are users and prescriptions limited during it?",
    [
        ("duration", ([r"14[ -]?day"], [r"14.days"]), "/request-free-demo/"),
        (
            "limits",
            (
                [
                    r"unlimited[^.]{0,80}users|users[^.]{0,50}unlimited",
                    r"unlimited[^.]{0,80}prescriptions|prescriptions[^.]{0,50}unlimited",
                ],
                [r"Unlimited Users", r"Unlimited Prescriptions"],
            ),
            "/request-free-demo/",
        ),
    ],
)
add(
    "healthcare-lk",
    "docpp-privacy",
    "Does HealthCare.LK say it shares data with third parties for marketing?",
    [
        (
            "marketing",
            ([r"\bnot\b|\bno\b|doesn.t", r"marketing"], [r"do not share", r"marketing purposes"]),
            "/privacy-policy/",
        )
    ],
)
add(
    "we-in-style",
    "store-returns-details",
    "For WE IN STYLE, how long after receipt can I request a return, can I exchange it, and who pays return shipping and customs?",
    [
        ("window", ([r"30[ -]?days?"], [r"30 days", r"receive"]), "/refund-policy"),
        (
            "exchange",
            (
                [r"exchanges?[^.]{0,50}(?:not|no)|(?:not|no)[^.]{0,50}exchanges?", r"refund"],
                [r"exchanges are not possible", r"only refunds"],
            ),
            "/refund-policy",
        ),
        (
            "fees",
            (
                [r"customer|buyer|you (?:pay|are responsible)", r"customs", r"shipping"],
                [r"customer is responsible", r"shipping and customs fees"],
            ),
            "/refund-policy",
        ),
    ],
)
add(
    "we-in-style",
    "store-shipping-details",
    "When is WE IN STYLE delivery free, and how soon after confirmation is an order dispatched?",
    [
        ("threshold", ([r"300"], [r"over €300"]), "/shipping-policy"),
        (
            "pickup",
            ([r"France", r"no minimum|without.{0,10}minimum"], [r"Pickup Points in France", r"no minimum purchase"]),
            "/shipping-policy",
        ),
        ("dispatch", ([r"2 business days|two business days"], [r"within 2 business days"]), "/shipping-policy"),
    ],
)
add(
    "packmojo",
    "packmojo-reimbursement",
    "What order quantity makes PackMojo custom samples reimbursable?",
    [
        (
            "quantity",
            ([r"500", r"at least|minimum|or more|500\+"], [r"reimbursable", r"at least 500 units"]),
            "/samples/",
        )
    ],
)
add(
    "fasthtml",
    "fasthtml-live-reload",
    "How do I enable live reloading with the FastHTML app class and uvicorn? Is it intended for production?",
    [
        ("class", ([r"FastHTMLWithLiveReload"], [r"FastHTMLWithLiveReload"]), "/live_reload"),
        ("uvicorn", ([r"uvicorn", r"--reload"], [r"uvicorn main:app --reload"]), "/live_reload"),
        (
            "scope",
            ([r"development|not.{0,30}production|disable.{0,30}production"], [r"only be used during", r"development"]),
            "/live_reload",
        ),
    ],
)
add(
    "picflow",
    "picflow-lightroom",
    "Which Lightroom version does Picflow’s plugin support, and where do I open the plug-in manager?",
    [
        ("version", ([r"Lightroom Classic"], [r"Lightroom Classic"]), "/articles/"),
        ("manager", ([r"File", r"Plug.in Manager"], [r"File", r"Plug.in Manager"]), "/articles/"),
    ],
)
add(
    "filmconnection",
    "film-tuition-contact",
    "Does Film Connection’s tuition page provide a specific numeric tuition amount, or how does it tell me to find out?",
    [
        (
            "advisor",
            ([r"advisor|adviser", r"form|contact|reach|consult"], [r"Fill out the form", r"mentee advisor"]),
            "/film-school-tuition/",
        )
    ],
    forbidden=[r"\$\s*\d"],
)
add(
    "mollieaspen",
    "mollie-unknown-future-rate",
    "What is the guaranteed exact nightly rate for a room at MOLLIE Aspen on December 31, 2028? If you cannot establish that exact rate, abstain.",
    [],
    True,
    forbidden=[r"\$\s*\d"],
)
# The HTML and Markdown versions are both verified evidence for this task.
for task in tasks:
    if task["id"] == "fasthtml-live-reload":
        for fact in task["facts"]:
            fact["evidence_urls"].append("https://www.fastht.ml/docs/ref/live_reload.html")
# Freeze generated guides beside their producer request hashes for standalone replay.
for task in tasks:
    path = Path(task["generated_file"])
    target = ROOT / "consumer-guides" / f"{task['site_id']}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(path.read_bytes())
    artifact = json.loads(path.with_suffix("").with_suffix(".json").read_text())
    from brief.corpus import digest

    write_json(
        target.with_suffix(".json"),
        {
            "source_artifact": str(path),
            "sha256": digest(target.read_bytes()),
            "producer_request_sha256": artifact["request_sha256"],
        },
    )
    task["generated_file"] = str(target)
write_json(ROOT / "consumer-tasks.json", tasks)
print(len(tasks), "consumer QA tasks")
