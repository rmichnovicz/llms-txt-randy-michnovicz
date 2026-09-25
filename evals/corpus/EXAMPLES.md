# Review of downloaded templates

Eight actual template blocks were downloaded from three publishers. These are published examples, **not deployed files on the fictional businesses**. Original page bytes, extraction selectors, timestamps and SHA-256 hashes live in `examples/manifest.json`. A Python demonstration embedded in the proposal page was excluded after inspecting its content. The fourth requested example page yielded no eligible blocks; it contributes no examples to the count.

These judgments concern structure and task usefulness. Placeholder destinations are expected in templates and must not be counted as broken production links.

| Template | Assessment | Why / what to improve |
|---|---|---|
| [Proposal restaurant example](https://llmstxt.org/domains.html) | Mixed; contains a semantic defect | Useful menu/hours structure, but the dessert description refers to Starlette software documentation. “Every day” menu availability also conflicts with Sunday closure. Replace copied descriptions and preserve opening-day exceptions. |
| [Generator: Acme Analytics](https://llmstxtgenerator.app/llms-txt-examples) | Good developer introduction | Setup, API and feature routes are differentiated. For a buyer-facing guide, add pricing and security sources only if the actual site provides them. |
| [Generator: Example Store](https://llmstxtgenerator.app/llms-txt-examples) | Good minimal shopping guide | Includes category, shipping and return routes. Does not invent stock, prices or eligibility terms. |
| [Kit: SaaS](https://llmstxtkit.com/templates/llms-txt-examples.html) | Strong buyer/developer guide | Pricing authority, documentation and security are separate; private roadmap speculation is discouraged. Do not copy a security claim just because the template has a security section. |
| [Kit: Store](https://llmstxtkit.com/templates/llms-txt-examples.html) | Strong policy hierarchy | Current product/policy pages are differentiated from older blog content; useful for resolving contradictory evidence. |
| [Kit: Local Repair](https://llmstxtkit.com/templates/llms-txt-examples.html) | Strong local-service structure | Service areas and contact authority are explicit. The same-day service assertion must be replaced or verified for each real business. |
| [Kit: Docs](https://llmstxtkit.com/templates/llms-txt-examples.html) | Strong documentation structure | Quickstart, API, deployment and changes serve separate tasks; version boundaries are explicit. |
| [Kit: Publisher](https://llmstxtkit.com/templates/llms-txt-examples.html) | Strong editorial structure | Methodology, corrections and affiliate disclosure help assess recommendations. A template is not evidence that a real publisher actually follows those practices. |

The lesson is not to reproduce a particular template. Select the relevant user tasks and preserve evidence boundaries. Correct Markdown cannot detect mismatched content; a polished template can introduce invented business facts when copied without checking.
