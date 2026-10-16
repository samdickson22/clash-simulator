# R21 schema precedence + raw-token provenance repair — SOURCE ONLY

Worktree `/mpac/sdicks02/repos/clasher-bot-levels` on05. Read the full R21 brief,
R19 independent review, exact failed v2 JSON/text and prior R13/R14/R15/R17 receipts.
No Python imports/parsing/compilation, project execution, tests, probes, sync, jobs,
CPU host-launch scripts or descendants. Source/text edits and read-only01 metadata/
serving-source reads only. NEW independent review is still required before sync or
execution. This handoff claims no PASS or primary readiness. No changes to diagnostics/,
recorder/native/frozen/live/configs/root/scope/bank/report/player or true population.

## Preserved failure and classification evidence

Parent executed only the R19-reviewed v2 probe: terminal1 BEFORE TAPS, with all145
native catalogue classifications recorded, Cannon rows0/river rows0. It failed on:

| card | v2 static class | native placement code | native flying |
|---|---|---:|---|
| Tornado | rolling |2 (unrestricted spell)|false|
| MergeMaiden | unrestricted |0 (troop)|true|

Immutable `/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.json`
SHA256 `d0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4`
and its raw text were read, not altered. The earlier R14 receipt remains untouched
(SHA d9115358634e937ac3b4af6f60c9ae447370ad576f2c5df7f54706111feb8abd).
R12 failure is intact; primary BASE/bank remain absent. No full tests/native/all11
were executed at v2, and no physics result is inferred from its catalogue failure.

Read installed01 cards data, exact pin c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc:

- `.../royalesim/data/derived/cards.json:18761` Tornado is kind=spell; its nested
  spell at :18873 has SpellAsDeploy=true AND CanDeployOnEnemySide=true. V2 read
  only the first flag and incorrectly assigned troop territory.
- At :20914 MergeMaiden is a root spell with a variant block: options first
  MergeMaiden_Mounted (trigger6000 milli-elixir, precast1200ms), then
  MergeMaiden_Normal (3000 milli-elixir). Root kind is not its effective form kind.
- Text inspection confirms145 named card rows in the pinned `cards` list. The
  observed native145 unique names all resolved through that list in v2 (otherwise
  v2 would have recorded another unknown-class failure).

Supplementary source audit under `/mpac/sdicks02/tmp/bot-upstream/RoyaleSim/`:
`crates/royalesim/src/card.rs:9193–9202` uses troop territory only for
`SpellAsDeploy && !CanDeployOnEnemySide`, then AnywhereButWater for spawning
projectiles, else Anywhere. `py.rs:723–750` kind_code recurses into a variant's
first form before classifying, and reports0/1/2/3/4/5/6 deployment codes.
`card.rs:12036–12050` checks that resolved variant forms have uniform body kinds;
`state.rs:13158–13185` dispatches territory from the effective body/spell placement.
These local upstream sources are corroboration, NOT established as the installed
binary revision. The installed immutable metadata plus observed native codes are
the exact-binary evidence; the fresh v3 full-catalogue check remains mandatory.

## Five changed sources

`placement.py`, protocol `rsim-static-water-intersection-v3`:

- Fix spell precedence generically with both metadata flags; no card-name override.
  This makes Tornado unrestricted as its exposed binary class says.
- Resolve variant options through the pinned static card table. Uniform resolved
  troop/building/tunnel classes inherit the first class, consistent with native
  first-form classification. Missing/empty/mixed/cyclic/unclassifiable forms fail
  closed. This makes MergeMaiden a troop class without adding mechanics or reading
  per-match elixir/levels/forms/state. No proof table or install recursion is needed.
- Keep public own identity/Mirror history/unknown handling, immutable water geometry,
  all existing no-unmask/WAIT/ability/occupancy/affordability/territory restrictions,
  common actor routes and actual-instance validation unchanged. Native geometry is
  still a documented model mismatch. No Battle/check_deploy/hidden oracle in players.

`placement_probe.py`:

