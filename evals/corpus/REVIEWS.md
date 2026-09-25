# Review of actual files

These are purpose-specific editorial judgments by Codex, not independent factual certification, adoption measurements, or SEO scores. Large-file reviews sampled openings, headings and link entries; a separate routing test measures a limited set of tasks. Strong means useful for the stated purpose, not universally correct. Fetch failures remain ungraded.

## stripe — strong-reference

Source: [stripe](https://docs.stripe.com/llms.txt)

Task sections, Markdown destinations and integration-specific cautions give actionable technical routes. The index is large and repeats some destinations; search it rather than loading every linked page.

Purpose: API integration. Evidence: `raw/stripe.txt`, lines 5, 9, 152. Snapshot hash is recorded in reviews.json.

## cloudflare — strong-router

Source: [cloudflare](https://developers.cloudflare.com/llms.txt)

A product-level directory delegates to smaller product llms files. Descriptions differentiate services without flattening the entire platform into one enormous index.

Purpose: Find product documentation. Evidence: `raw/cloudflare.txt`, lines 5. Snapshot hash is recorded in reviews.json.

## anthropic — mixed-reference

Source: [anthropic](https://docs.anthropic.com/llms.txt)

Broad API coverage and Markdown destinations are useful. Many entries lack descriptions and the index is large, so a short-context reader needs search or a first-task guide.

Purpose: API documentation lookup. Evidence: `raw/anthropic.txt`, lines 11. Snapshot hash is recorded in reviews.json.

## nextjs — strong-reference

Source: [nextjs](https://nextjs.org/docs/llms.txt)

The file identifies its documented version, explains entries, and separates legacy Pages Router material. It is an extensive reference index, not a concise getting-started answer.

Purpose: Build a current Next.js app. Evidence: `raw/nextjs.txt`, lines 5, 6. Snapshot hash is recorded in reviews.json.

## svelte — strong-router

Source: [svelte](https://svelte.dev/llms.txt)

Small, explicit choices between compressed, abridged, full and package-specific documentation make context-budget decisions possible. Actual answers require another fetch.

Purpose: Choose documentation scope. Evidence: `raw/svelte.txt`, lines 8, 20. Snapshot hash is recorded in reviews.json.

## vite — mixed-reference

Source: [vite](https://vite.dev/llms.txt)

Compact grouping and Markdown resources are useful, but many link labels have no explanation. Introductory and reference links repeat; this is not automatically harmful.

Purpose: Build tool documentation. Evidence: `raw/vite.txt`, lines 20. Snapshot hash is recorded in reviews.json.

## fasthtml — strong-guide

Source: [fasthtml](https://www.fastht.ml/docs/llms.txt)

Explains potentially costly framework confusions and points to a concise guide, reference, and examples. The distinction from FastAPI is more valuable than generic marketing.

Purpose: Write idiomatic applications. Evidence: `raw/fasthtml.txt`, lines opening and section structure. Snapshot hash is recorded in reviews.json.

## llmstxt — strong-small-guide

Source: [llmstxt](https://llmstxt.org/llms.txt)

Very small annotated directory with a clear definition. Coverage is narrow; the historical parser/library is an entry point, not evidence that every old convention remains current.

Purpose: Understand the proposal. Evidence: `raw/llmstxt.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## framer — strong-guide

Source: [framer](https://www.framer.com/llms.txt)

Clear product scope, pricing authority, Markdown fallback and separate external-agent path. Descriptions tell the reader which source settles a question.

Purpose: Evaluate and build websites. Evidence: `raw/framer.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## taskade — mixed-profile

Source: [taskade](https://www.taskade.com/llms.txt)

Useful developer authentication and API/MCP distinctions, but extensive positioning and recommendation language competes with navigation. Embedded plan and tool-count facts can drift.

Purpose: Evaluate or integrate a workflow product. Evidence: `raw/taskade.txt`, lines 87. Snapshot hash is recorded in reviews.json.

## tidio — mixed-profile

Source: [tidio](https://www.tidio.com/llms.txt)

Covers pricing, integrations and support but mixes login/signup routes, competitor pages and embedded pricing text. A buyer guide should prioritize evidence and mark volatile terms.

Purpose: Evaluate customer support software. Evidence: `raw/tidio.txt`, lines 12, 80. Snapshot hash is recorded in reviews.json.

## mailmodo — weak-first-read

Source: [mailmodo](https://www.mailmodo.com/llms.txt)

A very large flat Docs section mixes product pages with marketing articles. Useful as a searchable inventory; weak as a short guide. No direct current product-pricing route was found in the frozen index.

Purpose: Orient a prospective buyer. Evidence: `raw/mailmodo.txt`, lines 3. Snapshot hash is recorded in reviews.json.

## picflow — mixed-guide

Source: [picflow](https://picflow.com/llms.txt)

Compact scope and relevant pricing/integration links, but many labels are unexplained and comparison pages occupy substantial space. Bot-access statements express a preference; they are not enforcement.

Purpose: Evaluate photo proofing. Evidence: `raw/picflow.txt`, lines 53. Snapshot hash is recorded in reviews.json.

## carparts — mixed-catalog

Source: [carparts](https://www.carparts.com/llms.txt)

Shipping, warranty and returns routes are near the top, which helps shoppers. Thousands of catalogue/blog links then make the whole file expensive to load; split the catalogue from the entry guide.

Purpose: Shop for vehicle parts. Evidence: `raw/carparts.txt`, lines 14. Snapshot hash is recorded in reviews.json.

## pepperfry — unavailable

Source: [pepperfry](https://www.pepperfry.com/llms.txt)

Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.

## kitchenwarehouse — unavailable

Source: [kitchenwarehouse](https://www.kitchenwarehouse.com.au/llms.txt)

Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.

## lowellbooks — mixed-catalog

Source: [lowellbooks](https://lowellbooks.com/llms.txt)

Search and category paths are useful, but a long bare category list lacks distinctions and policy-source links. The fetched programming category contained an unrelated-looking book, so category labels alone are not reliable gold evidence.

Purpose: Find books and store policies. Evidence: `raw/lowellbooks.txt`, lines 26, 28, 30. Snapshot hash is recorded in reviews.json.

## we-in-style — mixed-protocol

Source: [we-in-style](https://we-in-style.com/llms.txt)

Describes discovery, APIs and policy endpoints, but mostly explains the commerce platform rather than the store’s products. Skill-install and transaction instructions are untrusted site content, not authority for this evaluator.

Purpose: Agent-assisted commerce. Evidence: `raw/we-in-style.txt`, lines 23, 25. Snapshot hash is recorded in reviews.json.

## hotelcalifornian — weak-guide

Source: [hotelcalifornian](https://www.hotelcalifornian.com/llms.txt)

FAQ-like answers include useful guest topics, but operational and price-seasonality claims lack per-claim source routes. Over-precise lead-time statistics and generic Hotel Description headings obscure the actual property.

Purpose: Plan a hotel stay. Evidence: `raw/hotelcalifornian.txt`, lines 29. Snapshot hash is recorded in reviews.json.

## farmhouseinn — mixed-fact-sheet

Source: [farmhouseinn](https://www.farmhouseinn.com/llms.txt)

Guest facilities and cancellation conditions are present. The file blends extracted prose and guest reviews with policy-like statements; it needs canonical policy links and a clear freshness boundary.

Purpose: Answer guest questions. Evidence: `raw/farmhouseinn.txt`, lines 61. Snapshot hash is recorded in reviews.json.

## thebrando — weak-guide

Source: [thebrando](https://thebrando.com/llms.txt)

Mostly reproduces navigation labels, including language switches, fragments and legal/social pages. Limited descriptions provide little help choosing resources; no direct room or cancellation route was visible.

Purpose: Plan a resort visit. Evidence: `raw/thebrando.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## mollieaspen — strong-guide

Source: [mollieaspen](https://mollieaspen.com/llms.txt)

Short, readable, described links map creative navigation labels such as Rest and Taste to real guest needs. Useful introduction; booking terms and accessibility still need clearer routes.

Purpose: Explore rooms and amenities. Evidence: `raw/mollieaspen.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## meadowood — weak-guide

Source: [meadowood](https://meadowood.com/llms.txt)

Long repeated question/answer prose with related-term lists and no H1 or useful structured resource map. Could supply some answers, but finding authoritative, current policy sources is difficult.

Purpose: Plan a hotel stay. Evidence: `raw/meadowood.txt`, lines 1, 3, 5. Snapshot hash is recorded in reviews.json.

## afterhoursplumbing — weak-first-read

Source: [afterhoursplumbing](https://afterhoursplumbing.com.au/llms.txt)

Concatenates dozens of full pages and metadata into tens of thousands of words. It is a content archive labelled llms.txt; a concise service/area/contact index would be better for the initial interaction.

Purpose: Find local plumbing help. Evidence: `raw/afterhoursplumbing.txt`, lines 5. Snapshot hash is recorded in reviews.json.

## bensplumbing — mixed-profile

Source: [bensplumbing](https://bens.plumbing/llms.txt)

Specific area, contact and service information makes the business identifiable. Absolute positioning, an embedded hourly price and directions about how to describe the company require evidence and freshness checks.

Purpose: Request local plumbing service. Evidence: `raw/bensplumbing.txt`, lines 61. Snapshot hash is recorded in reviews.json.

## salazarroofing — mixed-guide

Source: [salazarroofing](https://www.salazarroofing.com/llms.txt)

Direct service and location links are useful. Multiple top-level headings and many project/social entries reduce clarity; descriptions would help distinguish service coverage from project examples.

Purpose: Find roofing services. Evidence: `raw/salazarroofing.txt`, lines 8. Snapshot hash is recorded in reviews.json.

## neonelectrical — strong-small-guide

Source: [neonelectrical](https://www.neonelectrical.co.nz/llms.txt)

Compact geographic scope, contact information, services and a qualifications route. Guarantee and insurance figures are owner claims here, not independently verified by this review.

Purpose: Find an electrician in the service area. Evidence: `raw/neonelectrical.txt`, lines 11. Snapshot hash is recorded in reviews.json.

## tau — strong-guide

Source: [tau](https://tau.edu.gy/llms.txt)

Explicit institution/geographic scope helps avoid mixing campuses. Admissions, recognition, tuition, financial aid and handbooks directly support applicant decisions. Fetching destination evidence failed in this environment, so claims remain unverified.

Purpose: Research university admission. Evidence: `raw/tau.txt`, lines 5, 27, 82. Snapshot hash is recorded in reviews.json.

## samiolearning — mixed-profile

Source: [samiolearning](https://www.samiolearning.com/llms.txt)

Distinguishes the consumer, school and companion products and provides privacy routes. Long quotable-fact and FAQ sections repeat positioning and compliance assertions; those need source verification.

Purpose: Compare children’s learning tools. Evidence: `raw/samiolearning.txt`, lines 150. Snapshot hash is recorded in reviews.json.

## filmconnection — strong-small-guide

Source: [filmconnection](https://www.filmconnection.com/llms.txt)

Clear explanation of the apprenticeship model with courses, mentors, locations and tuition routes. Focused decision support; current programme promises still belong on destination pages.

Purpose: Evaluate an apprenticeship. Evidence: `raw/filmconnection.txt`, lines 19. Snapshot hash is recorded in reviews.json.

## elitelearning — mixed-reference

Source: [elitelearning](https://elitelearning.com/llms.txt)

State and profession routing is useful for this catalogue, but hundreds of entries are expensive for an initial guide. Accreditation and licensing applicability should be checked on the exact course page.

Purpose: Find profession/state-specific education. Evidence: `raw/elitelearning.txt`, lines 10, 13, 16. Snapshot hash is recorded in reviews.json.

## uams — strong-router

Source: [uams](https://uams.edu/llms.txt)

Explicit institutional scope and links to separate authoritative pillars prevent patient-care queries being confused with academic information. This is a good hierarchical entry point.

Purpose: Route clinical, education and research queries. Evidence: `raw/uams.txt`, lines 27. Snapshot hash is recorded in reviews.json.

## uamshealth — strong-guide

Source: [uamshealth](https://uamshealth.com/llms.txt)

Maps clinical services, providers, locations and patient information directly to tasks; includes a scope/freshness section. It supports navigation, not independent clinical advice.

Purpose: Find providers and patient logistics. Evidence: `raw/uamshealth.txt`, lines 15, 33. Snapshot hash is recorded in reviews.json.

## garydriver — weak-format-mixed-navigation

Source: [garydriver](https://www.drgarydriver.com/llms.txt)

Relevant destinations are present, but a space between closing label bracket and opening URL parenthesis makes them plain text under CommonMark. A forgiving agent may recover them; strict Markdown consumers do not.

Purpose: Find practice services and contact. Evidence: `raw/garydriver.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## healthcare-lk — mixed-profile

Source: [healthcare-lk](https://healthcare.lk/llms.txt)

Identifies country, software scope and currency, which avoids confusion with a care provider. Duplicated Pages/FAQs sections and embedded prices increase maintenance burden.

Purpose: Evaluate Sri Lankan clinic software. Evidence: `raw/healthcare-lk.txt`, lines 5, 39. Snapshot hash is recorded in reviews.json.

## allianz — unavailable

Source: [allianz](https://www.allianz.de/llms.txt)

Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.

## attainloans — weak-first-read

Source: [attainloans](https://attainloans.com.au/llms.txt)

Hundreds of thousands of words of concatenated pages overwhelm orientation. Full content can serve an offline search corpus, but should not be the default guide or be treated as current financial advice.

Purpose: Find loan brokerage information. Evidence: `raw/attainloans.txt`, lines 5. Snapshot hash is recorded in reviews.json.

## cake — strong-localized-guide

Source: [cake](https://cake.vn/llms.txt)

Vietnamese labels, privacy, fee and product routes suit the local audience. Good evidence that evaluation must handle languages other than English; financial claims still need dated product evidence.

Purpose: Navigate Vietnamese banking products. Evidence: `raw/cake.txt`, lines 12. Snapshot hash is recorded in reviews.json.

## bitcoin — strong-guide

Source: [bitcoin](https://www.bitcoin.com/llms.txt)

Task-oriented navigation separates basic education, wallets and live market information. Treat commercial self-descriptions as claims; current market facts belong at their live destinations.

Purpose: Find introductory cryptocurrency resources. Evidence: `raw/bitcoin.txt`, lines 9, 35. Snapshot hash is recorded in reviews.json.

## johnmu — weak-task-labels

Source: [johnmu](https://johnmu.com/llms.txt)

Link labels are playful Swiss-German song-like text rather than descriptions of the linked technical posts. Valid syntax and plentiful links do not establish routing usefulness.

Purpose: Find technical blog articles. Evidence: `raw/johnmu.txt`, lines 1. Snapshot hash is recorded in reviews.json.

## boehs — mixed-policy-note

Source: [boehs](https://boehs.org/llms.txt)

Short author context and a plain blog URL can orient readers. Most of the file communicates attribution/training preferences, not a resource guide; those statements are not a technical access-control mechanism.

Purpose: Identify author and blog entry point. Evidence: `raw/boehs.txt`, lines 11. Snapshot hash is recorded in reviews.json.

## gilesthomas — mixed-reference

Source: [gilesthomas](https://www.gilesthomas.com/llms.txt)

Current author link, recent posts and category groupings are useful. The file openly repeats cross-category posts and has a large archive; duplicates here are not evidence of a careless generator by themselves.

Purpose: Find technical articles. Evidence: `raw/gilesthomas.txt`, lines 8. Snapshot hash is recorded in reviews.json.

## ketofocus — mixed-catalog

Source: [ketofocus](https://www.ketofocus.com/llms.txt)

Large recipe inventory and labels permit title-based search. Biography-heavy promotion and scarce recipe descriptions give little dietary/task disambiguation; health assertions are not validated here.

Purpose: Find recipes. Evidence: `raw/ketofocus.txt`, lines 14. Snapshot hash is recorded in reviews.json.

## jagranjosh — unavailable

Source: [jagranjosh](https://www.jagranjosh.com/llms.txt)

Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.

## backpackbed — weak-navigation

Source: [backpackbed](https://backpackbed.org/llms.txt)

Names many useful actions but mainly links to one homepage. A list of section names does not provide direct donation/intake routes. Donation impact figures need current underlying evidence.

Purpose: Donate or request assistance. Evidence: `raw/backpackbed.txt`, lines 14. Snapshot hash is recorded in reviews.json.

## webrecorder — strong-guide

Source: [webrecorder](https://webrecorder.net/llms.txt)

Explains distinct tools and task-specific guides including embedding and browser profiles. Clear routing between product purpose, documentation and command-line usage.

Purpose: Choose web archiving tools. Evidence: `raw/webrecorder.txt`, lines 9, 12. Snapshot hash is recorded in reviews.json.

## answerai — strong-small-guide

Source: [answerai](https://www.answer.ai/llms.txt)

Mission, founding context and project overview form a concise introduction. Three links suffice for this narrow purpose; short does not inherently mean incomplete.

Purpose: Understand a research lab. Evidence: `raw/answerai.txt`, lines 11. Snapshot hash is recorded in reviews.json.

## transitionzero — strong-reference

Source: [transitionzero](https://docs.transitionzero.org/llms.txt)

Descriptive workflow links cover first scenario, inputs, results and infeasibility. A useful technical index even without an introductory blockquote or many section headings.

Purpose: Build an energy model. Evidence: `raw/transitionzero.txt`, lines 13. Snapshot hash is recorded in reviews.json.

## trailofbits — strong-guide

Source: [trailofbits](https://www.trailofbits.com/llms.txt)

Distinguishes library, reports, tools and services, explaining which content lives where. Useful task taxonomy; destination fetches were unavailable in this run.

Purpose: Find security work and tools. Evidence: `raw/trailofbits.txt`, lines 9. Snapshot hash is recorded in reviews.json.

## wheelhouse — mixed-guide

Source: [wheelhouse](https://www.wheelhousedmg.com/llms.txt)

Service, case-study and contact routes support buyers, but descriptions are often promotional and long. Multiple labels share a destination; avoid treating them as independent evidence.

Purpose: Evaluate a marketing agency. Evidence: `raw/wheelhouse.txt`, lines 5, 8, 9. Snapshot hash is recorded in reviews.json.

## axelerant — mixed-reference

Source: [axelerant](https://www.axelerant.com/llms.txt)

Core paths have useful explanations and Markdown-discovery guidance. A long tail of unexplained post/case URLs becomes an inventory, so keep it secondary to the buyer routes.

Purpose: Evaluate a consulting partner. Evidence: `raw/axelerant.txt`, lines 7. Snapshot hash is recorded in reviews.json.

## elogic — mixed-profile

Source: [elogic](https://elogic.co/llms.txt)

Organized plain URLs provide company and service evidence routes. The profile asserts ratings and delivery metrics without verification in this review; lack of Markdown links alone does not make it unusable.

Purpose: Evaluate ecommerce consulting. Evidence: `raw/elogic.txt`, lines 21. Snapshot hash is recorded in reviews.json.

## greyhound — mixed-guide

Source: [greyhound](https://www.greyhound.com.au/llms.txt)

Covers baggage, booking and cancellation tasks, but many different labels lead to the same FAQ URL. This is useful coverage with limited destination precision, not 42 independent sources.

Purpose: Plan coach travel. Evidence: `raw/greyhound.txt`, lines 68, 71. Snapshot hash is recorded in reviews.json.

## himalayas — mixed-guide

Source: [himalayas](https://himalayas.app/llms.txt)

Separates job seekers, employers and agent integrations. Claims about leadership and tool counts add promotional/volatile content; authentication and action boundaries deserve explicit treatment.

Purpose: Find jobs or hiring tools. Evidence: `raw/himalayas.txt`, lines 4, 8, 32. Snapshot hash is recorded in reviews.json.

## openalternative — mixed-catalog

Source: [openalternative](https://openalternative.co/llms.txt)

Alternative-to descriptions add useful matching information. The file is a large inventory with recent blog links first; a category/task hub could make first-use navigation cheaper.

Purpose: Find alternative software. Evidence: `raw/openalternative.txt`, lines 17. Snapshot hash is recorded in reviews.json.

## terminaltrove — strong-plain-url-guide

Source: [terminaltrove](https://terminaltrove.com/llms.txt)

Compact plain-URL routes explain catalogue, categories and feeds. It violates the preferred Markdown-link convention but remains clear and useful for agent navigation.

Purpose: Browse terminal tools. Evidence: `raw/terminaltrove.txt`, lines 5. Snapshot hash is recorded in reviews.json.

## barco — mixed-plain-url-guide

Source: [barco](https://www.barco.com/en/llms.txt)

Task guidance distinguishes technical specifications, solutions and support. Many H1 headings and plain URLs weaken fixed-parser compatibility but not necessarily human or model understanding.

Purpose: Find industrial product/support evidence. Evidence: `raw/barco.txt`, lines 5. Snapshot hash is recorded in reviews.json.

## solitek — strong-localized-reference

Source: [solitek](https://www.solitek.eu/llms.txt)

Separates English and German content with product-specific links. Repeated company headings and mixed regional domains need care; certifications should be interpreted per product.

Purpose: Compare solar and storage products. Evidence: `raw/solitek.txt`, lines 9. Snapshot hash is recorded in reviews.json.

## sepmag — unavailable

Source: [sepmag](https://www.sepmag.eu/llms.txt)

Fetch failed, was blocked, or returned an error. No quality judgment about an unavailable file.

## packmojo — mixed-guide

Source: [packmojo](https://packmojo.com/llms.txt)

Clear packaging categories, samples and ordering routes support procurement. Embedded minimum quantities, lead times and sustainability figures should defer to current product terms.

Purpose: Source custom packaging. Evidence: `raw/packmojo.txt`, lines 3, 5, 44. Snapshot hash is recorded in reviews.json.
