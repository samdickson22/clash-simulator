# C1 complete launcher preparation independent review r5

**APPROVE** the complete revised launcher repair at exact candidate
`97171f531a31f9663f74ff95093d58053125860d`. No actionable code finding remains from this review.
R4-1 is repaired by the record-only cancellation architecture, and the complete F1–F7 repair and earlier
R2/R3 corrections remain consistent with their source, helper readpaths and local negative controls.

This approves launcher **preparation**, with the prerequisites below still required. It establishes no actual
host/engine coverage, B2/integrated acceptance, full byte equivalence or live-pin authority.

Reviewed `/mpac/sdicks02/repos/clasher-cards-c1`, branch `cards/c1`, 2026-10-16. Exact candidate tree:
`a70fd27a61f02b377fb2cd79105bafc1857a895d`. Complete reviewed delta:
`476a747f75569040f9b137d0991691c95e6f1b29..97171f531a31f9663f74ff95093d58053125860d`.
Focused reviewed delta:
`c7de06ea5a6171b4490682a7bb1be9baa825a2b4..97171f531a31f9663f74ff95093d58053125860d`.

Read the full original CARD LEAD `C1-final-tools-r1.md`, full FINAL-TOOLS-r2/r3/r4, all four r2/r3/r4/r5
response files, current C1 PROGRESS authority and full FINAL-GATE-PLAN.md. Inspected all seven executable
tools, current tests, complete source/documentation changes, historical helper originals and relevant
dependency readpaths. All 62 files in the candidate delta were fetched from this exact Git commit, hashed
and matched against worktree bytes. Historical defect-expecting review scripts were read as historical
evidence, never executed against this revision. Their original receipts and failures remain intact.

## Cancellation and cleanup assessment

- `final_gate.py:300–307`: `interrupted` only latches the first nonzero stop value. It performs no I/O,
  signal-mask operation, cancellation check or raise. Further TERM/INT/HUP requests cannot raise out of
  arbitrary bookkeeping, phase-receipt unwinding, cleanup entry or cleanup itself. The parent driver has
  no remaining pthread_sigmask calls, so the rejected mask-entry window is absent.
- `final_gate.py:166–174`: cancellation is checked before spawning and after the returned PID is stored.
  A stop during Popen is recorded while PID registration completes; the later check unwinds through the
  already-established run_gate finally. Phase labels are registered before spawn at252/267/284. A failed
  spawn leaves the attempted phase represented by its final receipt, including an empty phase if no PID
  was returned. No success is inferred from an incomplete phase.
- `final_gate.py:176–199`: individual waits poll with timeout1. A timeout returns to a controlled check;
  an observed exit is persistently stored before removal from live state and before cancellation is
  checked. Phase-exits.json is written even when the later checkpoint or wait raises. This retains R3-1's
  correction, including earlier exit0, exit17 and signal statuses.
- `final_gate.py:201–220,294–297`: mandatory cleanup contains no cancellation checkpoint. The handler
  cannot escape its first instruction, TERM/KILL/wait operations or final phase/all-child receipt writes.
  Existing completed rows retain their original status/time and are not duplicated or overwritten. Only
  registered child PGIDs are addressed. Timeout cleanup escalates TERM to KILL and waits for the known PID.
- `final_gate.py:335–351`: the latch is checked after cleanup/gate return, after exclusive temporary PASS
  creation and after linking/removing the temporary name. A stop observed before the final checkpoint
  removes PASS and returns1 with FAIL. An exception immediately after the actual scratch link does the
  same. Repeated stops during FAIL writing remain record-only. The checkpoint at342 commits success;
  a later request at the return boundary is after that commit, as explicitly documented at plan171–173.
  The independent test checks that boundary rather than claiming cancellation can revoke completed work.

