from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("end_to_end", Path(__file__).parents[1] / "evals" / "end_to_end.py")
assert SPEC is not None and SPEC.loader is not None
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)
CORPUS, measure, run, run_case = harness.CORPUS, harness.measure, harness.run, harness.run_case


def test_metrics_separate_crawl_loss_from_generation_loss() -> None:
    metrics = measure({"root", "policy", "blocked"}, {"root", "policy", "extra"}, {"root", "invented"})
    assert metrics["crawl_important_coverage"]["matched"] == 2
    assert metrics["generated_important_coverage"]["matched"] == 1
    assert metrics["generated_usable_source_coverage"]["missing"] == ["extra", "policy"]
    assert metrics["generated_link_precision"]["ratio"] == 0.5
    assert metrics["unsupported_destinations"] == ["invented"]
    empty = measure({"blocked"}, set(), set())
    assert empty["crawl_important_coverage"]["ratio"] == 0
    assert empty["generated_link_precision"]["ratio"] is None


async def test_frozen_replay_keeps_known_gaps_and_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "replay"
    report = await run(CORPUS, output)
    assert report["mode"] == "metadata-baseline"
    assert report["summary"]["cases"] == 12
    assert report["summary"]["generation_errors"] == 0
    assert report["summary"]["crawl_important_coverage"] == {"matched": 23, "total": 30, "ratio": 23 / 30}
    rows = {row["id"]: row for row in report["results"]}
    expected_counts = {
        "developer-docs": (3, 3),
        "retail-shop": (3, 3),
        "local-services": (3, 3),
        "news-publication": (3, 3),
        "multilingual": (3, 3),
        "sitemap-discovery": (2, 2),
        "path-scoped": (2, 2),
        "robots-blocked": (1, 2),
        "transient-failure": (1, 2),
        "javascript-only": (0, 1),
        "pdf-resource": (1, 2),
        "bounded-crawl": (1, 4),
    }
    for case, (matched, total) in expected_counts.items():
        metric = rows[case]["metrics"]["crawl_important_coverage"]
        assert (metric["matched"], metric["total"]) == (matched, total), case
    for case, missing in {
        "robots-blocked": "/restricted",
        "transient-failure": "/accessibility",
        "javascript-only": "/",
        "pdf-resource": "/handbook.pdf",
        "bounded-crawl": "/lesson-three",
    }.items():
        assert f"https://{case}.example.com{missing}" in rows[case]["metrics"]["crawl_important_coverage"]["missing"]
    assert rows["bounded-crawl"]["crawl_truncated"]
    assert rows["javascript-only"]["metrics"]["generated_usable_source_coverage"]["ratio"] is None
    assert rows["sitemap-discovery"]["metrics"]["crawl_important_coverage"]["ratio"] == 1
    requests = json.loads((output / "path-scoped" / "requests.json").read_text())
    assert "https://path-scoped.example.com/archive/old" not in requests
    assert (output / "corpus.json").read_bytes() == CORPUS.read_bytes()
    for case in rows:
        for name in ("crawl.json", "requests.json", "request.json", "response.json", "llms.txt", "result.json"):
            assert (output / case / name).is_file()
    with pytest.raises(FileExistsError):
        await run(CORPUS, output)


async def test_invalid_adapter_result_is_retained_as_failure(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    adapter.write_text('#!/bin/sh\nprintf \'{"guide": null,"questions": [],"explanation":"Broken generation"}\\n\'\n')
    adapter.chmod(0o700)
    case = json.loads(CORPUS.read_text())[0]
    output = tmp_path / "case"
    result = await run_case(case, output, adapter=str(adapter))
    assert result["generation_error"]["type"] == "ValueError"
    assert result["metrics"]["generated_important_coverage"]["matched"] == 0
    assert result["metrics"]["crawl_important_coverage"]["matched"] == 3
    assert (output / "response.json").exists()
    assert not (output / "llms.txt").exists()
