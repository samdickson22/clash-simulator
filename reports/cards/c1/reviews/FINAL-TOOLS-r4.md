# C1 complete launcher preparation independent review r4

**REJECT** candidate `c7de06ea5a6171b4490682a7bb1be9baa825a2b4`: R4-1 leaves a cancellation window that can
skip child cleanup and its final provenance receipts. Correct it and obtain fresh independent commit-bound
approval before host execution. This verdict covers the complete revised preparation, not only the latest patch.

Reviewed `/mpac/sdicks02/repos/clasher-cards-c1`, branch `cards/c1`, 2026-10-16. Candidate tree:
`d525cc4b5957f58894b9f7991917a65360096fda`. Complete delta:
`476a747f75569040f9b137d0991691c95e6f1b29..c7de06ea5a6171b4490682a7bb1be9baa825a2b4`; focused delta:
`4bfae6b0844b4620d9482cc996a74bf86f1a1887..c7de06ea5a6171b4490682a7bb1be9baa825a2b4`.

Read the full original CARD LEAD rejection `C1-final-tools-r1.md`, full FINAL-TOOLS-r2.md and FINAL-TOOLS-r3.md,
all r2/r3/r4 implementation responses, current PROGRESS authority and full FINAL-GATE-PLAN.md. Inspected all
seven executable tools, tests, helper adaptations, relevant readpaths and documentation changes. All 43 files
in the complete candidate delta were read from the exact Git commit, hashed and matched against worktree bytes.
Historical defect-expecting review scripts were read as evidence only, never executed against revised source.

## Finding requiring correction

### R4-1 — P2: a stop at cleanup entry bypasses the mask and leaves known children running/unreaped

Location: `tools/final_gate.py:291–298`, especially the first masking statement at294; unconditional raising
handler at301–302, installed at328–329; outer error handling at336–343. This contradicts the repeated-stop
cleanup guarantee in `FINAL-GATE-PLAN.md:157–169` and FINAL-TOOLS-r4-response.md.

The mask protects cleanup **after** it has been installed. It does not protect entry into the finally suite.
After a first TERM/INT/HUP interrupts a wait, the phase finally restores the previous mask at197. The driver
then enters run_gate's finally with stop signals unblocked. If a second handler runs before the masking
statement at294 executes, `interrupted` raises again. The entire finally suite exits before `children.stop()`
at296. The outer main exception handler writes FAIL and returns1; it has no fallback child stop/reap operation.
Children were started in their own sessions at173, so exiting the driver does not itself terminate them.

This is a normal catchable-signal boundary, not SIGKILL/power loss. The first stop can also be an ordinary
failure with a live child, such as failure to start the next child; a subsequent first signal at cleanup
entry has the same effect. The issue is missing cleanup/status provenance and potentially continuing work,
not an observed false PASS: the reproduced cancellation still fails the driver.

Independent reproduction copies **only** the exact run_gate cleanup finally suite into a scratch function,
with a synthetic initial InterruptedError in its replacement body. A stdlib trace invokes the actual
AST-extracted `interrupted(SIGTERM, None)` at the line294 boundary, before any mask call. A registered fake
PID101 remains live; there are **zero mask, killpg and wait calls**, no fixtures-final-exits.json, and no
all-child-exits.json. The fake child's intended final status is never observed. No run_gate/main, OS signal,
real signal mask, Popen, worker or engine is executed.

Evidence: `r4-independent/cleanup-entry-reproduction.json` and independently repeated
`cleanup-entry-reproduction-rerun.json`. Exact reproduction is
`independent_checks.py:test_R4_cleanup_entry_second_stop_bypasses_reap_and_final_receipts`; its passing
assertions deliberately prove the defect and do not approve the launcher. A separate positive control
confirms cancellation deferred **after** masking is restored only after all final receipts exist. Thus the
new masking works inside its protected region; the unprotected entry remains actionable.

Fix cancellation handling so subsequent stop requests cannot raise out of entry into mandatory cleanup,
as well as cleanup itself. For example, latch the first cancellation and make later handlers non-raising
through unwinding, or have handlers record cancellation and raise only at controlled boundaries. Preserve
the rule that any cancellation prevents PASS. Continue stopping/reaping only known child groups and retain
complete phase/all-child exits. Add mocked controls at cleanup entry before masking, during phase-receipt
unwind, and on pending-mask restoration, including prior successful/failed children. Merely moving another
mask call to a later finally statement leaves the same entry problem. Preserve this failed evidence.

