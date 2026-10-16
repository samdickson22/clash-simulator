# Batch B2 (spells + spell-like) — progress (restart notes)

Worker: CARD LEAD engine sub-agent. Worktree `/mpac/sdicks02/repos/clasher-cards-b2` (05), branch `cards/b2` from
7720915a8. Edits only `engine-cards/**`, `reports/cards/b2/**`. Parallel worker on cards/b1 (troops).

## Layout (127x08: /mpac/sdicks02/jobs/clasher/cards/b2/)
- `base/` = git archive of engine-cards @7720915a8 (Batch A WIP commit); `tree/` = rsync of my engine-cards.
- `root/`, `baseroot/` = {engine-rs, src, gamedata.json -> tree|base, reports -> r1/reports} (Batch A layout).
- `fid/` = copies of `reports/cards/b2/tools/*` + fidelity pool.json, summarize.py, controlled.py.
  `run_fid.sh ROOT OUT N --cards ...` (cpu_job lease, nice 15, PYTHONHASHSEED=0); `tr.sh ROOT CARD SCEN [--names ..]`
  = per-tick both-engine trace (trace.py); `diffs.py`/`show.py`/`table.py` from Batch A.
- `base.jsonl` = baseline (adapter table) for the 10 cards; reproduces reports/cards/fidelity/results.jsonl verdicts.

## Rules
- New native Spec/Stats fields: `#[serde(default, skip_serializing_if = ...)]` (lead 01:50Z; Batch A native 1923619e).
- Pure stat values -> overlay rows in RESULTS, scratch gamedata only (apply_stats.py), never git.

## Findings so far
- Poison × dash (native-diff): native `c56.rs:area_targets` lacks `!e.dash_travel()`; dash exists only on BanditDash
  bodies (Bandit, BossBandit) -> fix is C56-inert.
- Mirror × SkeletonBalloon: `c56.rs:bomb_tick` looks up `bomb_children[stats.name]`; use `stats.key()` (falls back
  to name) -> C56 (level 11) inert.
- Spell area boundary (controlled probe: ours misses at r+0.5, RS hits up to r+1.0): RS `AOE_HIT_TEST` is a LOW-confidence
  guess; ours is the client's `LogicGameObject::intersects` (strict). Native authoritative; not changed. Shared by C56.
- Snowball cluster: knock+slow identical; 1-tick post-push step differs (ours steps back to the pre-push waypoint after a
  1.8-tile push). Fireball (C56) same scenario is identical -> push length, shared route code. Not Snowball code.
- Stats (adapter arm CLIENT16402_VALUES): Freeze AreaBuffTime 3500 (+ 16.402 life 3500); HealSpirit HP 84.
- Rage: controlled effect first tick 16/11, last 113/105 (timing mechanic, TODO).
- DarkMagic: hits 340 at [32,52,72] vs RS 696 at [33,57,81] (damage scaling + cadence, TODO).

