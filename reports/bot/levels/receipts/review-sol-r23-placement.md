# Fresh independent Sol R23 — placement/schema and final raw-token provenance

2026-10-16. SOURCE ONLY. W = `/mpac/sdicks02/repos/clasher-bot-levels` on05; J = `/mpac/sdicks02/jobs/clasher/bot-levels`; R = `J/runtime/live16402b-r2` on01; S = `/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/royalesim` on01. This is a fresh independent review; I did not implement these files.

**Decision: conditionally APPROVE the exact R21 bytes identified below for the existing owner-only diagnostic sequence: reviewed-file sync and deployed hash verification, exclusive v3 probe, inspect, integration-enabled five-file tests, native gates, fresh original four-case all11 A/B, then report. No remaining source blocker was found in this repair. R19-P1 is addressed in source, including both token roots and meaningful identity/resume/preparation regressions. Execution closure remains outstanding. This review establishes neither a v3/native/test PASS nor primary readiness. Primary BASE/bank must remain absent until every final mandatory gate passes.**

No project code, imports, JSON parsing, compilation, tests, simulations, probes, Runtime/model construction, sync, host-launch scripts, CPU jobs, account/emulator/GPU actions, native/frozen/live writes, commits or descendants were performed. Existing JSON was inspected as text. Read-only shell/source/hash reads and SSH01 were used. Only this report was written. No input tool or completion DM was used; automatic final delivery suffices.

Read the full R21 implementation handoff and focused patch, R21 repair brief, R19 review, R17 handoff/patch, R15 review, R14 handoff/patch and R13 territory diagnostic. Read the failed R17 raw JSON/text, R14 raw JSON and both owner audits under W/reports/bot/levels/receipts. Read current DESIGN/RESULTS/HANDOFF/PROGRESS including later overrides, R12 review, R8/R9/R11 reviews and R9 implementation response. Inspected the five current changed sources plus player/root/config/scope/profile/runner/report/launcher, recorder, actual runtime/policy/search routing and frozen01 mask/candidate/poller/token contracts. Separate s27 R20/R22 work is not imported into this review or made a primary prerequisite.

## Findings and prior-response assessment

### 1. R19-P1 raw token provenance: source repair accepted; matching-byte execution still required

Locations: W/bot/levels/run.py:63–104, especially :72 and :80–84; test_harness.py:261–342; R/src/clasher/rl/contract_v5.py:70,157–179; R/imitation/evaluation/paths.py:6–24; W/bot/players/runtime.py:142–166.

I independently read the frozen01 loader: TOKEN_FILE is the JSON beside contract_v5.py, and load_pinned_tokens reads that file. Its semantic token digest does not identify formatting. The actual normal token file still hashes to `5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0`.

runtime_files now explicitly enumerates that exact relative JSON at both normal Runtime root and effective selected serving root. Selection uses CLASHER_EVAL_RUNTIME_ROOT → CLASHER_ROOT → normal root, matching the serving paths helper under the authorized environment. It resolves paths, deduplicates equal roots and requires each token path to be a file before hashing. Missing/non-file data cannot disappear silently through a Python glob. No broad output/perception JSON scan was added. This completes the particular raw dependency omitted by R19 without changing tokens, policy features, weights or serving behavior.

The existing R17 Python closure remains: normal imitation, council imitation/root-v3, and selected src/engine-rs/council serving trees. The raw proof, simulator/data, model/checkpoint, vocabulary, prior, raw/canonical level cache, source/environment/scope identities are preserved. experiment samples source/runtime inputs before Runtime, checks them after preload before any resume or fork, and does so on an all-done resume. Children rehash the parent-bound input paths. Consequently the new raw entries participate in all those existing comparisons.

The added tests are substantive protocol tests, not merely assertions about a helper's returned path. Three selection modes cover equal roots, distinct evaluation override and CLASHER_ROOT fallback with absent evaluation override. A clean completed row must resume first. A valid JSON formatting-only mutation then changes only the appropriate raw token digest and forces successful-row resume refusal; parsed JSON, fixture config/vocab/prior/behavior identity, weights and every other raw digest remain unchanged. Missing normal and selected files are tested separately. Another test invokes actual experiment with mocked expensive preload, mutates the file there, and requires the preparation comparator's specific error before forbidden resume_done/run_jobs in all three modes. The isolated token fixture is generic valid JSON, not an invocation of the real model vocabulary loader; the claim is raw provenance independent of already-loaded semantic identity. That is adequate for R19-P1, and no frozen file is mutated.

