# Fresh independent Sol R19 — R17 placement and primary provenance, SOURCE ONLY

2026-10-16. Actual worktree W = `/mpac/sdicks02/repos/clasher-bot-levels` on05. R = `/mpac/sdicks02/jobs/clasher/bot-levels/runtime/live16402b-r2` on01. S = `/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/royalesim` on01. J = `/mpac/sdicks02/jobs/clasher/bot-levels`. This is a new independent review; this reviewer did not implement R14 or R17.

**Decision: conditionally APPROVE the exact-byte, owner-only diagnostic sequence below: reviewed sync/hash verification, exclusive v2 probe, inspect, full integration-enabled five-file tests, native gates, fresh original four-case all11 A/B, report. This is diagnostic authorization, not placement PASS or primary readiness. One P1 primary-provenance blocker remains: the actual raw `contract_v5_tokens.json` serving dependency is omitted at both possible source roots. Repair and independently review that narrow manifest/test change before final primary provenance, BASE/bank registration or outcomes. Prefer repairing it before diagnostics to avoid repeating final-byte evidence. Any changed source bytes require fresh review; this receipt does not approve an unseen repair.**

No project imports, Python parsing/compilation/execution, tests, probes, Runtime/model construction, synchronization, CPU jobs, host scripts, commits, runtime/live/account/GPU actions or descendants occurred. Only this receipt was written. Shell source/text/hash reads and read-only SSH01 were used. Existing JSON was read as text, not parsed/executed. No routine DM or input tool was used. No new R17 test PASS is claimed.

Read the complete R17 handoff/patch, R15 review, R14 handoff/patch, R13 diagnostic, original R14 microprobe JSON and owner audit, current DESIGN/RESULTS/HANDOFF/PROGRESS including latest overrides, R12 review, relevant R8/R9/R11 reviews and R9 implementation response. Inspected current placement/probe/tests/player/run, recorder, runtime/policy/search/mask contracts and frozen01 serving sources. The owner's additional R18 token-data finding was independently traced in the primary runner; the separate diagnostic implementation and its other findings are outside this review.

## Primary blocker: R19-P1 — raw contract token data is outside runtime identity

Locations: W/bot/levels/run.py:63–97, especially :77 and explicit inputs :80–84; R/src/clasher/rl/contract_v5.py:70,157–179; R/imitation/evaluation/paths.py:6–24; W/bot/players/runtime.py:142–166.

`runtime_files()` recursively selects only `*.py` under runtime and selected serving roots. Its explicit data list includes gamedata, prior, weights, RoyaleSim vocabulary and placement proof/data, but not `src/clasher/rl/contract_v5_tokens.json`. This is an actual serving input: `TOKEN_FILE` is the JSON beside the loaded contract_v5.py, and `load_pinned_tokens()` reads it to construct the model's contract vocabulary and card identities. Read-only01 source/hash inspection confirms the real file exists; SHA256 is `5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0`.

The embedded base-token semantic digest is not a raw-file identity. A whitespace-only JSON change remains loadable, leaves parsed inputs/config/prior/models unchanged, and is invisible to the present `runtime_files()` comparisons. The same gap exists during construction and in children: the runner checks this omitted manifest before/after preload and before child work, so those checks cannot detect this raw mutation. A later invocation with otherwise identical identity can reuse clean rows across it. No mutation of frozen files is alleged; this is missing evidence in the exact-content/resume contract.

The selected-root case must be repaired too. `CLASHER_EVAL_RUNTIME_ROOT` survives Runtime's `setdefault`; `paths.setup()` can select its src/engine-rs/council import roots. R17 correctly adds those Python trees, but its `rglob('*.py')` still omits the token JSON next to an alternate contract_v5.py. Hashing only R's token file would not bind that accepted selected serving path. Some actual import orders keep `clasher` loaded from R; cover both authorized possible roots rather than relying on that accidental order. `dev/env.sh` does not unset an inherited evaluation-root override.

Required repair, without any frozen-source/data/model edits:

