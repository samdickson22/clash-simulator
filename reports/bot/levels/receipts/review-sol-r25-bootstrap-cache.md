# R25 fresh independent Sol-high source review

2026-10-16. W = `/mpac/sdicks02/repos/clasher-bot-levels` on05; J = `/mpac/sdicks02/jobs/clasher/bot-levels`; R = `J/runtime/live16402b-r2` on01; C = `J/level-configs/50d22f86b3590abc` on01. I did not implement the reviewed bytes. Only this report was written.

**Decision: REQUEST CHANGES for one bounded P2 regression defect, R25-P2-1 below. The required standalone primary no-write regressions depend on another test module having already imported the new helper. The five-file command masks that dependency during collection. Keep sync/restoration/execution on hold until the owner corrects this and a fresh matching-byte source review closes it.** The timed-WAIT semantics, Runtime-first fixture repair, real B fairness paths, existing-only primary loader and exact restoration approach otherwise have sound source responses to the R24 failures. This is not a physics defect or a request to change the experiment. No runtime/test/native PASS or primary readiness is claimed.

Read the complete R25 brief, complete R24 repair brief/authorized Astra response, full R24 implementation receipt and all 780 patch lines, full bounded Astra audit, full R23 review, R21 repair brief/implementation/patch, current DESIGN/PROGRESS/HANDOFF/RESULTS, preserved full failed pytest log and bad/original-candidate support evidence. Inspected all changed source bytes and relevant configs/root/player/runtime/search/placement/probe/identity/launcher dependencies, the R12 support identity and s27 cache receipt. Regenerated the focused diff in a read-only process substitution and compared it byte-for-byte with the handoff patch: identical. All 26 entries of the R24 source manifest independently hash-match current W. No AGENTS.md was found in the applicable ancestor directories or reviewed bot/levels subtree.

No Python/project imports, parsing/compilation of project code, tests, Runtime/model construction, native/simulator/probe execution, CPU jobs, sync, restoration, frozen/live/input edits, commits, descendants or input tools were used. Existing JSON was read as text. Read-only shell/hash/source inspection and SSH01 only. A remote `rg` was unavailable; the follow-up used grep. Its only matching process was the source-audit shell itself, not a level workload; the no-writer premise also comes from the parent's frozen handoff. No blanket Opus hold or additional03 probe is requested.

## Finding requiring correction

### R25-P2-1 — cold primary error-path tests import a helper against a function in place of its base class

Locations: `test_harness.py:441–458,582–617`; `run.py:377–378`; `fixture_support.py:12,118`.

The `level_cache` fixture replaces `configs.LevelConfigs` with `lambda _: lc` at line457. In a fresh process collecting only `test_harness.py` (or selecting one of its new mismatch node IDs), nothing imports `fixture_support` before that fixture runs. Several new faults reach the exact-check11 discrepancy branch, which lazily executes `from .fixture_support import differences`. First importing that module also executes `from .configs import ... LevelConfigs ...` and `class FrozenLevelConfigs(LevelConfigs)`. Its base is now the fixture's lambda, so class creation raises TypeError before the intended actionable ValueError. For example, `missing_card`, `wrong_unsupported`, `numeric_L11_difference` and `side_table_difference` all take this path. This is a deterministic source inference, not an executed failure or a quoted observed traceback.

The proposed five-file suite collects `test_placement.py`, whose line17 imports `fixture_support` before any fixtures run. That leaves the real class cached in the module and hides this defect. Consequently an apparent full-suite success would not establish that these primary error-path regressions are independent of placement-module collection. Ordinary primary execution with the real constructor is not implicated; the no-write implementation still refuses mismatches. The defect matters to the requested meaningful, independently runnable preload/failure regressions and the new helper's import order.

Minimal correction: ensure the helper is imported against the real class before `level_cache` monkeypatches that symbol, or patch constructor acquisition through a stable class/factory without replacing the helper's future base. A pure formatter split is another option but is unnecessary scope expansion. Do not weaken `pytest.raises`, swallow TypeError, or require unrelated placement collection to make the tests pass. Preserve the no-write guards, exact field diagnostics and all mismatch cases. Owner supplies revised bytes/receipt and fresh review; reviewer does not edit them. After that review, validate the selected primary error-path test in a clean process before the full integration suite, using the bounded command below.

## Accepted source responses and practical limits

