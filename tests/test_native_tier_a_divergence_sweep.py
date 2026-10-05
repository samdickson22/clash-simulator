"""Closed-loop Tier A branch regressions from the 2026-09-30 divergence sweep (15.535.86).

Each case re-runs one frozen scalar branch plan (tier-a-fresh-v4/v6) with its
controllers through run_readiness_v2 and compares the named bodies with the
native reference frame of the paired reference job at the listed ticks
(tests/fixtures/native_tier_a_divergence_sweep_15_535_86.json). Each rule
case fails when its one scalar rule is reverted:

* crown_tower_retarget_keeps_hit: a Crown Tower whose lock leaves reach
  mid-windup keeps its hit on an in-range replacement (Entity._note_combat_target);
* frozen_push_keeps_hit: a push does not stop the hit while the unit is
  stunned; the stop waits for the first push frame after the thaw and lapses
  with the push (Troop._update_knockback_movement). The companion
  zap_push_outlasting_stun_stops_hit case guards the deferral: a push that
  outlasts the stun still stops the hit;
* killed_building_avoidance_obstacle: a building killed by this tick's combat
  is still a static avoidance obstacle for this tick's scans
  (Troop._update_native_avoidance);
* displaced_deploy_snap_side: the symmetric one-unit deploy nudge takes its
  x side from the requested anchor, not the searched one
  (BattleState._apply_symmetric_deploy_snap).

Mechanism write-ups: reports/strategy_council_20260928/m0/readiness/
divergence-sweep-20260930/README.md.
"""

import argparse
import contextlib
import importlib
import json
import time
from pathlib import Path

import pytest

from clasher.battle import BattleState
from clasher.entities import Building, Troop

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "reports/strategy_council_20260928/m0/readiness"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/native_tier_a_divergence_sweep_15_535_86.json").read_text()
)
CASES = {case["name"]: case for case in FIXTURE["cases"]}


def _selected_bodies(battle, select):
    wanted = {tuple(s) for s in select}
    return sorted(
        (e.player_id, e.card_stats.name, round(e.position.x * 1000), round(e.position.y * 1000),
         round(e.hitpoints))
        for e in battle.entities.values()
        if isinstance(e, (Troop, Building))
        and e.card_stats is not None
        and e.is_alive
        and e.hitpoints > 0
        and (e.player_id, e.card_stats.name) in wanted
    )


@pytest.mark.parametrize("name", sorted(CASES))
def test_tier_a_branch_matches_native_frames(name, monkeypatch, tmp_path):
    case = CASES[name]
    attempt = READINESS / case["attempt"]
    if not (attempt / "branch-plan.json").exists():
        pytest.skip("Tier A readiness artifacts absent")
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    runner = importlib.import_module("run_readiness_v2")
    from clasher.rl.readiness_execution import ExecutionPlan, jobs

    plan = ExecutionPlan.model_validate_json((attempt / "branch-plan.json").read_text())
    job = jobs(plan)[case["scalar_job"]]
    assert job.engine == "scalar"
    checks = {c["tick"]: c for c in case["checks"]}
    seen = {}
    original_step = BattleState.step

    def step(self, *args, **kwargs):
        result = original_step(self, *args, **kwargs)
        if self.tick in checks and self.tick not in seen:
            seen[self.tick] = _selected_bodies(self, checks[self.tick]["select"])
        return result

    monkeypatch.setattr(BattleState, "step", step)
    args = argparse.Namespace(deadline=time.monotonic() + 3600, port=None)
    with contextlib.ExitStack() as stack:
        result = runner._execute_job_body(plan, job, tmp_path, args, stack, [], None)

    for tick, check in sorted(checks.items()):
        expected = sorted(
            (b["owner"], b["card"], b["xy"][0], b["xy"][1], b["hp"]) for b in check["bodies"]
        )
        assert seen.get(tick) == expected, (name, tick)
    if case["terminal"] is not None:
        assert [result["score"], result["own_remaining_hp"], result["enemy_remaining_hp"]] == case[
            "terminal"
        ]