- Retain original Cannon64 + river960 =1024 commands and original18 observations,
  exact reason expectations and actual inward3x3 Cannon row14 settlement checks.
  No numeric tolerance, coordinate exception, physics relaxation or tap change.
- Still compare every exposed native row before taps. Generator AND receipt validator
  now require exactly145 unique names equal to the complete pinned static card set;
  each class is recomputed with variant context and checked against exposed codes.
  This closes R19's noted eight-row structural completeness limit. Unknown/missing/
  duplicate/wrong names or codes fail. Native flying is recorded, not claimed to
  match root static flying fields; air/ground WATER behavior is a matrix obligation.
- New source hashes/protocol reject old v1/v2 receipts; the current failed receipt
  never authorizes v3. Preserve all accumulated evidence on probe error as before.

`test_placement.py`:

- Hash-pin/read the preserved failed v2 receipt as HISTORICAL classifier evidence,
  require exactly the original two mismatches and empty physics arrays, then compare
  repaired static classes against all145 exposed native codes. This is an unexecuted
  regression using prior observations, not a new native/physics PASS.
- Add generic non-card-specific enemy-side spell precedence and uniform variant
  tests, missing/mixed/cyclic variant refusal, complete145 structural proof fixtures,
  missing-class refusal, and explicit stale-v2 rejection. Existing exact proof-byte,
  geometry/class/relocation, actual candidates/fallback/opponents, hidden invariance,
  positive actual B roots, no-export and zero-FAILURES obligations remain unchanged.
  The raw historical JSON is a test input only, never a player input or proof fallback.

`run.py`, response to R19-P1:

- Require and raw-hash `src/clasher/rl/contract_v5_tokens.json` at BOTH normal Runtime
  root and effective selected serving root. Selection is unchanged:
  CLASHER_EVAL_RUNTIME_ROOT -> CLASHER_ROOT -> normal root, matching paths.setup.
- Deduplicate equal resolved token paths. A required missing/non-file path raises an
  actionable error; it cannot silently disappear from a glob. No unrelated JSON
  output trees are scanned. Existing entire Python serving closure, checkpoints,
  native/installed simulator files, gamedata/catalogue/vocab, exact proof bytes,
  calibration/arena/cards, raw+canonical level cache, behavior env, scope and source
  checks remain. Existing before/after preparation and child rehash fences now bind
  raw token data as well as semantic config/vocab digests.
- Require v3 proof identity. Scope-less all11 exception remains unchanged and only the
  original exact DEV bank below is authorized for proposed diagnostics. Primary
  still requires exact registered bank.scope before actor installation/resume/forks.

`test_harness.py`, R19-P1 coverage:

- Normal/alternate fixture roots now supply required token files. Tests cover normal
  serving, explicit evaluation-root override, and CLASHER_ROOT fallback with absent
  evaluation-root env; equal paths appear once in the manifest.
- Valid JSON formatting-only mutation at the actual token relative path changes
  runtime identity and rejects an otherwise successful-row resume. Parsed JSON,
  loaded semantic config/vocab/prior and ALL other identity fields/weights/raw inputs
  remain fixed. Normal and alternate roots both exercise this requirement.
- Missing normal OR selected token data fails closed. A formatting mutation during
  mocked preload also exercises the actual experiment before/after preparation fence
  and must stop before resume/forks in all three root-selection modes.
- Existing all-done parent/identity/resume/scope/proof/cache/source/model checks stay.
  No isolated fixture mutates the frozen runtime/token file.

## R19 response and remaining limits

R19-P1 is implemented in source and awaits fresh review/execution, not declared closed.
R15 Python closure repair remains intact; no runtime policy/model/features changed.
R19's incomplete-classification validator concern is strengthened to exact145 names.
R19's flying caveat is retained explicitly; recording flying is not a parity assertion.
Raw normal01 token hash independently read unchanged:
`5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0`.
The reviewed execution environment must still leave CLASHER_EVAL_RUNTIME_ROOT absent
or resolving to the normal authorized Runtime; hashing alternatives is not approval
to run an unreviewed alternate source tree.