1. **Timed WAIT and actual decisions.** `candidate_allowed` recognizes only integral non-bool actions, uses the actual TIMED_WAITS dictionary 2400/2401/2402 =10/20/40 simulation ticks, and authorizes them only through public WAIT2304. It never indexes a timed action into the2306-entry tile mask. Ordinary deployments remain in range and must have their own enabled bit; unknown oversized/negative/floating/bool IDs refuse. Ability2305 retains its own mask bit in the helper; actual player decisions still exclude it under the existing disabled-ability contract. Existing mask-tail equality assertions preserve WAIT/ability eligibility. Enabled/disabled WAIT and unknown-ID regressions are substantive. Selected timed actions are checked against `stats.action` and the real `_done` conversion to public WAIT plus exact wait_ticks. Candidate/ranked/scripted/proposal checks now share the semantic predicate; the illegal deployment proposals remain explicitly rejected. No production action-generation or placement-physics change is made.

2. **Actual Runtime first.** Integration uses the module autouse bootstrap, calls proof before expensive initialization, constructs actual Runtime exactly once, then installs scope, verifies the existing cache/spell anchors and installs placement. Every builder fixture depends on bootstrap and consumes `rt.R.builder`. Top-level helper imports only standard-library/config definitions; it does not build a builder or touch the cache. The other four requested test modules use synthetic configs/fake Runtime, and their inspected imports/tests do not materialize a real spell registry before this bootstrap. Lightweight paths-only mode is clearly optional and supplies no integration evidence. No registry reset, frozen Runtime edit, normalization tolerance or hidden override was introduced. This ordering claim is bounded to the proposed clean invocation; embedding into an already contaminated interpreter is not repaired.

3. **Cause and exact numbers.** Independently read the actual01 builder descriptor lookup, lazy spell registry, dynamic crown override and battle L11 reuse paths. They agree with Astra: constructing the builder can cache Fireball172 before Runtime pops its override, whereas the approved export/reference requires688 ordinary/159 crown HP atL11. The+13 is hitpoints per crown impact. Native integer ceiling gives `(688*23+99)//100=159`; atL4 `(357*23+99)//100=83`. Poison92/21 has no numerical override discrepancy. The failed full R.config was not captured: no empirical one-field-only claim or reconstruction of f008… is justified. New exact field/type/units diagnostics distinguish tuple/list JSON representation from real int/float or numeric changes. Full current Runtime/config equality remains an execution obligation.

4. **Frozen fixture/gates.** The helper pins historical reference193b…, the121-card complete support mapping with empty unsupported, exact L11 check11, and raw plus compact canonical identities for support/registered exports. It verifies complete disjoint card/error coverage. Approved lower exports keep118 cards plus the exact three Clone/Earthquake/Tornado errors through byte pins; no new export or L11 fallback appears. Registered loads/support use memory; unknown levels/builds refuse. `verify` checks runtime reference, directory inventory, registered memory keys, file bytes and loaded canonical objects before/after placement tests and native gates, including test failure teardown. Integration also patches the original LevelConfigs supported/build methods to refuse accidental secondary instances. Gates use the subclass and inject that same cache into actual B roots. Their existing254 substantive checks are retained; setup/final verification failures make the process nonzero rather than awarding a pass. Synthetic successful/no-write/future-read and mismatch/post-use-mutation cases are meaningful and isolated from C.

5. **Primary loader.** `preload_configs` now reads existing supported bytes once before any call that could previously write them; validates schema/version/reference/unique strings; installs a frozen support accessor; loads only registered exports once; verifies exact L11 good AND bad mappings and complete level coverage; records both hashes from those exact bytes. The separate implicit support writer and export builder are both bypassed/blocked on the inherited instance. Cache installation happens only after validation. Runtime initialization and preload precede resume/all-done/forks/root construction. The generic synthetic unsupported mapping remains legitimate; actual integration/gates independently require the historical121/empty baseline. No diagnostics package is imported into primary. The lazy mismatch formatter import causes the test isolation finding above but does not start policy/simulator work in normal primary execution.

6. **Regression/provenance continuity.** The new valid preload test forbids original support/build and Path writers, counts one support and one L11 raw read, checks raw+loaded identity, forbids later disk reads, and exercises real check11/entry/unknown-level refusal. Bad-support/changed-L11 cases assert byte equality and no installed cache; retain them after fixing R25-P2-1. Formatting-only support mutation keeps semantic identity while changing raw identity and refusing a successful row's resume. Existing loaded-export and token/Python/model/prior/scope/environment/preparation/all-done/resume/error/cleanup/report regressions remain present and meaningful. `source_hashes` includes immediate bot/levels Python files, so the new helper participates in primary source identity automatically. The older token/source closure is retained, not replaced by cache hashes.

