# C1 launcher preparation independent review r3

**REJECT** `4bfae6b0844b4620d9482cc996a74bf86f1a1887`: one reproducible failure-receipt defect remains.
Do not execute this preparation before correction and fresh independent commit-bound approval.

Reviewed branch `cards/c1` in `/mpac/sdicks02/repos/clasher-cards-c1`, 2026-10-16. Exact candidate tree:
`82f9e1a2d089799fc39ad2e25d52cd4ca16d2055`. Reviewed the complete launcher delta from
`476a747f75569040f9b137d0991691c95e6f1b29`, including all seven executable tools, tests, plan, current PROGRESS
authority, documentation corrections and preserved response/review artifacts. Also separately reviewed the
focused delta from rejected `c45854febf93352284dd9f76b02651d989d906a7`. Read the full original CARD LEAD
`C1-final-tools-r1.md`, full `FINAL-TOOLS-r2.md`, and both `FINAL-TOOLS-r{2,3}-response.md`.

This is a fresh independent review of this exact candidate, not continuation or execution of the old r2
defect-expecting tests. Their original source/logs remain preserved and were read as historical evidence only.

## Finding requiring correction

### R3-1 — P2: interruption during a phase loses exit receipts for children already waited

Location: `reports/cards/c1/tools/final_gate.py:163–172`, especially the deletion at170 before the append
to persistent bookkeeping at171; cleanup at175–189. The real signal handler at262–263 raises an exception,
and is installed for SIGTERM/SIGINT/SIGHUP at289–290. `run_gate` invokes cleanup in its finally at258–259.

`Children.wait` accumulates completed statuses in a local `rows` list, removes each completed child from
`self.live`, and only extends `self.rows` after **every** phase wait returns. If SIGTERM/SIGINT/SIGHUP arrives
while waiting for a later child, earlier rows are discarded during unwinding. Cleanup can see only children
still in `self.live`; it cannot recover the removed child or its exact status. It then publishes an
`all-child-exits.json` missing those completed children, and no phase receipt was written.

Independent reproduction uses only the AST-extracted `Children`/filesystem helpers, two fake child objects,
and an inert `killpg`. The first fake child, PID101, returns exit0 and is removed from `self.live`. The second,
PID102, raises `InterruptedError` on its first wait, simulating the installed signal handler. Calling the
actual extracted cleanup waits PID102 and writes `all-child-exits.json` containing **only fixtures-total**.
`fixtures-pinned` is absent, `self.rows` likewise lacks it, and `fixtures-exits.json` does not exist. No
process, signal, launcher, worker or engine was actually started. The same loop serves the eight-root phase.

Evidence: `r3-independent/interrupted-wait-reproduction.json` and independently repeated
`interrupted-wait-reproduction-rerun.json`; exact mock code is
`r3-independent/independent_checks.py:test_reproduce_interrupted_wait_loses_already_reaped_exit_receipt`.
The test deliberately asserts this defect; its passing result is not approval.

This fails the requested F1 status-preservation repair and the plan's explicit failure evidence promise
(`FINAL-GATE-PLAN.md:155–161`: per-phase and all-child exits on interruption/failure). It does **not** show
a false PASS: interruption still unwinds to failure. It prevents reconstructing the complete attempted run's
child/status provenance after an ordinary stop, including any already-reaped nonzero status.

Fix: retain each observed status in persistent child bookkeeping before removing that child's live entry;
preserve partial phase evidence when a later wait raises, and let final cleanup publish the complete union
of already-waited and stopped children without loss or duplicates. Add fixture/root interruption controls
after at least one prior successful and failed wait. Preserve these failed artifacts and obtain a fresh
independent review bound to the revised commit before host execution.

## Complete repair assessment

The two r2 startup findings and the parent-discovered hash-seed issue are corrected in this candidate.