- Include the exact raw token file under R and under the effective selected serving root calculated with the same CLASHER_EVAL_RUNTIME_ROOT → CLASHER_ROOT → R precedence. Deduplicate equal resolved paths. Bind the actual authorized serving file; do not broadly hash unrelated output/perception JSON trees. If supporting a distinct root, require its needed serving-data file rather than silently omitting it; alternatively reject distinct roots explicitly, with matching documentation/tests.
- Keep loaded semantic checks/digests, raw proof/cache identities, complete Python closure and all existing environment/model/prior/scope checks.
- Add actual-relative-path regressions for `src/clasher/rl/contract_v5_tokens.json` at the normal root and a distinct selected root. A valid JSON byte-only change must alter runtime identity and reject an otherwise successful-row resume while weights, loaded config/vocabulary, prior and all other identity fields remain fixed. Also exercise the before/after preparation fence or the same manifest comparator. Missing required token data must fail closed. These tests may use isolated fixtures; never mutate R.
- Review the changed runner/test bytes and obtain final-byte mandatory execution evidence before primary registration. R19 does not authorize primary draw/launch, including an automatic run.sh8 launch.

This is the primary counterpart of R18's token-data observation. It does not import the rest of the diagnostic review into placement scope. It is small and reversible; no Opus hold, Claude retry or new launcher is needed.

## R15-P1 Python repair assessment

The Python part of R15-P1 is source-correct. `runtime_files()` now includes full R/imitation, council/imitation and council/c56/engine/root-v3. Read-only01 `paths.py` establishes the actual extra roots: selected src, engine-rs, council imitation, stage5b-r3, stage5, engine-speed and root-v3, followed by SNAPSHOT_ROOT at highest package precedence. R17 enumerates these selected Python roots in addition to the normal frozen roots. Read-only find returned no symlinks under the three previously omitted R directories. No frozen file was edited.

`test_serving_python_mutation_changes_identity_and_refuses_resume` mutates meaningful relative paths, including standalone.py, d1.py and model/features.py, inside fake runtime metadata. It requires only runtime_files to change and successful-row resume to fail while weights/gamedata/other identity fields remain fixed. The selected-root parametrization covers src, engine-rs and council roots and requires hash changes. Its own assertions stop at hash change; selected-root resume rejection is inferred from the existing common complete-identity comparison, not separately exercised there. These are meaningful unexecuted regressions. They do not cover raw token data, so “complete serving closure” remains unfulfilled until R19-P1 is closed.

## Common placement rule and integration assessment

1. `water_tiles()` is a public immutable geometry predicate. It pins/read-hashes arena/cards, checks dimensions and WATER bit, reduces each tile's surrounding 2×2 half-cells with any-WATER, and asserts 180-degree symmetry. For tile centre x+0.5 the closed touched half-columns are 2x and 2x+1; the reshape is consistent with this, not a per-coordinate repair list. Pinned bridge half-columns5..8 and27..30 leave only own x3.5/14.5 wholly interior on river rows15/16. The independent test expectation is32 removed WATER tiles. Supplementary RoyaleGym closed-cell source corroborates geometry, but is not treated as the exact installed revision. The binary probe remains required.

2. `card_kind()` classifies pinned static card metadata, then the actual wrapper resolves public own identities through the existing alias map. Ordinary buildings retain exactly the base mask below own row15 and lose rows15..31; WATER adds no additional own-half erosion for them. Troops including flying/champions, tunnelling Miner/Drill, SpellAsDeploy and projectile-spawn spells intersect with not-WATER. Tunnels retain base enemy-side land; unrestricted Fireball remains unchanged. Unknown/unclassifiable identity clears the slot. Mirror resolves accepted public own history through the same classification; missing/recursive history fails closed. Low confidence alone adds no new predicate. All existing affordability, occupancy, territory and WAIT/ability bits survive, with an explicit no-unmask assertion. No live Battle, check_deploy, full state, legalmask, opponent truth, arm, case or outcome enters this wrapper. No movement/refund/unlogged WAIT rewrite exists.