## Complete repair assessment

The specific R3-1 lost-local-row defect is corrected. `Children.completed` at153–159 persists observations
by label before live deletion at188–190. Cleanup preserves an existing row at207–209, retaining its original
status/time without duplication. The phase finally writes partial observations; final phase and all-child
receipts retain the union when cleanup is reached. Fresh tests cover both fixture2/root8 sizes, every later
wait boundary, and prior exit0/17/signal-15: 24 combinations. Additional tests interrupt after wait returns
but before storage, and after storage but before live deletion. These preserve the exact original status.
R4-1 concerns reaching this cleanup, not recurrence of R3-1's discarded local list.

Expected phases are registered before fixture/root/comparator starts at249/264/281. Fresh mocked spawn
controls confirm registration precedes deferred cancellation and that an exec failure can produce an empty
final phase receipt. The worker resets its inherited mask at gate_worker.py:11 before bootstrap/dispatch.
The normal timeout cleanup control confirms TERM, then KILL on only the tracked PGID, followed by a wait and
signal-9 receipt. All mask/kill/Popen operations in these checks are inert mocks.

- **F1:** each of two fixture parents, eight root workers and the comparator is individually waited, with
  nonzero/signal exits rejected even after complete output. Fixture exit/audit failure prevents roots;
  root exit/audit failure prevents comparator/PASS. Original status-preservation repair now works when
  cleanup runs. R4-1 prevents full approval of the interruption/cleanup contract.
- **F2:** final_gate_contract.py:90–222 and final_gate.py:94–150 enforce complete exact inventories,
  canonical relative paths, duplicate-free JSON, no input links/special files, full engine and bot Git
  archive matching, B2 ancestry, native roles, running tools, and typed matching B2/integration/build/test/
  launcher-review/platform evidence with affected-case identities and raw artifact hashes. Fresh archive
  mocks cover full/engine/tools argv and reject symlink/submodule modes. Read-only real Git queries at
  this candidate succeed for all three forms. Approval and artifact truth remain owning-lead authority;
  these hashes bind bytes/identities, not human authenticity or whether raw evidence actually proves PASS.
- **F3:** owned canonical private directories, fresh initial entries, persistent exclusive claim, nofollow/
  exclusive outputs, reserved helper files under a nonwritable directory, and atomic no-clobber PASS remain
  present at final_gate.py:33–52,236–241,315–343. Synthetic symlink-parent, stale/dangling PASS and external
  sentinel controls reject without truncation. Publication-tail-only checks verify successful publication
  and PASS removal/FAIL creation on an injected exception immediately after the link. No host main ran.
- **F4:** original ready/manifest bytes and the complete original inventory are retained at87–91,96–104;
  checks at248/262/280/287 precede fixtures, roots, comparator and completion. No replacement baseline is
  generated. Fresh controls reject tool content changed with original modes restored and replaced manifest
  bytes, in addition to the submitted changed-control/added-file tests.
- **F5:** env-i precedes the unchanged CPU wrapper and driver; bash-p prevents inherited BASH_ENV. The
  documented invocation supplies identity-derived USER before both cpu_room.sh ps selectors. MIN_ENV
  excludes stale roots, pins, Python path/optimization and preload settings. Workers fix r1, remove EVAL,
  isolate paths and enforce frozen base_prefix/version and seed/flags. Fresh inert bootstrap controls
  cover both arms and reject each incorrect flag before dispatch. Real stdlib-only flag probes produce
  `0 True 1 1` under `-P -s -S -B` and `1 True 1 1` under `-I -S -B`, both with seed0. Nice15, single-thread
  libraries and the direct-parent eight-slot lease are retained. The control interpreter alone uses-I.
- **F6:** final_gate_contract.py:225–263,285–354 derives 577 fixture IDs/ticks/plays from the frozen input,
  and exactly 300 deterministic roots with four shards and full/cut pairs. It validates chain/action
  schema and counts, digests, root identities, action selection, rollout/evaluation/view/mask/select/step/
  apply counts and complete headers. Submitted identity/schema/count/header negatives pass. Fresh small
  synthetic inputs check train/validation filtering, duplicate split rejection, action/end/champion
  boundaries, deterministic sampling and changed config rejection. Historical lockstep residuals remain
  allowed; they are not silently reclassified as Python/native agreement.
