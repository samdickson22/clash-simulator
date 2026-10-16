# R24 fixture/bootstrap and existing-only preload repair

Source-only handoff, 2026-10-16. W = `/mpac/sdicks02/repos/clasher-bot-levels` on05; J = `/mpac/sdicks02/jobs/clasher/bot-levels`; C = `J/level-configs/50d22f86b3590abc` on01. Read the complete R24 repair brief, Astra bootstrap audit and authorized response, R23 review, preserved failed pytest evidence/support snapshot, and relevant owned/runtime contracts. The response explicitly authorizes the minimal run.py/test_harness.py addition. **New bytes have not been imported, parsed, compiled, tested, synced or executed. No cache restoration, Runtime construction, job, native action or descendant was performed. Fresh independent review is required before any of those actions.**

## Concrete repair and retained failures

Changed only `bot/levels/fixture_support.py` (new), `test_placement.py`, `gates.py`, `run.py`, `test_harness.py`. The focused patch is `J/gates-r24-implementation.patch`, SHA256 `7298068407d2ee9ec3abbe8f62abcd63569946f84ce64b152bb531cbc5c3daa6`; it compares the four existing files with saved pre-R24 bytes and includes the complete new helper. Full root-level source/recorder/search/B0/bank hashes are `J/gates-r24-source.sha256`, SHA256 `eec161f8aa8eec743233658ba9f7e67c846c3f1a9f1384d06d0b0567bc452b63`. Source inspection and diff whitespace inspection only; no test PASS is inferred.

1. Ten candidate-fixture failures: legality uses actual `bot.search.players.TIMED_WAITS` (2400/2401/2402 →10/20/40 simulation ticks) and the existing public WAIT bit2304, rather than indexing a2306-entry mask with2400. All ordinary IDs still require integer/range/mask eligibility; negative, unknown oversized, float and boolean IDs refuse. Explicit enabled/disabled WAIT and bogus-ID regressions were added. Real A/B/B0 candidate generation, injected illegal proposals, ranked/scripted/proposal/fallback/policy decisions, both seats/four Cannon patterns/Tesla and no-FAILURES assertions remain. A selected timed action must become public WAIT with the exact duration.
2. Two legitimate Fireball-root failures: integration autouse bootstrap now initializes actual Runtime before any fixture builder/spell construction, installs the common scope, and reuses its real builder. It loads/verifies all six approved exports and support before roots or decisions. Lightweight optional mode remains explicitly non-integration evidence. No registry clearing, runtime modification, changed estimator, all11 substitution, support exclusion or weakened root failure was introduced.
3. Shared frozen fixture/gate cache: `FrozenLevelConfigs` reads existing support/registered levels, pins raw and compact canonical hashes plus actual runtime reference, requires exactly121 L11 cards/empty unsupported/exact check11, and requires complete disjoint card/error coverage at each level. Registered memory-only loads, frozen support and a rejecting build method prevent lazy reads/exports/receipt generation. Module integration additionally blocks the original LevelConfigs support/build methods. Before/after every placement test and every native gate, the fence checks runtime reference, directory inventory, registered memory keys, raw bytes and parsed canonical identities. Synthetic tests exercise successful no-write/memory-only use, seven initial mismatch classes and four after-use mutation classes; writes occur only in isolated tmp_path fixtures before guards, never the real cache.
4. Primary writer hazard: `run.preload_configs` never calls the mutating support loader. It reads the existing support bytes exactly once, checks schema/comparison/reference/duplicates, freezes the support method/set, loads registered export bytes once, requires complete L11 and exact check11 good AND bad mappings, then binds raw+loaded digests from those same bytes. Later registered reads/support access are memory-only and build/unknown reads refuse. Complete lower-level card/error coverage preserves known errors for the root's existing fail-closed behavior. This path remains generic: small synthetic configs may legitimately have a supported subset and matching unsupported mapping. Actual integration/gates separately require the historical121-card baseline. Only mismatch diagnostics lazily import the new helper's pure JSON difference formatter; primary execution imports no diagnostics module or simulator-policy machinery through it.
5. Meaningful primary regressions: valid generic unsupported support remains accepted; writer methods and original support/build methods are forbidden during preload; exact support/L11 read counts and raw+loaded provenance are checked; subsequent disk reads/builds refuse while real `check11`/`entry` work from memory. Missing/malformed/stale-reference/stale-comparison/missing-card/duplicate-card/wrong-unsupported/numeric-L11/side-table discrepancies preserve all cache bytes and refuse installing the cache. Existing incomplete/missing-export/noB/fair-level/known-error tests remain. A support whitespace-only mutation preserves semantic identity but changes raw identity and must invalidate successful-row resume. Existing loaded-export, runtime Python/raw-token/weights/prior/scope/environment/preparation/all-done/error/exit provenance tests remain.