Fresh independent controls inject repeated direct calls to the extracted handler at **27 executed cleanup/
receipt helper line boundaries**, including cleanup entry, with both normal entry and an ordinary initial
failure: **54 combinations**. Every case stops/waits the fake child and writes final phase/all-child receipts;
the original ordinary failure survives. Additional checks cover every later fixture2/root8 wait boundary
after prior0/17/signal-15 (**24 combinations**), a stop as wait returns before status storage, cancellation
before/during spawn, ordinary exec failure, timeout escalation, and publication line boundaries335/336/337/
338/340/341/342/343. No real process signals, masks or gate processes were used.

The worker's defensive inherited-mask reset remains at `gate_worker.py:11`; normal exec resets the parent's
caught Python signal dispositions before worker execution. Bootstrap snippets were exercised with an inert
mask operation and inert runpy dispatch only. Real worker or descendant cancellation was not exercised.

## Complete original repair assessment

- **F1 — APPROVE:** `final_gate.py:176–220,249–297` individually waits two fixture parents, all eight root
  workers and comparator. Complete-output exit17/signal-9 still fails. Fixture status/audit rejection occurs
  before roots; root status/audit rejection occurs before comparator; comparator status/summary rejection
  occurs before PASS. Partial/final phase and all-child observations survive cancellation as assessed above.
- **F2 — APPROVE:** `final_gate_contract.py:45–124,149–222` and `final_gate.py:95–151` enforce canonical,
  duplicate-free, exact no-link lstat inventories; full engine and bot archives authenticated to declared Git
  commit/blob content; B2 ancestry; both native roles; executing driver/tool identity; typed matching B2,
  integration, build, affected-case, independent-review, platform and raw-artifact bindings. Exact full,
  engine and tools Git query argv are tested, including forbidden symlink/submodule modes and corrupted
  commit/blob bytes. Actual read-only queries at this candidate succeed. Human approval and the truth of
  arbitrary raw evidence remain the owning lead's explicit authority; content hashes do not authenticate
  those claims. This approval does not fill any future receipt or attest a platform inventory.
- **F3 — APPROVE:** `final_gate.py:34–53,238–243,320–350` requires owned canonical private output/run
  directories, exact fresh initial entries, persistent exclusive claim, nofollow/exclusive files and reserved
  helper outputs under a nonwritable directory. Stale/dangling PASS and output links cannot be silently
  reused. Independent symlink-parent and external-sentinel checks reject without truncation. Atomic
  no-clobber PASS publication and exception/cancellation removal pass the isolated publication-tail checks.
- **F4 — APPROVE:** `final_gate.py:88–108,150,251,265,283,290` retains the original validated control bytes
  and complete inventory, checking those same originals before each phase and at completion. No replacement
  trusted baseline is generated. Changed tool content with restored modes, replaced ready/manifest bytes,
  and added/missing/unrelated inventory entries reject in local controls.
- **F5 — APPROVE:** `final_gate.sh:1–7`, `final_gate.py:22–24,230–248`, `gate_worker.py:14–31` and plan178–189
  retain env-i before wrapper and driver, bash-p, explicit seed0 and worker -P/-s/-S/-B flags, frozen Python
  prefix/version guards, explicit r1 policy, per-arm runtime/native paths, EVAL removal, disabled bytecode,
  nice15 and single-thread library settings. Identity-derived USER precedes unchanged cpu_room.sh's two
  ps selectors. Both arms and every wrong flag/prefix/version rejection were independently checked with
  inert dispatch. Stdlib-only real flag probes confirm worker `0 True 1 1` and control-I `1 True 1 1`.
  The eight-slot direct-parent lease check remains at330–332. No CPU wrapper or ps command was run.
- **F6 — APPROVE:** `final_gate_contract.py:225–263,285–354` derives the actual 577 train/validation fixture
  identities, end/start tick and eligible-action counts from frozen inputs; checks required chain/action/
  residual schemas and digests; derives the deterministic300 root sample; validates every shard's150 full/
  cut records, source identity, legal-action sampling, rollout/evaluation/view/mask/select/step/apply counts
  and complete headers. Driver fixture and root body comparisons remain byte-exact across arms. Submitted
  fabricated-ID, empty-chain, missing-check, bad-count/metadata/header negatives pass. Independent small
  synthetic inputs verify actual expectation derivation, filtering, action/end/champion boundaries,
  duplicate split rejection, sampling order and config-content rejection. Historical lockstep residuals
  remain allowed; they are not misreported as Python/native agreement.
