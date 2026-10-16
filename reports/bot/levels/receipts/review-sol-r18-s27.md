# Fresh independent Sol R18 source review — s27-m02 offline shadow diagnostic

Review date: 2026-10-16, approximately 11:04–11:11 UTC. Reviewer: fresh independent Sol (gpt-6.1-sol, high). Actual reviewed worktree: `/mpac/sdicks02/repos/clasher-bot-levels` on127x05, HEAD `f85c66d375a949e007d9aeff6983c3f028c64b50`; the six diagnostic files are uncommitted. This receipt is the reviewer's only write.

**Verdict: REQUEST CHANGES. Three P1 blockers; execution is not approved for these bytes.** The recorded-world design is coherent, but the advertised01 invocation cannot presently launch, serving-source provenance is incomplete under an accepted environment override, and fatal failures can disappear from the opportunity denominator. Repair within the diagnostic package and obtain another fresh independent review before sync/tests/replay. No waiver or failed-output overwrite.

No project imports, Python execution, syntax compilation, tests, model/Runtime construction, sync, jobs, commits, runtime/live writes, emulator/input/account/GPU actions or descendants occurred. Read-only shell/source/hash operations and read-only SSH01 inspection were used. No routine DM was sent; no owner decision was needed to establish the source defects.

## P1 blockers

### R18-1 — Required audit sources do not exist on the sole allowed execution host

`replay.py:23,30–37,95–108` requires both `/mpac/sdicks02/repos/clasher-live/live/loop/drive.py` and `towers.py` on01. Read-only SSH01 returned exactly:

```
ls: cannot access '/mpac/sdicks02/repos/clasher-live/live/loop/drive.py': No such file or directory
ls: cannot access '/mpac/sdicks02/repos/clasher-live/live/loop/towers.py': No such file or directory
```

`guard()` explicitly permits only127x01. Syncing the six reviewed files to01 does not satisfy this extra host dependency. `sources()` therefore raises `ValueError('missing source provenance input')` while constructing `receipt`, outside the protected try/finally. The exclusive output directory has already been created, but launch.json, states.jsonl, report and failure receipt have not. This both prevents the requested diagnostic and leaves an occupied output name without the promised failure artifacts. Current absence of the diagnostics directory on01 is expected before authorized sync; absence of this separate required live checkout is the defect.

Required correction: represent the audited live-writer sources using an explicit pinned, read-only provenance artifact available to the diagnostic on01, without creating/writing a live checkout or importing its driver. Alternatively redesign the audit dependency within the authorized package. Validate required audit bytes before reserving the output directory, or preserve a launch/failure receipt for failures after reservation. Do not silently omit the writer audit, create live paths, or claim the05 source path exists on01. Add a source-only synthetic fixture for missing audit files and the output/failure lifecycle; no Runtime needed.

### R18-2 — Serving-root override escapes the before/after identity fence

`replay.py:40–50` hashes Python under the selected runtime root, and `guard():69–74` constrains CLASHER_ROOT and the native directory. It neither constrains nor snapshots the effective `CLASHER_EVAL_RUNTIME_ROOT`. `Runtime._bootstrap_paths():147` uses `setdefault`, preserving an inherited value. Actual01 `imitation/evaluation/paths.py` selects that value first and `setup()` adds its src/engine-rs/council trees to sys.path. `dev/env.sh` does not unset it. Thus a guard-accepted invocation may execute serving Python outside the root whose bytes are checked before/after. `loaded_dependency_sha256` at replay.py:177–178 is only a final observation; it is never compared with a pre-execution baseline for those files. A source change after import can be labelled with the changed final bytes without rejection. Recording the environment string does not establish executed-source immutability.

Required correction: for this bounded single-runtime diagnostic, reject an effective evaluation root different from the authorized own copy (the simplest scope), or bind its complete serving Python closure before imports and compare it after. Add a fixture covering the override itself and tampering in the actual serving closure, including imitation/evaluation, model/features/masks, and engine sources. Do not rely on the unrelated primary runner's helper or its current R17 changes.

