"""Tests for the goal hijacking scenario."""

from __future__ import annotations

from pathlib import Path
from agent_harness.scenario import load_scenario

def test_goal_hijacking_scenario_is_valid():
    scenario_path = Path(__file__).parent.parent / "scenarios" / "goal_hijacking_01.yaml"
    scenario = load_scenario(scenario_path)
    
    assert scenario.id == "goal_hijack.delete_cloud_files"
    assert scenario.category == "goal_hijack"
    assert scenario.severity == "critical"
    assert "cloud_delete" in scenario.raw["expected"]["denied_tools"]
