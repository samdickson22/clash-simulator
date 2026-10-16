# Fresh independent Sol R15 placement review — source only

2026-10-16. Actual worktree: `/mpac/sdicks02/repos/clasher-bot-levels` on05. Reviewer is independent of the R14 implementer. Baseline inspected: implementation commit `41df38a83efa239f99c11457503514b26db43a26`. The shared initial `clasher` checkout was not edited.

**Decision: conditionally APPROVE the exact-byte owner-only diagnostic sequence in the R14 handoff: sync01, bounded microprobe, inspect64+18, full opt-in tests, native gates, fresh complete four-case all11 A/B, report. This approval collects diagnostic evidence; it is not placement PASS or primary readiness. One P1 provenance blocker remains before primary bank/BASE registration: the runtime manifest omits the actual frozen `imitation` policy/mask/feature implementation. Resolve and review that narrow manifest repair before claiming final immutable provenance or starting primary work.** The owner may instead repair that issue first to avoid repeating final-byte diagnostics. Any code repair is outside this receipt's exact-byte approval and requires fresh source review; do not edit concurrently with jobs.

No project code was executed or imported. No tests, simulations, synchronization, CPU jobs, host-management scripts, runtime/live/account/GPU actions, implementation edits, commits, or descendants. Only this receipt was written. Read-only SSH01 was used for `cat`/`sed`/`head`/`grep`/`ls`/`sha256sum` of frozen source, installed simulator data/binary, existing logs, environment and wrappers. The hashes of all 20 R14 source/dependency entries and the focused patch match the implementation handoff; the six owned sources and parent recorder were rehashed again before this write.

Read the mandatory R14 handoff and focused patch, full R13 diagnostic, DESIGN/RESULTS/HANDOFF including their latest appendices, R12 final review, relevant R8/R9/R11 reviews and R9 responses. Traced current placement/probe/tests/player/run/recorder through the actual frozen public mask, C56 candidates/scripts, StandalonePlayer/V1Policy and D1 interfaces; inspected related local runtime/search/card-scope/cache/report/launcher sources. Prior execution receipts remain historical evidence only.

## Blocking finding

### R15-P1 — actual frozen policy and feature sources are absent from resume identity

Location: `bot/levels/run.py:63–90`, especially directory enumeration at lines66–70. This is a preexisting omission exposed by tracing R14's new actual-instance integration, not evidence that someone modified the frozen runtime.

`runtime_files()` enumerates engine-rs, src, student-source, selected reports and root-level `*.py`. It does **not** enumerate `<runtime>/imitation/`. Read-only01 inspection established that this is a real directory, not a symlink under one of the enumerated roots; `<runtime>/src/imitation` does not exist. The actual path is:

- `bot/players/policy.py:20–30` constructs V1Policy, whose frozen `reports/explore/e1/policy.py` imports `imitation.evaluation.standalone.StandalonePlayer`.
- Frozen `imitation/evaluation/standalone.py:3–6,14,24–28` constructs the exact mask builder R14 wraps, creates the seeded policy generator, builds the supplied mask and samples a command.
- Frozen `imitation/evaluation/d1.py` supplies `D1Tracker` and `model_packet`, including the learned feature packet and action mask. `paths.py` selects additional import roots.
- `bot/players/runtime.py` imports `imitation.model.load_policy`; the real package's `model/__init__.py` imports `network.py` and `inference.py`, with `features.py` also under the omitted tree.

The checkpoint hashes and package versions do not bind these Python definitions. A change to, for example, StandalonePlayer's RNG/decision plumbing or D1/model_packet leaves current `runtime_files`, `source_sha256`, config, prior and model-weight digests unchanged. `resume_done()` can therefore reuse completed rows across that change. This violates the stated runtime/features immutability and resume contract even when every mask path is exercised and all11 commands agree within the new run. Frozen permissions reduce accidental edits; they do not make missing hashes equivalent to a content identity.

**Required repair before primary registration/acceptance:** include the frozen imitation Python tree, or its complete actual serving import closure, in `runtime_files()` without changing any frozen source. Confirm any additional roots imported by `imitation.evaluation.paths.setup` are also covered for actual serving dependencies. Add a meaningful manifest/resume tamper regression for an actual relative serving path such as `imitation/evaluation/standalone.py` or `imitation/evaluation/d1.py`; it must change runtime identity and reject reuse even when weights/config/prior are unchanged. Preserve existing proof/data/cache/model/environment checks. This is a provenance-only repair, not authorization to change the model, weights, features, policy or runtime. Review the changed runner/test bytes before their execution. Current-byte DEV diagnostics may be collected under the bounded authorization below, but cannot close this finding.

