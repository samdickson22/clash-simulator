# live16402d / r1-cards4 release — PROGRESS

## HANDOFF (keep current)
- 2026-10-18T02:50:12Z: r1-cards4 + live16402d RELEASED READ-ONLY on04/08; 4/4 Runtime(verify=True) PASS; 03 down/skipped.
- Final source 89692ef4db3be1e89cf9354c074762f565992f02; native/data/checkpoint pins verified, parents unchanged; no active/Mac pin changes.
- All16 final phase exits0 and strict SUMMARY PASS. Original Numba failure resolved with reviewed env-only defaults; Sol r2 APPROVE and fleet deployment receipts retained.
- Coordinator explicitly chose documented NOREPLACE directories; no symlink procedure introduced. Source/pins/receipts are being integrated through the authorized temporary-index release-d/main merge; final Git receipt records pushed refs.
- Consumers require external writable NUMBA_CACHE_DIR; later Mac adoption is LIVE-owner work. No work on03 or09–18.
- Final aggregate: receipts/FINAL-RELEASE-RESULT.json; docs: ../RELEASES.md. Historical failures and decision/recovery records below are retained verbatim.

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
- Sol review r1 REJECT (2 should-fix in overlay pass 3: calibration matched by path; tier changes propagated by name; note: NaN
  graph rows). Fixed in e694df2b3 (identity calibration, pass 3 excluded from propagation, non-finite rows → PublicGraphError),
  tests 19/19 + 12/12 + 25/25, mutation-checked; real overlay unchanged df93121d. Delta review r2 running
  (`cards-release-d-graph-overlay-review-r2`). Prep roots on 08 were built from b07927454 (pre-fix); final assembly uses final source.
- Review r2 REJECT (propagation INTO tiers by name; coord overflow note) → 938759f0e. r3 REJECT (sourced/odd-kind tiers escaped
  pass-3 ownership) → bf9ee2d62: every detection-tier BuffType block is pass-3-owned (excluded from pass 2 and propagation).
  21/21 overlay tests, mutation-checked; real overlay still df93121d. Review r4 running (`cards-release-d-graph-overlay-review-r4`).
- stress-02 (live16402c-dev + candidate helper, natural GG vs Fisherman/Tornado/Log/Fireball/Snowball/BarbLog/RoyalDelivery/Bowler/
  Clone games): after 2 games 1,676 roots, old helper a156cf5b1 errors 20, candidate 0 errors, 20 structural boards, 20/20 native
  clone/reload/step continuations on structural roots; 244e385ca 0 errors so far (complete populations only).
- Review r4 REJECT (pass-1 crown search could write a tier) → 4ec76f954 single write choke point. **Review r5 APPROVE, no findings.**
- stress-02 PASS (6 games, 4,930 roots, 13,488 attached rows; old helper a156cf5b1 42 errors, candidate 0; 42 structural boards,
  42/42 native continuations on them). Receipt: 08 `jobs/clasher/cards/release-d/stress-02/out.json`.
- Prep gates: all steps exit 0 (smoke, none, class 4 shards, totality 4, HEADLINE candidate, mixed 4+2); stress step on the
  dev root running; `tools/summarize.py` does the content checks (stricter: zero mixed root errors) → SUMMARY.json.
- Release tools ready: `tools/build_native.sh` (fresh native-<sha8>/, -j8) — dry run rebuilt 86a5d050 bit-identical from
  b07927454 (08 `release-d/nbuild-prep`); `tools/release.py` + `release_host.sh` (r1-cards3 procedure, parents r1-cards3/live16402c).
- 21:09Z **Prep gates PASS** (dev roots from b07927454 + C1 native 86a5d050; receipts/PREP-SUMMARY-b07927454.json, sha 4e13f75f…):
  smoke 2/2; None-stat 38,842×2 / 0; class 122 cards / 366 scenarios / 96,896 checks / 0 exceptions; totality 4×6,707 / 0 panics /
  0 unexpected; K4L HEADLINE 12/12 identical vs r1-total (baseline hashes from r1-cards3 GATES); mixed 6/6, 0 crashes, **0 root
  errors**; graph class on live16402d-dev 5,222 roots, 40 structural, 0 candidate errors (old helper would have failed 40).
  (SUMMARY-v1 had a reference-key naming bug in graph_class, fixed and re-summarized.)
