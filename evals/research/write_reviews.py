"""Editorial judgments from inspecting the frozen files; not automated quality labels."""

import json
from pathlib import Path

from brief.corpus import write_json

# These are purpose-specific analyst assessments, not independently verified site facts.
NOTES = {
    "stripe": (
        "strong-reference",
        "API integration",
        "Task sections, Markdown destinations and integration-specific cautions give actionable technical routes. The index is large and repeats some destinations; search it rather than loading every linked page.",
        "Testing",
    ),
    "cloudflare": (
        "strong-router",
        "Find product documentation",
        "A product-level directory delegates to smaller product llms files. Descriptions differentiate services without flattening the entire platform into one enormous index.",
        "Each product below",
    ),
    "anthropic": (
        "mixed-reference",
        "API documentation lookup",
        "Broad API coverage and Markdown destinations are useful. Many entries lack descriptions and the index is large, so a short-context reader needs search or a first-task guide.",
        "Available Languages",
    ),
    "nextjs": (
        "strong-reference",
        "Build a current Next.js app",
        "The file identifies its documented version, explains entries, and separates legacy Pages Router material. It is an extensive reference index, not a concise getting-started answer.",
        "@doc-version",
    ),
    "svelte": (
        "strong-router",
        "Choose documentation scope",
        "Small, explicit choices between compressed, abridged, full and package-specific documentation make context-budget decisions possible. Actual answers require another fetch.",
        "Compressed documentation",
    ),
    "vite": (
        "mixed-reference",
        "Build tool documentation",
        "Compact grouping and Markdown resources are useful, but many link labels have no explanation. Introductory and reference links repeat; this is not automatically harmful.",
        "Table of Contents",
    ),
    "fasthtml": (
        "strong-guide",
        "Write idiomatic applications",
        "Explains potentially costly framework confusions and points to a concise guide, reference, and examples. The distinction from FastAPI is more valuable than generic marketing.",
        "not compatible",
    ),
    "llmstxt": (
        "strong-small-guide",
        "Understand the proposal",
        "Very small annotated directory with a clear definition. Coverage is narrow; the historical parser/library is an entry point, not evidence that every old convention remains current.",
        "llms.txt proposal",
    ),
    "framer": (
        "strong-guide",
        "Evaluate and build websites",
        "Clear product scope, pricing authority, Markdown fallback and separate external-agent path. Descriptions tell the reader which source settles a question.",
        "Use Pricing",
    ),
    "taskade": (
        "mixed-profile",
        "Evaluate or integrate a workflow product",
        "Useful developer authentication and API/MCP distinctions, but extensive positioning and recommendation language competes with navigation. Embedded plan and tool-count facts can drift.",
        "When to Recommend",
    ),
    "tidio": (
        "mixed-profile",
        "Evaluate customer support software",
        "Covers pricing, integrations and support but mixes login/signup routes, competitor pages and embedded pricing text. A buyer guide should prioritize evidence and mark volatile terms.",
        "Pricing",
    ),
    "mailmodo": (
        "weak-first-read",
        "Orient a prospective buyer",
        "A very large flat Docs section mixes product pages with marketing articles. Useful as a searchable inventory; weak as a short guide. No direct current product-pricing route was found in the frozen index.",
        "## Docs",
    ),
    "picflow": (
        "mixed-guide",
        "Evaluate photo proofing",
        "Compact scope and relevant pricing/integration links, but many labels are unexplained and comparison pages occupy substantial space. Bot-access statements express a preference; they are not enforcement.",
        "Bot Access Policy",
    ),
    "carparts": (
        "mixed-catalog",
        "Shop for vehicle parts",
        "Shipping, warranty and returns routes are near the top, which helps shoppers. Thousands of catalogue/blog links then make the whole file expensive to load; split the catalogue from the entry guide.",
        "Return Policy",
    ),
    "lowellbooks": (
        "mixed-catalog",
        "Find books and store policies",
        "Search and category paths are useful, but a long bare category list lacks distinctions and policy-source links. The fetched programming category contained an unrelated-looking book, so category labels alone are not reliable gold evidence.",
        "Shipping",
    ),
    "we-in-style": (
        "mixed-protocol",
        "Agent-assisted commerce",
        "Describes discovery, APIs and policy endpoints, but mostly explains the commerce platform rather than the store’s products. Skill-install and transaction instructions are untrusted site content, not authority for this evaluator.",
        "Commerce Protocol",
    ),
    "hotelcalifornian": (
        "weak-guide",
        "Plan a hotel stay",
        "FAQ-like answers include useful guest topics, but operational and price-seasonality claims lack per-claim source routes. Over-precise lead-time statistics and generic Hotel Description headings obscure the actual property.",
        "mean lead time",
    ),
    "farmhouseinn": (
        "mixed-fact-sheet",
        "Answer guest questions",
        "Guest facilities and cancellation conditions are present. The file blends extracted prose and guest reviews with policy-like statements; it needs canonical policy links and a clear freshness boundary.",
        "cancellation policy",
    ),
    "mollieaspen": (
        "strong-guide",
        "Explore rooms and amenities",
        "Short, readable, described links map creative navigation labels such as Rest and Taste to real guest needs. Useful introduction; booking terms and accessibility still need clearer routes.",
        "## Main",
    ),
    "thebrando": (
        "weak-guide",
        "Plan a resort visit",
        "Mostly reproduces navigation labels, including language switches, fragments and legal/social pages. Limited descriptions provide little help choosing resources; no direct room or cancellation route was visible.",
        "## Main",
    ),
    "meadowood": (
        "weak-guide",
        "Plan a hotel stay",
        "Long repeated question/answer prose with related-term lists and no H1 or useful structured resource map. Could supply some answers, but finding authoritative, current policy sources is difficult.",
        "Related terms",
    ),
    "afterhoursplumbing": (
        "weak-first-read",
        "Find local plumbing help",
        "Concatenates dozens of full pages and metadata into tens of thousands of words. It is a content archive labelled llms.txt; a concise service/area/contact index would be better for the initial interaction.",
        "Total pages",
    ),
    "bensplumbing": (
        "mixed-profile",
        "Request local plumbing service",
        "Specific area, contact and service information makes the business identifiable. Absolute positioning, an embedded hourly price and directions about how to describe the company require evidence and freshness checks.",
        "Strict Constraints",
    ),
    "salazarroofing": (
        "mixed-guide",
        "Find roofing services",
        "Direct service and location links are useful. Multiple top-level headings and many project/social entries reduce clarity; descriptions would help distinguish service coverage from project examples.",
        "Main / Core",
    ),
    "neonelectrical": (
        "strong-small-guide",
        "Find an electrician in the service area",
        "Compact geographic scope, contact information, services and a qualifications route. Guarantee and insurance figures are owner claims here, not independently verified by this review.",
        "Service Region",
    ),
    "tau": (
        "strong-guide",
        "Research university admission",
        "Explicit institution/geographic scope helps avoid mixing campuses. Admissions, recognition, tuition, financial aid and handbooks directly support applicant decisions. Fetching destination evidence failed in this environment, so claims remain unverified.",
        "Tuition",
    ),
    "samiolearning": (
        "mixed-profile",
        "Compare children’s learning tools",
        "Distinguishes the consumer, school and companion products and provides privacy routes. Long quotable-fact and FAQ sections repeat positioning and compliance assertions; those need source verification.",
        "Quotable facts",
    ),
    "filmconnection": (
        "strong-small-guide",
        "Evaluate an apprenticeship",
        "Clear explanation of the apprenticeship model with courses, mentors, locations and tuition routes. Focused decision support; current programme promises still belong on destination pages.",
        "Tuition",
    ),
    "elitelearning": (
        "mixed-reference",
        "Find profession/state-specific education",
        "State and profession routing is useful for this catalogue, but hundreds of entries are expensive for an initial guide. Accreditation and licensing applicability should be checked on the exact course page.",
        "Nursing",
    ),
    "uams": (
        "strong-router",
        "Route clinical, education and research queries",
        "Explicit institutional scope and links to separate authoritative pillars prevent patient-care queries being confused with academic information. This is a good hierarchical entry point.",
        "Authority and Scope",
    ),
    "uamshealth": (
        "strong-guide",
        "Find providers and patient logistics",
        "Maps clinical services, providers, locations and patient information directly to tasks; includes a scope/freshness section. It supports navigation, not independent clinical advice.",
        "Patient Logistics",
    ),
    "garydriver": (
        "weak-format-mixed-navigation",
        "Find practice services and contact",
        "Relevant destinations are present, but a space between closing label bracket and opening URL parenthesis makes them plain text under CommonMark. A forgiving agent may recover them; strict Markdown consumers do not.",
        "Pages:",
    ),
    "healthcare-lk": (
        "mixed-profile",
        "Evaluate Sri Lankan clinic software",
        "Identifies country, software scope and currency, which avoids confusion with a care provider. Duplicated Pages/FAQs sections and embedded prices increase maintenance burden.",
        "Pricing",
    ),
    "attainloans": (
        "weak-first-read",
        "Find loan brokerage information",
        "Hundreds of thousands of words of concatenated pages overwhelm orientation. Full content can serve an offline search corpus, but should not be the default guide or be treated as current financial advice.",
        "Total pages",
    ),
    "cake": (
        "strong-localized-guide",
        "Navigate Vietnamese banking products",
        "Vietnamese labels, privacy, fee and product routes suit the local audience. Good evidence that evaluation must handle languages other than English; financial claims still need dated product evidence.",
        "Biểu mẫu",
    ),
    "bitcoin": (
        "strong-guide",
        "Find introductory cryptocurrency resources",
        "Task-oriented navigation separates basic education, wallets and live market information. Treat commercial self-descriptions as claims; current market facts belong at their live destinations.",
        "How to use",
    ),
    "johnmu": (
        "weak-task-labels",
        "Find technical blog articles",
        "Link labels are playful Swiss-German song-like text rather than descriptions of the linked technical posts. Valid syntax and plentiful links do not establish routing usefulness.",
        "John Mueller",
    ),
    "boehs": (
        "mixed-policy-note",
        "Identify author and blog entry point",
        "Short author context and a plain blog URL can orient readers. Most of the file communicates attribution/training preferences, not a resource guide; those statements are not a technical access-control mechanism.",
        "Blog:",
    ),
    "gilesthomas": (
        "mixed-reference",
        "Find technical articles",
        "Current author link, recent posts and category groupings are useful. The file openly repeats cross-category posts and has a large archive; duplicates here are not evidence of a careless generator by themselves.",
        "many posts have multiple categories",
    ),
    "ketofocus": (
        "mixed-catalog",
        "Find recipes",
        "Large recipe inventory and labels permit title-based search. Biography-heavy promotion and scarce recipe descriptions give little dietary/task disambiguation; health assertions are not validated here.",
        "## Recipes",
    ),
    "backpackbed": (
        "weak-navigation",
        "Donate or request assistance",
        "Names many useful actions but mainly links to one homepage. A list of section names does not provide direct donation/intake routes. Donation impact figures need current underlying evidence.",
        "Get HELP",
    ),
    "webrecorder": (
        "strong-guide",
        "Choose web archiving tools",
        "Explains distinct tools and task-specific guides including embedding and browser profiles. Clear routing between product purpose, documentation and command-line usage.",
        "Key Tools",
    ),
    "answerai": (
        "strong-small-guide",
        "Understand a research lab",
        "Mission, founding context and project overview form a concise introduction. Three links suffice for this narrow purpose; short does not inherently mean incomplete.",
        "Answer.AI projects",
    ),
    "transitionzero": (
        "strong-reference",
        "Build an energy model",
        "Descriptive workflow links cover first scenario, inputs, results and infeasibility. A useful technical index even without an introductory blockquote or many section headings.",
        "Understanding Infeasibilities",
    ),
    "trailofbits": (
        "strong-guide",
        "Find security work and tools",
        "Distinguishes library, reports, tools and services, explaining which content lives where. Useful task taxonomy; destination fetches were unavailable in this run.",
        "Key pages",
    ),
    "wheelhouse": (
        "mixed-guide",
        "Evaluate a marketing agency",
        "Service, case-study and contact routes support buyers, but descriptions are often promotional and long. Multiple labels share a destination; avoid treating them as independent evidence.",
        "Capabilities",
    ),
    "axelerant": (
        "mixed-reference",
        "Evaluate a consulting partner",
        "Core paths have useful explanations and Markdown-discovery guidance. A long tail of unexplained post/case URLs becomes an inventory, so keep it secondary to the buyer routes.",
        "How to read",
    ),
    "elogic": (
        "mixed-profile",
        "Evaluate ecommerce consulting",
        "Organized plain URLs provide company and service evidence routes. The profile asserts ratings and delivery metrics without verification in this review; lack of Markdown links alone does not make it unusable.",
        "Evidence URLs",
    ),
    "greyhound": (
        "mixed-guide",
        "Plan coach travel",
        "Covers baggage, booking and cancellation tasks, but many different labels lead to the same FAQ URL. This is useful coverage with limited destination precision, not 42 independent sources.",
        "Baggage Allowance",
    ),
    "himalayas": (
        "mixed-guide",
        "Find jobs or hiring tools",
        "Separates job seekers, employers and agent integrations. Claims about leadership and tool counts add promotional/volatile content; authentication and action boundaries deserve explicit treatment.",
        "Job Seekers",
    ),
    "openalternative": (
        "mixed-catalog",
        "Find alternative software",
        "Alternative-to descriptions add useful matching information. The file is a large inventory with recent blog links first; a category/task hub could make first-use navigation cheaper.",
        "## Tools",
    ),
    "terminaltrove": (
        "strong-plain-url-guide",
        "Browse terminal tools",
        "Compact plain-URL routes explain catalogue, categories and feeds. It violates the preferred Markdown-link convention but remains clear and useful for agent navigation.",
        "Core Resources",
    ),
    "barco": (
        "mixed-plain-url-guide",
        "Find industrial product/support evidence",
        "Task guidance distinguishes technical specifications, solutions and support. Many H1 headings and plain URLs weaken fixed-parser compatibility but not necessarily human or model understanding.",
        "AI Assistant Guidance",
    ),
    "solitek": (
        "strong-localized-reference",
        "Compare solar and storage products",
        "Separates English and German content with product-specific links. Repeated company headings and mixed regional domains need care; certifications should be interpreted per product.",
        "English Content",
    ),
    "packmojo": (
        "mixed-guide",
        "Source custom packaging",
        "Clear packaging categories, samples and ordering routes support procurement. Embedded minimum quantities, lead times and sustainability figures should defer to current product terms.",
        "Samples",
    ),
}
root = Path("evals/corpus")
manifest = json.loads((root / "manifest.json").read_text())
rows = []
for m in manifest:
    if not m["accepted"]:
        rows.append(
            {
                "id": m["id"],
                "assessment": "unavailable",
                "why": "Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.",
                "url": m["url"],
            }
        )
        continue
    verdict, purpose, why, needle = NOTES[m["id"]]
    text = (root / m["raw_path"]).read_text(encoding="utf-8-sig", errors="replace")
    matching = [i + 1 for i, line in enumerate(text.splitlines()) if needle.lower() in line.lower()]
    rows.append(
        {
            "id": m["id"],
            "assessment": verdict,
            "purpose": purpose,
            "why": why,
            "url": m["url"],
            "sha256": m["sha256"],
            "evidence_lines": matching[:3],
            "reviewer": "Codex editorial assessment",
            "review_scope": "Opening context, section structure and sampled link entries; large files were not exhaustively fact-checked.",
            "factual_verification": "Not established; destination snapshots available for a subset.",
        }
    )
write_json(root / "reviews.json", rows)
lines = [
    "# Review of actual files",
    "",
    "These are purpose-specific editorial judgments by Codex, not independent factual certification, adoption measurements, or SEO scores. Large-file reviews sampled openings, headings and link entries; a separate routing test measures a limited set of tasks. Strong means useful for the stated purpose, not universally correct. Fetch failures remain ungraded.",
    "",
]
for row in rows:
    lines += [f"## {row['id']} — {row['assessment']}", "", f"Source: [{row['id']}]({row['url']})", "", row["why"], ""]
    if row.get("purpose"):
        lines += [
            f"Purpose: {row['purpose']}. Evidence: `raw/{row['id']}.txt`, lines {', '.join(map(str, row['evidence_lines'])) or 'opening and section structure'}. Snapshot hash is recorded in reviews.json.",
            "",
        ]
(root / "REVIEWS.md").write_text("\n".join(lines))
print(len(rows), "documented file assessments")