The new bootstrap records exact actual Fireball L11 damage688/crown159/multiplier0.22999999999999998/level11/radius2.5/travel_speed11.999999999999998/knockback1.0; Poison L11 damage92/crown21/multiplier0.21999999999999997/level11; and existing L4 Fireball357/83 plus357 carrier damage for both owners. Exact field/type diagnostics use hitpoint units for crown/damage, no tolerance. Runtime reference must be193b6615… before roots. Gates emit the same anchors. These are assertions awaiting execution, not new measurements.

Astra's early-builder source chain explains stale Fireball172 versus159 crown HP (+13 per hit), but the failed full R.config was not captured. Do not claim an empirically proven one-field-only full-config difference or reconstruct the bad reference from a guessed single edit. Poison21 is numerically unchanged. Native/root/config/scaling/placement mechanics are unchanged; native rollout placement remains the documented model mismatch.

## Exact source and evidence anchors

```text
29d6509ec18452ffe3d535b1f91afed9d84cea61be38b42a79f5a942faa8850f  bot/levels/run.py
7c90ca56835740ac64ed7a6b9fb512eb9d7938ba2ba9b0fc268e4371d33986b7  bot/levels/test_harness.py
3fe16baa155120959ce541a78e4b24fba6336855296eb14981db305758fc7bc9  bot/levels/test_placement.py
d59475d3b4cf44983541a497d9a96106d4fe3023ea540a2fbde9fc38bd8cf41f  bot/levels/gates.py
674bf0fbb966c6e0a8ded4805ae615a3187ae25e13a5eab3fd32463a033fe4f4  bot/levels/fixture_support.py
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  bot/levels/placement.py (unchanged)
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  bot/levels/placement_probe.py (unchanged)
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py (unchanged)
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py (unchanged)
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py (owner recorder, unchanged)
276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf  J/dev/placement-micro-r21.json
219700e61efcf489939f5377ed02940772f99c2031ff0f050a087705e1e25455  J/dev/pytest-placement-r21.txt
4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41  J/dev/supported-after-pytest-r21-failed.json
e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc  J/dev/supported-restoration-candidate-r24.json
```

R21 probe145 classifications/1024 commands is prior matching placement/probe-byte evidence, reusable because both files and dependencies are unchanged; no redundant binary probe is proposed. R21 integration remains terminal1,179 passed/12 failed. Old R6/R12/R14/R17 failures and their raw receipts remain failed and immutable. s27 DONE23/23 is separate completed work, untouched. No primary BASE/bank is created.

All six current01 exports were independently read-only hash-checked against prior s27 receipts. No net export byte change was observed; that is not a write-trace claim. The helper pins each raw/canonical pair, from those prior clean receipts. Restoration repairs ONLY supported.json to the exact prepared original bytes, never reconstructs exports or recomputes support.

## Proposed owner sequence after NEW independent review

Review both source and restoration plan. Parent alone serializes01 sync/cache freeze/execution after approval, verifies matching deployed hashes (including the new helper and unchanged recorder), the existing probe/data pins and original bank SHA below. No03 retry,05 compute, GPU, hosts09–18, frozen/runtime/live writes, global monkeypatch, concurrent cache/source writers or duplicate jobs. Keep full-pool priority/resource admission, cpu_job.sh, nice10, bytecode off and one math thread. Effective evaluation root must resolve to normal owned runtime; no alternate LEVELS_RUNTIME.

Use fresh unused output names, shell noclobber and explicit inspection between stages; do not paste into an unattended multi-stage loop. If any required step fails/defers or its bytes change, stop dependent stages and preserve receipts. Do not resume failed all11 outputs. Commands below are text proposals ONLY, not executed here.

On01, after reviewed source-only sync and deployed manifest verification:

```bash
set -euo pipefail
set -o noclobber
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
test "$CLASHER_BOT_RUNTIME" = /mpac/sdicks02/jobs/clasher/bot-levels/runtime/live16402b-r2
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json
LEVELS_CACHE_DIR=/mpac/sdicks02/jobs/clasher/bot-levels/level-configs/50d22f86b3590abc
LEVELS_RECEIPTS=/mpac/sdicks02/jobs/clasher/bot-levels/dev
test "$(sha256sum "$CLASHER_LEVELS_PLACEMENT_PROOF" | cut -d ' ' -f1)" = 276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf
test "$(sha256sum reports/bot/levels/receipts/all11-dev-cases.json | cut -d ' ' -f1)" = b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a
```

Exact restoration, separately approved and performed by parent only: before modifying C, compare both preserved failed bytes and the restoration candidate with their hashes. Current supported.json must still be the failed snapshot; otherwise STOP for inspection. Capture before hashes. Copy the candidate through a unique temporary sibling and rename atomically only after verifying the temporary copy. No exporter/support-builder is invoked.