- GO: admission-class merged main d5d7d31ff (engine tree f3507930 == gated 611779cab, native 5b2e45d7). Rebased → bf0892d72; native
  rebuilt on 08 (`release-d/final/native-5b2e45d7`) **bit-identical 5b2e45d72cc4…** → no C56 re-gate (engine-cards differs from
  611779cab only in Python public_root.py). Pins → 5b2e45d7 (89692ef4d). Final pipeline on 08 `release-d/final` (PID 4007414):
  ASSEMBLY PASS (gamedata 892fbfa0 / df93121d); gates running (08 load ~111).

- 2026-10-17T23:47Z publisher took over; background PID-exit watcher active. Final pipeline still in class gate, zero failures in partial shard logs. Both target roots absent on 04/08; no publication attempted.
- 2026-10-17T23:56Z final PID remains active; class shards now probing buildings, partial logs still zero failures. Destination checks on both hosts passed.
- 2026-10-18T00:04Z waiting on final pipeline PID; class shards in final spell scenarios, zero failures observed. Full content checks remain pending.
- 2026-10-18T00:10Z class 4/4 shards exit 0; totality started (root-scrub exit 0). Final PID still active; headline, mixed, graph and aggregate content checks remain.
- 2026-10-18T00:18Z resumed after harness interruption; pipeline PID 4007414 remains active and unchanged. Previous local watcher session was removed by interruption; restarted bounded SSH watcher (90 × 60 seconds). Totality 4/4 exit 0; HEADLINE running.
- 2026-10-18T00:23Z second harness interruption removed the unified-exec watcher again. Pipeline unchanged (HEADLINE 6/12 rows so far). Watcher now detached with setsid/nohup and flock; `/tmp/clasher-release-d-wait-4007414.sh` performs SSH kill-0 every 60 seconds (90-check bound), log `/tmp/clasher-release-d-wait-4007414.log`.
- 2026-10-18T00:32Z HEADLINE 11/12 records; class/totality complete with all exits 0. Waiting for remaining HEADLINE, mixed and graph, then strict aggregate checks.
- 2026-10-18T00:43Z HEADLINE candidate exit 0 (12 records), mixed 4+2 runs exit 0. Final graph probe started. After PID exits, run strict summary and prep comparison before any snapshot/publication.

## live16402d publication failure — 2026-10-18T02:34:58Z

Final source `89692ef4db3be1e89cf9354c074762f565992f02`. All 16 pipeline phase exits are 0; strict SUMMARY PASS, HEADLINE 12/12 identical, mixed 6/6 with zero crashes/root errors, graph 6 seeds / 5,222 roots / zero candidate errors. The old waiter only checked process exit and had finished without publishing.

**STOPPED: release verification failed (exit 1) on both 127x04 and 127x08.** `release_host.sh` created the new immutable r1-cards4 root, then `release.py verify` failed importing Numba's cached `_build_blocked_mask_numba` from the read-only tree: `RuntimeError: cannot cache function ... no locator available`. The host wrapper does not supply the external NUMBA_CACHE_DIR used by the gates. No runtime source repair, chmod, overwrite, retry, merge, commit or push followed this verification failure.

Partial state: `/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4` exists read-only on both hosts, with CREATE receipts but no successful VERIFY receipt; **live16402d remains absent on both**. Existing runtime directories and active pins were not changed; no Mac commands ran. 127x03 was skipped as directed (down). Do not rerun the host create wrapper against these existing roots. Parent must decide how to resume verify with an external writable cache and preserve these immutable roots before any further publication.

Evidence: `reports/cards/release/live16402d/receipts/PUBLISH-FAILURE.json`; host SHA256s and exact last 30 log lines follow.

### 127x08

Phase: `release.py verify r1-cards4 / Runtime(verify=True)`; exit: **1**. Log: `/mpac/sdicks02/jobs/clasher/cards/release-d/final/release-host.log`.