7. **Fairness and unchanged science.** Both seats still execute two genuinely identical public views with different hidden opponent order/levels/elixir/pending command/Ghost; compare whole public info, masks, fixed-seed actions/waits and actual root snapshots. B is constructed without parity_all11 in those tests; it still estimates opposite-seat Fireball at rareL4. Both manual B roots and additional positive root calls during act remain mandatory; cache identity is asserted. Candidate tests still exercise A/B0/B and R3a/v1 over four Cannon tower patterns per seat plus Tesla. No stats-only replacement, L11 opponent substitution, dropped Fireball or waived native FAILURES. Recorder on/off still compares refused then accepted commands and public effects. Root fail-closed, exact scaling, native physics, original supported population and conditional serial/crown-controller interpretation remain unchanged. R23 v3 proof reuse is justified only while placement/probe and their pinned dependencies remain unchanged; no new physics PASS follows from this review. Completed s27 remains separate, with no rerun/edit requested.

## Exact restoration assessment

The prepared candidate independently hashes to the exact original R12 support raw digest e034…; the R12 launch also records the same canonical b97c… and reference193b…. The s27 receipt independently records the same support/raw+canonical six-export identities. Direct read-only01 hashing still finds bad current support4566… and all six original export raw hashes below. This demonstrates no net export-byte change, not absence of transient writes. Candidate has121 cards/empty unsupported/native-json-v1; failed snapshot omits Fireball and records referencef008…. Preserve both.

**The restoration proposal is acceptable as a narrowly bounded exact-byte operation after source approval and exclusive parent preflight. It is not authorized for execution by this REQUEST CHANGES verdict.** Do not recompute support, export data, create a new baseline, alter errors or normalize the candidate. Parent copies candidate to a distinct01 receipt path, verifies its SHA and the still-current bad SHA, preserves current bad bytes to a fresh guarded snapshot, captures all seven before hashes, publishes only the exact candidate, verifies all seven afterward and leaves evidence intact. A distinct temporary sibling followed by atomic rename, as in the implementation receipt, is preferable to exposing a partially copied supported.json. All stage commands remain individually inspected; no automatic retry/advance.

A fixed-path parent proposal, to use only AFTER the finding has been corrected, newly reviewed and deployed source hashes verified (commands are TEXT ONLY):

```bash
# on05; parent only; first verify destination does not already exist on01
scp /mpac/sdicks02/jobs/clasher/bot-levels/dev/supported-restoration-candidate-r24.json 127x01:/mpac/sdicks02/jobs/clasher/bot-levels/dev/supported-restoration-candidate-r25.json
```

On01, after parent independently verifies no owned jobs/exporters/writers and reviews resource admission:

```bash
set -euo pipefail
set -o noclobber
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
LEVELS_RECEIPTS=/mpac/sdicks02/jobs/clasher/bot-levels/dev
LEVELS_CACHE_DIR=/mpac/sdicks02/jobs/clasher/bot-levels/level-configs/50d22f86b3590abc
test "$CLASHER_BOT_RUNTIME" = /mpac/sdicks02/jobs/clasher/bot-levels/runtime/live16402b-r2
test -z "${CLASHER_EVAL_RUNTIME_ROOT:-}" || test "$(readlink -f "$CLASHER_EVAL_RUNTIME_ROOT")" = "$CLASHER_BOT_RUNTIME"
test -z "${LEVELS_RUNTIME:-}" || test "$(readlink -f "$LEVELS_RUNTIME")" = "$CLASHER_BOT_RUNTIME"
export CLASHER_LEVELS_PLACEMENT_PROOF="$LEVELS_RECEIPTS/placement-micro-r21.json"
test "$(sha256sum "$CLASHER_LEVELS_PLACEMENT_PROOF" | cut -d ' ' -f1)" = 276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf
test "$(sha256sum reports/bot/levels/receipts/all11-dev-cases.json | cut -d ' ' -f1)" = b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a
test "$(sha256sum "$LEVELS_CACHE_DIR/supported.json" | cut -d ' ' -f1)" = 4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41
test "$(sha256sum "$LEVELS_RECEIPTS/supported-restoration-candidate-r25.json" | cut -d ' ' -f1)" = e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc
cmp "$LEVELS_CACHE_DIR/supported.json" "$LEVELS_RECEIPTS/supported-after-pytest-r21-failed.json"
test ! -e "$LEVELS_RECEIPTS/supported-before-restore-r25.json"
cp --no-clobber "$LEVELS_CACHE_DIR/supported.json" "$LEVELS_RECEIPTS/supported-before-restore-r25.json"
cmp "$LEVELS_RECEIPTS/supported-before-restore-r25.json" "$LEVELS_RECEIPTS/supported-after-pytest-r21-failed.json"
sha256sum "$LEVELS_CACHE_DIR"/{supported,L4,L5,L6,L7,L9,L11}.json > "$LEVELS_RECEIPTS/cache-before-restoration-r25.sha256"
test ! -e "$LEVELS_CACHE_DIR/.supported.restore-r25.tmp"
cp --no-clobber "$LEVELS_RECEIPTS/supported-restoration-candidate-r25.json" "$LEVELS_CACHE_DIR/.supported.restore-r25.tmp"
cmp "$LEVELS_CACHE_DIR/.supported.restore-r25.tmp" "$LEVELS_RECEIPTS/supported-restoration-candidate-r25.json"
mv -T "$LEVELS_CACHE_DIR/.supported.restore-r25.tmp" "$LEVELS_CACHE_DIR/supported.json"
```