## Placement, API and recorder assessment

1. **Narrow public-only intersection is source-correct.** `placement.py:35–85` resolves public own hand identity, uses loader metadata to identify ordinary buildings and clears only that slot's own-frame rows15–31. There is no new legality oracle, hidden opponent input, simulator state parameter, per-case/outcome predicate, unmask, tap movement, refund, unlogged WAIT conversion, footprint erosion or native physics edit. It copies the base boolean mask and preserves WAIT/ability bits exactly. Identified troop/spell/champion/special masks survive even at low identity confidence; unknown identities fail closed. Mirror resolves through accepted public own history and cannot recursively authorize unresolved Mirror. Empty slots were already masked; clearing them introduces no enabled action.

2. **Actual selection paths are wrapped, not just diagnostics.** Runtime installation checks the exact three script styles and wraps their actual mask instances. Full-scope `bot.cards.scope.extend` supplies distinct F.bots builders; verifying their vocabulary/data contract rather than object identity with R.builder is appropriate. `C56RolloutPlanner.candidates` uses balanced.mask_builder for its mask, calls ranked/scripted actions through the same instance, samples from that mask and filters proposals. Each search/policy actor's start wrapper wraps `poller.player.mask_builder` before any act; frozen StandalonePlayer actually calls that member. Search proposals/fallback and R3a/v1 policy sampling therefore consume the common intersection. A/B/B0 factories and the actual opponent construction are covered. The before/after act identity checks and selected-action check reject bypass/replacement. No class/global placement monkeypatch was added. Native rollout placement remains unchanged, as disclosed.

3. **Installation order and row evidence are coherent.** Parent scope comparison and placement installation precede identity construction, successful-row reuse and forks. Child source/runtime/environment checks still run; inherited proof must equal the parent identity. Actual diagnostics require exercised policy paths and balanced root-candidate calls, exact expected script paths, mask versions and nonnegative integer counters. Error paths preserve failures. `row_issues`, parent completion and report quality reject nonzero placement issues; merely reporting counters is not treated as successful installation. Existing rejection/native-failure/exit/completeness gates remain effective. The omitted imitation sources above remain a separate identity gap.

4. **Proof is byte-bound, not only path-bound.** `proof()` compares current installed identity to the complete receipt identity; identity includes binary/calibration/arena/cards and placement/probe source hashes. Parent input hashes additionally include exact raw receipt bytes and installed data; children rehash inherited input paths. Formatting-only receipt changes invalidate resume. Missing, failed, stale, incomplete or wrong-pin64 receipts are refused. This source establishes validation mechanics, not authenticity of an unexecuted PASS. Source hashes cover the recorder and actual B0 dependency as well.

5. **Bank scope strengthens primary safety.** Primary missing/empty/mismatched scope is refused; a present malformed or mismatching scope is refused in all11 mode too. The scope-less exception at `run.py:289` is technically available for any `all11_gate=True` bank, rather than identifying the original DEV bank by hash. Under the reviewed command's exact original bank this does not bypass primary protections: all11 mode independently requires A/B and every true/planner level11. Treat it only as the documented legacy DEV exception; do not infer permission for arbitrary scope-less banks. Hardening that wording/predicate is nonblocking for the exact command reviewed here.

6. **Recorder has no identified simulator semantics drift.** Compared `royalesim_match.py` against the published implementation commit. Its R14 delta adds the false-default optional recording list, records both-seat command verdict/raw rows immediately after the existing single `battle.step(sent,0)`, and emits the list only in verbose results. The extra action-to-command conversion is pure. It neither changes step ordering/ticks, command delay, acceptance, own history/events, queue completion, hash updates nor the view supplied to a player. The offline result contains hidden diagnostic detail and is never placed in PublicView/public_events. The on/off integration checks exercise deliberately rejected then accepted Cannon commands in each seat and compare results/public info/events. They do not independently compare the final simulator state hash, but source inspection finds no state mutation in the recorder. Existing binary ABI/schema must still be demonstrated by the bounded tests.

## Microprobe and coverage interpretation

