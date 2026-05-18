"""Run every bundled scenario against its passing trace fixture.

Each scenario at ``scenarios/<category>/<name>.yaml`` is paired with a
representative passing trace at
``examples/traces/<category>/<name>_pass.json``. This test loads the
pair, evaluates assertions, and confirms the top-level result is
``pass`` or ``not_run`` — never ``fail`` or ``error``.

A result of ``not_run`` is accepted because some bundled scenarios
intentionally include assertions that are recognized but not fully
implemented yet (e.g. ``no_secret_disclosure``). Those report
``not_run`` which dominates the aggregate when no assertion has failed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_harness.runner import run_scenario_with_trace
from agent_harness.scenario import load_scenario
from agent_harness.trace import load_trace

REPO_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"
TRACES_DIR = REPO_ROOT / "examples" / "traces"


def _scenario_fixture_pairs() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for scenario_path in sorted(SCENARIOS_DIR.glob("*/*.yaml")):
        category = scenario_path.parent.name
        basename = scenario_path.stem
        fixture_path = TRACES_DIR / category / f"{basename}_pass.json"
        pairs.append((scenario_path, fixture_path))
    return pairs


@pytest.mark.parametrize(
    ("scenario_path", "fixture_path"),
    _scenario_fixture_pairs(),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_every_scenario_has_a_passing_fixture(
    scenario_path: Path,
    fixture_path: Path,
) -> None:
    assert fixture_path.is_file(), (
        f"Missing passing trace fixture for {scenario_path.relative_to(REPO_ROOT)}. "
        f"Expected at {fixture_path.relative_to(REPO_ROOT)}. "
        "See examples/traces/README.md for the naming convention."
    )

    scenario = load_scenario(scenario_path)
    trace = load_trace(fixture_path)
    result = run_scenario_with_trace(scenario, trace)

    assert result.result in {"pass", "not_run"}, (
        f"{scenario.id} against {fixture_path.name} produced "
        f"{result.result!r} — passing trace fixtures must produce 'pass' "
        f"or 'not_run' (one or more recognized-but-unimplemented "
        f"assertions). Assertion results: "
        f"{[(a.id, a.result) for a in result.assertions]}"
    )
