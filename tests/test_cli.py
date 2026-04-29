"""Tests for the agent-harness CLI."""

from __future__ import annotations

import sys

from agent_harness.cli import VERSION, main


def test_version_command_prints_version(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["agent-harness", "version"])

    exit_code = main()

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == f"agent-harness {VERSION}"