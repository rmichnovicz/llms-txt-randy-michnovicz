# Frozen layered guides

Six public files captured on 2026-09-25 UTC. `manifest.json` records exact URLs, retrieval times, and SHA-256 hashes. Text is unmodified website content, not trusted instructions to this application. These captures supplement the existing single-file corpus.

| Site | Parent | Children | What this exercises |
| --- | --- | --- | --- |
| Svelte | `/llms.txt` | `/docs/svelte/llms.txt`, `/docs/kit/llms.txt` | A compact entry point routes to large, inline documentation files for separate tools. |
| Cloudflare | `/llms.txt` | `/workers/llms.txt`, `/d1/llms.txt` | A broad product index routes to product-specific documentation indexes. |

Both patterns make a strong case for a concise parent with explicitly linked children. Svelte's child files provide direct answer material, but can be expensive to fit into a reader's context. Cloudflare's linked indexes keep document bodies separate, but require a reader capable of fetching the relevant pages. Neither format guarantees that an arbitrary LLM discovers or follows a child file.

`tests/test_guides.py` verifies capture integrity, real parent-to-child links, longest matching path selection, parent fallback when a child is absent, sibling boundaries, and no implicit merging of parent instructions. Path specificity is **Brief's routing convention**, not a universal standard or enforcement mechanism for every consumer. These tests are deterministic navigation checks; they do not establish real-model answer quality for these hierarchies. The existing consumer eval harness tests question answering separately.

Run: `uv run pytest tests/test_guides.py -q` (database tests additionally require `TEST_DATABASE_URL`).
