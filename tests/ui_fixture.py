"""Local browser-test data only. No network crawler or paid model calls."""

from __future__ import annotations

import json
import sys
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from brief.contracts import Source
from brief.crawl.runner import CrawlResult
from brief.db import Database, require_row
from brief.model import Completion
from brief.refresh import Observation, content_hash
from brief.store import Store

store = Store(Database("postgresql://brief:brief-local-only@localhost:55432/brief_browser"))


def drain(project_id: UUID) -> None:
    with store.db.connect() as connection:
        job = connection.execute(
            """UPDATE jobs SET status='running', attempt=attempt+1, lease_token=%s,
            lease_expires_at=now()+interval '3 minutes' WHERE id=(SELECT id FROM jobs WHERE project_id=%s
            AND status='pending' ORDER BY created_at LIMIT 1) RETURNING *""",
            (uuid4(), project_id),
        ).fetchone()
    if not job:
        return
    context = store.generation_context(job)
    links = [{"sourceId": s.id, "label": s.title, "description": s.description} for s in context.sources]
    question: dict[str, Any] = {
        "topic": "audience",
        "question": "Who should this guide help first?",
        "rationale": "Developers need implementation details. Buyers need to understand capabilities and pricing.",
        "evidenceIds": ["home", "api"],
        "options": ["Developers integrating Acme", "Teams evaluating Acme", "Both, with a short path for each"],
        "recommendedOption": 0,
    }
    questions = (
        [] if "audience" in context.dismissed_topics or any(d.needs_review for d in context.decisions) else [question]
    )
    guide: dict[str, Any] = {
        "title": "Acme",
        "summary": {
            "text": "Search your internal knowledge with a simple, developer-friendly API.",
            "evidenceIds": ["home"],
        },
        "context": [
            {"text": " ".join(d.statement.split()), "evidenceIds": [d.id]}
            for d in context.decisions
            if not d.needs_review
        ],
        "sections": [{"title": "Start building", "links": links}],
    }
    raw: dict[str, Any] = {
        "guide": None if context.mode == "questions" else guide,
        "questions": questions,
        "explanation": "I’ve organized the essentials around the product, API reference, and pricing. One audience choice could make this more useful."
        if questions
        else "No consequential questions remain. Your saved direction is clear.",
    }
    store.finish_generation(
        job, context, Completion(raw, {"provider": "browser-test-fixture", "model": "deterministic"})
    )


token: str | None
if sys.argv[1] in {"seed", "seed-auto", "crawl"}:
    if sys.argv[1] in {"seed", "seed-auto"}:
        project, token, _ = store.create_project("https://acme.example.com/")
    else:
        with store.db.connect() as connection:
            project = require_row(
                connection.execute("SELECT * FROM projects WHERE id=%s", (UUID(sys.argv[2]),)).fetchone()
            )
        token = None
    base = project["site_url"].rstrip("/")
    sources = [
        Source(
            id="home",
            url=base + "/",
            title="About Acme",
            description="What Acme does and who it helps.",
            content="Acme offers a hosted search API for internal documents.",
        ),
        Source(
            id="api",
            url=base + "/docs",
            title="API reference",
            description="Authentication, search requests, and response formats."
            + (" Updated source." + (sys.argv[3] if len(sys.argv) > 3 else "") if sys.argv[1] == "crawl" else ""),
            content="Authenticate with an API key and send a search query to get matching documents.",
        ),
        Source(
            id="pricing",
            url=base + "/pricing",
            title="Pricing",
            description="Plans for small teams and larger organizations.",
            content="Starter costs twenty dollars per month. Enterprise pricing is custom.",
        ),
    ]
    if sys.argv[1] == "seed-auto":
        sources.extend(
            [sources[1].model_copy(update={"id": f"docs-{i}", "url": base + f"/docs/page-{i}"}) for i in range(3)]
        )
    with store.db.connect() as connection:
        job = connection.execute(
            "UPDATE jobs SET status='running',attempt=1,lease_token=%s,lease_expires_at=now()+interval '3 minutes' WHERE project_id=%s AND status='pending' RETURNING *",
            (uuid4(), project["id"]),
        ).fetchone()
    result = CrawlResult(
        sources=sources,
        observations=[Observation(s.url, "ok", content_hash(s.title, s.description, s.content)) for s in sources],
        attempted=3,
        discovered=3,
    )
    assert job is not None
    store.finish_crawl(job, result, enqueue_generation=True)
    drain(project["id"])
    print(json.dumps({"id": str(project["id"]), "token": token}))
