from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from brief.evals import invoke


def run_cli(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "brief.evals", *map(str, args)], capture_output=True, text=True, check=False
    )


def test_export_excludes_gold_and_removed_decisions(tmp_path: Path) -> None:
    result = run_cli("--export", tmp_path)
    assert result.returncode == 0, result.stderr
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 9
    request = json.loads((tmp_path / "removed-answer.json").read_text())
    assert "expected" not in request
    assert "OLD_DECISION_MARKER" not in request["user"]
    assert request["outputSchema"]["additionalProperties"] is False


def test_baseline_fails_and_replay_reproduces_grade(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    result = run_cli("--baseline", "--out", baseline)
    assert result.returncode == 1
    original = json.loads((baseline / "report.json").read_text())
    assert original["mode"] == "metadata-baseline"
    assert original["evaluation"] == "deterministic-checks-only"
    assert original["humanReviewCompleted"] is False
    assert sum(r["passed"] for r in original["results"]) == 2
    responses = tmp_path / "responses"
    responses.mkdir()
    for case in original["results"]:
        artifact = json.loads((baseline / f"{case['id']}.json").read_text())
        (responses / f"{case['id']}.json").write_text(json.dumps(artifact["response"]))
    replay = tmp_path / "replay"
    result = run_cli("--responses", responses, "--out", replay)
    assert result.returncode == 1
    replayed = json.loads((replay / "report.json").read_text())
    assert [(r["passed"], r["failures"]) for r in original["results"]] == [
        (r["passed"], r["failures"]) for r in replayed["results"]
    ]


def test_missing_responses_are_per_case_failures(tmp_path: Path) -> None:
    result = run_cli("--responses", tmp_path / "missing", "--out", tmp_path / "out")
    assert result.returncode == 1
    report = json.loads((tmp_path / "out/report.json").read_text())
    assert len(report["results"]) == 9
    assert all(not r["passed"] for r in report["results"])


def executable(tmp_path: Path, code: str) -> str:
    adapter = tmp_path / "adapter"
    adapter.write_text(f"#!{sys.executable}\n" + code)
    adapter.chmod(0o700)
    return str(adapter)


def test_adapter_protocol_and_malformed_output(tmp_path: Path) -> None:
    adapter = executable(
        tmp_path, "import json, sys\nrequest=json.load(sys.stdin)\nprint(json.dumps({'received': request['system']}))\n"
    )
    assert invoke(adapter, {"system": "test"}) == {"received": "test"}
    adapter = executable(tmp_path, "print('not JSON')\n")
    with pytest.raises(ValueError):
        invoke(adapter, {})


def test_adapter_timeout_and_nonzero_exit(tmp_path: Path) -> None:
    adapter = executable(tmp_path, "import time\ntime.sleep(10)\n")
    with pytest.raises(subprocess.TimeoutExpired):
        invoke(adapter, {}, timeout=0.1)
    adapter = executable(tmp_path, "import sys\nsys.exit(3)\n")
    with pytest.raises(ValueError, match="exited 3"):
        invoke(adapter, {})


def test_valid_replay_returns_success(tmp_path: Path) -> None:
    from brief.contracts import GenerationInput
    from brief.evals import metadata_baseline

    case = next(c for c in json.loads(Path("evals/cases.json").read_text()) if c["id"] == "agency")
    corpus = tmp_path / "cases.json"
    corpus.write_text(json.dumps([case]))
    responses = tmp_path / "responses"
    responses.mkdir()
    (responses / "agency.json").write_text(json.dumps(metadata_baseline(GenerationInput.model_validate(case["input"]))))
    result = run_cli("--cases", corpus, "--responses", responses, "--out", tmp_path / "out")
    assert result.returncode == 0, result.stderr