- **F7 — APPROVE, prose only:** SNAPSHOT-DIAGNOSTICS102, RESULTS and current PROGRESS correctly state
  **through expiry (10 updates to expiry)**. Unchanged `probe_snapshot_followup.py:180–183` stops at removal.
  This revision makes no ten-post-expiry coverage claim and no new simulation was needed or performed.

The R2 startup corrections remain functional: full archive queries omit the empty pathspec; prefixed queries
retain it and strip the prefix; CPU accounting receives identity-derived USER. The parent-discovered worker
hashseed correction also remains in place. No deliberately deferred code finding remains.

## Helper/readpath compatibility and limits

Independent reversal of only the declared adaptations recovers exact bytes of all three historical
native-total-tools helpers. Fixture changes relocate rp.D at all three entry paths and expose the existing
action_results. Root changes relocate the bot import root and expose legal_actions/runtime/policy metadata.
The descriptive comparator is byte-identical. Pools, episode order, sample seeds, four shards, historical
rollout arguments/styles, cumulative1/50/200 steps and chain operations remain unchanged.

Source-only reads of fixture.py/rs_parity.py confirm split/start/end/action semantics and residual record
shape. Runtime/native_parity/lopp_fast, differential, paths, es_common, fair_player, quickwin_resources and
c56_controller trace native/resource/gamedata/config and transitive report imports under materialized
runtime/bot roots. The es_common import-time mkdir requires its existing results directory in the frozen
dependency bundle. Actual standalone Python/dynamic-library/dependency closure remains owner-authenticated
future staging and authorized host validation; no such modules were imported by this review.

No engine/native source, approved snapshot comparator or follow-up code differs from476a747f. Comparator
SHA256 remains `aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`; follow-up remains
`60be8aaf65052557b333d5fe6cfd74636841d55ff7c4a3eef15835e1d66a3208`. The earlier comparator approval retains
its selected-field/readpath scope. Original final follow-up raw-file authenticity limitations remain; the
owning lead must obtain/hash/inspect those actual files before admitting them as coverage evidence.

## Exact local commands, results and evidence

CWD for all checks: `/mpac/sdicks02/repos/clasher-cards-c1`. The collector's 80 exact argv/result records,
environment overrides, UTC times, stdout/stderr hashes, complete/focused deltas, full/prefixed raw Git
listings, all62 candidate file hashes, readpath hashes and61 preserved-artifact hashes are in
`r5-independent/receipt.json`. Test source and logs are new r5 artifacts; no old review script was rerun.

```bash
/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r5-independent/record_review.py > reports/cards/c1/reviews/r5-independent/record-review.log 2>&1
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r5-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/tools/test_final_gate_contract.py
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r5-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r5-independent/independent_checks.py
/bin/bash -n reports/cards/c1/tools/final_gate.sh
/usr/bin/git diff --check 476a747f75569040f9b137d0991691c95e6f1b29 97171f531a31f9663f74ff95093d58053125860d
/usr/bin/git diff --exit-code 476a747f75569040f9b137d0991691c95e6f1b29 97171f531a31f9663f74ff95093d58053125860d -- engine-cards reports/cards/c1/tools/probe_snapshots.py reports/cards/c1/tools/probe_snapshot_followup.py
/usr/bin/git --no-replace-objects ls-tree -r -z 97171f531a31f9663f74ff95093d58053125860d
/usr/bin/git --no-replace-objects ls-tree -r -z 97171f531a31f9663f74ff95093d58053125860d -- engine-cards
/usr/bin/git --no-replace-objects ls-tree -r -z 97171f531a31f9663f74ff95093d58053125860d -- reports/cards/c1/tools
```