- R2-1: `FINAL-GATE-PLAN.md:166–177` now supplies `USER="$(/usr/bin/id -un)"` inside the explicit environment
  before `cpu_job.sh`. Read the actual unchanged CPU wrapper/room helpers: both `ps -u "$USER"` selectors
  consume this identity. The inner driver/worker environments remain sanitized. No wrapper or ps ran.
- R2-2: `final_gate.py:61–84` omits the pathspec arguments for the full tree and retains `-- <prefix>` plus
  prefix stripping for engine/tools. Fresh mock checks assert the exact full/engine/tools argv separately.
  Actual read-only local full-tree and prefixed queries at the **new exact candidate** both exit0. The prior
  Git128 evidence remains historical and was not rerun as a current defect.
- Hash seed: `final_gate.py:199–216` uses explicit minimal environment, seed0 and worker flags `-P -s -S -B`,
  recording their effective contract. `gate_worker.py:11–14` enforces standalone base_prefix/version and all
  four flag properties before dispatch. Independent AST mocks cover both arms and rejection of each bad
  flag with inert runpy; real stdlib-only probes return `0 True 1 1` for these flags and `1 True 1 1` for
  `-I -S -B` under seed0. The control interpreter retains-I and performs no engine work.

Assessment against the original findings:

- F1: normal completion individually waits both fixture parents, all eight roots and comparator, rejecting
  nonzero/signal exits even after complete output. Fixture exit/audit failure prevents roots; roots are audited
  before comparator, which is waited before PASS. Submitted negative checks pass. R3-1 prevents full approval
  of the promised failure/interruption receipts.
- F2: `final_gate_contract.py:90–222` and `final_gate.py:94–150` require complete exact no-link inventories,
  canonical paths and duplicate-free JSON; typed accepted B2, integration, build, affected-case, independent
  review and platform/dependency evidence; raw artifact identities/hashes; full engine and bot Git content;
  B2 ancestry; both native roles; actual running driver/tool hashes; complete approved runtime/input/Python
  inventories. Full-tree startup is now functional. Human approval authenticity and actual raw artifact
  truth remain explicitly the owning lead's responsibility, as the plan correctly states.
- F3: `final_gate.py:33–52,206–211,266–304` rejects stale initial entries including PASS/dangling links,
  exclusively claims/creates private outputs, reserves helper files before making their directory nonwritable,
  and publishes PASS with atomic no-clobber linking. Additional filesystem checks reject a symlink parent
  and stale dangling PASS; AST-extracted publication-tail checks exercise success and an exception immediately
  after linking PASS, confirming PASS removal and FAIL publication. No host main ran.
- F4: original ready/manifest bytes are retained and compared with the full original frozen inventory before
  fixtures, roots, comparator and completion (`final_gate.py:87–91,218,231,248,254`). No replacement baseline
  is generated. Additional pure checks reject changed tool bytes after modes are restored and changed manifest
  bytes, supplementing submitted control-replacement/additional-file checks.
- F5: env-i precedes the wrapper and driver; bash-p blocks inherited BASH_ENV. MIN_ENV omits overlays, stale
  roots, pin selection, Python optimization/path variables and preload. Bootstrap fixes policy r1, removes
  EVAL root and selects the frozen arm/native paths. USER and hashseed corrections above are verified. Nice15,
  thread limits, eight-slot direct-parent lease and existing owner limits are retained in source.
- F6: `final_gate_contract.py:225–263,285–354` derives 577 expected fixture IDs/ticks/action counts, deterministic
  300-root sample/shards, full/cut pairing, schema/check counts and complete headers. Submitted fabricated
  ID/schema/count/header negatives pass while historical lockstep residuals remain allowed. Independent small
  synthetic fixture files exercise actual expectation derivation and end-boundary/champion/rejected-event
  filtering; synthetic root files confirm ordering/sample and rejection of changed config bytes.
- F7: current PROGRESS, RESULTS and SNAPSHOT-DIAGNOSTICS correctly say **through expiry (10 updates to expiry)**.
  The unchanged follow-up loop stops at removal; no ten-post-expiry coverage is claimed by this revision.