elif sys.argv[1] == "existing-guide":
    from brief.publication import save_check

    save_check(
        store,
        UUID(sys.argv[2]),
        {
            "checked_at": "2026-09-25T00:00:00Z",
            "complete": True,
            "guides": [
                {
                    "url": "https://acme.example.com/llms.txt",
                    "requested_url": "https://acme.example.com/llms.txt",
                    "markdown": "# Existing Acme guide\n\nAn older overview.\n",
                    "sha256": "fixture",
                }
            ],
            "checks": [{"url": "https://acme.example.com/llms.txt", "status": "found"}],
        },
    )
elif sys.argv[1] == "drain":
    drain(UUID(sys.argv[2]))
elif sys.argv[1] == "fail":
    with store.db.connect() as connection:
        connection.execute(
            "UPDATE jobs SET status='failed', error='The website did not respond. Try again.' WHERE project_id=%s AND status='pending'",
            (UUID(sys.argv[2]),),
        )
elif sys.argv[1] == "cleanup":
    with store.db.connect() as connection:
        connection.execute(
            "DELETE FROM sites WHERE id=(SELECT site_id FROM projects WHERE id=%s)", (UUID(sys.argv[2]),)
        )
elif sys.argv[1] == "progress":
    from psycopg.types.json import Jsonb

    with store.db.connect() as connection:
        connection.execute(
            "UPDATE jobs SET progress=%s WHERE project_id=%s AND status='pending'",
            (
                Jsonb(
                    {
                        "stage": "reading",
                        "message": "Read: Plans and pricing",
                        "pages_read": 7,
                        "pages_found": 19,
                        "started_at": "2026-09-25T00:00:00Z",
                    }
                ),
                UUID(sys.argv[2]),
            ),
        )
elif sys.argv[1] == "evaluate":
    import asyncio

    from brief import guide_tests

    project_id = UUID(sys.argv[2])
    with store.db.connect() as c:
        job = c.execute(
            """UPDATE jobs SET status='running',attempt=attempt+1,lease_token=%s,
            lease_expires_at=now()+interval '3 minutes' WHERE project_id=%s AND status='pending' AND kind='evaluate' RETURNING *""",
            (uuid4(), project_id),
        ).fetchone()
        assert job is not None
        suite = c.execute(
            "SELECT s.sources FROM guide_test_suites s JOIN guide_test_runs r ON r.suite_id=s.id WHERE r.job_id=%s",
            (job["id"],),
        ).fetchone()
    assert suite is not None
    source = next(s for s in suite["sources"] if s["id"] == "api")

    class TestModel:
        def complete(self, request: dict[str, Any], *, result_type: type[BaseModel] = BaseModel) -> Completion:
            raw: dict[str, Any]
            if result_type is guide_tests.Suggestions:
                raw = {
                    "questions": [
                        {
                            "question": "How do I authenticate a search request?",
                            "expected_url": source["url"],
                            "reference_quote": source["content"],
                        }
                    ]
                }
            else:
                observations = json.loads(request["user"])["observations"]
                if source["url"] not in observations[0]["content"]:
                    raw = {
                        "action": "abstain",
                        "url": None,
                        "answer": "This guide does not link to authentication details.",
                        "citations": [],
                    }
                elif len(observations) == 1:
                    raw = {"action": "open", "url": source["url"], "answer": "", "citations": []}
                else:
                    raw = {
                        "action": "answer",
                        "url": None,
                        "answer": "Authenticate using an API key.",
                        "citations": [{"url": source["url"], "passage_id": "p1"}],
                    }
            return Completion(raw, {"model": "browser-test-fixture"})

    async def progress(data: dict[str, Any]) -> None:
        assert job is not None
        store.report_progress(job, data)

    asyncio.run(guide_tests.run(store, job, TestModel(), progress, reader=TestModel()))