3. Actual instance routing remains sound on source. All experimental A/B/B0 factories install before act; script instances under balanced/pressure/defense and each actual poller.player.mask_builder are wrapped. The search core checks its actual shared bots reference; candidates filter proposals through that builder, ranked/scripted/random routes use it, and fallback/student proposals use the poller's mask. R3a and v1 opponent construction is wrapped too. Before/after act checks reject replacement/bypass. No class-global patch or standard factory edit was found. Existing native rollout placement remains a disclosed simulator-model mismatch; this establishes no LIVE placement law and must not be applied to the separate LIVE replay.

4. Parent validates proof before Runtime, installs scope then exact primary bank.scope before placement installation, identity construction, resume or forks. Missing/empty/mismatching primary scope is refused. The scope-less all11 exception still technically accepts any scope-less all11 bank, rather than comparing the original bank hash inside the helper. It is nonblocking only under this receipt's exact original-bank command; it grants no authority for another scope-less bank. Child manifests and inherited proof are checked. Source identity explicitly includes actual B0 bot/live/levels.py and the recorder dependency.

5. R17 requires water_removed as a nonnegative integer in actual placement row evidence. Actor/script path/call evidence, placement failures, rejections, native failures, terminal/completeness and parent/child exit requirements remain enforced. `report.py` consumes row_issues for quality, preserving placement failures; Markdown's omitted explicit placement-failure count is still cosmetic.

## Probe assessment and limits

The new probe source has1024 taps, not1024 games: original Cannon64 plus960 =2seats×4public tower patterns×8cards×15tiles. Cards are Knight, Minions, Cannon, Miner, GoblinDrill, GoblinBarrel, Log and Fireball. Tiles cover both rows of both bridges at edges/interiors, river centre, home and left pocket. The original18 descriptive rows are retained as a subset, with strict verdict validation now. It covers both seat rotations and public lane openings; it is a class/geometry matrix, not a failed-case blacklist.

Each tap resets a unique8-card deck with the requested card in slot2, L11 cards/towers, tick100, own elixir10000, zero delay and no non-tower bodies. Entity kinds2/3 are retained crowns. It verifies current slot/tick/elixir/public tower HP before every tap. New-card replacement cannot silently create duplicate cards. Tower patterns map own left/right to world tower slots correctly. Current client16.402 uses default simulator settings, matching the adapter's current-client path.

`expected_verdict()` derives strict WATER/OUT_OF_TERRITORY/OK from the closed bridge bounds and public lane pattern, independently of the NumPy grid. Both water precedence and special-class acceptance remain binary hypotheses until measured. Cannon row14 controls now require actual settled own centre exactly [4.5,13.5] or [13.5,13.5], relocated=True and y+1.5<=15 after25ticks; lateral/outward displacement is rejected. No footprint erosion was substituted for measured inward relocation.

Catalogue prefix names are checked before positional use. Generation compares every exposed native catalogue row's placement code with the static classification before any tap. It records native flying, but **does not compare flying against static flying fields**: the handoff's broader “codes/flying vs static fields” wording overstates that assertion. This is nonblocking because the placement rule deliberately treats flying/ground troops alike, and actual Minions must independently pass the960 matrix. Do not report flying parity as tested.

Two further proof limits matter when accepting owner evidence:

- `validate_receipt()` requires unique classifications containing the8 matrix cards and valid per-row code/kind pairs, but does not independently require the entire native catalogue name set/count. The generator loops the full catalogue. Owner acceptance must inspect full classification completeness from the actual terminal0 exact-source probe; a hand-built8-row classification fixture is not native evidence. Do not edit a receipt or treat structural validation as authentication of execution.
- Caught exceptions preserve accumulated classifications/tap rows in the exclusive JSON; raw output is printed per completed tap. A hard outer timeout/kill before final serialization may leave an empty reserved JSON with partial text output. Preserve both; missing/incomplete receipt is failure, never PASS. No automatic retries or receipt replacement are approved.