The two test commands above are the collector's actual argv with TMPDIR override; it captures their streams
to submitted-tests.stdout/stderr and independent-tests.stdout/stderr. Results: **19 submitted groups PASS**,
**13 independent groups PASS**, collector exit0, all80 recorded commands exit0, Bash syntax0, diff-check0,
protected-source delta0/empty, three real Git listings0. All seven Python files parse. No failing synthetic
attempt occurred in this round. One exploratory sed read used a nonexistent engine-speed/c56_controller.py
path; the actual engine-cards/c56_controller.py was located, read and hash-bound. No production defect follows.

No actual driver main/run_gate/worker/helper/launcher/staging/host script, real OS signal/mask, engine/native
import, simulation, build, remote command, emulator, deploy, pin operation, child/delegation, production edit,
commit, push or other-worktree write occurred. Bootstrap/cleanup/publication executions were isolated AST
snippets with inert process/signal/dispatch operations. The only non-Git/syntax child probes use stdlib to
print interpreter flags. Scratch writes are solely under r5-independent; this requested report is the sole
additional write. All old failed logs/source/receipts/reproductions and local large .bin/.delta files remain
untouched; original untracked tools/peek.py and snapcmp_probe.py remain preserved. Final seal verifies the
historical receipt-indexed artifacts and this report/receipt identity without rerunning historical tests.

External prerequisites remain **B2 acceptance/integration before C1; actual exact-source combined build and
affected tests; owner-authenticated full platform/input/dependency inventory; duplicate-job audit; and fresh
C56**. Their intentional absence is not a placeholder code finding. No gate/pin promotion or host execution
is authorized by this source-review verdict alone. Owner approval and raw artifact truth remain human
owning-lead authority; hashes bind identities/content only.

## Exact identities and seven executable hashes

- Candidate: `97171f531a31f9663f74ff95093d58053125860d`.
- Tree: `a70fd27a61f02b377fb2cd79105bafc1857a895d`.
- Complete binary delta SHA256: `b90a0d0249715d9ef8950d5af9000b764cdd1d153d2ed32c990d05efa97c5719`.
- Focused binary delta SHA256: `b5e5b0c2ee566dcdae494d03da56f7367c82affc9a0cd4b86ff67a66c104ed1c`.
- Full candidate ls-tree bytes SHA256: `25ae18132d5465224ec2f08f309c03bae727a4c91e7c066fdd770d0928c97e09`.
- final_gate.py: `3cd4e36ce2c72721103ec7bf98086da65f1815747366060e4288ef42f6c67765`.
- final_gate.sh: `297fbbb2f0c0e3f4c4368afdd4245b78792408075ce94f655dc7bc8209caf1d5`.
- final_gate_contract.py: `222c69314e26d5aefcc3ad04a602ccac6e207ee7d22c65a5930a18d8ad291ad8`.
- gate_worker.py: `8966f1264a87a5237d33a1e7642fc632a31601ba62b38878876553e1b0038802`.
- gate_fixtures.py: `8737b53fde2966d14ce6359cd0c3e5e24cc783bb9c7b1348b3ff468df2cfbf21`.
- gate_roots.py: `155cbdb4b11ea8239057600e191465f073418f648070ee8f20f14cab25aefc5f`.
- gate_compare.py: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.
- test_final_gate_contract.py: `ba7a87cc37880c446542c8e8d58823b05dae5ff325559892c86fd5f888ea809a`.
- FINAL-GATE-PLAN.md: `6437b778c11165693c2a80a04446e28805eac5ec5e4799b4e8e2662c76dca0cf`.
- PROGRESS.md: `eefa2590e11ba2f39675246f4aad2eddd5305af317a6435f577016ec5ecab639`.

All62 candidate delta hashes are also listed in r5-independent/reviewed-hashes.md. HEAD remained the exact
candidate throughout. No production edit, commit or push was made by this reviewer.
