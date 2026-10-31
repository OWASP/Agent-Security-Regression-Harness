"""Unreadable or undecodable input files must produce validation errors."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agent_harness.cli import main
from agent_harness.scenario import ScenarioValidationError, load_scenario
from agent_harness.trace import TraceValidationError, load_trace

SCENARIO_YAML = """\
id: {scenario_id}
title: Input file handling
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
INVALID_UTF8 = b"{\xff\xfe}"


def test_load_trace_rejects_invalid_utf8(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_bytes(INVALID_UTF8)

    with pytest.raises(TraceValidationError, match="not valid UTF-8"):
        load_trace(trace_path)


def test_load_trace_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(TraceValidationError, match="cannot read trace file"):
        load_trace(tmp_path)


def test_load_trace_rejects_excessive_nesting(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("[" * 200_000, encoding="utf-8")

    with pytest.raises(TraceValidationError, match="nesting is too deep"):
        load_trace(trace_path)


def test_load_scenario_rejects_invalid_utf8(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_bytes(b"id: \xff\xfe\n")

    with pytest.raises(ScenarioValidationError, match="not valid UTF-8"):
        load_scenario(scenario_path)


def test_load_scenario_rejects_directory_with_yaml_suffix(tmp_path: Path) -> None:
    directory = tmp_path / "scenario.yaml"
    directory.mkdir()

    with pytest.raises(ScenarioValidationError, match="cannot read scenario file"):
        load_scenario(directory)


def test_load_scenario_rejects_excessive_yaml_nesting(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text("a: " + "[" * 50_000 + "]" * 50_000, encoding="utf-8")

    with pytest.raises(ScenarioValidationError):
        load_scenario(scenario_path)


def test_error_messages_do_not_echo_file_contents(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_bytes(b'{"api_key": "sk-live-SECRET"}\xff')

    with pytest.raises(TraceValidationError) as excinfo:
        load_trace(trace_path)

    assert "sk-live-SECRET" not in str(excinfo.value)


def test_cli_run_reports_invalid_trace_for_invalid_utf8(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(SCENARIO_YAML.format(scenario_id="a.1"), encoding="utf-8")
    trace_path = tmp_path / "trace.json"
    trace_path.write_bytes(INVALID_UTF8)
    monkeypatch.setattr(
        sys,
        "argv",
        ["agent-harness", "run", str(scenario_path), "--trace-file", str(trace_path)],
    )

    exit_code = main()

    assert exit_code == 1
    assert "invalid trace: trace file is not valid UTF-8" in capsys.readouterr().err


def test_cli_validate_reports_invalid_scenario_for_invalid_utf8(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = tmp_path / "good.yaml"
    good.write_text(SCENARIO_YAML.format(scenario_id="a.1"), encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_bytes(b"id: \xff\n")
    monkeypatch.setattr(sys, "argv", ["agent-harness", "validate", str(tmp_path)])

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "valid: " in captured.out
    assert "not valid UTF-8" in captured.err
    assert "summary: 1 valid, 1 invalid" in captured.out


def test_suite_continues_past_undecodable_inputs(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    for scenario_id in ("a.1", "b.1", "c.1"):
        (scenarios_dir / f"{scenario_id}.yaml").write_text(
            SCENARIO_YAML.format(scenario_id=scenario_id), encoding="utf-8"
        )
    (scenarios_dir / "broken.yaml").write_bytes(b"id: \xff\n")
    clean = json.dumps({"messages": [], "tool_calls": [], "events": []})
    (traces_dir / "a.1.json").write_bytes(INVALID_UTF8)
    (traces_dir / "b.1.json").write_text(clean, encoding="utf-8")
    (traces_dir / "c.1.json").write_text(clean, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["agent-harness", "suite", str(scenarios_dir), "--trace-dir", str(traces_dir)],
    )

    exit_code = main()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["counts"]["total"] == 4
    assert summary["counts"]["pass"] == 2
    assert summary["counts"]["error"] == 2
    reasons = sorted(
        entry["error_reason"] for entry in summary["scenarios"] if "error_reason" in entry
    )
    assert reasons == ["invalid_scenario", "invalid_trace"]