- **F7:** current authoritative prose correctly says **through expiry (10 updates to expiry)**. The
  unchanged follow-up breaks on the first missing shot at180–183. It does not test ten post-expiry updates;
  no new simulation or additional coverage claim is made here.

The two r2 defects remain corrected: full archive queries omit an empty pathspec, while prefixes and prefix
stripping remain intact; identity-derived USER precedes CPU accounting. The parent-discovered hashseed issue
also remains corrected. No intentionally missing future readiness value was counted as a code defect.

## Helper compatibility and readpaths

Fresh tests reverse only the documented adaptations and recover exact bytes of all three historical
native-total-tools helpers. Fixture changes relocate rp.D on all three entry paths and expose the existing
action_results list. Root changes relocate the bot import root and expose legal actions/runtime/policy
metadata. The descriptive comparator is byte-identical. Historical fixture pools, ordering, sample seeds,
four shards, action/style budgets, cumulative steps and chains are preserved.

Read fixture.py/rs_parity.py to check loader split/start/end/action behavior; Runtime bootstrap, native_parity
and lopp_fast to trace runtime/native/resource paths and root operations; differential, paths, es_common,
fair_player, quickwin_resources and c56_controller as source only. Runtime-added paths derive from frozen
runtime/bot roots; differential's report path resolves under the materialized runtime. es_common's existing
results directory must be staged in the frozen runtime for its import-time mkdir(exist_ok=True). These
observations do not verify the actual future standalone dependency bundle or import it. Owner-authenticated
runtime/Python/data closure and subsequent authorized host validation remain required.

Engine/native source, the approved snapshot comparator and follow-up have no delta from476a747f. Comparator
SHA256 remains `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`; follow-up remains
`60be8aaf65052557b333d5fe6cfd74636841d55ff7c4a3eef15835e1d66a3208`. Prior comparator approval retains its
selected-field/readpath scope. No full byte equivalence or actual final follow-up raw-file authenticity is
established by this review; the original owning-lead authenticity requirement remains explicit.

## Exact verification commands, exits and scope

All commands below used CWD `/mpac/sdicks02/repos/clasher-cards-c1`. Exact argv/environment, result codes,
58 read-only Git/syntax/flag checks, all 43 candidate file hashes, readpath hashes, preserved-artifact hashes,
test source/log hashes and raw full/prefixed listings/deltas are in `r4-independent/receipt.json`.

```bash
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r4-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/tools/test_final_gate_contract.py > reports/cards/c1/reviews/r4-independent/submitted-tests.log 2>&1
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r4-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r4-independent/independent_checks.py > reports/cards/c1/reviews/r4-independent/independent-tests.log 2>&1
/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r4-independent/record_review.py > reports/cards/c1/reviews/r4-independent/record-review.log 2>&1
bash -n reports/cards/c1/tools/final_gate.sh
git diff --check 476a747f75569040f9b137d0991691c95e6f1b29 c7de06ea5a6171b4490682a7bb1be9baa825a2b4
git diff --exit-code 476a747f75569040f9b137d0991691c95e6f1b29 c7de06ea5a6171b4490682a7bb1be9baa825a2b4 -- engine-cards reports/cards/c1/tools/probe_snapshots.py reports/cards/c1/tools/probe_snapshot_followup.py
/usr/bin/git --no-replace-objects ls-tree -r -z c7de06ea5a6171b4490682a7bb1be9baa825a2b4
/usr/bin/git --no-replace-objects ls-tree -r -z c7de06ea5a6171b4490682a7bb1be9baa825a2b4 -- engine-cards
/usr/bin/git --no-replace-objects ls-tree -r -z c7de06ea5a6171b4490682a7bb1be9baa825a2b4 -- reports/cards/c1/tools
```

Results: **16 submitted groups PASS**, **16 independent groups PASS**, collector exit0 and all58 recorded
checks exit0, Bash syntax0, diff-check0, protected-source delta0/empty, full/engine/tools listings0. All seven
Python files parse. Independent PASS includes the deliberate R4-1 finding reproduction.