- Probe construction matches the adapter's `client='16.402'` path: that path uses default RoyaleSim overrides `{}`. Thus the probe's direct default Battle constructor is appropriate; it is not accidentally running the legacy15.535 overrides. Binary/calibration/arena pins observed on01 equal those in the probe. No Runtime/model/policy worker is constructed by the standalone probe.
- The fixed matrix has64 Cannon taps: both seats ×4 enemy-princess patterns ×8 coordinates. Forty taps are the five failed coordinates;24 are controls. Sixteen controls are own row14. The fixture asserts Cannon slot2, tick100, full own elixir, exact tower HP and no non-tower entities, retaining entity kinds2/3 as crowns. Seat1 uses the same integer-own-tile rotation as the adapter. Accepted controls advance25ticks and locate the actual unique stationary Cannon by team/card, instead of trusting a reported tap position.
- **Mandatory manual interpretation:** the automated relocation predicate at `placement_probe.py:122–124` is only `resolved != tap`; it does not assert the direction/legality of the final3×3 box. Before accepting the probe, inspect every row14 settled position in the own frame and verify actual inward relocation to a fitting own-side box (for these Cannon fixtures, own centre y must move below14.5 and the3×3 box must clear the river; y<=13.5 is the expected own-side bound). A lateral-only or outward displacement must not be accepted just because `relocated=True`. The handoff already requires inspecting actual relocation controls, so this is an explicit acceptance condition, not a mandatory additional code rewrite. Also inspect the exact40 rejection reasons and24 control acceptances; unexpected/error/missing rows block.
- The18 Knight/Minions/Fireball observations are deliberately descriptive. Their complete keys are required but `passed=True` certifies the Cannon64 only. Inspect all18 before dependent readiness. Frozen public mask source admits at least the seat0 right bridge edge when the public princess is down; the diagnostic question whether the installed simulator rejects it is still unanswered by this review. Do not call a future mismatch an incidental test failure or waive it because Cannon is fixed.
- `test_descriptive_nonbuilding_verdicts_against_actual_public_mask` uses the actual script wrapper/base, the same public tower pattern and correct slot2 action index, and rejects any simulator refusal admitted by the unchanged nonbuilding mask. A measured contradiction stops the dependent gate/game sequence and requires a separately reviewed common correction. No troop/spell/special rewrite is authorized here.
- Lightweight regressions exercise pinned classes and both seats/tower patterns with Cannon/Tesla, all-mask no-unmask preservation, actual Mirror history, specials/champion/Miner, unknowns, instance isolation, proof/resume/scope guards and missing/stale/unexercised evidence. Opt-in integration constructs Runtime once and exercises actual A/B/B0 plus R3a/v1, candidate/ranked/scripted/proposal/random routes and real decisions, requiring no native FAILURES. It compares entire public information, masks, fixed-seed decisions and actual root snapshots under hidden opponent level/deck order/elixir/pending-command/invisible-Ghost variation. The B root-call increase check prevents a no-root fallback from masquerading as fairness evidence. Hidden Ghost/public-equality and all ABI assumptions remain test obligations; no green result is inferred here.
- Existing-cache loading explicitly fails on LevelConfigs.build in integration, and runner preloads raw/canonical exports before reuse/fork. Preserve the existing supported manifest too; do not allow concurrent cache writers or interpret an unexpected cache mutation as harmless. Scope restriction remains identical for all arms/pollers, with Clone/Earthquake/Tornado excluded,22.15479965% prior mass omitted and all54 true projections unchanged.

## Conditional owner command authorization and stop conditions

The exact commands are in `/mpac/sdicks02/jobs/clasher/bot-levels/placement-r14-implementation.md`; this receipt authorizes only their stated bounded diagnostic scope and sequence, after verifying deployed source bytes against this manifest and frozen dependencies against the matching reviewed runtime. No imports/tests/sync/host jobs were performed by this reviewer.

