# Batch B2 spell mechanics results

Status: **C56 gate FAIL** on the requested frozen B2 tree (`4916d66b8`, handoff `745d18c2c`).
The original 04 fixture sweep is still running; failure was reported immediately and the
Opus owner was woken with the one-hunk fix specification in [GATE-TRIAGE.md](GATE-TRIAGE.md).
No engine changes were made in this worktree by the test agent. A scratch diagnostic revert
was used only on 08. This report distinguishes completed fidelity/repro results from the
ongoing full gate. The Opus owner has since committed the one-hunk engine fix as `aa8d28a76`;
that corrected source is not the frozen gate arm measured here.

## Inputs and completed fidelity sweep

Primary arm: full RoyaleSim 16.402 table (`--table 160402`), not the adapter's older Void values.
Host 08, `/mpac/sdicks02/jobs/clasher/cards/b2/`:

- `baseroot` / `base`: pre-B2 `7720915a8`.
- `root` / `tree`: B2 mechanics, byte-matched by rsync checksum against this worktree's engine-cards.
- `rootstats`: B2 mechanics plus scratch `fid/stats-spec.json` overlay in `stats/gamedata.json`.
- `fid/run_pool.sh` recorded PID 3069080 has exited; `fid/final.done` exists and reads `done`.
- Full files: `fid/final-{base,mech,stats}.jsonl`, each 196 rows / 66 cards. Source engine
  files in 08 `tree` and `gtree` also matched the worktree before owner fixes.

| Passing measured scenarios | Before | Mechanics | Mechanics + scratch stats |
|---|---:|---:|---:|
| B2 (10 cards) | 13/28 | 16/28 | 24/28 |
| Other cards (56 cards) | 41/168 | 41/168 | 41/168 |
| Full 66-card pool | 54/196 | 57/196 | 65/196 |

Mirror has one harness scenario, the other nine B2 cards have three each: **28**, not 30,
rows in this fidelity sweep. Tolerance and verdicts are the existing `summarize.compare()`
ones, including one tick for impact timing. Improvements in difference count can occur
without changing a scenario from DIFF to PASS.

JSON summaries are retained in [evidence/fidelity-summary.json](evidence/fidelity-summary.json)
and [evidence/mixed-summary.json](evidence/mixed-summary.json). Input SHA256 values:

```text
final-base.jsonl  fd6ff1d12efd480587a7cf79ac8beb68ce68e3fef8e1e125b5491a9f2e44a688
final-mech.jsonl  b5c6e4d2cb1ef815799e1d604b18c1d43e921d8e584037c0f3249767c9671f00
final-stats.jsonl 80499d7c2fe5d157b1f5207685e5b10017e8afaf6c1bec4881add935fe89109f
```

## Cause / fix by card

Mechanics and controlled observations below are from PROGRESS.md; the verdict counts are
independently recomputed from the final three-arm JSONL files.

| Card | Before → mechanics → stats | Cause / implementation | Scratch stat rows (outside git) / residual |
|---|---|---|---|
| Freeze | 1/3 → 1/3 → 3/3 | AreaEffectSpell reads data crownTowerDamagePerHit | Area lifeDuration 3500, buffTime 3500, crown damage 15 (add); extra towerfreeze controlled probe identical in owner's notes |
| Heal | 0/3 → 0/3 → 3/3 | No mechanic gap | HealSpirit hitpoints 84 |
| DarkMagic / Void | 1/3 → 1/3 → 3/3 | Scope area skips birth update (previously one tick early) | lv3 dps/crown 2720/38; lv2 1155/20; lv1 600/14 |
| Vines | 2/3 → 2/3 → 3/3 | Birth skip; catch clock from data; re-pick each catch; air-to-ground 2.1 s; grounded flier keeps air collision plane | Vines_AeO lifeDuration 1400, hitSpeed 250 (add) |
| Rage | 2/3 → 3/3 → 3/3 | Haste applies on landing; cap is life left + HitSpeed; capBuffTimeToAreaEffectTime | No stat overlay; owner's controlled application window matches 11..105 |
| Clone | 2/3 → 3/3 → 3/3 | Object-phase cast; 500 ms hold; 10-tick column-edge slide after movement; route dropped at slide end | Final harness rerun closes the pending Clone item |
| Graveyard | 0/3 → 1/3 → 1/3 | Birth skip; against_forward Y orientation; deploy +1 tick; F+7 acquisition delay; creation-tick first update | Cluster/support residual: Skeleton contact drift after death at t106/t204, described by owner as shared physics. Separately, an accidental RollingProjectile +50 ms hunk breaks C56 (see triage) |
| GoblinCurse | 2/3 → 2/3 → 2/3 | Birth skip; data-driven curse slow; converted Goblin deploy +1 tick | GoblinCurseDamage speedMultiplier -15 (add). Cluster residual: converted-Goblin river snapping and slot-ordinal artifact (owner attribution) |
| Snowball | 2/3 → 2/3 → 2/3 | Knockback and slow match in controlled probe; cluster retains a step toward the old waypoint after a 1.8-tile push | Shared route behavior, also relevant to C56 Fireball/Log; left unchanged / C56-blocked |
| Mirror | 1/1 → 1/1 → 1/1 | Native bomb children lookup uses payload key with name fallback for mirrored SkeletonBalloon | No overlay; level-11 C56 intended inert |
| Poison × dash (native-diff) | Separate interaction probe | Native area_targets skips dash travel; only BanditDash bodies carry it | Not a B2 fidelity-pool scenario; mixed games 75/416/133 now match |