Before the rename, compare the six before-export hashes with the explicit manifest below; afterward independently verify support e034… and those same six hashes, then capture `cache-restored-r25.sha256`. A bad current hash, occupied fresh destination, source mismatch, temporary-copy discrepancy or changed export stops the sequence and preserves evidence. Parent may use its exact approved fixed-path cp alternative only with the same exclusivity and before/after verification. No new launcher/script is necessary.

## Bounded future execution sequence — not approved until R25-P2-1 closes

Use fresh output names below, noclobber and a fresh all11 directory; if occupied choose/record a new suffix rather than overwrite. No source/cache/input/runtime changes during any stage; parent inspects exit status, full receipt and cache before/after before proceeding. Use existing env.sh (hashseed0, math1, GPU hidden, bytecode off) and cpu_job.sh/nice10. Only01; no heavy05,09–18, frozen/live writes, full-pool interference or03 retry. Include parents in the overall16 process cap. A timeout/admission deferral/incomplete receipt is never PASS.

0. After the small correction and fresh review, a clean isolated protocol regression checks the identified dependency without collecting placement (CPU1, outer5m, no real Runtime). Exact node ID is quoted to keep shell brackets literal:

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -p no:cacheprovider 'bot/levels/test_harness.py::test_preload_bad_support_or_L11_never_repairs_cache' > "$LEVELS_RECEIPTS/pytest-preload-isolated-r25.txt" 2>&1
```

1. Clean-process mandatory five-file integration (CPU1/one actual Runtime, outer15m):

```bash
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > "$LEVELS_RECEIPTS/pytest-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-pytest-r25.txt"
```

Require terminal0/no mandatory skips; actual normalized688/159 and92/21/reference193b… before roots;121 exact check11; six raw/canonical pins/L4Fireball357/83; all real actors, legality/fallback/proposal/recorder and BOTH hidden B root/act paths with positive roots and zero FAILURES. All no-write/error/resume regressions must execute, including the corrected isolated cases. No predicted total test count.

2. Only after inspected integration PASS, native gates (CPU2 = parent plus one raw-fc child, outer15m):

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > "$LEVELS_RECEIPTS/gates-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-gates-r25.txt"
```

Require terminal0/all prior254 substantive obligations, plus new cache/anchor fences (explain count changes):121exports,13towers,32public bodies,30each cut/snapshot/raw-fc, A→B→A distinct/reused content keys and shipped[1,2,2], four actual fair B decisions/positive roots. Inspect both full raw snapshot diffs. Only prior source-proven absent empty String defaults normalize; no numeric/type/entity/order/position/owner/qualified key waiver.

3. Only after integration AND native PASS, original four-case bank at SHA b414… (run.sh2 reserves max3 Python processes = parent+two serial game children, outer15m):

```bash
test ! -e "$LEVELS_RECEIPTS/all11-placement-r25"
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out "$LEVELS_RECEIPTS/all11-placement-r25" --arms A,B --all11-gate --start 0 --count 4 > "$LEVELS_RECEIPTS/all11-placement-r25.txt" 2>&1
sha256sum -c "$LEVELS_RECEIPTS/cache-restored-r25.sha256" > "$LEVELS_RECEIPTS/cache-after-all11-r25.txt"
```

