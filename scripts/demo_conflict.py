"""Create a fictional shipping-policy demo using the real model after refresh.

Run with the local worker stopped so it cannot fetch this fictional website.
Only creates a new project; never modifies an existing one. Prints its private link.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from brief import editor
from brief.contracts import Source
from brief.crawl.runner import CrawlResult
from brief.db import Database
from brief.model import Completion, OpenAIGenerator
from brief.refresh import Observation, content_hash
from brief.store import Store


def capture(threshold: int) -> CrawlResult:
    sources = [
        Source(
            id="shipping",
            url="https://demo-shop.example.com/shipping",
            title="Shipping policy",
            description="Standard shipping within mainland France.",
            content=f"Demo Atelier sells homewares. Standard delivery in mainland France is free for orders over €{threshold}. Below that threshold, delivery costs €12. This policy applies to standard delivery only.",
        )
    ]
    return CrawlResult(
        sources=sources,
        observations=[Observation(s.url, "ok", content_hash(s.title, s.description, s.content)) for s in sources],
        attempted=1,
        discovered=1,
    )


def main() -> None:
    db = Database()
    db.migrate()
    store = Store(db)
    project, token, _ = store.create_project("https://demo-shop.example.com/")
    pid = project["id"]

    def claim() -> dict[str, Any]:
        # Scope demo work to this new project, even in a shared development DB.
        with store.db.connect() as connection:
            row = connection.execute(
                """UPDATE jobs SET status='running', attempt=attempt+1, lease_token=%s,
                lease_expires_at=now()+interval '3 minutes' WHERE id=(SELECT id FROM jobs
                WHERE project_id=%s AND status='pending' ORDER BY created_at LIMIT 1) RETURNING *""",
                (uuid4(), pid),
            ).fetchone()
            assert row is not None
            return row

    store.finish_crawl(claim(), capture(300), enqueue_generation=True)

    def baseline() -> None:
        job = claim()
        context = store.generation_context(job)
        guide: dict[str, Any] = {
            "title": "Demo Atelier",
            "summary": {"text": "Homewares delivered within mainland France.", "evidenceIds": ["shipping"]},
            "context": [
                {
                    "text": "Free standard delivery over €450, confirmed by the owner until the website is corrected.",
                    "evidenceIds": [context.decisions[0].id],
                }
            ]
            if context.decisions
            else [],
            "sections": [
                {
                    "title": "Shopping",
                    "links": [{"sourceId": "shipping", "label": "Shipping policy", "description": None}],
                }
            ],
        }
        store.finish_generation(
            job,
            context,
            Completion(
                {
                    "guide": guide,
                    "questions": [],
                    "explanation": "Fictional demo: the owner supplied a temporary shipping correction.",
                },
                {"provider": "demo-baseline"},
            ),
        )

    baseline()
    state = store.get_project(pid, token)
    assert state is not None
    editor.save_decision(
        store,
        pid,
        state["revision"],
        statement="Use €450 for free standard delivery in mainland France until the website is corrected.",
        kind="fact",
    )
    baseline()
    store.enqueue_refresh(pid, "demo-policy-change")
    store.finish_crawl(claim(), capture(600), enqueue_generation=True)
    job = claim()
    context = store.generation_context(job)
    completion = OpenAIGenerator().generate(context)
    store.finish_generation(job, context, completion)
    state = store.get_project(pid, token)
    assert state is not None
    assert state["decisions"][0]["needs_review"]
    assert "450" in state["draft"]["markdown"]
    assert all(amount not in state["proposal"]["markdown"] for amount in ["300", "450", "600"]), (
        "Model asserted a disputed amount; inspect saved project"
    )
    out = Path("evals/results/conflict-demo")
    out.mkdir(parents=True, exist_ok=True)
    (out / "generation.json").write_text(
        json.dumps(
            {"input": context.model_dump(by_alias=True), "output": completion.raw, "metadata": completion.metadata},
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "id": str(pid),
                "url": f"http://127.0.0.1:5174/p/{pid}#key={token}",
                "review": True,
                "proposal_omits_disputed_amount": True,
            }
        )
    )


if __name__ == "__main__":
    main()
