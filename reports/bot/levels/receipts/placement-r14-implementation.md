# R14 common placement compatibility — implementation handoff, SOURCE ONLY

Worktree: `/mpac/sdicks02/repos/clasher-bot-levels` on05. Baseline for the focused patch:
published implementation commit `41df38a83efa239f99c11457503514b26db43a26`.
Read the full R13 territory diagnostic, DESIGN/PROGRESS/RESULTS and R12 harness review.
No Python imports, project execution, tests, synchronization, jobs, native/runtime/live writes,
GPU work, account actions or descendants. Read-only01 source/log inspection only.
No PASS is claimed for these bytes. R12 failed data and the absent primary bank/BASE are untouched.

## Source changes

- `placement.py`: version `rsim-own-half-intersection-v1`. Actual mask-builder instance wrappers
  on all three `R.bots` scripts and each actor's `poller.player.mask_builder`. Ordinary buildings
  intersect existing eligibility with own-frame rows0..14; no unmasking, footprint erosion,
  command relocation, native edits or simulator-state/check_deploy input. Identified troops,
  champions, spells and enemy-side-capable buildings retain their base masks, including low
  hand-confidence quirks. Mirror uses accepted public own history; missing/unclassifiable identity
  clears that slot. WAIT/ability values are preserved exactly.
- Full scope has distinct script-builder instances: installation verifies their actual identities,
  shared token vocabulary and gamedata path, rather than incorrectly requiring the poller's builder
  object. It checks actual core-to-script and poller-to-mask references before/after each act.
  Replaced/missing/unsupported paths fail closed. There are no class/global mask monkeypatches.
- `player.py`: every experimental A/B/B0 actor receives the same wrapper; the standard factory
  outside this pilot is untouched. B tower metadata comment now explicitly includes scripted crown
  spell lethality/Lightning ordering, as well as leaf normalization.
- `run.py`: installs in parent before any resume/fork and wraps the actual R3a/v1 opponent.
  Exact microprobe receipt bytes, binary/data identity and source hashes enter the parent identity;
  proof file and installed calibration/arena/card JSON enter runtime input hashes. Children verify
  inherited installation/proof against that identity. Actual installation paths, calls and removals
  enter every new row; missing/stale/unexercised evidence invalidates acceptance. Existing rejection,
  failure, provenance, exit, cleanup and completeness gates remain intact.
- Registered `bank.scope` must equal installed `rt.levels_scope` before installation/resume/forks.
  Missing scope is refused for primary; only a scope-less legacy all11 DEV bank is explicitly allowed.
  A present mismatching/malformed scope is refused in both modes. No bank/population changes.
- `test_harness.py`: adapts the parent mocks to the new unconditional proof/installation calls and
  asserts ordering before resume; adds missing/mismatched primary-scope early-refusal coverage
  and checks exact proof bytes plus installed calibration/arena/cards enter runtime hashes.

## Offline probe and tests

`placement_probe.py` needs no Runtime/model. Fixed 64 Cannon fixtures: both seats × four public
enemy-princess patterns × five original failed own-frame coordinates and three own-side controls.
Cannon is slot2, L11, tick100, elixir10000, zero command delay, no non-tower bodies. The installed
schema was checked against existing `rsim-probe-01.txt`: crowns are entity kinds2/3 and must not be
mistaken for non-tower bodies. It records raw tap verdict/result and reported resolved position;
accepted controls advance25 ticks to inspect the actual stationary Cannon position and establish
raw 3×3 cross-river-box relocation. Exact installed RoyaleSim0.1.34 binary/calibration/arena pins
are checked; cards JSON and both implementation sources are hashed. Output creation is exclusive.

A separate descriptive section adds18 Knight/Minions/Fireball taps: both seats, enemy princesses
down, known bridge edge (13,16), bridge interior (14,16), and home (9,10), all in own tile indices.
It preserves exact verdicts without changing nonbuilding masks or the Cannon64 acceptance rule.
**Inspect this section before accepting primary readiness.** The real-runtime integration also
cross-checks these verdicts against the actual public nonbuilding mask and fails on an admitted
simulator refusal; such evidence requires a separate reviewed correction, not an implicit rewrite.