Require eight unique complete clean terminal rows, four full-command hash pairs, both seats/controllers, all four positive B roots, parent+children exit0 and exact source/runtime/proof/data/raw-token/cache/env/scope/prior identities. Zero errors/rejections/native/child/placement failures and complete both-seat command_events. Hash equality with rejections remains FAIL. Never resume R12/another failed output.

4. Only after accepted runner completion, report (CPU1, outer5m):

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report "$LEVELS_RECEIPTS/all11-placement-r25" > "$LEVELS_RECEIPTS/all11-placement-r25-report.txt" 2>&1
```

Require registered completeness/provenance and quality PASS. No primary BASE/bank/outcomes until integration/native/clean all11/report all PASS at final reviewed bytes. The100-case×A/B/B0 authority, pre-outcome registration, accepted fixed population, serial crown/controller semantics and rollback remain with parent. No new strategy requirement, extra s27 run, confirmation run, LIVE promotion or physics claim is introduced.

Rollback: retain failed evidence, prepared original and bad support bytes, current patch and saved pre-R24 source at `/tmp/levels-gates-r24.XX7704` (01 reviewed R21 backup remains parent-owned). Selecting saved known-failing sources does not authorize restarting. Select standard A outside the experimental factory/remove experimental hooks for experiment rollback; preserve original prior/frozen pins/models. Any later exact bad-cache restoration is a deliberate parent-owned evidence operation, never automatic repair during a running job. No arbitrary kill or deletion.

## Independently verified exact source manifest

Relative to W. `sha256sum -c J/gates-r24-source.sha256` matched every entry. This is the reviewed R24 snapshot, NOT approval of unseen correction bytes. First five changed files are run.py, test_harness.py, test_placement.py, gates.py and new fixture_support.py; the complete closure follows.

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  bot/levels/__init__.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
674bf0fbb966c6e0a8ded4805ae615a3187ae25e13a5eab3fd32463a033fe4f4  bot/levels/fixture_support.py
d59475d3b4cf44983541a497d9a96106d4fe3023ea540a2fbde9fc38bd8cf41f  bot/levels/gates.py
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  bot/levels/placement.py
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  bot/levels/placement_probe.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
29d6509ec18452ffe3d535b1f91afed9d84cea61be38b42a79f5a942faa8850f  bot/levels/run.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
7c90ca56835740ac64ed7a6b9fb512eb9d7938ba2ba9b0fc268e4371d33986b7  bot/levels/test_harness.py
3fe16baa155120959ce541a78e4b24fba6336855296eb14981db305758fc7bc9  bot/levels/test_placement.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
```

## Exact evidence, instructions and documentation hashes

J-relative unless W-relative is stated; raw SHA256 throughout this block. Documentation contains historical stale headings; latest appendices and frozen handoff determine current state.

```text
ee4f9443dc873cc798e6a0734166fa2181143f189cb15dd31dc279a0e86a4112  gates-r25-review-brief.md
c857fa061b3de69ffacdd1712e12bde25858263152c64c78f749f53703636dfc  gates-r24-repair-brief.md
1ebcc9a5f000737eb1e789d4e73872c78c1f92b29663dee855d894af7e16f164  gates-r24-astra-response.md
99cce4d024a66c5033ebdc81ffdc3ae985cf2f1cc85afd84b3a50ed8a8115ed4  gates-r24-implementation.md
7298068407d2ee9ec3abbe8f62abcd63569946f84ce64b152bb531cbc5c3daa6  gates-r24-implementation.patch
eec161f8aa8eec743233658ba9f7e67c846c3f1a9f1384d06d0b0567bc452b63  gates-r24-source.sha256
df8ad6a76e257c02fb310648beeaa1720aa371cdc6ea3337109a1f096e263505  fireball-bootstrap-astra-r24.md
7b5cdbfcb68f8aabe5274009d40a82286818f825e5fd5504efd06d42694284b0  placement-review-sol-r23.md
2e7c71426edf4e3ee2a66273e0f1a583f804bd77a78f7a1b405b8c88f58bee53  placement-r21-implementation.md
d7118c559ba84c5800eb1a72a78ef021137c35d88523a78262ce04a1a5de2aa0  placement-r21-implementation.patch
219700e61efcf489939f5377ed02940772f99c2031ff0f050a087705e1e25455  dev/pytest-placement-r21.txt
276426ec20f76010e72fb1fa0ca7cbd44abf9bfc93efe0b18b8fa5275f1cfbdf  dev/placement-micro-r21.json
4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41  dev/supported-after-pytest-r21-failed.json
e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc  dev/supported-restoration-candidate-r24.json
81291fbbdc251d245d694791a2bfdc4f215978bc378e84be2b42bf07b2f5a5bb  s27-diagnostic-dev-r20/receipt.json
b2b3036e7c757d78664fd98c33c3b6397fe2e7b6d46ecd5708967a0b9b12b6d6  dev/all11-r12-launch.json
23c77ccba1f35f16164f4121efee03055cc130575bdb3d1bc185a46d1b87a130  W/reports/bot/levels/DESIGN.md
ed627c5259bc5600d9a3b61d4b924bad85499ec5d551ddad6bd685da1bfe55ea  W/reports/bot/levels/PROGRESS.md
72fa6105ceeced5bb2389e5eb046ddfcee3aecc0328133ff4962dbe2f6f72fd7  W/reports/bot/levels/HANDOFF.md
15b6abeb7fa1ce23b8fb6f1615fc11b6fe108f5b6d598967c2bfa8b206a41502  W/reports/bot/levels/RESULTS.md
```

