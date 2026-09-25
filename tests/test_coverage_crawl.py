from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel
from pytest import MonkeyPatch
from test_crawl import FakeFetcher
from test_model import FakeClient

from brief.crawl.cache import PageCache
from brief.crawl.fetch import Response
from brief.crawl.planning import assess
from brief.crawl.runner import crawl
from brief.interfaces import Progress
from brief.model import OpenAIGenerator

if TYPE_CHECKING:
    from brief.contracts import Source
    from brief.crawl.runner import CrawlResult
    from brief.model import Completion
    from brief.store import Store


ROOT = "https://example.com/"


def website(count: int = 65) -> tuple[FakeFetcher, list[str]]:
    urls = [ROOT + f"article-{i}" for i in range(count)]
    body = (
        "<html><title>Example</title><main><p>Example makes tools for teams to organize and share their documents.</p>"
    )
    home = body + "".join(f'<a href="{u}">Resource {i}</a>' for i, u in enumerate(urls)) + "</main></html>"
    pages = {ROOT: Response(ROOT, 200, "text/html", home.encode())}
    pages.update({u: Response(u, 200, "text/html", (body + "</main></html>").encode()) for u in urls})
    return FakeFetcher(pages), urls


async def test_default_crawl_is_not_cut_off_at_fifty_pages() -> None:
    fetcher, urls = website()
    result = await crawl(ROOT, fetcher=fetcher)
    assert len(result.sources) == len(urls) + 1 == 66
    assert result.stop_reason == "exhausted"
    assert not result.truncated


async def test_assessor_can_select_more_than_fifty_pages() -> None:
    fetcher, urls = website()
    calls = []

    async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
        calls.append(candidates)
        return {"urls": urls, "reason": "Each resource is needed for this inventory.", "gaps": []}

    result = await crawl(ROOT, fetcher=fetcher, initial_batch=1, assessor=assessor)
    assert len(calls) == 1 and len(result.sources) == 66
    assert result.stop_reason == "coverage_plan_finished"


async def test_targeted_pass_skips_redundant_pages_but_rechecks_previous_sources() -> None:
    fetcher, urls = website()

    async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
        return {"urls": [urls[3]], "reason": "Read the missing policy.", "gaps": ["Policy details"]}

    result = await crawl(ROOT, [urls[1]], fetcher=fetcher, initial_batch=1, assessor=assessor)
    assert {s.url for s in result.sources} == {ROOT, urls[1], urls[3]}
    assert result.unread == 63
    assert result.assessment is not None
    assert result.assessment["gaps"] == ["Policy details"]
    assert result.truncated  # Selected coverage is not an exhaustive site crawl.


async def test_invalid_plan_falls_back_without_fetching_invented_urls() -> None:
    fetcher, _urls = website(3)

    async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
        return {"urls": ["http://127.0.0.1/secrets"], "reason": "Wrong", "gaps": []}

    result = await crawl(ROOT, fetcher=fetcher, initial_batch=1, assessor=assessor)
    assert len(result.sources) == 4
    assert "http://127.0.0.1/secrets" not in fetcher.visited
    assert any("Coverage assessment unavailable" in w["reason"] for w in result.warnings)


@pytest.mark.parametrize("budget,reason", [("byte_budget", "download_budget"), ("text_budget", "text_budget")])
async def test_resource_budget_is_reported_honestly(budget: str, reason: str) -> None:
    fetcher, _ = website(3)
    options: dict[str, Any] = {budget: 1}
    result = await crawl(ROOT, fetcher=fetcher, **options)
    assert result.stop_reason == reason
    assert result.truncated


async def test_reading_order_prioritizes_pricing_over_signup_and_deep_articles() -> None:
    fetcher, _ = website(0)
    body = "<html><main><p>A product with comprehensive documentation and pricing for businesses.</p>"
    urls = [ROOT + "signup", ROOT + "docs/deep/tutorial", ROOT + "pricing"]
    fetcher.pages[ROOT] = Response(
        ROOT, 200, "text/html", (body + "".join(f'<a href="{u}">Link</a>' for u in urls) + "</main></html>").encode()
    )
    await crawl(ROOT, fetcher=fetcher)
    pages = [u for u in fetcher.visited if u in urls]
    assert pages[0] == ROOT + "pricing"
    assert pages[-1] == ROOT + "signup"