`test_placement.py` covers actual pinned mask builders, Cannon/Tesla, all tower patterns/seats,
no unmasking/mutation, unchanged nonbuildings/specials/WAIT, public-history Mirror, unknown identity,
per-instance isolation/idempotence/path tampering, exact proof bytes and resume, scope guards and
malformed/unexercised diagnostics. Opt-in integration builds Runtime once, then exercises actual
A/B/B0 candidate generation, scripted/ranked/random/proposal eligibility, real policy fallback,
both R3a/v1 opponents and real decisions, checking no native FAILURES. It varies hidden opponent
deck/order/elixir/levels/pending command/invisible Ghost while demanding identical complete public
information, masks and decisions. Actual A/B0/B root snapshots are compared with fixed belief/RNG;
B uses its ordinary fixed estimator and requires additional root calls during act. Existing level
exports are preloaded; an explicit failing build override prohibits exports. Recorder on/off tests
check accepted/rejected command results and unchanged public information/events in both seats.

Parent-owned `bot/players/royalesim_match.py` recorder dependency is in the manifest below; this
worker read it and added integration coverage, without editing that file. Source hashes are also
automatically included by `run.source_hashes()`.

## Owner commands AFTER fresh independent review, on01 only

Do not execute any of these before review. Verify matching deployed bytes first; no concurrent
source/cache edits or owned jobs. Existing env hides GPU, disables bytecode, fixes hashseed0 and
math threads1. Keep each failed receipt/output; choose a fresh name if a path exists.

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.placement_probe --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r14.json > /mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r14.txt 2>&1
```

First inspect the complete64 Cannon verdicts/relocation controls,18 descriptive nonbuilding
verdicts, pins and terminal status. Contradictions block acceptance. Only then:

```bash
export CLASHER_LEVELS_PLACEMENT_PROOF=/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r14.json
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py > /mpac/sdicks02/jobs/clasher/bot-levels/dev/pytest-placement-r14.txt 2>&1
```

The integration flag is mandatory for the reviewed full test command; skipped integration is not
evidence. If tests fail (including a newly measured nonbuilding mismatch), stop dependent execution.
If approved by the fresh reviewer and after tests pass, rerun the existing native suite at new bytes:

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > /mpac/sdicks02/jobs/clasher/bot-levels/dev/gates-placement-r14.txt 2>&1
```

After all reviewed checks pass, use the same original four-case bank in a NEW manifest/output:

```bash
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r14 --arms A,B --all11-gate --start 0 --count 4 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r14.txt 2>&1
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r14 > /mpac/sdicks02/jobs/clasher/bot-levels/dev/all11-placement-r14-report.txt 2>&1
```

Require the original complete/terminal/clean provenance,4/4 A/B full-command hashes, positive B
roots, zero native failures/rejections/child failures, both controllers/seats and actual placement
diagnostics. Do not resume or reinterpret R12. Parent handles design amendment and any later primary
registration/execution. This receipt grants no primary acceptance and no LIVE/deployment inference.

Process maxima: probe1 Python, full tests1 (one Runtime), native cut suite2 (parent+one pool child),
all11 runner3 (parent+two serial game children), report1; these commands are sequential. Existing
CPU lease/nice controls apply and total authorized allowance remains ≤16. No host05 compute.

Rollback: remove the experimental placement integration and use a fresh standard A Runtime outside
the pilot; retain all failed records. Frozen native rollout placement remains a documented model
mismatch. No troop/spell/special geometry rewrite, tap movement, outcome exclusion or rejection
gate relaxation is implemented.

## SHA256 manifest (source bytes for fresh review, not execution evidence)

Focused patch: `/mpac/sdicks02/jobs/clasher/bot-levels/placement-r14-implementation.patch`.
Source-only whitespace inspection produced no diagnostics. No Python parsing/imports/tests ran.
Manifest includes the six owned changed files, the parent recorder, and relevant unchanged
root/cache/scope/bank/report/search dependencies. Reviewer must rehash before owner host touches.

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
262ba4712851df9754fab2e2d4b024aeb23fd68bde580685349b632151e82407  /mpac/sdicks02/jobs/clasher/bot-levels/placement-r14-implementation.patch
```

Communication constraint for future/resumed work: no routine progress/ack/poll/receipt DMs.
Only essential dependency/blocker/action handoffs direct to the immediate parent (auto mode),
max2sentences/1path. No user-input tools or descendants. Fresh independent review remains a
prerequisite to any new code/test/import/sync/host script execution; owner alone runs commands.