**Disposition:** R15's Python-closure issue and R19's raw-token issue have source-correct responses. Their final-byte execution evidence is pending; no earlier test PASS closes it. Hashing an alternative root does not authorize running one: this diagnostic approval requires the normal reviewed R and an absent or same-resolved effective evaluation root.

### 2. Failed v2 classifications: generic schema repair accepted conditionally on fresh native evidence

Locations: placement.py:47–90; placement_probe.py:104–144; test_placement.py:66–96. Exact evidence: failed R17 receipt SHA `d0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4`.

The preserved receipt has protocol v2, passed=false, all145 catalogue records and exactly two failed class records: Tornado static rolling/native2/flying false; MergeMaiden static unrestricted/native0/flying true. Cannon, river and descriptive arrays are empty. Its raw text reports failed. This was a pre-tap schema failure; it provides no new water/territory/relocation evidence and cannot authorize v3.

Read-only01 confirms the pinned cards JSON's Tornado spell has both spell_as_deploy=true and can_deploy_on_enemy_side=true. R21 makes troop-territory classification conditional on the first flag AND absence of enemy-side permission. Projectile spawning retains the following water-sensitive branch; otherwise the spell is unrestricted. There is no Tornado-specific exception.

MergeMaiden's root metadata kind is spell, but its variant options reference mounted first and normal second; both referenced card records are troop. R21 resolves options recursively from the same pinned immutable cards mapping before root-kind classification. It accepts only uniform resolved troop/ordinary/tunnel placement classes, using the first result; missing, empty, mixed, cyclic or unclassifiable variants fail closed. This is deliberately conservative for unsupported metadata, with no elixir/level/state-dependent variant selection. It does not infer that a root spell's own null body fields describe the selected form, and adds no new variant mechanics to the planning runtime.

Supplementary local upstream card.rs:9193–9202 corroborates the spell-flag precedence; py.rs:723–750 recurses through a variant's first form for catalogue placement; card.rs:12036–12050 requires uniform form body kinds; state.rs:13158–13185 maps deployment territory. I read these sources and hashed them, but their revision is NOT established as the installed binary's. Exact-binary support comes from immutable installed metadata plus the preserved native catalogue observations, with a new v3 full-catalogue probe still mandatory.

The historical regression hash-pins the raw failed JSON, asserts the original two failures and zero tap arrays, and compares repaired static classification with all145 recorded native placement codes. Generic tests also cover an arbitrarily named enemy-side spell and uniform/missing/mixed/cyclic variants. These are unexecuted regressions using prior observations. They are not a fresh native PASS. No card is dropped from the new catalogue check, and no population exclusion, hidden-state lookup or L11 fallback is added.

### 3. Exact145 generator/validator repair closes R19's structural completeness limitation

The generator requires exactly145 native rows, exactly145 unique names and equality to the pinned static card-name set before classification/taps. It checks the exposed eight-field CATALOGUE_FIELDS prefix before positional interpretation, recomputes every static class with the variant mapping and checks each native placement code. All class rows are accumulated before mismatch refusal. The receipt validator independently requires exactly145 unique names equal to the static set and rederives each row's kind before checking its code. Wrong/missing/duplicate/extra names cannot satisfy the set/count checks. I independently counted145 name rows in the installed cards-list text range, rather than counting unrelated later unit tables.

The full145 structural fixture is intentionally generated from static classes. By itself that would be circular evidence of native agreement; it is used for validator shape/tamper tests, while the distinct preserved-native regression and required fresh exact-binary generator supply native evidence. Missing-class and explicit old-v2 rejection join the existing stale source/pin, incomplete matrix, wrong class, air-edge and inward-fit refusal tests. Protocol v3 and changed placement/probe hashes make v1/v2 receipts stale.

