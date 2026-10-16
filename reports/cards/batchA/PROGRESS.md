# Batch A fidelity fixes — progress (restart notes)

Worker: CARD LEAD engine implementation sub-agent. Edits only engine-cards/** and reports/cards/batchA/**; commits nothing.

## Layout
- Worktree (05): /mpac/sdicks02/repos/clasher-cards (branch cards/lead). Baseline engine-cards = 7e64d8b93.
- 08 jobs: /mpac/sdicks02/jobs/clasher/cards/batchA/
  - tree/ = rsync of patched engine-cards; root/ = {engine-rs->tree, src->tree/py/src, gamedata.json->tree/py/gamedata.json, reports->r1/reports}
  - base/ = pristine engine-cards @7e64d8b93 (git archive); baseroot/ like root/ but base/.
  - fid/ = fidelity runs (scenarios.py copy with r1 import check relaxed to the root under test).

## Log
- 2026-10-16T00:25:44Z started; read fidelity harness (reports/cards/fidelity), RoyaleSim calibration (spawner.FIRST_WAVE etc, cards.CLIENT16402_VALUES).
- 2026-10-16T00:33:40Z round 1 (stat overrides in balance.py + spawner first-wave/blank-interval rule): PASS SpearGoblins Bomber SkeletonDragons (+MegaMinion Pekka); GoblinCage alone/giant, Tombstone alone, DartBarrell alone/minions, Witch minions pass. Barbarian HP left at 691 per lead (BOT LEAD decides). fid/r1.jsonl on 08.
- 2026-10-16T00:39:05Z coordinator ruling: pure stat-value corrections go to the live16402 overlay (never git). Moved them out of balance.py; scratch overlay = 08 batchA/stats/gamedata.json built by tools/apply_stats.py from fid/stats-spec.json (08 only); root with overlay = batchA/rootstats.
- r2: Mortar minimumRange mechanic (Python _is_valid_target + native target_candidate inside_min_range, Stats.min_range) -> Mortar PASS.
- r3 (rootstats): + Guards summonRadius 800, + Python-only prototype of spawned first update (PeriodicSpawner.first_update, battle._first_update_spawned) -> Witch knight, SkeletonWarriors PASS. Native port of first_update still TODO.
- 2026-10-16T01:11:20Z mechanics added since r3: death-spawn DeathSpawnDeployTime counts from the tick after death (+50 ms start), DartBarrell flyingHeight/mass (omitted trait), first-update gated off spawnCharacterWithDeploy (keeps C56 Furnace), death spawns of spawner buildings take a per-child first update without collision. r8: Tombstone giant + BarbarianHut all PASS.
- Native port: movement phase body extracted to lib.rs movement_one; BattleState.fresh queue + drain_fresh (combat_one + movement_one) drained at every per-entity boundary of tick_once; Spec.first_update, Stats.death_first_update, Stats.min_range. Built on 08: batchA/out sha256 112c0649...; copied to 04.
- C56 config export (all 56 cards) pinned vs patched: equal modulo inert new keys (04 batchA/cfg-*.json).
- Gate launched on 04: batchA/tools/gate.sh under cpu_job.sh 14 -> batchA/gate/compare.json (queued in cpu_room at 18:10 local).
- Probes on 08: fid/run_scen.sh -> scen-root.json, scen-rootstats.json, scen-negctl.json (pinned native, expect mismatches). Final fidelity: fid/final-{stats,mech,base}.jsonl (66-card pool).
- 2026-10-16T01:18:20Z native==Python: probe_native 14/14 ok; probe_native_scen 42/42 (root and rootstats); negctl (pinned native) diverges only on Tombstone/BarbarianHut/Witch/Mortar. Final fidelity (66 cards): Batch A 8/42 -> 23/42 (mech) -> 37/42 (mech+stats); no other-card regressions (DarkWitch improved; GoblinDrill giant 51->52 diffs). RESULTS.md written except §6 parity.
- Gate relaunched on 04 with cpu_job.sh 8 (fixtures then roots sequential), PID 2204895; waiting for room. Tree synced (comment-only changes) before it started; tree file-hash fe2300c5....
- Remaining: fill RESULTS §6 from 04 batchA/gate/compare.json.
- 2026-10-16T01:46:42Z gate r1 stopped: rust_only chains differed only via snapshot serialization of the new fields; made them skip_serializing_if default; rebuilt native sha256 1923619e...; 3-fixture spot check equals pinned. Gate rerun on 04 PID 2388512 (fixtures start 01:44:11Z); probes rerun on 08 (fid/scen2-*.json).
- 2026-10-16T02:19:17Z GATE PASS (04 batchA/gate/compare.json sha256 f925aaaf...): fixtures 577/577 identical (file sha f5a2665b... both), roots 600/600 identical. probe_native 14/14 and scen 42/42 (both roots) on native 1923619e.... RESULTS.md complete. DONE (nothing committed).
- 2026-10-16T02:19Z test-shepherd independent audit: **C56 PASS**, pinned 681b5f2c vs patched 1923619e; fixtures **577/577** records byte-identical, Rust-only **577/577** trajectories equal (1,010,680 ticks; 0 errors), roots **300/300 full + 300/300 cut**, exact shard bodies equal apart from headers. No differing fixture/root IDs; existing Python↔Rust full-length parity remains 429/577 in both arms. Original PGID 2388512 completed normally; no restart or new simulation jobs. Added per-variant counts and audit to RESULTS §6; no triage required; no engine edits, commit, or sealing.
- 2026-10-16T02:30:29Z Review round 1 (Sol REJECT): (1) death-spawn first update moved after Freeze inheritance; (2) periodic wave siblings hidden in first-update collision/avoidance (Python hidden ids, native BattleState.hidden). Probes --cases (frozen_tombstone_death{,_red}, witch_corner{,_red}) 4/4 identical; scen3 42/42 both roots; probe_native 14/14; fidelity r9 verdicts unchanged. Native 5f07238c.... Next: commit, relaunch gate on 04 (old gate outputs kept as gate-1923619e).