r1-cards4 RECEIPT.json SHA256: `d742af877a08245a2c75dea539eb86506dda3328c44f9e860e3c3451c046a1b4`.

```text
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/jobs/clasher/cards/release-d/final/publish-tools/release.py", line 176, in run
    start = time.monotonic(); rt = Runtime(verify=True)
                                   ^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/jobs/clasher/cards/release-d/final/release-verifier/bot/players/runtime.py", line 150, in __init__
    from fair_player import Resources
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py", line 15, in <module>
    from c56_controller import CARDS, resources
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/engine-rs/c56_controller.py", line 10, in <module>
    from clasher.rl.c56_scripted import C56_ADDED_CARDS
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/c56_scripted.py", line 16, in <module>
    from .public_observation import ConfidenceAwareActorObservation
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/public_observation.py", line 8, in <module>
    from .structured_obs import VISIBLE_CARD_SLOTS, ActorObservation
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/structured_obs.py", line 13, in <module>
    from clasher.battle import BattleState
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/battle.py", line 81, in <module>
    @njit(cache=True)
     ^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/decorators.py", line 227, in wrapper
    disp.enable_caching()
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/dispatcher.py", line 811, in enable_caching
    self._cache = FunctionCache(self.py_func)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/caching.py", line 687, in __init__
    self._impl = self._impl_class(py_func)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/caching.py", line 423, in __init__
    raise RuntimeError("cannot cache function %r: no locator available "
RuntimeError: cannot cache function '_build_blocked_mask_numba': no locator available for file '/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/battle.py'
```

### 127x04

Phase: `release.py verify r1-cards4 / Runtime(verify=True)`; exit: **1**. Log: `/mpac/sdicks02/jobs/clasher/cards/release-d/publish-04/release-host.log`.

r1-cards4 RECEIPT.json SHA256: `6ae04d1a593e3468f0d3571221d3c219ef4360cec0aaab9251d25bcc40ce1768`.

```text
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/jobs/clasher/cards/release-d/publish-04/tools/release.py", line 176, in run
    start = time.monotonic(); rt = Runtime(verify=True)
                                   ^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/jobs/clasher/cards/release-d/publish-04/release-verifier/bot/players/runtime.py", line 150, in __init__
    from fair_player import Resources
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py", line 15, in <module>
    from c56_controller import CARDS, resources
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/engine-rs/c56_controller.py", line 10, in <module>
    from clasher.rl.c56_scripted import C56_ADDED_CARDS
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/c56_scripted.py", line 16, in <module>
    from .public_observation import ConfidenceAwareActorObservation
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/public_observation.py", line 8, in <module>
    from .structured_obs import VISIBLE_CARD_SLOTS, ActorObservation
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/rl/structured_obs.py", line 13, in <module>
    from clasher.battle import BattleState
  File "/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/battle.py", line 81, in <module>
    @njit(cache=True)
     ^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/decorators.py", line 227, in wrapper
    disp.enable_caching()
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/dispatcher.py", line 811, in enable_caching
    self._cache = FunctionCache(self.py_func)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/caching.py", line 687, in __init__
    self._impl = self._impl_class(py_func)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/numba/core/caching.py", line 423, in __init__
    raise RuntimeError("cannot cache function %r: no locator available "
RuntimeError: cannot cache function '_build_blocked_mask_numba': no locator available for file '/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards4/src/clasher/battle.py'
```

- 2026-10-18T02:44:59Z Environment recovery: Sol r2 correctness review APPROVE after r1 findings fixed.42 tracked launchers contain only the requested comment/export; 235 deployed launcher defaults atomically applied and after-hashes verified on01/04/08; three operative release-wrapper copies patched. Writable NVMe caches confirmed. Existing r1-cards4 verification retries are running on04/08 under cpu_job1/nice15; no roots changed. Publication remains pending: release.py implements NOREPLACE directory publication and explicitly rejects symlink targets, contrary to the requested live16402d symlink; no alternative publication procedure was invented.


## Numba environment recovery — 2026-10-18T02:45:53Z