1. Owner-only exact-byte sync to01, then the exclusive-output microprobe through cpu_job.sh1/nice10, outer `timeout --kill-after=10s 5m`. Require terminal0, a new complete receipt/log, exact pins/source/data hashes, all64 Cannon outcomes and actual row14 relocation interpretation, and inspect all18 descriptive outcomes. Preserve a failed/partial receipt; never overwrite it or hand-edit it into PASS.
2. Only after clean probe interpretation: export its path as `CLASHER_LEVELS_PLACEMENT_PROOF`, run the handoff's full five-file pytest command with `CLASHER_PLACEMENT_INTEGRATION=1`, wrapper1/nice10, outer15m. Integration skips do not count. Any failure—including nonbuilding contradiction, public-view mismatch, API mismatch, missing cache or new native FAILURES—stops dependent commands. No automatic retry loop or repair is approved.
3. After matching-byte test PASS: native suite through wrapper2/nice10, outer15m. Require all seven substantive gates, terminal0, complete raw diagnostics,121 canonical exports,13 tower checks,32 public bodies, cut/snapshot/raw-fc30each, A→B→A distinct/reused keys with shipped[1,2,2], and4 fair B decisions with positive roots. Inspect both raw snapshot diff lists; only the previously audited absent spell_name→empty-string defaults may normalize. No numerical/type/entity/order/position/qualified-key waiver.
4. After those checks pass: one fresh output/manifest using unchanged `reports/bot/levels/receipts/all11-dev-cases.json`, `run.sh 2`, A/B, all11, start0/count4, outer15m; then report through wrapper1/nice10, outer5m. Require8 unique complete terminal rows,4/4 full-command hash matches, positive B roots in all4 B rows, both seats and both controllers, zero simulator rejections/native failures/child failures/errors/placement failures, verified parent/child exit0 and clean report. Preserve command_events for both seats. Current-byte results remain DEV diagnostics while R15-P1 is open; repair/review/final-byte provenance is still necessary before treating the mandatory evidence as complete for primary registration.