## Helper compatibility and readpaths

Independently reversed only the declared helper adaptations and obtained exact byte equality with all three
historical `reports/bot/learned-opponent/native-total-tools/` helpers. Fixture differences relocate `rp.D` at
all three entry paths and expose the existing action_results list. Root differences relocate the bot import
root and expose runtime/policy/legal-action metadata. Comparator bytes are unchanged. Pool sizes, ordering,
selection seeds, shards, rollout arguments/styles, cumulative steps and chain operations remain historical.

Read the fixture loader/rs_parity to confirm split filtering, start/end ticks and accepted-action timing; the
Runtime bootstrap/native_parity/lopp_fast sources to trace per-arm native/resource/action paths; engine
differential/es_common/paths and fair_player to trace frozen runtime imports and gamedata. Runtime installs
additional paths derived from its frozen root or the materialized bot root. Differential's report lookup
resolves under the materialized runtime. These are source/mock checks only: actual standalone Python/dependency
closure, runtime initialization and host filesystem behavior still require the later owner's authenticated
bundle and authorized validation. An existing results directory needed by es_common's import-time mkdir is
part of that materialized runtime/dependency staging; no such module was imported here.

No engine/native, approved snapshot comparator or follow-up code differs from476a747f. Comparator SHA remains
`aad00c4bed5418528db06308513f6edf66b12e0af9ca4c890dd8555bc5f150a8`; follow-up SHA remains
`60be8aaf65052557b333d5fe6cfd74636841d55ff7c4a3eef15835e1d66a3208`. The prior comparator approval retains its
selected-field/readpath scope. This review neither reruns engine coverage nor extends that approval to full
byte equivalence. The original final follow-up raw-file authenticity caveat remains in force.

## Commands, results and scope receipt

Exact argv, CWD, exit codes, hashes, raw local Git listings, complete/focused deltas, test sources/logs and
readpath identities are in `r3-independent/receipt.json`. All verification ran serially from the C1 checkout.
Scratch writes were confined to `reports/cards/c1/reviews/r3-independent/`; the only additional write is
this explicitly requested verdict. Full tested command strings:

```bash
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r3-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/tools/test_final_gate_contract.py > reports/cards/c1/reviews/r3-independent/submitted-tests.log 2>&1
TMPDIR=/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/reviews/r3-independent /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r3-independent/independent_checks.py > reports/cards/c1/reviews/r3-independent/independent-tests.log 2>&1
/mpac/sdicks02/repos/clasher-bot/.venv/bin/python -I -S -B reports/cards/c1/reviews/r3-independent/record_review.py > reports/cards/c1/reviews/r3-independent/record-review.log 2>&1
bash -n reports/cards/c1/tools/final_gate.sh
git diff --check 476a747f75569040f9b137d0991691c95e6f1b29 4bfae6b0844b4620d9482cc996a74bf86f1a1887
git diff --exit-code 476a747f75569040f9b137d0991691c95e6f1b29 4bfae6b0844b4620d9482cc996a74bf86f1a1887 -- engine-cards reports/cards/c1/tools/probe_snapshots.py reports/cards/c1/tools/probe_snapshot_followup.py
/usr/bin/git --no-replace-objects ls-tree -r -z 4bfae6b0844b4620d9482cc996a74bf86f1a1887
/usr/bin/git --no-replace-objects ls-tree -r -z 4bfae6b0844b4620d9482cc996a74bf86f1a1887 -- reports/cards/c1/tools
```

Results: **13 submitted groups PASS**, **10 independent groups PASS**, collector exit0 and all38 of its
read-only commands/flag probes exit0, bash-n exit0, diff-check exit0, protected-source diff exit0/empty,
full/prefixed Git query exit0. All seven Python tools parse. The independent PASS includes the deliberate
R3-1 reproduction and therefore does not imply acceptance.

