"""Editorial task labels. Queries are authored independently of retrieval results."""

import json
import re
from pathlib import Path

from brief.corpus import write_json

# Patterns select acceptable published entry points, not answers or invented destinations.
TASKS = {
    "stripe": [
        ("How do I verify webhook signatures?", r"webhooks(?:\.md)?$"),
        ("How can I test payments without real money?", r"/testing\.md$|/sandboxes\.md$"),
    ],
    "cloudflare": [
        ("Where do I deploy serverless application code?", r"/workers/llms.txt$"),
        ("Where is the relational SQL database documentation?", r"/d1/llms.txt$"),
    ],
    "anthropic": [
        ("How do I send my first API request?", r"get-started|quickstart"),
        ("How do prompt caching and cache reads work?", r"prompt-caching"),
    ],
    "nextjs": [
        ("How do I deploy a Next.js app?", r"/deploying"),
        ("How do I install a new application?", r"getting-started/installation"),
    ],
    "svelte": [
        ("I have a small context budget; which documentation should I load?", r"llms-small.txt$"),
        ("I need SvelteKit-specific documentation.", r"/docs/kit/llms.txt$"),
    ],
    "vite": [
        ("How do I configure the development server?", r"/config/server-options.md$"),
        ("How do I migrate an older application?", r"/guide/migration.md$"),
    ],
    "fasthtml": [
        ("I am new; where is a concise introduction?", r"concise_guide"),
        ("How does live reloading work?", r"live_reload"),
    ],
    "llmstxt": [
        ("Where is the file format defined?", r"/index.md$"),
        ("Where is the Python parser documented?", r"/intro.html.md$"),
    ],
    "framer": [
        ("What do plans cost and what are their limits?", r"/pricing\?md$"),
        ("How can an external coding assistant work inside my project?", r"/agents/external/"),
    ],
    "taskade": [
        ("How do I authenticate API calls?", r"/getting-started/authentication$"),
        ("Which MCP integration should I use?", r"/mcp/which-mcp$"),
    ],
    "tidio": [
        ("What does the support product cost?", r"/pricing/$"),
        ("Where can I try the AI agent before buying?", r"/ai-agent/playground/"),
    ],
    "mailmodo": [
        ("Where is current product pricing?", r"/pricing(?:\.md|/|$)"),
        ("Where can I read about email automation?", r"/features/email-automation-platform.md$"),
    ],
    "picflow": [
        ("How much does this photo review service cost?", r"/pricing$"),
        ("How do I install the Lightroom integration?", r"lightroom-plugin"),
    ],
    "carparts": [
        ("Where are the return rules?", r"need-to-return-an-item"),
        ("Where can I shop for headlights?", r"/headlights-and-lighting$|/headlights-components-and-accessories$"),
    ],
    "lowellbooks": [
        ("Where can I search for a book?", r"/search$"),
        ("Where are computer programming books?", r"/category/computer-programming-software-engineering/"),
    ],
    "we-in-style": [
        ("Where are refund terms?", r"/policies/refund-policy$"),
        ("Where are delivery policies?", r"/policies/shipping-policy$"),
    ],
    "mollieaspen": [
        ("What accommodation can I book?", r"/rooms/$"),
        ("Where can I see dining options?", r"/dine-drink/$"),
    ],
    "thebrando": [
        ("What activities can visitors do?", r"/experiences/$"),
        ("How do I contact the resort?", r"/contact/$"),
    ],
    "afterhoursplumbing": [
        ("How do I contact a plumber?", r"/contact/$|/services/24-hour-emergency-plumbing/$"),
        ("Where is help for a blocked drain?", r"/services/blocked-pipes-and-drains/$"),
    ],
    "bensplumbing": [("Where is the complete technical business profile?", r"llms-full.txt$")],
    "salazarroofing": [
        ("Do you work on commercial roofs?", r"/commercial-roofing-contractors-okc$"),
        ("Where do you operate?", r"/locations$"),
    ],
    "neonelectrical": [
        ("Where can I verify qualifications?", r"/qualifications/$"),
        ("How can I contact the electrician?", r"/contact/$"),
    ],
    "tau": [
        ("What are the tuition fees?", r"tuition|fees"),
        ("What recognition does the institution claim?", r"accreditation"),
    ],
    "samiolearning": [
        ("What safeguards cover children in schools?", r"schools.*privacy|privacy.*schools"),
        ("Where is the teacher interface?", r"dashboard"),
    ],
    "filmconnection": [("What does the apprenticeship cost?", r"tuition"), ("Where can I study?", r"locations")],
    "elitelearning": [
        ("Where is continuing education for California nurses?", r"california.*nursing|nursing.*california"),
        ("Where is Florida nursing education?", r"florida.*nursing|nursing.*florida"),
    ],
    "uams": [
        ("Where can I find clinical care rather than academic courses?", r"^https://uamshealth.com/llms.txt$"),
        ("Where can I find educational programs?", r"medicine.uams.edu/llms.txt$"),
    ],
    "uamshealth": [("How do I find a doctor?", r"/provider/$"), ("Where are care locations?", r"/location/$")],
    "garydriver": [
        ("Where can I learn about the surgeon?", r"/about"),
        ("Where can I contact the practice?", r"contact"),
    ],
    "healthcare-lk": [("Where is the privacy policy?", r"privacy"), ("How do I request a demo?", r"demo")],
    "cake": [
        ("Tôi muốn xem phí dịch vụ ngân hàng.", r"bieu-phi|bieu-mau"),
        ("Where is the data privacy policy?", r"bao-mat"),
    ],
    "bitcoin": [
        ("How do I learn what Bitcoin is?", r"/what-is-bitcoin/?$"),
        ("Where do I learn about self custody?", r"/wallet/bitcoin/$"),
    ],
    "gilesthomas": [
        ("Where is current information about the author?", r"/about.md$"),
        ("How does the author use AI for the blog?", r"ai.*blog|blog.*ai|/2026/07/ai-use.md$"),
    ],
    "ketofocus": [("Where can I browse recipes?", r"/recipes/$"), ("Who created the site?", r"/about")],
    "boehs": [("Where can I browse the author’s blog?", r"/in/blog$")],
    "backpackbed": [("Where is the Australian charity’s main website?", r"/au/$")],
    "webrecorder": [
        ("How can I embed an archive on a web page?", r"embed"),
        ("Where are automated crawler instructions?", r"crawler.*(guide|docs)|docs.browsertrix.com"),
    ],
    "answerai": [
        ("What research projects does the lab work on?", r"/overview.md$"),
        ("What is the lab’s mission?", r"2023-12-12-launch"),
    ],
    "transitionzero": [
        ("How do I create my first energy scenario?", r"creating-a-scenario"),
        ("How do I diagnose an infeasible energy model?", r"infeasib"),
    ],
    "trailofbits": [
        ("Where can I find security reports?", r"/reports/$"),
        ("Where can I browse open source security tools?", r"/tools/$"),
    ],
    "wheelhouse": [
        ("How can I contact the agency?", r"/contact/$"),
        ("Where are examples of previous work?", r"/work|/case-stud"),
    ],
    "axelerant": [("Where is company background?", r"/about$"), ("How does the delivery process work?", r"/approach$")],
    "elogic": [
        ("Where can I verify company background?", r"/about"),
        ("Where can I contact the consultancy?", r"/contact"),
    ],
    "greyhound": [
        ("What luggage may I bring?", r"/travel-information/faq$"),
        ("How can I cancel a trip?", r"/travel-information/faq$"),
    ],
    "himalayas": [("Where can I find remote job openings?", r"/jobs$"), ("Where is the agent integration?", r"/mcp$")],
    "openalternative": [
        ("Where can I find an open source alternative to Notion?", r"/affine$|/appflowy$|/outline$"),
        ("Where is an alternative to Google Analytics?", r"/plausible$|/umami$"),
    ],
    "terminaltrove": [
        ("Where is the full terminal tool catalogue?", r"/list/$"),
        ("Where can I browse text UI tools?", r"/categories/tui/$"),
    ],
    "barco": [("Where is product support?", r"/support(?:/|$)"), ("Where is investor information?", r"investor")],
    "solitek": [
        ("Where is English information on solar panels?", r"/en/solar-panels$"),
        ("Where is German information on batteries?", r"/de/.*(batter|speicher)"),
    ],
    "packmojo": [
        ("Where can I order packaging samples?", r"/samples/?$"),
        ("Where can I find mailer boxes?", r"/custom-packaging/mailer-boxes/$"),
    ],
}
root = Path("evals/corpus")
manifest = {m["id"]: m for m in json.loads((root / "manifest.json").read_text())}
rows = []
for site, tasks in TASKS.items():
    p = json.loads((root / "parsed" / f"{site}.json").read_text())
    for i, (query, pattern) in enumerate(tasks):
        links = p["links"] + p["bare_links"]
        gold = sorted({x["url"] for x in links if re.search(pattern, x["url"], re.IGNORECASE)})
        if not gold:
            print("UNRESOLVED", site, query, pattern)
        rows.append(
            {
                "id": f"{site}-{i + 1}",
                "file_id": site,
                "category": manifest[site]["category"],
                "split": manifest[site]["split"],
                "query": query,
                "acceptable_urls": gold,
                "rationale": "A published entry point directly addressing the requested task; routing relevance only, not verification of destination facts.",
            }
        )
write_json(root / "routing-tasks.json", rows)
print(len(rows), "curated routing tasks")