## Log
- 2026-10-16T01:38Z start; ~01:45Z stopped on usage limit; 01:50Z resumed.
- 2026-10-16T01:56:45Z Primary arm = full 16.402 table (--table 160402; adapter arm's Void 1200 ms is the 15.535 value).
  Scratch overlay: 08 b2/fid/stats-spec.json -> b2/stats/gamedata.json (apply_stats.py, "add" rows for ABSENT fields),
  root b2/rootstats. Fixes so far (Python; native mirrored, NOT yet built): native Poison×dash + bomb_children key;
  scope_spells._register birth-tick skip (Void/Vines/Curse were 1 tick early); Vines data-driven catch clock
  (hitSpeed/hitSpeedOffset/lifeDuration), re-pick each catch, grounding window 2.1 s, grounded flier keeps air
  collision plane. With stats: Freeze 3/3, Heal 3/3, DarkMagic 3/3, Vines 3/3 PASS (r2s/r3s.jsonl).
- 2026-10-16T02:15:28Z More fixes: GoblinCurse curse slow (data speedMultiplier) + goblin deploy +1 tick; Graveyard
  birth skip, against_forward y orientation, Skeleton deploy +1 tick, acquire delay F+7 (_targetable_from_ms /
  native lock_after), creation-tick first update; Rage haste area applies on landing, cap = life left + HitSpeed,
  balance.py Rage capBuffTimeToAreaEffectTime; Clone object-phase cast, 500 ms hold, 10-tick column-edge slide after
  movement, route dropped; Freeze crownTowerDamagePerHit read (data). Native port of all; birth = tick+1 for command
  scope objects. native df5443ab: scenario lockstep native==Python on the 10 cards (root + rootstats).
- 02:15Z GATE launched on 08: b2/gate.pid 3043090 (cpu_job 8; fid/gate.sh; arms pinned r1+681b5f2c vs gtree+gout
  df5443ab; gtree file-hash 8219fb79). Result -> b2/gate/compare.json. gtree == worktree engine-cards (rsync -c).

## HANDOFF 2026-10-16T02:17Z (Claude budget; Sol takes over)

### Per-card status (primary arm = full 16.402 table, `--table 160402`; scratch overlay = 08 b2/fid/stats-spec.json)
| Card | Status | Fix | Overlay rows (stat values, never in git) |
|---|---|---|---|
| Freeze | PASS 3/3 (mech + stats); extra `towerfreeze` scenario identical | dynamic_spells AreaEffectSpell reads `crownTowerDamagePerHit` when present | Freeze area lifeDuration 3500, buffTime 3500, crownTowerDamagePerHit 15 (ABSENT, add) |
| Heal | PASS 3/3 with stats (no mechanic gap) | — | HealSpirit hitpoints 84 |
| DarkMagic (Void) | PASS 3/3 with stats | scope area birth skip (was 1 tick early) | DarkMagicAOE_Damage_lv3 dps 2720 / crown 38; lv2 1155 / 20; lv1 600 / 14 |
| Vines | PASS 3/3 with stats | birth skip; catch clock from data (hitSpeed/hitSpeedOffset/lifeDuration); re-pick each catch; air-to-ground window 2.1 s; grounded flier keeps air collision plane | Vines_AeO lifeDuration 1400, hitSpeed 250 (ABSENT, add) |
| Rage | PASS 3/3 (controlled probe exact 11..105) | haste area applies on landing; cap = life left + HitSpeed; balance.py Rage area capBuffTimeToAreaEffectTime | — |
| Clone | support trace identical to RS for the whole scenario (fidelity rerun pending) | object-phase cast, 500 ms hold, 10-tick column-edge slide after movement, route dropped | — |
| Graveyard | tower PASS; cluster/support match RS until a Skeleton-swarm contact drift after a death (t=106 / t=204; C56-shared physics, as Batch A's SkeletonArmy control) | birth skip, against_forward y, deploy +1 tick, F+7 acquire delay, creation-tick first update | — |
| GoblinCurse | tower/support PASS; cluster: residual = river snapping of converted Goblins (arena passability, shared; RS flags its own snap as unmeasured) + RS slot-ordinal artefact | birth skip, curse slow from data, goblin deploy +1 tick | GoblinCurseDamage speedMultiplier -15 (ABSENT, add) |
| Snowball | tower/support PASS; cluster: 1-tick step after a 1.8-tile push. RS calibration knockback.LADDER_END_ROUTE = client16402_dropped (route dropped when the ladder ends) is the likely cause; it is shared with C56 pushes (Fireball/Log) -> NOT changed (would move C56 states). Report as C56-blocked. | — | — |
| Mirror | PASS (unchanged) | native bomb_tick looks up `bomb_children` by payload key (falls back to name) | — |
| Poison × dash (native-diff) | native fix done: `c56.rs:area_targets` skips dash travel (C56-inert: only BanditDash bodies dash) | | |

Spell boundary radius (controlled probes, ours misses at r+0.5, RS hits to r+1.0): RS AOE_HIT_TEST is a LOW-confidence
guess; ours is the client's strict intersects; shared by C56 spells -> not changed.

### Native / Python parity
- Native built on 08: `b2/out` and frozen gate copy `b2/gout` sha256 df5443ab...488 from `b2/gtree` (== commit 4916d66b8 engine-cards).
- `fid/run_scen.sh rootstats ../out ...`: all 30 scenarios of the 10 cards native==Python every tick (root and rootstats).

### C56 GATE — NOT RUN YET (needs relaunch on 127x04)
- 08 launch (PID 3043090, 02:15Z) exited in 34 s: parity_fixtures needs `/mpac/sdicks02/repos/clasher-bot-data/t1-split.json`,
  which exists only on 04 (Batch A ran its gate there). Roots files on 08 b2/gate/ were written but compare.py aborted.
- TO DO (Sol): on 127x04 make `/mpac/sdicks02/jobs/clasher/cards/b2/` with gtree (rsync from 08 b2/gtree, or `git archive 4916d66b8 engine-cards`
  + this commit's engine-cards), gout (copy 08 b2/gout/clasher_core.abi3.so, check sha df5443ab), rt (r1 symlinks with
  engine-rs->gtree, src->gtree/py/src, gamedata.json->gtree/py/gamedata.json), roots + gate-tools (copy batchA's on 04),
  then `setsid cpu_job.sh 8 bash <b2>/fid/gate.sh` (gate.sh has A=/mpac/sdicks02/jobs/clasher/cards/b2). Wait on the PID.
  Pinned arm = r1 + 681b5f2c; if Batch A's 04 pinned outputs (batchA/gate/*-pinned*) are complete they are identical and may be reused.
- PASS = compare.json fixtures identical_records 577/577 (rust_only chains equal) and roots identical 600/600 (300 x full/cut).
- If it FAILS: look at `differing` episodes; candidates touching shared code: `Entity.is_targetable_by` (_targetable_from_ms,
  default 0), native `lock_after()` (= stealth_until when untargetable_until 0), `uses_air_collision_plane` (_vines_grounded),
  `_queue_spell_cast` object_phase for CloneSpell, movement loop clone_slide skip, apply_action birth (+1 only when
  scope_skip_birth), new serialized fields (all skip_serializing_if default). Bisect by reverting one at a time in gtree.

### Other jobs on 08 (b2/fid)
- `run_pool.sh` PID 3069080: full 66-card fidelity, arms base(baseroot)/mech(root)/stats(rootstats) -> final-{base,mech,stats}.jsonl;
  `final.done` when finished. Use for "no other-card regressions" + per-scenario table (tools/table.py).
- `mixed_repro.py` (native-diff games 75 416 133 509 on B2) FAILED to import: add the engine-speed dir
  (`/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed`) to PYTHONPATH and rerun from b2/root.

### Unfinished
- RESULTS.md not written yet (fill from this table + final-*.jsonl + gate compare.json).
- Clone/Graveyard/GoblinCurse 3-scenario fidelity rerun with the final tree (traces were run, not the full harness for Clone).