The first independent run exited1: nine groups passed; one scratch output test expected FileExistsError but
correctly encountered the earlier private-directory mode rejection, because the local filesystem inherited
setgid onto its new directory. Fixed the **test harness** by explicitly chmod700 on its scratch directory,
then all10 passed. Preserved the original script/log as `independent_checks-first-attempt.py` and
`independent-tests-first-attempt.log`, plus the first interruption reproduction. No production source changed.
All inherited failed artifacts, old reviews and untracked `tools/peek.py`/`tools/snapcmp_probe.py` are preserved.

No driver main/run_gate, actual gate worker/helper, launcher/staging/host script, engine/native import,
simulation, build, remote command, emulator, deployment, pin change, descendant/delegation, commit, push or
other-worktree edit. Bash was syntax-only. Stdlib flag probes only print interpreter flags. Bootstrap mocks
never execute runpy or import engine/native modules. Fake waits/killpg never touch real PIDs.

Accepted/integrated B2, actual exact-source build and affected checks, owner-authenticated platform/input
dependency inventory, duplicate-job audit and fresh C56 remain intentionally missing external prerequisites,
not findings about placeholders. This verdict reviews source/plan preparation only; it grants no host launch,
B2/integrated gate or engine acceptance, full-byte-equivalence claim or live-pin promotion.

## Exact reviewed identities and code hashes

- Candidate: `4bfae6b0844b4620d9482cc996a74bf86f1a1887`.
- Tree: `82f9e1a2d089799fc39ad2e25d52cd4ca16d2055`.
- Complete binary delta SHA256,476a747f..candidate:
  `5242fbb807e069077683f8b64cb9a50f61301071201df889857f0ec997860c4d`.
- Focused binary delta SHA256,c45854f..candidate:
  `d310c202ee6c316f1430358ec95f8d076474ca44a8d4dcda08044978dc4f27cd`.
- `tools/final_gate.py`: `4f9fe978f2b80a746de50b0e7e5969df19fca576dddfdb47bd93169aeec82496`.
- `tools/final_gate.sh`: `297fbbb2f0c0e3f4c4368afdd4245b78792408075ce94f655dc7bc8209caf1d5`.
- `tools/final_gate_contract.py`: `222c69314e26d5aefcc3ad04a602ccac6e207ee7d22c65a5930a18d8ad291ad8`.
- `tools/gate_worker.py`: `8b8fc204a36849f0ee2d64705e9e9cec1dce32c7cab27d57ccf6e87811ba1742`.
- `tools/gate_fixtures.py`: `8737b53fde2966d14ce6359cd0c3e5e24cc783bb9c7b1348b3ff468df2cfbf21`.
- `tools/gate_roots.py`: `155cbdb4b11ea8239057600e191465f073418f648070ee8f20f14cab25aefc5f`.
- `tools/gate_compare.py`: `dce90963be2d46b6a0af8ba418d7c661b2d16a95f1d17202207c0c147eff9e6e`.
- `tools/test_final_gate_contract.py`: `0c5924ab846b8400bf46c0a337a7b2fe8c97eae4de45fe0767d36e179880fe22`.
- `FINAL-GATE-PLAN.md`: `85bd82a0866a05afd0c8894e8104664f37a48545fc383708742ce27a449c2620`.
- `PROGRESS.md`: `9aa211ae984d51be6e2eba7d48b1c1e23785ff9e5bb3817956d4b03d7da0d8bf`.
- `RESULTS.md`: `a8373f1e34e0d5875385db607ed9e4e2aa1718b1f90b7830b59d6709de4f91f9`.
- `SNAPSHOT-DIAGNOSTICS.md`: `5136eb6f3f80881a040e217e3e88220e146b0f83b2858dba7eef81856f9dbe01`.

All26 candidate delta files were read/hash-bound from Git and matched worktree bytes. Their complete hashes
are also listed in `r3-independent/reviewed-hashes.md`; the machine receipt includes unchanged readpaths,
original rejection and preserved diagnostic helper identities. HEAD remained the exact candidate throughout.