def test_model_coverage_schema_and_unknown_url_rejection() -> None:
    response = SimpleNamespace(
        status="completed",
        output=[],
        model="fixture",
        id="fixture",
        usage=None,
        output_text=json.dumps({"urls": [ROOT + "invented"], "reason": "Read more", "gaps": []}),
    )
    client = FakeClient(response=response)
    generator = OpenAIGenerator(client=client)
    with pytest.raises(ValueError, match="undiscovered"):
        assess(generator, [], [ROOT + "pricing"], [{"statement": "Help buyers"}])
    assert client.request is not None
    assert "Help buyers" in client.request["input"][1]["content"]
    assert "urls" in client.request["text"]["format"]["schema"]["properties"]


async def test_specific_entry_pages_beat_alphabetically_early_help_articles() -> None:
    from brief.crawl.planning import priority

    urls = [ROOT + "help/10-free-templates", ROOT + "help/get-started", ROOT + "help/plans-and-pricing"]
    ordered = sorted(urls, key=lambda u: priority(u, ROOT, set()))
    assert ordered[-1].endswith("10-free-templates")


async def test_targeted_pass_keeps_the_models_reading_priority() -> None:
    fetcher, urls = website(3)

    async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
        return {"urls": [urls[2], urls[0]], "reason": "Read the policy before the examples.", "gaps": []}

    result = await crawl(ROOT, fetcher=fetcher, initial_batch=1, assessor=assessor)
    assert [s.url for s in result.sources] == [ROOT, urls[2], urls[0]]


@pytest.mark.integration
async def test_worker_gives_the_planner_saved_owner_direction(store: Store, monkeypatch: MonkeyPatch) -> None:
    from test_editor import finish, setup_project
    from test_generation_jobs import Generator
    from test_store import result, source

    from brief import editor, worker
    from brief.model import Completion

    project, _token = setup_project(store)
    editor.save_decision(store, project["id"], project["revision"], statement="Prioritize buyers", kind="preference")
    finish(store)
    store.enqueue_refresh(project["id"], "coverage-check")
    requests = []

    class PlanningGenerator(Generator):
        def complete(self, request: dict[str, Any], *, result_type: type[BaseModel]) -> Completion:
            requests.append(json.loads(request["user"]))
            return Completion({"urls": [], "reason": "Enough detail for buyers.", "gaps": []}, {})

    async def crawler(
        url: str,
        previous: Sequence[str],
        *,
        assessor: Callable[[list[Source], list[str]], Awaitable[dict[str, Any]]],
        progress: Progress,
        cache: PageCache,
        discovery_state: dict[str, Any] | None,
    ) -> CrawlResult:
        plan = await assessor([source()], [ROOT + "pricing"])
        assert plan["reason"] == "Enough detail for buyers."
        return result(source())

    monkeypatch.setattr(worker, "crawl", crawler)
    await worker.run_once(store, crawler=crawler, generator=PlanningGenerator())
    assert requests[0]["direction"][0]["statement"] == "Prioritize buyers"


async def test_large_inventory_balances_model_candidates_and_retains_unread_urls() -> None:
    from brief.crawl.inventory import balanced

    fetcher, _ = website(0)
    urls = [ROOT + f"docs/reference/{i:05d}" for i in range(2200)] + [ROOT + "pricing", ROOT + "help/start"]
    xml = "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"
    fetcher.pages[ROOT + "sitemap.xml"] = Response(ROOT + "sitemap.xml", 200, "application/xml", xml.encode())
    calls = []

    async def assessor(sources: list[Source], candidates: list[str]) -> dict[str, Any]:
        calls.append(candidates)
        return {"urls": [], "reason": "Enough for the overview.", "gaps": []}

    result = await crawl(ROOT, fetcher=fetcher, initial_batch=1, assessor=assessor)
    assert result.discovered == 2203
    assert result.discovery_state is not None
    assert len(result.discovery_state["urls"]) == 2202
    assert ROOT + "pricing" in calls[0] and ROOT + "help/start" in calls[0]
    assert len(json.dumps(calls[0], ensure_ascii=False, separators=(",", ":")).encode()) <= 24000
    assert balanced(reversed(urls), ROOT) == balanced(urls, ROOT)


async def test_inventory_byte_budget_resumes_inside_sitemap() -> None:
    fetcher, _ = website(0)
    urls = [ROOT + f"docs/{i}" for i in range(20)]
    xml = "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"
    fetcher.pages[ROOT + "sitemap.xml"] = Response(ROOT + "sitemap.xml", 200, "application/xml", xml.encode())
    first = await crawl(ROOT, fetcher=fetcher, inventory_byte_budget=180, max_pages=1)
    pending = first.discovery_state
    assert pending is not None
    assert pending["sitemaps"][ROOT + "sitemap.xml"] > 0
    second = await crawl(
        ROOT,
        previous_urls=pending["urls"],
        discovery_state=pending,
        fetcher=fetcher,
        inventory_byte_budget=180,
        max_pages=1,
    )
    assert second.discovery_state is not None
    assert second.discovery_state["sitemaps"][ROOT + "sitemap.xml"] > pending["sitemaps"][ROOT + "sitemap.xml"]
    assert set(second.discovery_state["urls"]) - set(pending["urls"])