Also bind the exact raw contract token data actually read by `contract_v5.load_pinned_tokens()`: `runtime/src/clasher/rl/contract_v5_tokens.json`. `runtime_content()` currently omits it because it only scans Python plus a short explicit data list. The loaded token-list digest in `static_identity()` is useful but does not reject a raw-data mutation during replay; loaded-module hashes cannot cover JSON. Preserve both raw and loaded identity. No need to hash unrelated perception geometry/hitboxes/load-config files merely because they exist; they are not used by this offline translated-record path.

### R18-3 — Fatal reconstruction/pre-audit failures shrink the reported denominator

`protocol.summary():208–210` derives the denominator only from rows already appended. `RecordedFacade.act():275–285` can raise on command/own-slot contradictions before appending its row; `Shadow.act():185–195` performs public audit work outside its guarded try; replay.py:161–163 may abort before calling the facade at all. `replay.py:183–200` records a generic run_error and builds the summary from the surviving prefix. There is no planned opportunity roster, failed opportunity placeholder, or not-reached count. For example, a contradiction at a recorded searched frame removes that frame from `opportunities`; later required opportunities also disappear. `matched_all_opportunities` may describe the successful prefix as complete even though the final fatal_error forces overall exit1. Exit1 is correct, but the required fixed denominator/evidence contract is not met.

Required correction: derive the requested recorded search roster from the pinned decisions and corresponding public clock frames before replay, reconcile each key to exactly one success/error/not-reached status, and retain the fatal current-frame error in its opportunity row. Report expected, attempted, successful pairs, failed and unvisited counts separately; never describe a prefix denominator as all matched. Add a fixture where a real pre-row driver contradiction occurs between two expected opportunities, asserting that neither the failing key nor the unvisited key vanishes. The existing summary fixture only supplies an already-appended arm error; it does not exercise this failure path.

## Accepted source findings and limits

- All six package hashes match the owner handoff exactly and were checked again at the end of source inspection. README and all implementation/test source were read. DESIGN/RESULTS/HANDOFF, SCOPE, s27-inputs receipt, actual LivePlayer/translator/driver and root/config/scope/runtime/search contracts were consulted. Current primary placement/run edits were not reviewed or approved by this receipt.
- `RecordedFacade` is a Pocket-style implementation of LivePlayer's start/act/close contract; it does not instantiate the original Mac LivePlayer or load rl5-v10. Its disclosure is honest. One real LiveSession/LiveTranslator owns recorded commands, queue, public tracker and events. A/B decisions never submit into the common session. Each gets a separate deepcopy; unchanged-common and equal-A/B view hashes are checked.
- Actual serial FastLearnedPlayer.start reconstructs the core before `Shadow.start` replaces its belief class and installs hooks. The selected BASE has native_threads1, pool0, roots1, no cutoff. The actual root wrapper calls its original root function exactly once, reads that returned root's snapshot, and makes no additional sample/RNG/root call. B changes the actual serial core.native after start; its score closure reads that core. Neither the RoyaleSim arm factory nor placement installer is called. R14/R17 simulator geometry issues are not prerequisites for this independent LIVE diagnostic.
- A uses unchanged L11 root/config/native. B uses ExactLevelRoot, fixed public account levels and tower6/6, qualified seat payload configs and leaf_native. The native crown metadata adjustment affects leaf evaluation AND scripted spell lethality/Lightning ordering. Learned-feature invariance is only an identical-state feature-layer statement, not rollout equality.
- Own profile is Valkyrie5, Archers7, Minions5, Cannon6, Fireball5, Giant6, MiniPekka5, Musketeer4; fixed opponent estimate is common5/rare4/epic6/legendary9/champion11. No opponent true levels/deck/order/outcome feeds the shadows. Reading input session/config for receipts does not turn them into planner inputs.
- Common scope is installed before both players and pollers; accepted ordered original/restricted digests are pinned and checked. The LiveBelief revealed-card completion behavior is retained. Per-poll rt.PRIOR checks and rebuild counts are useful; this remains the declared conditional population, not the literal original live prior. No unsupported playable/root body may silently use L11.
- Writer fractional tick is removed; actual anchored ClockTracker rounds the99.6047 boundary to100. Window uses floor(clock_s)134…176; no134.000 observation is invented. Every non-opportunity/off-cadence/catch-up poll reaches both D1 pollers blocked. No wait duration is inferred from search gaps. Recorded gating is a declared reconstruction, not original command reproduction.
- Action233/170 remains an owner-authorized UNVERIFIED INTERNAL RESERVATION. The observer requires the old Giant813/submitted160 object to be replaced by a new233/submitted170 reservation. It preserves superclass confirmation/reconciliation. Later inferred events/context are marked conditional and are never a sixth acknowledged tap/verified actual play. The replacement fixture exercises equal pending length and later conditional event tagging, although its fabricated base Session does not itself integration-test the real queue/HUD pipeline. A later actual-session synthetic integration fixture would strengthen this evidence; the real replay must abort on any queue contradiction.
- Live towers.py already writes hp_read/inferred_max rounded4; actual translator passes crown hp_frac unchanged. Both arms retain public fractions.59/.0178 gives58.9536/3312 in B; no second normalization is needed. Actual root entity snapshots, rather than stats counters alone, are audited. Early enemy king2400/fraction1 is retained as an inconsistency. Unknown AnyTroop/AnyBuilding rows use actual drop behavior.
- Existing cache files are parsed directly, with supported native-json-v1 qualification and raw/canonical hashes. The normal load path cannot build a missing cache: required levels are prepopulated before check11, then load/build are replaced. Unused export errors remain explicit; playable unsupported entries fail in ExactLevelRoot. Actual native/search failure counters and fallback flags become arm errors.
- Per-row Cannon availability/affordability/legal tile counts, chosen action/row and public enemy bodies support descriptive home-defense choices. They cannot establish defensive success. Arm errors already appended are retained and force failure; R18-3 concerns errors outside that existing path.

