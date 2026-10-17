# live16402d / r1-cards4 release — PROGRESS

## HANDOFF (keep current)
- Owner: Opus release-d owner under CARD LEAD r2. Branch `cards/release-d`, worktree `/mpac/sdicks02/repos/clasher-cards-release-d`,
  based on main f273b0abe (C1 merged; engine-cards tree 03d63a0b == gated 269e59d5b, native 86a5d050).
- **Publish is BLOCKED** until CARD LEAD says `cards/admission-class` (C1 owner; native≠Python area-admission class) is reviewed and
  merged. Then: rebase, build native from the exact merged source into a fresh `native-<sha8>/`, C56 gate if engine source differs
  from what was gated, assemble + gate r1-cards4 / live16402d, publish read-only on 04 + 08 only (03 DOWN, never 01/02/09–18).
- Done here: (1) GG rider-graph class fix + tests, (2) Void tier overlay pass + Tornado crown pin. See sections below.
- Open: Sol review r1 of (1)+(2) (task `cards-release-d-graph-overlay-review-r1`, Sol high); graph stress on 08
  (`jobs/clasher/cards/release-d/stress-02`); prep dev-root gates on 08 (`jobs/clasher/cards/release-d/prep`, C1 native 86a5d050,
  source b07927454; `tools/pipeline.sh` = assemble.py + gates.py). PIN_SETS r1-cards4/live16402d in runtime.py carry the PREP native;
  replace with the final build before release.
- Release recipe (when admission-class is merged): rebase → `build_runtime.py --rev HEAD --export-only` + `git archive` → rsync to
  08 → build native into fresh `native-<sha8>/` (`-j8`, nice) → C56 gate if engine-cards differs from admission-class's gated tree
  beyond public_root.py → update pins → fresh JOB, `cpu_job.sh 4 bash tools/pipeline.sh JOB SRC REPO NATIVE` → snapshot/rsync to
  04 → `reports/cards/r1-cards3/tools/release.py` flow (atomic NOREPLACE, read-only) → RELEASES.md + PIN_SETS on main (temp index).

## 1. GoblinGiant rider-graph fallback
- Failure (live16402c mixed LIVE B1B2B game, seed 20261016600, cmd 869f612a): tick 350 seat 0, `parents=1,riders=2,matched=1,
  unsupported=[13]` → PublicGraphError → fast-tier fallback. Board: `reports/cards/b1/public-graphs/failing-public-board.json`.
- Cause: riders are carried after combat but before movement/push/forced movement (Fisherman drag here), so the observed parent can
  leave its riders' arc; the radial admission test rejected a rider 0.149 tiles from its parent (needs ≈0.65).
- 244e385ca (branch cards/public-graphs-20261016, B1 owner): structural fallback for **complete** owner populations (riders == 2·GG):
  recompute that owner's assignment with geometry as preference only. Reviewed (Sol round 08 APPROVE on e20105c4e), gated Python-only
  (K4L 12/12 identical, natural games, mixed 2/2 clean; native unchanged). Not on main/c1-main. Cherry-picked whole branch here.
- Gap left open: **partial** populations (a rider row missing, e.g. live perception) with the same displacement still raise.
- Class fix here (`engine-cards/public_root.py`): structural fallback whenever the owner's riders fit capacity (riders ≤ 2·GG),
  i.e. `!=` → `>`. Justification: a live SpearGoblinGiant is always mounted (immune, no forced movement, dies with its mount), so
  any capacity-feasible owner population has a valid assignment; geometry only orders it. Still rejected: over capacity, orphan
  riders, wrong owner; parents never invented, missing riders stay missing. Python-only; native untouched (C56 trivially identical).
- Tests: `reports/cards/b1/public-graphs/tools/test_graphs.py` 11/11 (adds transported-partial repro from the real board,
  3,000 random displaced feasible boards always reconstruct with unique slots/owner-correct parents, 500 over-capacity always
  reject, 2,000 undisplaced boards byte-identical to the old helper). Mutation `>`→`!=` fails 2 tests.
  `reports/cards/runtime/tools/test_b1_public_root.py` 25/25 (two partial remote/compressed controls became positive structural cases;
  wrong owner/type/over-capacity controls kept).
- Ram scope: RamRider rider/bola stays in C2; no RamRider rows are ever attached (unchanged).

## 2. Stat overlay fixes (RESIDUALS-16402c.md)
- Void: new pass 3 in `bot/cards/balance_overlay.py` (VERSION 2): detection-action tier buffs (`ActionLaserBall` →
  RoyaleSim `strike_area.kind=laser_ball`) matched by buff name, fields damagePerSecond / crownTowerDamagePerHit / hitFrequency,
  same decide() rules. On real inputs: exactly 6 cells differ from live16402c's a7de3e93 gamedata — DPS 1330/625/297 →
  2720/1155/600, crown/hit 19/10/7 → 38/20/14; comparer_check clean; output sha `df93121d…` (dev, before meta check).
  Tests 17/17 (`bot/cards/test_balance_overlay.py`).
- Tornado: live16402d pin uses `tournament_crown_from_gamedata=('Fireball','Poison','Tornado')` (26 L11 / 41 L16). Poison unchanged.

## Log (UTC)
- 2026-10-17T19:18Z start; worktree from origin/cards/c1-main; cherry-picked public-graphs branch.
- ~19:25Z lead: C1 merged f273b0abe; admission-class must merge before publish. Rebased onto f273b0abe.
- 19:28Z mixed repro launched on 08 (`jobs/clasher/cards/release-d/repro-01`, cpu_job 2, wrapper PID 2130884): live16402c-dev +
  frozen repo-eval callers, candidate helper exec'd into the runtime's public_root module.
- 19:31Z repro-01 done: 0 graph failures, 0 root/fast errors, 89 roots; but the game diverged before tick 350 (cmd 7800cec9 vs
  869f612a: deadline-bound search on a loaded host), so the exact board did not recur → deterministic stress probe instead.
- 19:33Z stress-01 (graph_stress.py) killed after game 0 (policy never cycled the hand); stress-02 relaunched with elixir-cap cycling.
- ~19:45Z Sol review r1 launched. Prep pipeline on 08: ASSEMBLY PASS (native 86a5d050, live gamedata df93121d); gates running.