@pytest.mark.integration
def test_discovery_frontiers_are_private_persistent_and_cascade(store: Store) -> None:
    from test_editor import setup_project

    from brief.crawl.inventory import load, save

    project, _ = setup_project(store)
    other, _ = setup_project(store)
    state: dict[str, Any] = {"urls": [ROOT + "docs/a"], "sitemaps": {ROOT + "sitemap.xml": 1234}}
    with store.db.connect() as connection:
        save(connection, project["id"], state)
    assert load(store.db, project["id"]) == state
    assert load(store.db, other["id"]) is None
    with store.db.connect() as connection:
        connection.execute("DELETE FROM projects WHERE id=%s", (project["id"],))
    assert load(store.db, project["id"]) is None


async def test_saved_plan_rechecks_sources_without_planning_or_expanding_selection() -> None:
    fetcher, urls = website(5)

    async def assessor(*args: Any) -> dict[str, Any]:
        pytest.fail("An unchanged selection must not call the planner")

    plan: dict[str, Any] = {
        "urls": [urls[2]],
        "reason": "Read the policy.",
        "gaps": [],
        "metadata": {"duration_ms": 16000},
    }
    messages = []

    async def progress(event: dict[str, Any]) -> None:
        messages.append(event["message"])

    result = await crawl(ROOT, [ROOT, urls[0]], fetcher=fetcher, saved_plan=plan, assessor=assessor, progress=progress)
    assert [s.url for s in result.sources] == [ROOT, urls[2], urls[0]]
    assert result.assessment is not None
    assert result.assessment["reused"] is True
    assert "metadata" not in result.assessment
    assert result.stop_reason == "coverage_plan_finished"
    assert result.discovery_state is not None
    assert set(result.discovery_state["urls"]) == {urls[1], urls[3], urls[4]}
    assert all(u not in fetcher.visited for u in [urls[1], urls[3], urls[4]])
    assert any("Reusing the saved page selection" in message for message in messages)
    assert "metadata" in plan  # Reuse does not mutate the prior snapshot.


@pytest.mark.integration
@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize("change_direction", [True, False])
async def test_worker_reuses_plan_until_owner_direction_changes(
    store: Store, monkeypatch: MonkeyPatch, legacy: bool, change_direction: bool
) -> None:
    from psycopg.types.json import Jsonb
    from test_editor import finish, setup_project
    from test_generation_jobs import Generator
    from test_store import result, source

    from brief import editor, worker
    from brief.model import Completion

    project, token = setup_project(store)
    plan: dict[str, Any] = {"urls": [], "reason": "The home page is enough.", "gaps": []}
    if not legacy:
        plan["direction"] = []
    with store.db.connect() as c:
        c.execute(
            "UPDATE crawl_snapshots SET coverage=%s WHERE id=%s",
            (Jsonb({"assessment": plan}), project["latest_snapshot_id"]),
        )
        c.execute("UPDATE projects SET existing_guide_check='{}'::jsonb WHERE id=%s", (project["id"],))
    if change_direction:
        editor.save_decision(
            store, project["id"], project["revision"], statement="Prioritize buyers", kind="preference"
        )
        finish(store)
    store.enqueue_refresh(project["id"], "check-selection")
    calls = []

    class PlanningGenerator(Generator):
        def complete(self, request: dict[str, Any], *, result_type: type[BaseModel]) -> Completion:
            calls.append(request)
            return Completion({"urls": [], "reason": "Updated selection.", "gaps": []}, {})

    async def crawler(url: str, previous: Sequence[str], **options: Any) -> CrawlResult:
        if change_direction:
            assert "saved_plan" not in options
            assessment = await options["assessor"]([source()], [])
            assert assessment["direction"][0]["statement"] == "Prioritize buyers"
        else:
            assert "assessor" not in options
            assessment = options["saved_plan"]
        output = result(source())
        output.assessment = assessment
        return output

    monkeypatch.setattr(worker, "crawl", crawler)
    await worker.run_once(store, crawler=crawler, generator=PlanningGenerator())
    state = store.get_project(project["id"], token)
    assert state is not None
    assert state["jobs"][0]["status"] == "succeeded"
    assert state["snapshot"]["changes"]["changed"] is False
    assert len(calls) == int(change_direction)
    # A completed draft plus unchanged source content needs no generation job.
    assert not await worker.run_once(store, generator=PlanningGenerator())
