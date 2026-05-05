"""Tests for bundled scenario files"""

from __future__ import annotations

from pathlib import Path

from agent_harness.scenario import load_scenario

def test_all_bundled_scenarios_validate():
    scenario_paths = sorted(Path("scenarios").rglob("*.yaml"))

    assert scenario_paths, "expected at least one bundled scenario"

    for scenario_path in scenario_paths:
        load_scenario(scenario_path)