No card/population subset is proposed: all145 native rows remain checked, including
Tornado and MergeMaiden. Accepted restricted prior/projections/counts/mass are unchanged;
there is no extra exclusion or L11/metadata fallback. A public identity unavailable in
the planning vocabulary still fails closed under the existing rule. Metadata support
for a variant is not a claim that new variant mechanics are supported by the121-card
planner. Both static precedence repairs must be confirmed by the new probe; matrix
physics remains unmeasured at v3. No LIVE claim, deployment or primary outcome inference.

## Sequential owner commands AFTER NEW independent review

Parent alone obtains new review, syncs only reviewed owned files, verifies deployed
hashes and launches. No concurrent source/cache writers, exporters, diagnostic jobs
or duplicate runs. Read resource admission/full-pool priority before launch. Existing
CPU wrapper/nice10, bytecode off, math threads1, GPU hidden, hashseed0. On01 only;
no05 compute/09–18/native/frozen/live writes or03 retry. Every output must be new;
failed R14/R17 receipts and logs stay untouched. Commands are proposals for review,
not execution authorization from this source writer.

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
set -o noclobber
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.placement_probe --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json > /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.txt 2>&1
```

Inspect terminal0, exact installed/source/data pins, all145 native class records,
Cannon64 (32territory+8WATER+24OK), all16 precise inward-box settlements, complete960
matrix and original18. Any class/schema/reason/geometry contradiction or incomplete
receipt STOPS dependent commands. No automatic retry or expected-verdict waiver.
Only after complete successful interpretation at final bytes:

```bash
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r21.json
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-placement-r21.txt 2>&1
```

All five files/full integration1 required; no integration skips or export builds.
Only after matching-byte tests PASS:

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-placement-r21.txt 2>&1
```

Require every unchanged substantive obligation:254 checks unless a legitimate count
change is explained,121 exports/13 tower checks/32 public bodies/30each cut-snapshot-
raw-fc/A-B-A distinct-reused keys/shipped[1,2,2]/4 actual fair B decisions and positive
roots. Inspect both raw snapshot differences; no numeric/type/entity/order/position/
qualified-key waiver. Only previously source-proven absent string defaults normalize.
After all reviewed prerequisites pass, unchanged original bank SHA
`b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a`, fresh output:

```bash
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21 --arms A,B --all11-gate --start 0 --count 4 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21.txt 2>&1
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r21-report.txt 2>&1
```

Require8 unique complete clean terminal rows,4of4 full-command A/B hashes, positive B
roots in all4 B rows, both seats/controllers, zero errors/rejections/native FAILURES/
child failures/placement failures, parent+child exit0, exact provenance including raw
tokens, and both-seat command_events. No old-output resume or primary registration.
The ordinary report follows clean runner acceptance; a failure can be inspected only.

Max Python processes: probe1, tests1(one Runtime), native2(parent+one pool child),
all11 runner3(parent+two serial games), report1; commands sequential, allowance<=16
including parents. No pooled LIVE inference. Parent handles further review/execution,
DESIGN amendment/logging, and any later primary decision. Rollback uses standard A
outside this experimental factory/removes experimental wrappers, preserving evidence.
Strict silence for future/resumed work: no routine DMs/acks/polls; essential blocker/
action questions only direct parent auto, max2sentences/1path, no input tools/children.

## Focused patch and source hashes

Patch baseline is the exact R19-reviewed R17 five-file bytes, copied before edits to
`/tmp/levels-placement-r21.e9YoAm`. New patch:
`/mpac/sdicks02/jobs/clasher/bot-levels/placement-r21-implementation.patch`.
Manifest includes all five changed sources, unchanged relevant dependencies, historical
probe test input and source-audit inputs. Hashes are review identities, not executions.