## Exact cache manifest and focused01 source audit

Each row is filename, approved raw SHA256, approved compact canonical SHA256. Canonical pairs were independently read from the prior s27 receipt and agree with PILOT_CACHE/R12 anchors; no JSON reserialization was executed by this reviewer. Direct01 raw hashing independently matches all six exports. Current supported.json instead remains the preserved bad raw4566… above, so it intentionally does NOT match this good manifest yet.

```text
supported.json e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc b97c2a61edd7fedc37182320a143673012f34e5b35e34effd69eb99d1aded8e7
L11.json 1a36f377d55be3ea34e20225aa17eb92bead8e148b216b5b1346f0e7d04c8a94 0700072fb0c81682de7e419363f3cee19cb2518ce49ece2332149ffc093828f9
L4.json bd77caea134e469c89dc1d25d60f30474a404feef6b529d26b0e307a8f3a7d95 314a6eaf17947386d889f04edc7ea7a7080aad703e4e6dc20a52ac8f26c7ee1c
L5.json e88a6e04183f449754775b7f9d999c2ca3982601cb6f35dbbc1aec28d1555dfe 38dc346eeaccbb14a625eb65cf055bb5fdaae7e069dc69ded2c90f17519caafd
L6.json ad4b725b180cb2aa0abf50c13cf378ba2a954233eac43080b248f2f40146dcbb 6dc6240cede22c916cd519a372b73f49265caf633f854ffdb382d48cc19d1398
L7.json 8fc9633bbd50906d7f95575b7c93ba6a39e540aec2997f67c2d50b8a1477b6f3 af59897ecc32c11b40d5b67746f4a58bd85516f47e756498029b1663fddd8c84
L9.json 88a2472e54b090853bd18016cdafda642aafa1fd00f03ca6e7fa20f3edd638b2 825ce4dc7b1fb58bce9b345df5dbaf325b5a9207b4738db310b6050f17a5eb0e
```

Focused independently hashed01 source dependencies (R-relative), not a claim to have executed the full runtime manifest:

```text
6214658ec5b0ee6b51a0f62ce10a2531f2488753845911b1ff40165e7ddf0944  src/clasher/spells.py
ca90d41002d0beb41f634aa26578d5158997db2c7b5e1768107edb7a9546ac16  src/clasher/dynamic_spells.py
3b05a9439f3ec92cc62982f380e1f14d9fc2d59cd70b49c7a24070f9ed3458cc  src/clasher/balance.py
88abc76504cbe8303d136b62f089b75f4582dcdf842227de0ec3fc6f92689b94  src/clasher/battle.py
810910fd9f7edeab07506340be16116fd6231b50de4849f5e60cd73ab6608ac5  src/clasher/logic_math.py
b0de1fb681924fc7d99525791fa24f3172cd4e391e79a4e8ddb4ac9c99e41b08  src/clasher/rl/contract_v5.py
5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0  src/clasher/rl/contract_v5_tokens.json
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  J/dev/env.sh
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh
```

Historical outcomes retain their original limits: R21 integration FAILED179/12; R23 v3 probe prior PASS145/1024 only; R11 native prior PASS254; R12 all11 FAILED despite4hashpairs; s27 completed23/23 is separate. Only the correction/review and subsequent matching-byte execution can close this phase. Automatic final delivery only; no duplicate completion message.