**r1-cards4 Runtime verification now PASS on both 04/08, retry exits 0/0.** Sol correctness review r2 APPROVE after fixes for conditional-cache precedence and missing launcher coverage. The only launcher changes are the requested two-line comment/export, deployed atomically on 01/04/08 (31/110/94 files) plus 3 operative release-wrapper copies. All deployed after-hashes match the reviewed plans. NVMe cache `/mpac/sdicks02/cache/numba` exists and is writable on all three hosts. Existing conditional job cache defaults and explicit overrides remain intact. Reviewer r1/r2 and diff are retained in receipts.

Both roots remain READ-ONLY, parents unchanged, 477 overlay hashes verified, 121 metadata cards / 237 config entries / 359 templates. Native, gamedata and original CREATE receipt bytes are unchanged.

- 127x04: PASS at 2026-10-18T02:45:19Z; original CREATE SHA256 `6ae04d1a593e3468f0d3571221d3c219ef4360cec0aaab9251d25bcc40ce1768`; VERIFY receipt file SHA256 `37fe105bf0ec0ab0748874a9e4370ff5837684064ea9ec9cab88d70537625122`. Log `/mpac/sdicks02/jobs/clasher/cards/release-d/publish-04/r1-cards4-verify-retry.log`.

- 127x08: PASS at 2026-10-18T02:45:24Z; original CREATE SHA256 `d742af877a08245a2c75dea539eb86506dda3328c44f9e860e3c3451c046a1b4`; VERIFY receipt file SHA256 `dd5036bff3063189291d5d59e0a4e722783f60444c6744584685cbc39a806785`. Log `/mpac/sdicks02/jobs/clasher/cards/release-d/final/r1-cards4-verify-retry.log`.

**Publication decision required:** live16402d remains absent on both hosts. The requested “live16402d symlink” conflicts with the documented release tool, which atomically publishes a directory using renameat2 NOREPLACE and explicitly rejects target/ancestor symlinks. No new procedure was invented and no release.py/source/pin changed. Coordinator must choose the documented directory publication or authorize a revised symlink procedure. No merge, commit or push occurred; Mac active state was not touched. RELEASES.md now records the consumer NUMBA_CACHE_DIR prerequisite and later LIVE-owner Mac export requirement.

Evidence: `receipts/ENV-RECOVERY-RESULT.json`, `127x04-r1-cards4-VERIFY.json`, `127x08-r1-cards4-VERIFY.json`, `NUMBA-REVIEW-r2.md`, `numba-env-default.diff`. The complete reviewed main-based launcher patch and temporary index remain at `/tmp/clasher-cards4-publish-5d98zvo_/main` and `/tmp/clasher-cards4-publish-5d98zvo_/env-main.index`; no shared index was modified.


## r1-cards4 / live16402d released — 2026-10-18T02:50:12Z

**Both releases are READ-ONLY and verified on127x04/127x08 (4/4 Runtime PASS)**. 03 skipped (down). Final exported source `89692ef4db3be1e89cf9354c074762f565992f02`; native `5b2e45d72cc4ab1d9cde300800f907e97224212a0c938c882909b04894a21932`. All16 phase exits0; strict SUMMARY PASS; HEADLINE12/12 identical, mixed6/6 with0 crashes/root errors, graph6 seeds/5,222 roots/0 candidate errors. All477 overlays, pins, complete content/mode/symlink manifests, read-only state and unchanged parents verified. Source/pins and release receipts are integrated through the authorized release-d/main publication flow.

The coordinator chose documented atomic NOREPLACE directory publication. Existing r1-cards4 roots/CREATE receipts were preserved; live16402d was created fresh and verified. Original Numba failure retained; Sol r2-approved external-cache default is deployed on01/04/08. Consumers require NUMBA_CACHE_DIR; later Mac adoption by LIVE needs the same export/appropriate writable override. No active pins, existing runtime roots or Mac state changed. See `reports/cards/release/RELEASES.md` and `reports/cards/release/live16402d/receipts/FINAL-RELEASE-RESULT.json` for exact host receipts, hashes, timestamps and scope limits.