**Retained caveat:** native flying is recorded, not checked for equality with root static flying fields. MergeMaiden's root and first form illustrate why those are different concepts. Do not claim flying parity. Ground Knight and flying Minions must independently satisfy the full physics matrix; both receive the same WATER intersection.

### 4. Common placement predicate and actual actor routing remain coherent

placement.py:26–44 derives a fixed public WATER predicate from the pinned18×32/36×64 arena, bit32, any-WATER in each touched2×2 half-cell block, with a180-degree symmetry assertion. It does not use a failed-action list. For this arena, bridge-interior centres x3.5/14.5 survive on river rows15/16 while closed-edge centres touch water.

Ordinary buildings retain the base mask on own rows0..14 and clear15..31; the WATER predicate adds no erosion below that boundary. Troop/air/champion, tunnel, rolling and projectile-spawn-spell classes intersect with not-WATER; unrestricted spells preserve the base mask. Tunnels retain base enemy-side land eligibility. Public own accepted history resolves Mirror, with unresolved/recursive/unknown identities failing closed. The wrapper copies the existing boolean mask, checks no-unmask and preserves WAIT/ability exactly, retaining affordability, public occupancy and territory restrictions. No Battle/check_deploy/state/hidden legality oracle is accepted by a player. No command relocation, refund, silent WAIT conversion, arm/case/outcome predicate or additional RNG call was introduced.

The experimental factory wraps every A/B/B0 actor. install_runtime wraps actual balanced/pressure/defense instances, verifying builder vocabulary/data and references. install_player wraps each actual poller.player.mask_builder after start and before act. Frozen StandalonePlayer.decide reads that actual member; V1Policy returns its actual mask. Search fallback/proposals use the poller's mask; C56 candidates build the shared balanced script mask, filter proposals, rank/script through the same instance and sample from its legal pool. Both policy opponents are explicitly wrapped by the runner. Before/after-act reference validation and selected deployment checks reject replaced/bypassed paths. The standard factory and another Runtime instance receive no global patch.

Actual Runtime integration remains a mandatory execution gate: one Runtime; A/B/B0 and R3a/v1 decisions; both seats/four Cannon tower patterns plus Tesla both seats; Knight/Minions opening slots and Fireball preservation; candidate/ranked/scripted/proposal and random sampling paths; injected illegal water proposals; no new native FAILURES. Hidden-state tests require whole-public-info equality, identical masks/fixed-seed decisions and A/B0/B root snapshots while varying hidden opponent order/levels/elixir/pending command/Ghost, with additional B roots during act. A publicly unequal hidden fixture is a failed test, not grounds to waive equality. Existing caches must be present and export construction is forbidden in integration. None of these assertions has executed at R21.

The native rollout placement model is unchanged and remains a disclosed simulator mismatch. This is common simulator command eligibility before bank/outcomes, not a LIVE placement-law or whole-planner-equivalence claim. Do not apply this mask to the separate LIVE s27 replay.

### 5. Probe physics obligations and strict failure handling are preserved

The probe still has1024 commands: Cannon64 plus960 =2seats×4public princess patterns×8cards×15tiles. Original18 Knight/Minions/Fireball observations are retained as a subset. Eight cards span ground/air troop, ordinary/tunnelling building, spawning/rolling/unrestricted spell. Tiles cover both bridge edges/interiors on both river rows, river centre, home and pocket. expected_verdict is an analytical reason table independent of the adapter's NumPy grid. R21 does not alter these coordinates, expected reasons or physical tolerances.

Every tap starts with a unique8-card deck and the exact requested card in slot2; L11 cards/towers, tick100, own elixir10000, delay0, exact public tower HP and no non-tower entities, retaining crowns2/3. Seat1 rotates its own tile centre consistently with the real adapter. Catalogue/schema/class checks precede taps. Accepted Cannon controls advance25ticks and identify the actual unique stationary Cannon by team/card. All16 row14 controls require relocated=true, exact own centre x4.5 or13.5 and y13.5, and whole3×3 box y+1.5<=15. Lateral-only/outward displacement cannot pass. This uses actual settlement, not merely a reported tap or counter.