Spell-area boundary probe (ours misses at r+0.5, RS hits to r+1.0) was left unchanged:
owner identified the RS AOE_HIT_TEST as a low-confidence guess, while ours follows strict
client intersects. It also affects C56 spells.

## Final per-scenario fidelity

Generated by `tools/table.py final-base.jsonl final-mech.jsonl final-stats.jsonl -- Freeze Heal
DarkMagic Vines Rage Clone Graveyard GoblinCurse Snowball Mirror`. Parentheses are the number
of measured differences; any following metric is the first difference, ours/RS.

| Card | Scenario | Before | Mechanics | Mechanics + stats |
|---|---|---|---|---|
| Freeze | tower | PASS (0) | PASS (0) | PASS (0) |
| Freeze | cluster | DIFF (21) tower_hits[0].tick 222/212 | DIFF (21) tower_hits[0].tick 222/212 | PASS (0) |
| Freeze | support | DIFF (13) tower_hits.count 7/8 | DIFF (13) tower_hits.count 7/8 | PASS (0) |
| Heal | alone | DIFF (6) HealSpirit[0].max_hp 230/215 | DIFF (6) HealSpirit[0].max_hp 230/215 | PASS (0) |
| Heal | knight | DIFF (1) HealSpirit[0].max_hp 230/215 | DIFF (1) HealSpirit[0].max_hp 230/215 | PASS (0) |
| Heal | minions | DIFF (1) HealSpirit[0].max_hp 230/215 | DIFF (1) HealSpirit[0].max_hp 230/215 | PASS (0) |
| DarkMagic | tower | DIFF (6) tower_hits[0].damage 48/97 | DIFF (6) tower_hits[0].damage 48/97 | PASS (0) |
| DarkMagic | cluster | DIFF (62) tower_hits.count 27/6 | DIFF (62) tower_hits.count 27/6 | PASS (0) |
| DarkMagic | support | PASS (0) | PASS (0) | PASS (0) |
| Vines | tower | PASS (0) | PASS (0) | PASS (0) |
| Vines | cluster | DIFF (48) tower_hits.count 26/23 | DIFF (9) enemy_hits[2].tick 70/74 | PASS (0) |
| Vines | support | PASS (0) | PASS (0) | PASS (0) |
| Rage | tower | PASS (0) | PASS (0) | PASS (0) |
| Rage | cluster | PASS (0) | PASS (0) | PASS (0) |
| Rage | support | DIFF (4) tower_hits[0].tick 194/190 | PASS (0) | PASS (0) |
| Clone | tower | PASS (0) | PASS (0) | PASS (0) |
| Clone | cluster | PASS (0) | PASS (0) | PASS (0) |
| Clone | support | DIFF (25) tower_hits.count 8/9 | PASS (0) | PASS (0) |
| Graveyard | tower | DIFF (17) Skeleton[0].ready 53/55 | PASS (0) | PASS (0) |
| Graveyard | cluster | DIFF (41) Skeleton[0].ready 83/85 | DIFF (16) enemy_hits.count 15/17 | DIFF (16) enemy_hits.count 15/17 |
| Graveyard | support | DIFF (79) Skeleton[0].ready 88/90 | DIFF (42) tower_hits.count 28/33 | DIFF (42) tower_hits.count 28/33 |
| GoblinCurse | tower | PASS (0) | PASS (0) | PASS (0) |
| GoblinCurse | cluster | DIFF (80) Goblin[0].ready None/112 | DIFF (77) Goblin[0].ready None/112 | DIFF (70) Goblin.count 8/6 |
| GoblinCurse | support | PASS (0) | PASS (0) | PASS (0) |
| Snowball | tower | PASS (0) | PASS (0) | PASS (0) |
| Snowball | cluster | DIFF (5) tower_hits[1].tick 187/185 | DIFF (5) tower_hits[1].tick 187/185 | DIFF (5) tower_hits[1].tick 187/185 |
| Snowball | support | PASS (0) | PASS (0) | PASS (0) |
| Mirror | mirror | PASS (0) | PASS (0) | PASS (0) |