Protocol/version and complete installed identity bind binary, calibration, arena, cards, placement source and probe source. Parent runtime_files additionally binds exact receipt bytes. Old v1/R14 proof is rejected. Fixture changes test incomplete/failed/stale/missing-matrix/air-edge/class/relocation/old-version refusal and raw-byte proof/resume binding. These source assertions are unexecuted.

## Required tests and historical evidence

The960 cross-check uses the actual balanced script wrapper/base, correct slot2 action and each row's public tower pattern/seat. It fails for any admitted native refusal and any removed accepted base-eligible control. Fireball's entire slot mask must remain identical. General mask tests preserve no-unmask, WAIT/ability, idempotence, base immutability, Mirror/unknown/confidence and Runtime instance isolation.

Actual Runtime integration puts Knight and Minions in opening slots0/1, ordinary Cannon in2 and Fireball in3. It covers both seats/four Cannon tower patterns, plus both-seat Tesla with both princesses down; light Cannon/Tesla masks cover all patterns. It invokes A/B/B0 and R3a/v1 actual decisions, proposals, ranked/scripted/candidate paths, illegal water proposals and native scoring, requiring no increase in FAILURES. Runtime is constructed once; existing L4/5/6/7/9/11 caches must exist, and build is replaced with a hard failure. CLASHER_PLACEMENT_INTEGRATION=1 is mandatory; skip is not acceptance.

Hidden-state integration compares the complete public info, masks, actual decisions and A/B0/B root snapshots with fixed belief/RNG while changing hidden opponent order/levels/elixir, delayed pending command and Ghost. B act must add roots. Source can establish the intended equality checks, not that the fixture really remains publicly identical; that must execute successfully. Recorder on/off compares both-seat refused then accepted Cannon results, public info/events and stored raw verdict fields. Recorder bytes match R15; the optional branch adds offline output around the existing single step, never public player input. No new recorder semantics drift found.

Historical receipts remain historical: native R11 254/254, canonical121/121,13 tower checks,32 bodies, cut/snapshot/raw-fc30each, A→B→A distinct/reused keys with shipped[1,2,2],4 fair B decisions; R12 tests114. R12 all11 matched4/4 but failed10 total paired Cannon rejections. R14 Cannon64 passed32territory+8water refusals/24OK, all16 inward controls fitted; Knight+Minions edge WATER both seats remained an overall blocker. I read the original raw JSON and owner audit and rehashed it unchanged. No earlier PASS certifies R17, and no outcome exclusion, rejection waiver or reinterpretation of R12/R14 is accepted.

## Bounded owner-only command authorization

Only current manifest bytes below are approved for this diagnostic sequence. Parent owns the exact reviewed-file sync to01 and deployed hash checks; this reviewer performs neither. No concurrent source/cache/input changes, diagnostic replay, exporters or overlapping owned jobs. No whole-bot sync that overwrites another owner's package. Inspect live resource admission independently before launch; this review makes no liveness claim.

Use the exact authorized own R copy on01. Effective CLASHER_EVAL_RUNTIME_ROOT must be absent or resolve to R for this bounded command approval; no unreviewed alternate serving tree is approved merely because its Python can be hashed. Retain the normal default behavior environment. Before and after any current-byte diagnostic, independently retain the token JSON SHA above as an interim read-only audit because the current runner omits it. This temporary audit does not close R19-P1 or authorize primary. The owner may instead do the narrow repair/review first; then use that new reviewed manifest and fresh output names.

All outputs/logs must be unused; preserve occupied/failed paths and choose a fresh recorded name rather than overwrite. Existing env.sh fixes hashseed0, NUMPY_MADVISE_HUGEPAGE0, empty CUDA, bytecode disabled, threads1. Full-pool priority, existing cpu_job.sh leases and nice10 apply. Commands are **sequential**, each later command depends on inspected success of all prerequisites. An admission timeout is deferral/failure, not PASS. The original twice deferred03 exploratory probes remain explicitly NONBLOCKING; no03 retry/window is required.