Strict64/960/18 completeness and reasons are required in validation. The exclusive receipt retains accumulated evidence on caught exceptions. A hard outer kill may leave an empty reserved JSON with partial text; preserve it and treat it as incomplete/failure. Do not overwrite, edit a receipt into PASS, rerun automatically or waive any contradictory code/reason/geometry result.

### 6. Scope, provenance, recorder and report contracts are retained

Parent proof validation precedes Runtime. Common scope installation and exact bank.scope comparison precede placement installation, identity/resume/forks, including all-done resume. The legacy scope-less all11 helper still technically accepts any scope-less all11 bank; this is unchanged and nonblocking only because the command here fixes the original bank hash below. It authorizes no other legacy bank or primary scope bypass.

The entire source/runtime/cache/environment comparators remain. source_hashes uses immediate *.py/*.sh files under bot/levels and the other declared serving source directories, explicitly includes actual B0 bot/live/levels.py, and excludes the diagnostics subdirectory. Independent s27 source work therefore neither becomes an imported primary module nor invalidates this review's root-file identities. Parent must serialize01 sync/tests/jobs across owners.

The optional recorder bytes equal R15/R19. record_commands defaults false; verbose enables both-seat command_events. It observes the result around the existing single step(sent,0), without changing the accepted public events or player input, queue/step timing or selected command. Hidden raw verdicts remain offline. Recorder on/off integration still compares both-seat rejected then accepted Cannon results, public info and events. Zero rejections remains mandatory for accepted all11 games.

row_issues continues to require actual installation proof/path/call evidence, integer water_removed and other counters, complete diagnostic/terminal/exit/prior evidence, zero placement errors/native failures/rejections. Runner completion and report quality use those issues; matching command hashes alone cannot pass. Markdown's omitted explicit placement-failure count is cosmetic, as R19 noted.

## Preserved historical results and remaining blockers

R11 native254/254,121 canonical exports,13tower checks,32public bodies,30each cut/snapshot/raw-fc, one-fork A→B→A distinct/reused keys and shipped[1,2,2], four actual fair B decisions/positive roots remain prior evidence. The20 raw differences were only absent spell_name→empty String; no numerical/type/entity/order/position/qualified-key waiver is permitted. R12's114 tests are prior-byte evidence. R12 all11 had8rows/4matched full-command pairs/positive B roots/zero native FAILURES but10total pair-identical Cannon rejections; acceptance remains FAILED.

R14 Cannon64 passed32territory+8WATER refusals and24OK; all16actual boundary Cannon settlements fit inward at own y13.5. Its additional Knight/Minions edge refusals in both seats blocked dependent tests/native/all11; Fireball6/6 and interior/home controls were accepted. R17v2 failed catalogue classification before taps. Both failures are preserved unchanged, not reclassified as a repair PASS.

**Current blockers are execution/evidence, not a newly identified source repair:** obtain fresh matching-byte v3 catalogue+physics PASS; full integration-enabled tests with no relevant skips/refusals/overmasking/public mismatch/exports/native failures; all substantive native gates and raw-diff interpretation; fresh original all11 eight clean terminal rows with exact provenance and report PASS. Any contradiction stops dependent work and requires a reviewed explanation/repair. Prior approvals do not authorize unseen changed bytes. Before any primary registration, parent must record the final v3 design/status amendment and immutable final source/evidence manifests. Stale earlier status prose does not override this receipt or later implementation evidence.

Original authority is unchanged:100cases A/B primary+B0 diagnostic=300serial games after all mandatory gates; fixed own Cannon8/tower6, fair fixed common5/rare4/epic6/legend9/champ11/publictower6, no hidden per-match truth. Common prior removes only Clone/Earthquake/Tornado425/2925decks,15371/69380weight22.15479965%, retains2500, all54true projections unchanged; original remains immutable. B crown metadata affects leaf AND scripted crown lethality/Lightning; identical-state learned-feature invariance establishes only that layer. Conditional-population physics only; no literal LIVE prior/equivalence, pooled behavior or promotion claim. This review is limited to the existing diagnostic sequence; no new primary launcher approval or unrelated s27 repair is required by it. Original03 exploratory admission deferrals remain explicitly NONBLOCKING; no03retry/window.

## Conditional owner commands — sequential01 only

These are reviewed proposals for the parent to execute, not commands run here. First verify the normal owned R, matching source/binary/data/cache/environment identities and the historical test-input SHA. Sync only reviewed owned files; no whole-bot overwrite or diagnostics edits. Source05 R21 hashes below match the handoff. Read-only01 currently still has the R17 hashes listed below; deployed-byte verification is therefore a real prerequisite, not assumed complete. Effective CLASHER_EVAL_RUNTIME_ROOT must be absent or resolve to R; LEVELS_RUNTIME must not select another runtime. No concurrent source/cache/input writers, exporters, diagnostics or other owned jobs. Observe full-pool priority/resource admission and existing cpu_job.sh/nice10. No frozen/native/live edits or05compute/09–18/GPU/account activity.

Use existing dev/env.sh: hashseed0, NUMPY_MADVISE_HUGEPAGE0, GPU hidden, bytecode off, math threads1; pool start unset/fork. All output/log paths must be unused, with fresh recorded names if occupied. Preserve all failed/partial receipts. Do not paste the stages into an unattended loop: inspect each prerequisite before the next command.

A. Exclusive v3 probe, CPU1, outer5m:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
set -o noclobber
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.placement_probe --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json > /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.txt 2>&1
```

Require terminal0, exact installed/source/data pins, all145 classifications with exact complete name set including both formerly failed names, Cannon64=32territory/8WATER/24OK, all16 exact inward centres/boxes, complete960 independent verdicts and original18. Inspect raw records, not just passed:true. ANY contradiction or missing/incomplete result stops. No auto-loop, exception list or expected-verdict waiver.

B. Only after A is complete and interpreted cleanly: full five-file integration tests, CPU1, outer15m:

```bash
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-placement-r21.txt 2>&1
```

Require terminal0, all five files, actual Runtime integration once, no integration skips, export builds, public mismatch, admitted refusal, removed accepted base-eligible control or native FAILURES. New raw-token/historical-class regressions must execute. No predicted test count/PASS is inferred from source.

C. Only after B PASS at the matching bytes: native gates, CPU2, outer15m:

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-placement-r21.txt 2>&1
```

Require terminal0 and all254 substantive obligations unless a legitimate count change is explained:121exports/13tower/32publicbodies/30each cut-snapshot-rawfc/A→B→A distinct-reused keys shipped[1,2,2]/four fair actual B decisions and positive roots. Inspect both raw snapshot diff lists; selected numeric/type/entity/order/position/qualified keys stay strict. Only previously source-proven missing String defaults may normalize.

D. Only after A–C PASS: same original bank SHA `b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a`, fresh all11 output, run.sh2 (three reserved Python slots), outer15m:

```bash
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21 --arms A,B --all11-gate --start 0 --count 4 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21.txt 2>&1
```

Require8unique complete clean terminal rows, four full-command hash pairs, positive B roots all4, both seats and R3a/v1, zero errors/rejections/native/child/placement failures, parent+children exit0, exact full identity including raw tokens and both-seat command_events. Never resume old failed outputs or accept hashes despite rejections. Only after clean runner acceptance, report CPU1 outer5m:

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21-report.txt 2>&1
```

Require complete registered provenance and report quality PASS. A failed run may be inspected as failed evidence, never advanced to primary. Process maxima A1/B1(one Runtime)/C2(parent+one raw-fc child)/D3(parent+two serial game children)/report1, sequential and≤16including parents. Admission timeout/incomplete terminal evidence is deferral/failure, not PASS. Parent alone coordinates01 freezes and later execution. Rollback selects standard A outside the experimental factory/removes experimental hooks while preserving all receipts/catalogues; no promotion or frozen changes.

## Exact SHA256 — reviewed source05 bytes

Paths relative to W unless otherwise stated. Five changed files were rehashed again immediately before writing this receipt and match R21's handoff. These hashes identify source review, not execution results.

```text
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  bot/levels/placement.py
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  bot/levels/placement_probe.py
372612aef24367b98bbb465bd27aca9668fc3f215f800680810a61db590ce9b1  bot/levels/test_placement.py
1c9d80e9d2cc5a031a33839b1e54e7a1d19253065affc816453149d96ee8f061  bot/levels/run.py
a7019ef1452fc35c7e28037d70e6217b82728a62a30bcc787462c4b3e9ebf9ab  bot/levels/test_harness.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3  bot/levels/gates.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
16c631a39c1f9757c416896c8b449111bfa4ab9fcb280f1c574121aee4b84951  bot/levels/test_scope.py
762bc666079119d5559fac29401d59f2c3fbc8798bee83168b06b675bbcb0be0  bot/levels/test_configs.py
0d21af2288182c9c134546ce5141f78820ce6e8bbb409b3cc681c485a7ab98a7  bot/levels/test_bank.py
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  bot/players/policy.py
164cd6e92158e57c0fef2ede7f29a103ef2846c6a0d35b9c93250d50004b6d2f  bot/players/royalesim_adapter.py
96229925be51b54ae330f0711082198dae997f0031189988125bbeb00de1bf36  bot/players/royalesim_translate.py
24c21cb6c31fb0c4b0f2ae7dbc7104897c4181cdbf9100607bf9138b47b81a16  bot/players/royalesim_vocab.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
c04bef9322dc0e4fc605f78e079d4b8fc2b7ce7613847139b61767da5b102dd8  bot/search/lopp.py
dd0a067c8871300c34ead222b72c3fafe72901f83f8bf2532742e65040397f2b  bot/search/lopp_fast.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440  reports/bot/levels/receipts/opponent-decks-snapshot.jsonl
4e0353e19ac1031a0f0c85a873ce419843ffeba5fcdefd35c55bcd60c5beec54  reports/bot/levels/DESIGN.md
2d7ba1053cff98cda19451f348db842082545e154bd15c957ac44a805175c1b5  reports/bot/levels/RESULTS.md
9c5a2d1f2641ef5f079529c359e19b35dba4591b9566dbc8d208b82ca43f3dc5  reports/bot/levels/HANDOFF.md
2840e1cc6b01f79fe53cf3cc463b207247f38ed21f6b6b8fddd80d27ceb8513d  reports/bot/levels/PROGRESS.md
```

## Exact SHA256 — handoffs, patches and historical evidence

```text
2e7c71426edf4e3ee2a66273e0f1a583f804bd77a78f7a1b405b8c88f58bee53  J/placement-r21-implementation.md
d7118c559ba84c5800eb1a72a78ef021137c35d88523a78262ce04a1a5de2aa0  J/placement-r21-implementation.patch
470cd8070a414f75a75146729299aa10211c066fd80c4fc0f5da0da7b12a655d  J/placement-r21-repair-brief.md
1bcacf6cea70ba14842f3b4d9c2e1fb99fb8fabacd7f742dec420225541c4b28  J/placement-manifest-review-sol-r19.md
37267517312e59e5d2eb909ffd890696fe70fedb2d7a005ce14d63a9d8832b08  J/placement-manifest-r17-implementation.md
2f29dbceb46b440bf461c069afc8d73ad50ad516aa7e8c7f74f20287e31144f7  J/placement-manifest-r17-implementation.patch
f9da7a4fc693135fcf372ce3e38fc855eaf61d49f2003f145031a23d578aeca6  J/placement-review-sol-r15.md
d06e062f9860806eaeb872e1ee760f4970bdab566e334cfc91ce9f42686c6ba2  J/placement-r14-implementation.md
262ba4712851df9754fab2e2d4b024aeb23fd68bde580685349b632151e82407  J/placement-r14-implementation.patch
60ec24febec2c83f5323f968ff28ea86b69b3a977a827a816fa6a0422335a3ca  J/territory-diagnostic-astra-r13.md
d0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4  J/dev/placement-micro-r17.json
2e0b377bf304724cb815f787a2e011f3293b0b64b288c7b526109a310a6453d3  J/dev/placement-micro-r17.txt
d9115358634e937ac3b4af6f60c9ae447370ad576f2c5df7f54706111feb8abd  J/dev/placement-micro-r14.json
f09f4921c0b413d07b6b4c9e16a652c8bc269ca64dbc4a632f208a283f7fbc59  J/dev/placement-micro-r14.txt
ddf5446070c6ddc9dd0d0f39bdea05590a324dcd648d5b5be226bf46432835c2  W/reports/bot/levels/receipts/placement-micro-r14-owner-audit.json
73df9f7bdf761811082a56bfd5af5a35924f5bbf520abfa33fbb454ebf5333b0  W/reports/bot/levels/receipts/placement-micro-r17-owner-audit.json
d0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4  W/reports/bot/levels/receipts/placement-micro-r17-failed.json
2e0b377bf304724cb815f787a2e011f3293b0b64b288c7b526109a310a6453d3  W/reports/bot/levels/receipts/placement-micro-r17-failed.txt
5c0b9133ef98875e1a0b2483beafd66d8f23635fdd77e7e176afd54ff8919fde  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/card.rs
8113da8f65509c58c4fce7b447b9be97598dca1284acc07c7c7eef5b49c3f7ab  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/py.rs
6ee15143ea110f3b6ad7e943a12e67fabc0970b6bfc1996bd662cfe9c1772566  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/state.rs
```

## Exact SHA256 — read-only01 observed dependencies

This is a focused independently verified dependency list, not a claim that this reviewer executed the full runtime manifest builder.

```text
5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0  R/src/clasher/rl/contract_v5_tokens.json
b0de1fb681924fc7d99525791fa24f3172cd4e391e79a4e8ddb4ac9c99e41b08  R/src/clasher/rl/contract_v5.py
3b90fff2a66b744fc4d93b1f73ec8d2d4afaba06603a3b9215c10f61f2747753  R/src/clasher/rl/public_action_mask.py
4fa6940fbaf8c13c64c4658286e42bdbfdd35dce9c69e1df675ac7c7427e2276  R/src/clasher/rl/c56_rollout_planner.py
932f1e9a88f9370b39d9b8b73e0600cdc5774225dadc9d2be2216d3f96753d76  R/src/clasher/rl/public_scripted_opponent.py
ce87ef97679118f45ac179eda3df6eb9591d93a135e43177f45ac17829ab4a8c  R/imitation/evaluation/paths.py
238fad80f1ba0cac8c76ed76c13c62eacc61fd5da01c84ce6759cf2d900b21e0  R/imitation/evaluation/standalone.py
e864b226baa819cf4fe5045119624c2ea04a2c8844f9c0a627ad430e16fe8076  R/imitation/evaluation/d1.py
97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb  S/royalesim.abi3.so
c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc  S/data/derived/cards.json
7fbe4b0dce373d49ec69f1cdaeb65047b1602ea58dd6ce3a79dfe9be03fe7169  S/data/derived/arena.json
4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf  S/data/calibration.json
b0992c5ca633598ead83c52554d6930acc4b3afd7bde5989129880a285b08adc  J/dev/env.sh
e77b40f7ef61009fb244f50edb69711a73b416e369091e3957b41715a3743949  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh
ae1d26161b1666a3b697a3c54bb2f7ddf1768e2bc2ca4e359f5107f5827a3c36  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh
```

Observed01 still-deployed root source hashes (R17; not approved as R21 evidence):

```text
8e6e55427942b5bd7fdb36cdbd241cbc0aecc82e143820b306d3896205281915  W/bot/levels/placement.py on01
d742f77bca2cb3866dd225a302e1b84399c0d05ac84e8e14dba651d9938916ea  W/bot/levels/placement_probe.py on01
bbe40078bfabccb24da8641981ec782d47e4f1e1a214340a16b9cc6a3ed6563a  W/bot/levels/test_placement.py on01
ba9e8fd40ef836f5d2d25a1a67bfdc8796f885bb7d7032bfd79d3b4e57b22f12  W/bot/levels/run.py on01
200c2afd8f636997578caf3921991b5a8ab68cd8c9157ed3c86910da1ce65523  W/bot/levels/test_harness.py on01
```

Automatic final delivery only. No new source change, native result or test PASS is implied by this receipt.