```bash
test "$(sha256sum "$LEVELS_RECEIPTS/supported-restoration-candidate-r24.json" | cut -d ' ' -f1)" = e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc
test "$(sha256sum "$LEVELS_RECEIPTS/supported-after-pytest-r21-failed.json" | cut -d ' ' -f1)" = 4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41
cmp "$LEVELS_CACHE_DIR/supported.json" "$LEVELS_RECEIPTS/supported-after-pytest-r21-failed.json"
sha256sum "$LEVELS_CACHE_DIR"/{supported,L4,L5,L6,L7,L9,L11}.json > "$LEVELS_RECEIPTS/cache-before-restoration-r24.sha256"
test ! -e "$LEVELS_CACHE_DIR/.supported.restore-r24.tmp"
cp --no-clobber "$LEVELS_RECEIPTS/supported-restoration-candidate-r24.json" "$LEVELS_CACHE_DIR/.supported.restore-r24.tmp"
cmp "$LEVELS_CACHE_DIR/.supported.restore-r24.tmp" "$LEVELS_RECEIPTS/supported-restoration-candidate-r24.json"
mv -T "$LEVELS_CACHE_DIR/.supported.restore-r24.tmp" "$LEVELS_CACHE_DIR/supported.json"
test "$(sha256sum "$LEVELS_CACHE_DIR/supported.json" | cut -d ' ' -f1)" = e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc
sha256sum "$LEVELS_CACHE_DIR"/{supported,L4,L5,L6,L7,L9,L11}.json > "$LEVELS_RECEIPTS/cache-restored-r24.sha256"
```

The scientific prerequisite is exact matching original support plus all six unchanged exports; review before proceeding. The failed snapshot/candidate never move or change. A temporary-copy discrepancy stops before rename and must be preserved for investigation. Source-only rollback selects the saved pre-R24 source bytes under `/tmp/levels-gates-r24.XX7704` and removes the newly added helper only with owned job stopped, retaining the patch/receipts; these bytes were already known to fail and do not authorize restarting. Cache rollback, if ever necessary, is parent-owned exact-byte restoration from the preserved failed snapshot with an explicit reason, not automatic repair or evidence deletion.

Stage1 — fresh process, full five-file integration suite, CPU1, outer15m:

```bash
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > "$LEVELS_RECEIPTS/pytest-placement-r24.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r24.sha256" > "$LEVELS_RECEIPTS/cache-after-pytest-r24.txt"
```

Require terminal0, no integration skips, actual Runtime once BEFORE builders, explicit normalized spell anchors/reference193b…/121 exact check11, exact six-level raw+canonical manifests and unchanged cache hashes; candidate regressions and BOTH actual B hidden-state roots/decisions must execute with positive root calls and zero FAILURES. A/B0/opponent/fallback/ranked/proposal/mask/recorder/hidden-state assertions remain mandatory. No predicted total count or source-based PASS.

Stage2 — only after Stage1 inspection succeeds at these exact bytes, native gates, CPU2, outer15m:

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > "$LEVELS_RECEIPTS/gates-placement-r24.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r24.sha256" > "$LEVELS_RECEIPTS/cache-after-gates-r24.txt"
```

Require all substantive prior254 obligations (explain a legitimate count change): complete121 exports,13 tower checks,32 public bodies,30 each cut/snapshot/raw-fc, one-child A→B→A keys distinct then reused/shipped[1,2,2], four actual fair B decisions with positive roots. Read both complete raw snapshot difference lists: entity/order/owner/class/position/HP/maxHP/damage/qualified payload/spell keys stay strict. Only the prior source-proven absent empty String defaults may normalize. No stats-only or tolerance waiver.

Stage3 — only after1–2 pass, original four-case clean all11 A/B, run.sh2 (parent+two serial game children), outer15m:

```bash
test ! -e "$LEVELS_RECEIPTS/all11-placement-r24"
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out "$LEVELS_RECEIPTS/all11-placement-r24" --arms A,B --all11-gate --start 0 --count 4 > "$LEVELS_RECEIPTS/all11-placement-r24.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r24.sha256" > "$LEVELS_RECEIPTS/cache-after-all11-r24.txt"
```

Require eight unique complete terminal rows/four full command hash pairs, both seats/R3a/v1, positive B roots in all four, exact parent/child source/runtime/cache/proof/data/raw-token/environment/scope identities, command_events and zero errors/rejections/native/child/placement failures. Current parent all-done and before-fork provenance checks remain. Matching A/B commands with rejected commands is still FAIL.

Stage4 — only after clean runner acceptance, CPU1 outer5m:

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report "$LEVELS_RECEIPTS/all11-placement-r24" > "$LEVELS_RECEIPTS/all11-placement-r24-report.txt" 2>&1
```

Expected workload process maxima are1/2/3/1 across these sequential stages (native gate has one raw-fc child; no other gate creates a pool). Use existing admission and include parent/monitor processes within the overall16 cap. All actual execution, interpretation, immutable review/result recording and primary authorization remain with parent. No new acceptance, primary readiness, LIVE equivalence or promotion is claimed.