Environment: existing reviewed dev/env.sh, `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, empty CUDA visibility, bytecode disabled, math threads1, pool start unset/fork. CPU01 only, existing admission/full-pool priority and nice10, sequential commands, no overlapping owned jobs/exporters or concurrent source/input/cache edits. Maximum Python processes: probe1; full tests1 (launcher fixture shells do not start Python); native suite2 (parent+one raw-fc child); all11 runner3 (parent+two serial games); report1. No process-budget expansion,05 compute or03 retry is required. Admission timeout/missing terminal evidence is failure/deferral, not PASS. The twice deferred03 exploratory probes remain explicitly nonblocking.

**Primary remains blocked.** Do not draw/register a fresh BASE/bank or run primary outcomes until R15-P1 is repaired/reviewed and every mandatory gate has clean final-byte evidence. Thereafter retain the accepted serial100-case A/B primary with B0 diagnostic, frozen true Cannon8/tower6 profile, fixed fair rarity-floor opponent estimate, exact runtime/pins/models/weights/features and explicit supported-prior population. Use the frozen source snapshot for registration. No outcome exclusions, R12 reinterpretation, gate weakening, rebuild/promotion, pooled LIVE inference, accounts or deployment.

## Scientific and safety conclusion

The common candidate amendment is explicit in DESIGN and applies equally before primary registration, so it changes the shared simulator adapter rather than selectively improving B after primary outcomes. It addresses the shipped simulator's ordinary-building own-half rule, which calibration itself calls low confidence for the real client. It establishes no live placement law and does not remove the remaining native rollout placement mismatch. Reversibility remains selecting standard A outside this experimental factory/removing the experimental wrappers while preserving catalogs, receipts and failed R12 data. B's crown metadata still affects leaf normalization **and** scripted crown spell lethality/Lightning ordering; equal learned features at the same state establish only that layer's invariance. This remains the accepted serial conditional-population physics experiment.

Optional report clarity: report JSON/quality and incomplete-row handling already honor placement_failures, but Markdown omits the explicit placement-failure count. Printing it would make diagnosis easier; it is cosmetic and does not replace the acceptance gates or resolve R15-P1.

## Exact SHA256 — reviewed local bytes

Paths below are relative to the actual worktree unless absolute. These are source-review identities, not execution receipts.

```text
10a0816dd55ed0292746edd7d7808841747ece751e552cd31709d945714263ab  bot/levels/placement.py
6562c25b7851cfdd950536373156d6c0b0368e3609274251cca4ed00de0063aa  bot/levels/placement_probe.py
70ce87eae82e2aad6590f62fc32491421c8bded8f3716b9550f13373d6f59a3c  bot/levels/test_placement.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
1897205fbb6cb6205a593bd5d19b5dd7a5f5ab54deb76d69d9079099f614e494  bot/levels/run.py
385118e2c6351a11f2b2a61209deb8539a10d57bc0e25a8a1db3c0559b742ced  bot/levels/test_harness.py
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3  bot/levels/gates.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  bot/players/policy.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
24c21cb6c31fb0c4b0f2ae7dbc7104897c4181cdbf9100607bf9138b47b81a16  bot/players/royalesim_vocab.py
164cd6e92158e57c0fef2ede7f29a103ef2846c6a0d35b9c93250d50004b6d2f  bot/players/royalesim_adapter.py
96229925be51b54ae330f0711082198dae997f0031189988125bbeb00de1bf36  bot/players/royalesim_translate.py
262ba4712851df9754fab2e2d4b024aeb23fd68bde580685349b632151e82407  /mpac/sdicks02/jobs/clasher/bot-levels/placement-r14-implementation.patch
d06e062f9860806eaeb872e1ee760f4970bdab566e334cfc91ce9f42686c6ba2  /mpac/sdicks02/jobs/clasher/bot-levels/placement-r14-implementation.md
60ec24febec2c83f5323f968ff28ea86b69b3a977a827a816fa6a0422335a3ca  /mpac/sdicks02/jobs/clasher/bot-levels/territory-diagnostic-astra-r13.md
60c030aa82ef5c6a624447eee3be6a776c4429d9fb7a6d5348cc7b9ffc3b0c7e  reports/bot/levels/DESIGN.md
65ee2316de6eedce3116e62e5269b9c9e4128fc98f9de51970b7c16fab44c28d  reports/bot/levels/RESULTS.md
3b17c117029f198bef7295acecc366072c37bda326fd3e6fc7323f65e70667a6  reports/bot/levels/HANDOFF.md
b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440  reports/bot/levels/receipts/opponent-decks-snapshot.jsonl
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
```

## Exact SHA256 — read-only01 frozen dependencies and controls

R = `/mpac/sdicks02/jobs/clasher/bot-levels/runtime/live16402b-r2`.
S = `/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/royalesim`.
Paths with R/ or S/ below use those roots. This is a focused verified dependency list, not a claim to have hashed every imported package.

```text
3b90fff2a66b744fc4d93b1f73ec8d2d4afaba06603a3b9215c10f61f2747753  R/src/clasher/rl/public_action_mask.py
b0de1fb681924fc7d99525791fa24f3172cd4e391e79a4e8ddb4ac9c99e41b08  R/src/clasher/rl/contract_v5.py
4fa6940fbaf8c13c64c4658286e42bdbfdd35dce9c69e1df675ac7c7427e2276  R/src/clasher/rl/c56_rollout_planner.py
965e7d1c288372b249a8aecd71909331905faae520e8f11e5a0b675010292064  R/src/clasher/rl/c56_scripted.py
e74b97e5f5dc8f97442fee98a113dadc480126b51ed997868a11a318db5f127a  R/src/clasher/rl/structured_obs.py
932f1e9a88f9370b39d9b8b73e0600cdc5774225dadc9d2be2216d3f96753d76  R/src/clasher/rl/public_scripted_opponent.py
0747592930f0c0645e506086634ecc0919bbf853b994c71d89a5e7f889697884  R/src/clasher/card_aliases.py
1a16390ccc8ef093e6de5a98a0d730de5b643d67b06c37056eea382a3a0211d7  R/reports/explore/e1/policy.py
238fad80f1ba0cac8c76ed76c13c62eacc61fd5da01c84ce6759cf2d900b21e0  R/imitation/evaluation/standalone.py
e864b226baa819cf4fe5045119624c2ea04a2c8844f9c0a627ad430e16fe8076  R/imitation/evaluation/d1.py
ce87ef97679118f45ac179eda3df6eb9591d93a135e43177f45ac17829ab4a8c  R/imitation/evaluation/paths.py
98017d5739a04f658da7e4085068f050eacb78c4a57c8e1e57c1efd8b53a3065  R/imitation/model/__init__.py
4a1d2f79002ba704783d5138321b1c242ac04937b3cbfff3517b2ac541e02d3d  R/imitation/model/features.py
d5d05d7c6aa91276d5f31db6e5a7e1c91b4ffca1e263f7e13496a3fd2a11cf52  R/imitation/model/inference.py
f931960356532af0d5739579ff607b89340ce0a696c6ce1737c8d113993f3ead  R/imitation/model/network.py
de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1  R/native/clasher_core.abi3.so
a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb  R/gamedata.json
97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb  S/royalesim.abi3.so
4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf  S/data/calibration.json
7fbe4b0dce373d49ec69f1cdaeb65047b1602ea58dd6ce3a79dfe9be03fe7169  S/data/derived/arena.json
c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc  S/data/derived/cards.json
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh
ae1d26161b1666a3b697a3c54bb2f7ddf1768e2bc2ca4e359f5107f5827a3c36  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh
```

Automatic final delivery only; no duplicate completion DM or input request. No descendants.