```text
1301a07011ac40bae28de0298b1643599e4dfaf1707521f7d6b463fe09ff5e44  bot/levels/placement.py
e96be73dacab0a5d70afb33f4aa9e570fc6c052277651e30a8b01180dda89deb  bot/levels/placement_probe.py
372612aef24367b98bbb465bd27aca9668fc3f215f800680810a61db590ce9b1  bot/levels/test_placement.py
1c9d80e9d2cc5a031a33839b1e54e7a1d19253065affc816453149d96ee8f061  bot/levels/run.py
a7019ef1452fc35c7e28037d70e6217b82728a62a30bcc787462c4b3e9ebf9ab  bot/levels/test_harness.py
20521d5468f86f7605094fcb37bd497a10389998e04c11930426e9ce5e66af9f  bot/levels/player.py
2e4eaf6a1691b34bec4f1aaf54221fc2923a419edb3aed676bee11f36d30b4c3  bot/levels/gates.py
9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3  bot/levels/configs.py
fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8  bot/levels/root.py
0ae75da5a978d9cac4a52125afc5cefcd123c58d170d285930ed1ff41e9065b2  bot/levels/scope.py
7a705926bd69a3b1a31f2951bc0ef53f69b931e09158a3ee4e79c3c437d56620  bot/levels/bank.py
2a828a846173ea33cbb0a11fc06566ce2e213f28769063dd079cdeaa270d72df  bot/levels/profile.py
43c943c2b2b1065215737191c114a9f0cbdf5398c860d09e6a77f5df215798e7  bot/levels/report.py
d6fcbbd8151710c7d7a4220db5c9e6790fb9efa336b1a4679154426414363165  bot/levels/run.sh
35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029  bot/players/royalesim_match.py
7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c  bot/players/runtime.py
8ce946cad30974abbd8ab3cc6fd32895b28d9377b84bd3c91799929e647f0ee3  bot/players/policy.py
a58a47875588691677a165f07678f48af103970f980b1f3b0baef8731fdeb1cd  bot/search/players.py
822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5  bot/live/levels.py
b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a  reports/bot/levels/receipts/all11-dev-cases.json
d0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4  /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.json
2e0b377bf304724cb815f787a2e011f3293b0b64b288c7b526109a310a6453d3  /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.txt
d9115358634e937ac3b4af6f60c9ae447370ad576f2c5df7f54706111feb8abd  /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r14.json
470cd8070a414f75a75146729299aa10211c066fd80c4fc0f5da0da7b12a655d  /mpac/sdicks02/jobs/clasher/bot-levels/placement-r21-repair-brief.md
1bcacf6cea70ba14842f3b4d9c2e1fb99fb8fabacd7f742dec420225541c4b28  /mpac/sdicks02/jobs/clasher/bot-levels/placement-manifest-review-sol-r19.md
d7118c559ba84c5800eb1a72a78ef021137c35d88523a78262ce04a1a5de2aa0  /mpac/sdicks02/jobs/clasher/bot-levels/placement-r21-implementation.patch
5c0b9133ef98875e1a0b2483beafd66d8f23635fdd77e7e176afd54ff8919fde  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/card.rs
8113da8f65509c58c4fce7b447b9be97598dca1284acc07c7c7eef5b49c3f7ab  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/py.rs
6ee15143ea110f3b6ad7e943a12e67fabc0970b6bfc1996bd662cfe9c1772566  /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/crates/royalesim/src/state.rs
```

Read-only01 data/source evidence (R = frozen live16402b-r2 Runtime, S = installed
python3.12/site-packages/royalesim; neither was modified):

```text
5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0  R/src/clasher/rl/contract_v5_tokens.json
ce87ef97679118f45ac179eda3df6eb9591d93a135e43177f45ac17829ab4a8c  R/imitation/evaluation/paths.py
97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb  S/royalesim.abi3.so
c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc  S/data/derived/cards.json
7fbe4b0dce373d49ec69f1cdaeb65047b1602ea58dd6ce3a79dfe9be03fe7169  S/data/derived/arena.json
4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf  S/data/calibration.json
```

Source-only diff whitespace check produced no diagnostics. No Python parsing,
imports/tests/project execution/sync/jobs occurred. Fresh independent review and
new exclusive v3 probe-first execution remain outstanding under the parent owner.