### 1. Exclusive v2 probe only, then inspect

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
set -o noclobber
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.placement_probe --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.json > /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.txt 2>&1
```

Require terminal0, complete exact-pin/source1024 receipt, Cannon64 reason/counts, all16 strict inward centres/boxes, complete960 verdict matrix and original18, and every exposed catalogue classification. Inspect raw records, not only passed:true. Any contradiction, schema/class mismatch, missing row/receipt or unexpected verdict STOPS dependent commands. No coordinate/card exception or automatic retry.

### 2. Only after clean probe interpretation: five-file full tests

```bash
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.json
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-placement-r17.txt 2>&1
```

Require terminal0/full meaningful integration, no integration skips, missing caches, public mismatch, admitted refusal, removed eligible accepted control or native failure. No passing count is predicted from source. Failure blocks native/all11.

### 3. Only after tests PASS: unchanged substantive native suite

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-placement-r17.txt 2>&1
```

Require terminal0 and all substantive obligations:254 checks (or explain any legitimate count change without dropping obligations),121 exports,13 tower checks,32 public bodies,30each cut/snapshot/raw-fc, A→B→A key distinction/reuse/[1,2,2],4 fair B decisions with positive roots. Inspect BOTH raw snapshot lists: only the source-proven absent spell_name→empty String defaults may differ. No numeric/type/entity/order/position/qualified-key waiver, even if Python normalized equality is green.

### 4. Only after native acceptance: original four-case all11 and report

Original bank SHA256 must remain `b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a`. No R12/R14 resume or new bank substitution.

```bash
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r17 --arms A,B --all11-gate --start 0 --count 4 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r17.txt 2>&1
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r17 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r17-report.txt 2>&1
```

The normal report follows only a clean terminal runner. Failure output may be read/audited, never treated as permission for another outcome run. Require8 unique clean complete terminal rows,4of4 full-command A/B hashes, positive B roots in all4, both controllers/seats, zero errors/rejections/native FAILURES/child failures/placement failures, parent/child exit0, actual current provenance and both-seat command_events. A report quality PASS alone does not close the known raw-token omission.

Max Python processes: probe1, tests1, native2(parent+one child), all11 runner3(parent+two games), report1. Total authorized allowance stays≤16 including parents, only allowed CPU hosts01/03/04/08 generally and01 for these commands. No05 compute,09–18,GPU,live/account actions, pin/model/cache builds or new launcher. Existing run.sh N is valid1..15 and leasesN+1; this receipt deliberately does not assess/approve a primary launch command.

## Primary conditions and scientific interpretation

Primary BASE/bank remains absent until R19-P1 is repaired/reviewed and every mandatory gate passes at final frozen bytes/proof/runtime/source/cache/model/environment identity. Owner should update DESIGN's still-R14 wording (currently says preserve troop/spell masks) to explicitly record the common v2 WATER class amendment before registration. This is an explicit common candidate change before primary outcomes, not a selective B improvement. Preserve all failed data; no outcome exclusions. R18's separate unfinished diagnostic scope is neither approved nor duplicated here, and no Rsim mask is authorized in LIVE.

The accepted science stays serial100-case A/B primary plus B0 diagnostic (300games), fixed own Cannon-version deck levels/towers6, fixed fair rarity-floor opponent estimator, no hidden per-match levels/deck/order. A remainsL11, B0 remains legacy root-only, B uses exact root/qualified seat/body/spell/payload rollouts. B crown metadata affects leaf AND scripted crown lethality/Lightning; equal learned features at identical state establish that layer only. Common prior excludes Clone/Earthquake/Tornado425/2925decks and22.15479965% weight with all54 true projections unchanged. Conditional-population physics only; no literal current-live-prior, pooled LIVE or promotion claim. Frozen runtime/models/pins untouched. Standard A outside the experiment remains available; rollback selects it/omits experimental root/native/prior/mask hooks and retains receipts/catalogs.