## Other-card regressions

Across all 168 scenarios of the other 56 cards, both B2 arms have **exactly the same verdict
and full compare() difference list** as baseline. No passing scenario became DIFF, either
inside or outside B2. This fidelity-pool finding does not imply C56 parity: the separate
real-fixture gate caught BarbLog's 50 ms spawn delay regression, absent from this 66-card pool.

## C56 gate (frozen original B2)

Host 04, `/mpac/sdicks02/jobs/clasher/cards/b2/`. Exact launch:

```sh
REUSE_PINNED=1 setsid /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash /mpac/sdicks02/jobs/clasher/cards/b2/fid/gate.sh
```

Own PID/PGID 2737392, held by a shell waiting on that exact PID; no pgrep/pkill used.
All Python gate work uses nice 15. Batch A's PID 2388512 was already gone and no Batch A job
was signaled or changed. `gate.pid`, `gate.log`, and eventual `gate.exit` record this run.

Root `rt` mirrors r1 symlinks except `engine-rs → gtree`, `src → gtree/py/src`, and
`gamedata.json → gtree/py/gamedata.json`. 04 gtree/gout were copied from frozen 08 copies.
Native SHA256: `df5443abf6d629fc34fded6fbc515ea40c70ecd6efe6693e379462500b617488`.
Pinned native: `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`.
Gate-tools and roots were copied from 04 Batch A and rsync checksums found no differences.

Pinned arm reused from the completed PASS Batch A gate: 577 fixture rows and four root
shards, each 150 records + a header (600 records, 300 sampled roots). Copied files, not
links. Same host, runtime r1, native SHA, gate tools, recorded fixture data, roots, sample
seed 20261015, sample 300, shards i/4, and PYTHONHASHSEED=0; root header has command/opponent
delay 27, horizon 160, interval 10, elixir weight 1.0. Runtime/data source timestamps predate
Batch A's run. Baseline Batch A itself passed 577/577 fixture records and 600/600 root records.

| Check | Result | Evidence |
|---|---|---|
| Fixture complete-record equality | **FAIL (sweep running)** | First failing episode v4-phase-a-1975100701 |
| Rust-only native chains | **FAIL (sweep running)** | First digest divergence t1439; config differs from initial snapshot t1200 |
| Roots, 300 full + 300 cut | PENDING | Scheduled by gate.sh after fixture pool completes |
| Overall requested frozen B2 | **FAIL** | One failing fixture is sufficient; full counts will be filled from compare.json |

See [GATE-TRIAGE.md](GATE-TRIAGE.md) for precise owner fix and one-hunk bisect: all 2402
digest and snapshot hashes in the first failing fixture match pinned after reverting only
the RollingProjectile deploy-delay hunk in an 08 scratch gtree. Diagnostics detail/phase_step
confirm the Barbarian deploy/target/movement transition. No frozen gate engine code was changed.

## Native-diff mixed repros

The old run failed at import (`ModuleNotFoundError: es_common`). `tools/run_mixed.sh` fixes
PYTHONPATH by including r1's `reports/strategy_council_20260928/engine-speed`, runs from
08 b2/root, uses frozen gout, and takes `cpu_job.sh 1` with nice 15. Summary output is
08 `fid/mixed-b2.json`; exited 0. The tooling now also retains per-game full diagnostics.

| Game | B2 outcome | Ticks | First mismatch |
|---|---|---:|---|
| 75 | MATCH | 3600 | None |
| 416 | MATCH | 3600 | None |
| 133 | MATCH, game over | 3254 | None |
| 509 | MISMATCH | 3600 | Digest, t341 |

Game 509: Python creates IceGolemite entity 49; native does not (`next_id` 50 vs 49).
The new entity/ID difference appears in the object phase in diagnostics.phase_step. It has
no exception/panic; this mismatch is separate from the C56 BarbLog regression. Full evidence
08 `fid/mixed-509-details-game-509.json` (retained by an extra one-game diagnostic rerun).