The first independent run exited1: 15 groups passed; the timeout escalation control hit a review-harness
AttributeError because its inert signal namespace omitted SIGKILL. Added that constant to the mock only;
all16 then passed. The first script/log and first cleanup-entry reproduction are preserved as
independent_checks-first-attempt.py, independent-tests-first-attempt.log and cleanup-entry-reproduction.json.
No production source changed. Two exploratory source reads returned2 for guessed nonexistent helper paths;
rg located the correct engine-speed/stage5/fair_player.py and engine-cards/quickwin_resources.py, which were
then read/hash-bound. These were read-location errors, not production failures.

No actual driver main/run_gate/worker/helper/launcher/staging/host script, engine/native import, simulation,
build, remote command, emulator, deployment, pin operation, child delegation, commit, push or other-worktree
write. Bash was syntax-only. Bootstrap/cleanup/publication checks execute isolated AST snippets with inert
dispatch/process/signal operations; no OS masks or signals were changed. Real Python child probes only print
stdlib interpreter flags. Scratch writes are confined to r4-independent; the sole additional write is this
requested report. No old review script was rerun or receipt overwritten. All r3 receipt-indexed artifacts,
including untracked large .bin/.delta files and failed harness/reproductions, still match their original
hashes. The original untracked peek.py and snapcmp_probe.py remain untouched and match r3's recorded hashes.

Accepted/integrated B2, actual combined-source build and affected tests, owner-authenticated full dependency/
input/platform inventory, duplicate-job audit and fresh C56 remain external prerequisites. Their absence is
not a placeholder code defect. This REJECT grants no host execution, integration/gate/engine acceptance,
full-byte-equivalence claim or live-pin promotion. Human approval/raw artifact authenticity remains explicit
owning-lead authority; content hashes only bind evidence identities and bytes.

## Exact identities and tool hashes

- Candidate: `c7de06ea5a6171b4490682a7bb1be9baa825a2b4`.
- Tree: `d525cc4b5957f58894b9f7991917a65360096fda`.
- Full binary delta SHA256: `3da2e8796dc79fb475e7c8d4ccd4b0d0c4ba49730cae512d5db69c2222a9daf3`.
- Focused binary delta SHA256: `ab3ff1ef36ea28b250bb0ae7579e11a421bd93cf978aa9ce76a3df6d0ce20fc2`.
- Full candidate ls-tree bytes SHA256: `0a417f18974018b0d9c683dc2625d91f0f5e7f854d3b010a87b24112da04c07c`.
- final_gate.py: `393a4a450328e66289663338f3887dea3f3a66fe01b384751e7401cf7a5e4f00`.
- final_gate.sh: `297fbbb2f0c0e3f4c4368afdd4245b78792408075ce94f655dc7bc8209caf1d5`.
- final_gate_contract.py: `222c69314e26d5aefcc3ad04a602ccac6e207ee7d22c65a5930a18d8ad291ad8`.
- gate_worker.py: `b67704d4f0c6f68e690a585ef7ffa22927bcc1ef4c7592ed9c75c910de5afdb4`.
- gate_fixtures.py: `8737b53fde2966d14ce6359cd0c3e5e24cc783bb9c7b1348b3ff468df2cfbf21`.
- gate_roots.py: `155cbdb4b11ea8239057600e191465f073418f648070ee8f20f14cab25aefc5f`.
- gate_compare.py: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.
- test_final_gate_contract.py: `47172615f2836c5150ad5bc48b91da68a91e290021f3ac92a72f707f06fc47dc`.
- FINAL-GATE-PLAN.md: `e6af124e3565a777cde1a5295d29fbe17c2114548626c42a888396c1ef145a87`.
- PROGRESS.md: `2112b133aee7a6d2da0aa95dd8fb157822d94c1917e7861cf2a744f4fe518cff`.
- RESULTS.md: `fa2edd48f854d6205033633888e46a3a31cee667cbc02be8a75aeed1668224b4`.
- SNAPSHOT-DIAGNOSTICS.md: `5136eb6f3f80881a040e217e3e88220e146b0f83b2858dba7eef81856f9dbe01`.

All43 candidate delta file hashes are also listed in r4-independent/reviewed-hashes.md. HEAD remained the
exact candidate throughout. The final seal binds this report, machine receipt and preserved evidence.
