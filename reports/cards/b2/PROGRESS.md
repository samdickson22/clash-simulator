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
- 2026-10-16T02:26:30Z GATE FAIL (Sol triage, GATE-TRIAGE.md): my Graveyard deploy +50 ms replace() also hit the identical
  call in RollingProjectile._spawn_units (C56 BarbLog Barbarian deploy/tunnel_total 1.0 -> 1.05). Reverted that one
  argument only (Graveyard hunk kept); audit of added lines found no other duplicated hunk. Python-only change: native
  df5443ab unchanged. NEXT: rerun the full gate on 04 with this commit's Python + df5443ab; recheck Graveyard fidelity
  and mixed repros (75/416/133 match per triage; 509 IceGolemite spawn is not B2's).
- 2026-10-16T02:29Z CORRECTED GATE launched on 127x04 in a separate dir `/mpac/sdicks02/jobs/clasher/cards/b2-fix/`
  (gate.pid 2961219, cpu_job 8; both arms; gtree = git archive aa8d28a76 engine-cards; gout = df5443ab copy; roots +
  gate-tools copied from b2/). Output b2-fix/gate/compare.json. The original frozen run in b2/ (PID 2737392,
  4916d66b8/df5443ab) is left untouched and is reported as FAIL regardless.

## Test-agent completed results (2026-10-16)

- Original frozen gate on 04 PID 2737392 finished: **FAIL** fixtures and Rust-only chains
  410/577 equal, 167 different; **PASS** roots 600/600 (300 full + 300 cut); no Rust-only errors.
  Native df5443ab; source 4916d66b8; pinned outputs reused from complete identical-input Batch A.
  Exact-PID wait returned 0 (runner completion, not a PASS verdict). See RESULTS.md and evidence/gate-compare.json.
- One-hunk scratch bisect isolated RollingProjectile._spawn_units +50 ms (BarbLog). Revert restores
  2402/2402 digest + snapshot hashes in first failing fixture; full C56 normalized config then identical.
  GATE-TRIAGE.md sent to Opus owner immediately; owner fix aa8d28a76 and corrected b2-fix gate are separate.
- Pool PID 3069080 completed, final.done exists. B2 fidelity **13/28 → 16/28 → 24/28**
  (base/mechanics/mechanics+scratch stats). Full pool **54/196 → 57/196 → 65/196**.
  All 168 other-card compare verdicts and difference lists unchanged. Final Clone 3/3;
  Graveyard 1/3; GoblinCurse 2/3; remaining scenarios and cause/fix table in RESULTS.md.
- mixed_repro PYTHONPATH fixed via run_mixed.sh; games75/416 MATCH3600, 133 MATCH3254(game over),
  509 MISMATCH first digest t341 (missing native IceGolemite death area, known alias/export signature).
  Detail/phase_step retained; all four ran without exception/panic.
- 2026-10-16T06:52Z MERGE of origin/cards/lead (878d5f459 synchronous first update, de11f124 base) into cards/b2 =
  9e881f00a. Conflicts: lib.rs movement loop (flush_grid + Clone slide skip), Clone pending-cast dispatch, is_zero_i64;
  battle.py _first_update_spawned signature. Graveyard first update -> first_update_now (sync) instead of fresh queue.
  Merged native 466aeba37eb7d273a4a92f7aceb1d7cbe6192a55a83e8fd13537f598c51ad926 (08 b2m/out). Parity on 08 b2m/fid:
  B2 10-card scenarios 28/28 native==Python (root and rootstats), Batch A 42/42, probe_first_update_paths 42/42.
  GATE on 127x04 `/mpac/sdicks02/jobs/clasher/cards/b2-merge/` PID 2123864 (cpu_job 8, both arms) -> gate/compare.json.
- 2026-10-16 review r1 REJECT fixes (fresh Sol review of e545eb6bd..27ef53e5c): native scope_targets + scope_periodic skip
  dash travel; native collide() lets a dashing unit consume its queued controlled vector (Tornado pull, found by the new
  audit probe); Clone slide steps settle (arena clamp, building footprint refuse, river recovery) in both engines.
  Audit table + Clone settle in RESULTS.md. Native 58f993748b2160fcc6e38226cba533974be6c11803263077d2773ecc3b6c1674
  (08 b2m/out2). Parity: B2 28/28 (root, rootstats), Batch A 42/42, first-update paths 42/42, dash audit 20 sources x
  2 seats x 40 offsets 0 mismatches, Clone bounds 6/6. Old b2-merge gate (PID 2123864, native 466aeba3) killed by group.
- 2026-10-16T08:13Z GATE b2-merge2 on 127x04 `/mpac/sdicks02/jobs/clasher/cards/b2-merge2/` PID 2553495 (cpu_job 8, both arms; gtree = a40557019 engine-cards; gout = 58f99374) -> gate/compare.json.


## Sol-high resume audit — 2026-10-16T09:23:31Z

Authority: resumed in place on codex/gpt-6.1-sol, reasoningEffort=high (t3_thread_configuration checked).
Parent remains CARD LEAD `thread:delegated-task:command%3Amcp%3A7f0bf0df-35b9-48b9-bbf9-8f9cdcc3f584%3Adelegate-task%3Aclasher-card-lead-20261016-r1`.
Top coordinator: `0523ae6f-baa3-4d4e-b233-b392671670db`.

**Rule correction:** Sam's updated 2026-10-16 direction supersedes the earlier blanket Opus/promotion HOLD.
Routine confident reversible fixes, normalization and reviewed releases/pins within ownership may proceed when
meaningful review/parity/coverage gates pass with exact receipts and rollback. No step is deferred merely
for its design/promotion label. Failed tests, invalid evidence and unmet host-script review still block
acceptance. LIVE LEAD retains active live-pin authority. No main merge, rebase, release/pin/model change
was performed in this resume; current acceptance is held for evidence, not for Opus.

**Coordination:** missing information/clarification/constraints/routine questions go directly to the parent
or existing owner through t3_thread_send(mode=auto), including question, paths/evidence, recommendation and
whether dependent work waits; continue independent work. Never user-input tools. No legacy input request
is pending. This rule and updated authority were propagated to the only active child (final harness reviewer);
all three own children are codex/gpt-6.1-sol high, read-only reviews. Future briefs must repeat these rules.

### Preserved identity / claims / receipts

- Branch cards/b2 started at `659815b30445e09256af644df12575f870a1764a`. Existing six-file engine WIP remains
  unchanged by this resume: battle.py, c56.rs, clone.rs, lib.rs, projectiles.rs, spawn.rs. No rollback/discard.
- 08 launcher **PID/PGID561530**, child **561552**, same command below; at 09:21:21Z elapsed37:33, waiting
  in cpu_room8. lease-561530 absent (not yet admitted); r2.done absent; no r2 outputs at the initial read.
  Its source scripts remain byte-identical to the frozen queued copies in evidence. No duplicate/relaunch.
- C1 launcher PID1042473, cpu_job4, was alive at 09:07:13Z; untouched. B2→C1 integration/gate order retained.
  C1 notified that B2 owns target exclusion, C1 owns new boulder/axe filters. B1 owns its newly reported
  GoblinGiant Clone attachments, BattleHealer Mirror/config/heal recipient and ThreeMusketeers selector issues.
- 04 obsolete gates2123864 /2553495 absent on exact-PID inspection; no b2-merge/b2-merge2 restart, no merge3.
- Frozen native08b2m/out4 SHA256 `7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff`;
  mutantA `ff74a2fc8cfb7e78c60d0c1eb9e0880aebab8fb010939b2fa9d0eb6cfe01ee33`;
  mutantB `2964dec34f8a0a29c9352e249e7e87e77adfce7bcdc908bdbb1443fb8b4265f3`.
  Existing builds.done: 2026-10-16T08:43:37Z. No build launched in this resume.
- Queued run_r2.sh SHA256 `1f72545ff1d2e8a3d8d8cec97dfde49987e6f69908f161548eacf338e2755226`;
  queued probe_dash_full.py `1841fd1d966ef14400c7d8a26ee8dc4412bbdfe6de1f8d5d039281d8ac4ef5dd`.

Exact launcher command (existing, NOT re-executed):
`bash /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash /mpac/sdicks02/jobs/clasher/cards/b2m/fid/run_r2.sh /mpac/sdicks02/jobs/clasher/cards/b2m /mpac/sdicks02/jobs/clasher/cards/b2m/out4 /mpac/sdicks02/jobs/clasher/cards/b2m/mutA /mpac/sdicks02/jobs/clasher/cards/b2m/mutB`

Exact read-only status/hash commands used (remote date uses UTC; ps STARTED uses host local timezone):
```bash
ssh 127x08 'date -u +%FT%TZ; ps -o pid,ppid,pgid,lstart,etime,stat,args -p 561530,561552; cat /mpac/sdicks02/jobs/clasher/cards/b2m/r2.pid; if test -f /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-561530; then cat /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-561530; else echo lease-561530=absent-waiting-for-room; fi; if test -f /mpac/sdicks02/jobs/clasher/cards/b2m/fid/r2.done; then cat /mpac/sdicks02/jobs/clasher/cards/b2m/fid/r2.done; else echo r2.done=absent; fi; ps -o pid,ppid,pgid,etime,stat,args --ppid 561530; sha256sum /mpac/sdicks02/jobs/clasher/cards/b2m/fid/run_r2.sh /mpac/sdicks02/jobs/clasher/cards/b2m/fid/probe_dash_full.py /mpac/sdicks02/jobs/clasher/cards/b2m/out4/clasher_core.abi3.so; ps -o pid,ppid,pgid,etime,stat,args -p 1042473'
ssh 127x04 'date -u; ps -o pid,ppid,pgid,etime,args -p 2553495,2123864; ls -d /mpac/sdicks02/jobs/clasher/cards/b2-merge*; ls -l /mpac/sdicks02/jobs/clasher/cards/b2-merge2/gate/compare.json 2>/dev/null'
```

### Audit / implementation / validation

- Preserved /tmp/b2sites.py and saved84 raw matches in evidence; documented every row in RESULTS, including
  Python counterpart, admission rule, probe source and static-only gaps. Found scanner boundary bug omitting
  entity-length loops plus hit_ids.extend. Corrected scanner adds4 (88 total), no new engine edits needed.
- Independent harness review1 rejected illegal enemy Log/BarbLog/Spirit placements + accepted-looking cast
  rejection, ineffective rolling mutation coverage, bare wait/unconditionaldone, missing combined Clone
  regression and incomplete snapshot comparison. Parent notified immediately; queued evidence is provisional.
- Local-only corrected tools: probe_dash_full.py, run_r2.sh, validate_r2.py, probe_clone_recovery.py,
  native_entity_sites.py, test_r2_harness.py. Complete root serde-normalized snapshot comparisons (constructor
  only; never step expected native), source guard-query observations, required cast success, both-seat exact
  hit-set mutants (B digest-equal), exact Clone water/building/legal fallback fixture, exact PID/exit receipts,
  fresh-tag exclusive identity + full input hashes + strict validator before atomicPASS. No corrected files
  copied to a host or executed there. Old queued copies retained in evidence.
- Independent harness review2 rejected legitimate zero-action first-update fixtures and missing top-level
  exporter/pool hashes. Corrected exact21case/42seat/action counts (6 setup-only cases) and input hashes.
- Independent final review **APPROVED FOR BOUNDED TEST EXECUTION**, not engine acceptance. Exact taskID and
  six reviewed SHA256s: evidence/harness-review-approved-20261016.json. Prior review task suffixes
  b2-r2-harness-independent-review-20261016-0910 and ...review2-20261016-0918; final ...review3-20261016-0920
  (all node:delegated-task:command%3Amcp%3Ac2371be3-b4fc-4c4c-9d4e-c37424334a7c%3Adelegate-task%3A prefix).
- Tests: **8/8 local stdlib-only tests PASS (0.001s)**. Python AST parse and bash syntax PASS. No engine
  simulations/builds/heavy compute on05, no hosts09–18, emulator/input activity, main/runtime/pin changes.

Exact local verification commands (worktree /mpac/sdicks02/repos/clasher-cards-b2):
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/b2/tools/test_r2_harness.py
bash -n reports/cards/b2/tools/run_r2.sh
python3 reports/cards/b2/tools/native_entity_sites.py engine-cards/src
git diff --check
```
AST parsing used ast.parse on engine-cards/py/src/clasher/battle.py and all reports/cards/b2/tools/*.py.

### Next / rollback

The frozen queued r2 run stays intact. A direct parent scheduling message recommends waiting for its
terminal receipt before the corrected fresh-tag run, to avoid competing functional sweeps. Dependent
corrected dynamic execution waits on coordination; audit/documentation continues. New script execution
requires the exact reviewed bytes and a fresh non-r2 tag under cpu_job8; never overwrite queued scripts
or old receipts. Any strict comparator failure remains a failure; do not widen ignores to manufacturePASS.
Final engine review readiness awaits valid snapshot/mutation/scenario receipts and meaningful path coverage;
C56 gate must then run for the exact engine commit before acceptance and eventual B2→C1 integration.

Rollback: no engine/host/live state changed here, so none was needed. The documentation/tooling commit is
reversible independently of the six preserved engine WIP files. For a later distinct validation job, retain
its new PGID/identity and stop only that verified group if required; never stop561530 or C1 by broad match.
Release/pin rollback decisions are not required until such a change is actually proposed within ownership.

### 2026-10-16T09:24Z scheduling correction (supersedes “wait frozen run” above)

CARD LEAD explicitly authorized superseding561530 only while it remains our exact queued/no-lease/no-output
cpu_room8 job. Recheck09:24:35Z: PID/PGID561530, start_ticks193963347, child561552, only cpu_room/sleep
work, no r2 outputs/lease. Prepare a reviewed one-shot scheduler, no host mutation before independent review.
After exact identity/start/args/UID/PGID checks, brief groupSTOP closes admission race; repeat no-work checks.
If admitted, CONT and leave intact, no new run. Otherwise TERM only group561530 then CONT to deliver TERM;
verify no live group, no lease and no cpu_room claim; preserve original files/logs and exclusive superseded-not-evidence
receipt. No rm/pkill/broad matches. Fresh isolated corrected validation only: 08
`/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0925Z`, tagr2v2, cpu_job4/nice15, runner phases4/4/3.
Local new scheduler tools/supersede_r2.py + changed run_r2.sh submitted for independent review
(task suffix b2-r2-cpu4-scheduler-review-20261016-0929). Reviewer found NUL escaping in git -z / /proc argv
parsing; fixed actual Python source to single-backslash NUL syntax and verified both embedded/local AST constants
evaluate to NUL. Not executed yet. The approved8-worker receipt is historical and does not approve the modified
4-worker scheduler bytes; a fresh exact-hash receipt is required.

C1 focusedr2 f68e5f80f/native631ac approved; preserve exact future integrated attacks.rs22 secondary_recipients
and c56.rs309 chain_release in B2 audit. Added rows in RESULTS; Python currently permits ordinary/secondary
targetability during dash, so re-pair integrated semantics rather than blindly adding area filters. No C1
queue/boulder fixes copied, no merge/rebase/pin change; B2→C1 remains.

### 2026-10-16T09:33:21Z: one-shot scheduling result and explicit staging failure

- Independent scheduler review APPROVED exact supersede_r2.py e84bb490263603e9e9df6bc3197b6b5b9a7eb052ad48a1d820b002ee25453ea0
  and four-worker run_r2.sh39ee7dff1d2172d8e58f9041f1b6e6c629fa7d10017fe4a8b39c744b67beacf4.
  Exact reviewed seven-file receipt: evidence/scheduler-review-approved-20261016.json.
  Reviewer withdrew the initial escaping finding after AST inspection; current source delimiters are NUL.
- Exact executed command (nice15, local light staging only):
  `nice -n 15 python3 -B reports/cards/b2/tools/supersede_r2.py reports/cards/b2/evidence/scheduler-review-approved-20261016.json`.
- 09:30:50.120840Z fresh identity check: owner/current PGID561530, start193963347, exact frozen argv,
  no lease/outputs/log content; child561552 cpu_room8 and sleep3156679. Reviewed remote sequence:
  `os.killpg(561530, SIGSTOP)`; recheck same identity and waiting/no admission;
  `os.killpg(561530, SIGTERM)`; `os.killpg(561530, SIGCONT)` to deliver pendingTERM.
  At09:30:50.498639Z no live group members, no lease and no cpu_room claim. Frozen files/logs unchanged.
  Receipt08b2m/r2.superseded.json copied to evidence/r2-superseded-20261016.json. Status **superseded-not-evidence**.
- Staging then FAILED before extraction/launch: systemPython08=3.8.10 lacks Path.is_relative_to.
  Script exited1; no replacement PID, no CPU lease/job, no simulation. Empty directory
  b2-r2v2-20261016T0925Z preserved (confirmed09:31:31Z), no rm or implicit retry.
  Failure evidence/r2v2-staging-failure-20261016.json; parent notified immediately.
- Narrow compatibility recovery prepared as tools/stage_r2v2.py: reuse reviewed staging body with
  Python3.8 Path.relative_to containment check, require old PID/lease/claim absent and failed directory empty,
  use different fresh b2-r2v2-20261016T0933Z, no termination/requeue of frozen arm. New independent
  review task suffix b2-r2-python38-stageonly-review-20261016-0933 pending; not executed.
  Rollback: frozen source/logs/old failure remain intact. No reason to requeue invalid frozen arm.

Exact read-only follow-up:
`ssh 127x08 'date -u +%FT%TZ; python3 --version; ls -la /mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0925Z; ps -o pid,ppid,pgid,stat,args -p 561530,561552; test ! -f /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-561530 && echo lease-561530=absent; test ! -f /mpac/sdicks02/jobs/clasher/bot-cpu-claims/claim-561552 && echo claim-561552=absent; cat /mpac/sdicks02/jobs/clasher/cards/b2m/r2.superseded.json'`.

### 2026-10-16T09:35:20Z: corrected validation queued; audit/tooling commit

Independent stage-only compatibility review APPROVED exact stage_r2v2.py
ff9c9a86b425cd5dedcc569a602fc39916bc7925ca37ccbf1f5d18f0e024bd73 (task suffix
b2-r2-python38-stageonly-review-20261016-0933). Eight-file reviewed receipt:
evidence/stage-recovery-review-approved-20261016.json. Exact executed command:
`nice -n 15 python3 -B reports/cards/b2/tools/stage_r2v2.py reports/cards/b2/evidence/stage-recovery-review-approved-20261016.json`.
It ran once, exited0; did not terminate/requeue anything. New isolated staging succeeded, and every staged
tracked engine file hash equals already-built08b2m/tree. Old failed directory preserved.

**ONE active corrected validation:** 08 PID/PGID**3422841**, launched2026-10-16T09:33:56.816158Z,
jobdir `/mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z`, tagr2v2, cpu_job4/nice15, phases4/4/3.
At09:34:12Z launcher NI15, child**3422863** cpu_room4, no lease yet and no probe outputs. No second run.
C1 queue remains untouched. Source/tools manifest SHA256
001a53753aaa78aa788075029de25f7847638dfd81d8b3a0a1eb548acb52a9c4; exact source WIP diff/commit,
script/native hashes and launch args in hostsource-and-tools.json/launch.json and local
evidence/r2v2-launch-20261016.json. Parent notified at launch with exact PID/jobdir/hash.

Expected evidence: fid/r2v2-identity.json, r2v2.pids, per-child .exit/.json/.log, and
fid/r2v2.pass.json only after strict validation. A mere process exit or completion marker is not PASS.
Guard mutations A/B need intended hit-ID differences in both seats, B digest-equal; exact Clone recovery
fixture and scenario/FU parity must pass. No dynamic result yet; not ready for final engine review/C56 gate.
Do not relax comparator exclusions on failure. Do not restart obsolete b2-merge/b2-merge2 gates.

Exact read-only launcher check:
`ssh 127x08 'date -u +%FT%TZ; ps -o pid,ppid,pgid,ni,etime,stat,args -p 3422841; ps -o pid,ppid,pgid,ni,etime,stat,args --ppid 3422841; if test -f /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-3422841; then cat /mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-3422841; else echo lease-3422841=absent; fi; ls -l /mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z/fid/r2v2* 2>/dev/null; cat /mpac/sdicks02/jobs/clasher/cards/b2-r2v2-20261016T0933Z/run.log'`.

Commit scope: reports/cards/b2/ documentation/evidence/tools only, explicit path adds, staged secret scan
before commit, push cards/b2. Six existing engine files deliberately remain WIP pending parity; no engine
commit/pin/release/main merge is implied. Eight small local tests + Python/bash syntax PASS.
Rollback: tooling/documentation commit can be reverted independently; new validation only may be stopped
by verified PGID3422841 if necessary. Frozen superseded arm is not requeued automatically; only do so if
actually needed under a new decision. Failed first staging remains recorded as failure.

- Pre-commit diff check found trailing spaces at truncated source-snippet boundaries in two TSV displays; trimmed display whitespace only, no site/guard/result changes. Raw scanner/saved script is unchanged. Rechecked staged diff and reran staged secret scan before commit.
