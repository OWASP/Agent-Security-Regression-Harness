"""Suite output must never collide with inputs or other results."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agent_harness.cli import main

SCENARIO_YAML = """\
id: {scenario_id}
title: Suite collision
category: goal_hijack
severity: high
target:
  adapter: http_agent
input:
  user_message: hi
expected:
  denied_tools:
    - send_email
assertions:
  - type: no_denied_tool_call
"""
DENIED_TRACE = json.dumps(
    {"messages": [], "tool_calls": [{"name": "send_email", "arguments": {}}], "events": []}
)
CLEAN_TRACE = json.dumps({"messages": [], "tool_calls": [], "events": []})


def _setup(tmp_path: Path, scenario_ids: list[str]) -> tuple[Path, Path]:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    for index, scenario_id in enumerate(scenario_ids):
        (scenarios_dir / f"s{index}.yaml").write_text(
            SCENARIO_YAML.format(scenario_id=scenario_id), encoding="utf-8"
        )
    return scenarios_dir, traces_dir


def _run_suite(
    monkeypatch: pytest.MonkeyPatch, scenarios_dir: Path, *args: str
) -> int:
    monkeypatch.setattr(sys, "argv", ["agent-harness", "suite", str(scenarios_dir), *args])
    return main()


def test_scenario_named_summary_is_reported_as_reserved(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, ["summary", "other.1"])
    (traces_dir / "summary.json").write_text(DENIED_TRACE, encoding="utf-8")
    (traces_dir / "other.1.json").write_text(CLEAN_TRACE, encoding="utf-8")
    out_dir = tmp_path / "out"

    exit_code = _run_suite(
        monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir), "--out-dir", str(out_dir)
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    by_id = {entry["scenario_id"]: entry for entry in summary["scenarios"]}
    assert by_id["summary"]["error_reason"] == "reserved_scenario_id"
    assert by_id["summary"]["result"] == "error"
    assert by_id["other.1"]["result"] == "pass"
    aggregate = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert aggregate["counts"]["total"] == 2
    assert "scenarios" in aggregate
    assert (out_dir / "other.1.json").is_file()


@pytest.mark.parametrize("scenario_id", ["Summary", "SUMMARY"])
def test_reserved_scenario_id_is_case_insensitive(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario_id: str,
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, [scenario_id])

    _run_suite(monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir))

    summary = json.loads(capsys.readouterr().out)
    assert summary["scenarios"][0]["error_reason"] == "reserved_scenario_id"


def test_scenario_ids_differing_only_by_case_are_duplicates(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, ["Foo.1", "foo.1"])
    (traces_dir / "Foo.1.json").write_text(CLEAN_TRACE, encoding="utf-8")
    (traces_dir / "foo.1.json").write_text(DENIED_TRACE, encoding="utf-8")

    exit_code = _run_suite(monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir))

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["counts"]["total"] == 2
    assert summary["counts"]["error"] == 1
    duplicate = next(e for e in summary["scenarios"] if "error_reason" in e)
    assert duplicate["error_reason"] == "duplicate_scenario_id"


def test_out_dir_equal_to_trace_dir_is_rejected_without_touching_traces(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, ["a.1"])
    trace_path = traces_dir / "a.1.json"
    trace_path.write_text(DENIED_TRACE, encoding="utf-8")

    exit_code = _run_suite(
        monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir), "--out-dir", str(traces_dir)
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--out-dir must not be the same directory as --trace-dir" in captured.err
    assert trace_path.read_text(encoding="utf-8") == DENIED_TRACE
    assert not (traces_dir / "summary.json").exists()


def test_out_dir_equal_to_trace_dir_via_alternate_path_is_rejected(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, ["a.1"])
    (traces_dir / "a.1.json").write_text(DENIED_TRACE, encoding="utf-8")
    alternate = traces_dir / ".." / "traces"

    exit_code = _run_suite(
        monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir), "--out-dir", str(alternate)
    )

    assert exit_code == 1
    assert "--out-dir must not be the same directory" in capsys.readouterr().err


def test_out_dir_in_a_different_directory_still_works(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir, traces_dir = _setup(tmp_path, ["a.1"])
    (traces_dir / "a.1.json").write_text(CLEAN_TRACE, encoding="utf-8")
    out_dir = tmp_path / "results"

    exit_code = _run_suite(
        monkeypatch, scenarios_dir, "--trace-dir", str(traces_dir), "--out-dir", str(out_dir)
    )

    assert exit_code == 0
    assert (out_dir / "a.1.json").is_file()
    assert (out_dir / "summary.json").is_file()
    assert (traces_dir / "a.1.json").read_text(encoding="utf-8") == CLEAN_TRACE
    capsys.readouterr()