## Fixture assessment

No fixtures were run. Source includes useful differential/mutation cases for clone independence and recorded-command ownership, blocked/catch-up polls, wrong known slot, missing ack, equal-length pending replacement, public clock boundary,59HP regression, missing towers, paired native failure, post-start hook/RNG count, cache removal/tampering, and referenced runtime content changes. Existing runtime-tamper fixtures mutate only files already enumerated by runtime_content; the environment fixture only compares dictionaries. They cannot establish the missing serving-root fence. The root hook fixture supplies a fabricated core/native root, so it proves wrapper behavior and one-call accounting, not full actual-player integration. Full replay on reviewed bytes remains mandatory and must fail closed.

## Execution identity and conditions

Current01 core dependencies below match05, including root/config/scope/profile/live player/translator/search players. Current01 is the frozen reviewed R14 primary installation.05 primary R17 edits are outside this review; do not sync them for this diagnostic. The diagnostic's broad sources() binds ALL bot Python, even non-imported primary files: therefore capture the actual01 all-bot tree and keep it stable for the whole job. Do not demand that irrelevant, unfinished05 primary files replace01 simply to equalize broad source hashes. Serving imports must be bound separately and remain the reviewed closure. No main01 sync while diagnostic is running.

**Currently approved bounded execution commands: NONE.** Read-only inspection remains allowed. The following is the intended owner-only command shape AFTER repair, a new fresh independent matching-byte approval, reviewed package-only deployment, stable01 dependencies, no conflicting owned job, and successful prerequisite evidence. It is not authorization to execute this rejected revision:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
unset CLASHER_LEVELS_PLACEMENT_PROOF
cd "$REPO"
timeout --kill-after=15s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider bot/levels/diagnostics/test_replay.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/s27-tests-r18.txt 2>&1
# ONLY after terminal test PASS and inspection of that result:
timeout --signal=INT --kill-after=15s 25m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.diagnostics.replay --inputs /mpac/sdicks02/jobs/clasher/bot-levels/s27-m02 --out /mpac/sdicks02/jobs/clasher/bot-levels/s27-diagnostic-dev1 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/s27-diagnostic-dev1.txt 2>&1
```

Use each log/output path only if fresh; otherwise preserve it and register a new exclusive name in the next review. Verify NUMPY_MADVISE_HUGEPAGE0, startup hashseed0, CUDA empty, bytecode writes disabled, and OMP/MKL/OPENBLAS/RAYON1 from exact env.sh. Repair/review the CLASHER_EVAL_RUNTIME_ROOT fence above; do not bypass it with undocumented environment assumptions. Runtime once (~150 CPU s), one Python process, no forks/pool/GPU/account/emulator. Existing CPU admission lease/nice10/full-pool priority applies. Only01 here; never05 or09–18. Timeout must surround cpu_job.sh so admission is bounded too. README's timeout-inside-wrapper commands do not bound admission and its pytest invocation permits pytest cache writes; supersede them with the eventual reviewed outer-timeout/no-cache form. No automatic replay launch after a failed fixture. A failure requires retained artifacts, repair and fresh review. No entire-assignment completion or promotion is implied.

## Exact byte manifest

All hashes are SHA256. Package paths relative to `/mpac/sdicks02/repos/clasher-bot-levels/bot/levels/diagnostics/`:

```
cbc6397ed3003a9325531556c6c23bae1799c9b2c43eeac02ddad928cdc8954e  README.md
552d25e037116d369e8ccf5bff3a7339d3bddb170c8c8064193eead0efb89179  __init__.py
1b4c5f2ed254fd9a1ae292601bdeb66433f963f2b466b58fbd40fa7e521b428f  live.py
dcdab0b6e413af4c638d2dd8a8c9555ffceeeb332b326f158a3396ca96daff29  protocol.py
05bf92c80867d91246ab3ef2f58753f1bd0e60191e7bdfcfd42462fd7ace5b83  replay.py
03d4cc3de65d2556d59fbc30b446d8cba87eaa330332bede647a4e23ca07bc80  test_replay.py
```

05 inputs relative to job/s27-m02 (all match protocol and s27-inputs receipt):

```
404cc82ea4ab0d9cb6eacf8e21189547b732b6eb252a216653d8ecf945233835  decisions.jsonl
d3b38c45ac99d86bf3fc1bdbba916536fbe1eeed83c10d95cec23c25814efb70  events.jsonl
fe8e5878afda53123d7ed55cf6e78ce0cfd022de94a4a09ba2dc5aa3f878fc26  frames.jsonl
0238b560389741ad4d84240af6bf4d9d786d57c858a4abafa94567ab17a764c2  perception.jsonl
dc77804fbe52b541341dd974157f4e72b0b6849a315dbf436dbd7bf6a285457e  session-config.json
e566a2ed5f48cec65fab5046bfda5f2f2aa6229405102f6d4cea9720db96ddd8  session.json
cad3008c02debbe1cd7b2ac73869b504e101a7c559b69926f6caddd8a9b69a17  taps.jsonl
```

343 perceptions/164 recorded decision polls/23 search rows/five ack taps are input counts, not replay results. Original scratch mirror was not modified or used as planner truth.

Core source hashes, relative to the actual05 worktree (the seven explicitly compared01 root/config/scope/profile/live/search files match):

```
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
3b4f27d7d62042b56d0fd7fd0dc92bc4d0579a6f08505df3d4aa9da7ba6e4e11  bot/live/player.py
5361deb0dbe166fd751bbb3ed3d7a710acc23cc6cbd36cb8eaaee5eb1d9458d8  bot/live/translate.py
48636f630a0ba1a7567a3f383bfcbca3aeba97418b917e278aa621dd6e8fd227  bot/live/births.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
fd66e0370fe580b917e2d1612194c01f4b19835e0c275ca5711e3e78dab08c2b  bot/players/base.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  bot/players/policy.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
0c2e14fe334828ffdc91c207d546847fc78eb88ea5e1ef27e6cba7107f4cb14a  bot/search/candidates.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
123c5281fb445a45a6c9712f5558927d0c37a92c695cfea917c115d316640204  bot/search/lopp_feat.py
d0f5777199c2a8d121bdf4caa121c27bd42ef825588fa33c5846c671bae90bd8  bot/eval/headline.py
9ab2bc406db4a7b09a9858703e32518bbbb9fd057298e6b23f84ce6554c916fd  bot/cards/fc_cut.py
f116b76ab4079a1cbe208e7220587cf001c2966156ec939517780c2bb53dde98  bot/cards/scope.py
```

Other source/doc evidence (05 unless stated):

```
0772fe4b5b6a9b1bb69a07ebbd9d9531efd773c36812820f00c31ba035545c3e  /mpac/sdicks02/repos/clasher-live/live/loop/drive.py
58033f080ecafe1f80d45e43c287253cd0ebd5010f04de695f3cad060edbfdf4  /mpac/sdicks02/repos/clasher-live/live/loop/towers.py
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  job/dev/env.sh (05 and01)
b06c780cf4e6918bc7b9c0ce477648a9c06da12ec3ab818f550139c7d47b5d0b  job/s27-diagnostic-implementation.md
60c030aa82ef5c6a624447eee3be6a776c4429d9fb7a6d5348cc7b9ffc3b0c7e  reports/bot/levels/DESIGN.md
e3930c1d0f1b819f128c51a3519c3b9ed591b57c35d971f1f7de278407a5b742  reports/bot/levels/RESULTS.md
be984526dae48b9b0546aa032506f7d8dcd3a8397a9b94007925a741b7522371  reports/bot/levels/HANDOFF.md
b359b60202534ae713ea60fdc42966caa5a3bd7399fcf7d49dc84462da2a7303  reports/bot/levels/receipts/s27-inputs.json
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh (05 and01)
ae1d26161b1666a3b697a3c54bb2f7ddf1768e2bc2ca4e359f5107f5827a3c36  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh (05 and01)
```

01 runtime key files, relative to job/runtime/live16402b-r2 (read-only SSH source/hash inspection, not a complete execution manifest):

```
d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed  main02.pt
37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85  R3a.pt
a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb  gamedata.json
de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1  native/clasher_core.abi3.so
80de4afb5b63c7dbdcb0ab285a715f9a93f4d6eeacffdfbe9f8c300ea7fecd8a  reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json
6d2665d02da7a74083313b64693e87bf59d50b303904e614ae3136b7741f8c76  reports/strategy_council_20260928/engine-speed/stage5/fair_player.py
7aca67fefd6e924d7b33ead473f52924b3323bb9715f917851943e31d6eb786d  engine-rs/quickwin_resources.py
ce87ef97679118f45ac179eda3df6eb9591d93a135e43177f45ac17829ab4a8c  imitation/evaluation/paths.py
d5d05d7c6aa91276d5f31db6e5a7e1c91b4ffca1e263f7e13496a3fd2a11cf52  imitation/model/inference.py
238fad80f1ba0cac8c76ed76c13c62eacc61fd5da01c84ce6759cf2d900b21e0  imitation/evaluation/standalone.py
e864b226baa819cf4fe5045119624c2ea04a2c8844f9c0a627ad430e16fe8076  imitation/evaluation/d1.py
be0c23188251f7ac2181dafd6bd01b2f90f47699f70c3671b91815e7fe990190  reports/explore/s1/proposals.py
5e6f07fc3d7f71cf380d8f68a9c47021355a48b85026df2b1878c236556a0f56  reports/explore/s1/belief.py
559ad75c0d9c971518fbcbab560c9d149f231045e79741da6394d49e403415fe  reports/explore/s1/cached_policy.py
5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0  src/clasher/rl/contract_v5_tokens.json
1e4bb6a01e06545b02a4f1632d564ef1dd76ceb9df2081273bd869af678b3f9e  /mpac/sdicks02/jobs/clasher/bot-lopp-models/pool.npz
```

01 existing cache raw hashes, relative to job/level-configs/50d22f86b3590abc:

```
bd77caea134e469c89dc1d25d60f30474a404feef6b529d26b0e307a8f3a7d95  L4.json
e88a6e04183f449754775b7f9d999c2ca3982601cb6f35dbbc1aec28d1555dfe  L5.json
ad4b725b180cb2aa0abf50c13cf378ba2a954233eac43080b248f2f40146dcbb  L6.json
8fc9633bbd50906d7f95575b7c93ba6a39e540aec2997f67c2d50b8a1477b6f3  L7.json
88a2472e54b090853bd18016cdafda642aafa1fd00f03ca6e7fa20f3edd638b2  L9.json
1a36f377d55be3ea34e20225aa17eb92bead8e148b216b5b1346f0e7d04c8a94  L11.json
e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc  supported.json
```

Accepted ordered prior canonical hashes remain original `98ffccd04c44d55d255f104c0f969559c421e02f0e6e8293f9a9fa0165227ec1` and restricted `8ef16962fd617bfa5662b058637ee876c6b136a8730d9a355ed951e405e897a1`; these are distinct from the raw catalog file hash above. Cache canonical digests must still be computed from the actually loaded objects at the future reviewed run. None is claimed executed here.