## Exact reviewed SHA256

Local W paths unless absolute. All match the R17 handoff entries where listed. These are source-review hashes, not executed-result hashes.

```text
8e6e55427942b5bd7fdb36cdbd241cbc0aecc82e143820b306d3896205281915  bot/levels/placement.py
d742f77bca2cb3866dd225a302e1b84399c0d05ac84e8e14dba651d9938916ea  bot/levels/placement_probe.py
bbe40078bfabccb24da8641981ec782d47e4f1e1a214340a16b9cc6a3ed6563a  bot/levels/test_placement.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
ba9e8fd40ef836f5d2d25a1a67bfdc8796f885bb7d7032bfd79d3b4e57b22f12  bot/levels/run.py
200c2afd8f636997578caf3921991b5a8ab68cd8c9157ed3c86910da1ce65523  bot/levels/test_harness.py
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
164cd6e92158e57c0fef2ede7f29a103ef2846c6a0d35b9c93250d50004b6d2f  bot/players/royalesim_adapter.py
96229925be51b54ae330f0711082198dae997f0031189988125bbeb00de1bf36  bot/players/royalesim_translate.py
2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3  bot/levels/gates.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  bot/players/policy.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440  reports/bot/levels/receipts/opponent-decks-snapshot.jsonl
ddf5446070c6ddc9dd0d0f39bdea05590a324dcd648d5b5be226bf46432835c2  reports/bot/levels/receipts/placement-micro-r14-owner-audit.json
37267517312e59e5d2eb909ffd890696fe70fedb2d7a005ce14d63a9d8832b08  J/placement-manifest-r17-implementation.md
2f29dbceb46b440bf461c069afc8d73ad50ad516aa7e8c7f74f20287e31144f7  J/placement-manifest-r17-implementation.patch
f9da7a4fc693135fcf372ce3e38fc855eaf61d49f2003f145031a23d578aeca6  J/placement-review-sol-r15.md
d06e062f9860806eaeb872e1ee760f4970bdab566e334cfc91ce9f42686c6ba2  J/placement-r14-implementation.md
262ba4712851df9754fab2e2d4b024aeb23fd68bde580685349b632151e82407  J/placement-r14-implementation.patch
60ec24febec2c83f5323f968ff28ea86b69b3a977a827a816fa6a0422335a3ca  J/territory-diagnostic-astra-r13.md
0be387a22e0bf4cfeab3508dcdea13f84220a186236b24aadd3d07b30083c463  J/s27-diagnostic-review-sol-r18.md
d9115358634e937ac3b4af6f60c9ae447370ad576f2c5df7f54706111feb8abd  J/dev/placement-micro-r14.json
```

Read-only01 independently verified key serving/data hashes (not a complete execution manifest):

```text
ce87ef97679118f45ac179eda3df6eb9591d93a135e43177f45ac17829ab4a8c  R/imitation/evaluation/paths.py
238fad80f1ba0cac8c76ed76c13c62eacc61fd5da01c84ce6759cf2d900b21e0  R/imitation/evaluation/standalone.py
e864b226baa819cf4fe5045119624c2ea04a2c8844f9c0a627ad430e16fe8076  R/imitation/evaluation/d1.py
b0de1fb681924fc7d99525791fa24f3172cd4e391e79a4e8ddb4ac9c99e41b08  R/src/clasher/rl/contract_v5.py
5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0  R/src/clasher/rl/contract_v5_tokens.json
97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb  S/royalesim.abi3.so
4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf  S/data/calibration.json
7fbe4b0dce373d49ec69f1cdaeb65047b1602ea58dd6ce3a79dfe9be03fe7169  S/data/derived/arena.json
c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc  S/data/derived/cards.json
```

Automatic final delivery only. No duplicate completion DM, routine poll, user-input tool or descendant. Essential owner action questions, if ever needed, remain auto-mode direct to owner, max2sentences/1path.
