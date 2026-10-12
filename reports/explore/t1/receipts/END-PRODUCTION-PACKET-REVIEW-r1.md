# T1 / PREREG-SEARCH-TIERS END: production packet review r1 (PC1–PC4)

- **Reviewer:** Claude Opus 5.5, independent production-packet reviewer. I am not the T1 worker, the E4 author or the A5 drafter.
- **Where and when:** on 127x05, 2026-10-12, from 08:00Z to 08:16Z.
- **Inputs:**
  - origin/main `02aeddda` (fetched 08:00:58Z);
  - pool check commit `95774e86`, with pool check `43a6f0f2`, pool manifest `0e517b96` and descriptor `f4319e5f`;
  - adoption `46ab6923` / merge `8799a0d6`;
  - roots `4ff93a10` and push receipt `053f898d`;
  - disclosures `13c3dbe4` and `a22c17f3`.
- **Scope kept:**
  - I opened no TIERS reporting outcome, heldout data or game bytes.
  - I opened no old-code reference timing (A6, 01 r1, 08 r1/r2/r3). For the D-attempts I read only their manifests, ACKs, file names and stat metadata. The one exception is the 08 r1 `failure.json`/`detach.log` traceback, which is the RF1 C1 predicate and contains no timing.
  - I did not open T1's T4 comparison file.
  - I made no edits to T1 files and no commits.
- **SSH:** two read-only listings only, under the PC1 exception:
  `ssh -o ControlMaster=no -o BatchMode=yes 127x0{1,8} 'nice -n 19 find …/fleet-end-attempts-0108 -maxdepth 2 -printf …'`, at 08:01Z.
- **Local compute:** `nice -n 19 taskset -c 63`. My scratch files are in `/tmp/sdicks02/pcreview/` on 05.

## Verdicts

| Check | Verdict |
| --- | --- |
| **PC1:** every original END attempt accounted for | **PASS** |
| **PC2:** `measurement_source` = reviewed E4 inventory | **PASS** |
| **PC3:** e4v3-venv Python 3.12.12 for pooling and the checker | **INCOMPLETE.** The pooling interpreter is proven. The interpreter of T1's checker run was not preserved. My independent rerun under e4v3-venv 3.12.12 passes and is byte-identical (F4) |
| **PC4:** OP-6 sensitivity sidecar | **INCOMPLETE.** I could not run the CLI against the durable root (F2). The CLI identity and reducer alignment need a ruling (F3). Offline cross-checks of the committed sidecar against the inventory and ledger pass |
| **The pool itself:** both hosts in, ratios within ±5%, first-passing classification correct, no old code in `pool_inputs` | **PASS** |
| **The pool-check receipt as release-barrier input** | **BLOCKED (F1).** It fails closed at `release_reference.prerequisites` because of the path keys in `input_files` |
| **T4:** old D-timing sealed | **INTACT.** There is no evidence of any opening before the pool check committed. The one permitted comparison started after it (F10) |
| **Overall** | **NOT CLEARED. Neither release route may proceed.** No outcome exposure was found. Every blocker fails closed |

## Findings

### F1. BLOCKER (release barrier): pool check 43a6f0f2 cannot satisfy `release_reference.prerequisites`

`release_reference.py` f8b61c60, which A5 leaves unchanged, enforces two things:
- `check['input_files'] == pool_inputs(<repo>/<descriptor path>, <repo>/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3)`;
- the in-barrier `recheck(...)['input_files'] == check['input_files']`.

`pool_inputs` keys every input by its **absolute resolved path**.

The committed check keys its inputs from two different roots:
- the descriptor under the T1 worktree, `/mpac/sdicks02/jobs/clasher/t1-health-stop-reconcile-20261010/reports/explore/t1/receipts/…`;
- the 18 measurement files under `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-CANDIDATE-0775b704-0108-r1/runtime/reports/…/e4v3/`.

That runtime is not a git repository and contains no `reports/explore/t1`. No symlinks are involved.

**Empirical check (read-only).** `pool_inputs` with repo = the T1 worktree gives 204 entries with an identical digest multiset, but 18 keys differ: `<repo>/…/e4v3/*` against `end-a5-CANDIDATE…/runtime/…/e4v3/*`. So `equal == False`. No single `repo` can reproduce both key prefixes.

**Effect.** The barrier raises "Checked reference inputs changed or incomplete", which fails closed. The pool itself and its bytes are unaffected.

**Remedy.** See step R3. Re-run the reviewed checker c848baa2 with `--descriptor` and `--measurement-root` inside the exact clean checkout the barrier will use. Commit the new pool-check receipt, and bind its SHA in registration and the pre-release evidence.

### F2. BLOCKER (PC4): the reviewed CLI has not been run by the reviewer against the final durable counted-block root

**What exists.** `ssh-sensitivity-final-op7-r3.json` 48730da5 is committed at bc3730c4. It is byte-equal to the 05 copy in `reporting-completion-sealed-r1/`.

**Why I could not run the CLI:**
- `ssh_sensitivity.py` reads `<root>/*/complete.json` and requires `hub-ack.json` for every non-01 block. The counted blocks with their complete proofs exist only on the hub, 127x01.
- 05 holds only `observer/` metadata and the sealed summary files. A search of `/mpac/sdicks02` on 05 found no T1 `hub-ack.json` or `complete.json`.
- My SSH authority covers PC1 listings only.

**What is missing:**
- **(a)** authority, or a byte-identical durable copy on 05, to run the CLI against the counted root;
- **(b)** the exact root argument. The counted blocks span 8 phase roots: 01 and 08 × reporting and replacement-r1/r2/r3. The CLI takes a single `--root`, and the completion receipt does not record the argv/root that produced 48730da5;
- **(c)** the reviewer check receipt PC4 requires, binding sidecar SHA + blind-ledger SHA + complete-proof SHAs + reviewed CLI SHA. None is committed.

### F3. HIGH (PC4/reducer): the "reviewed CLI" is ambiguous, and the reducer recheck may not match the committed sidecar

**Two candidate CLIs:**
- PC4 is anchored on OP-6 confirmation 9118153b. That is `ssh_sensitivity.py` **e643a342** (d60586b3), the version on origin/main and pinned by main's `FROZEN-T1.json` 24817e16.
- The committed sidecar 48730da5 was generated by **bb124cc4**, the OP-7 version. It carries `apt_flagged`, `ssh_or_apt_flagged`, `*_meter_stop`, `cpu_accounting_rule` and `flag_counts`, which e643a342 does not emit.
  - bb124cc4 is frozen at 04633bdb on `worker/t1-op7-apt-20261010`, with OP-7 reviews r1–r3 and confirmation 1947830b.
  - It is not on main (d8cc4ff7 is not an ancestor of origin/main).

**The reducer problem.** Main's `reduce.py:131-136` imports e643a342's `health_ledger/analyze`. The OP-7 `reduce.py` adds `analyze_apt` and `analyze_union`. PC4 requires the reducer's recheck to match "schema, sealed status, blind-ledger SHA and block entries" of the checked sidecar. An e643a342 regeneration would have different block entries (no OP-7 keys), so that recheck would fail.

**Needs a coordinator ruling** on:
- which CLI SHA PC4 binds;
- which reducer/integration branch (c5b2e059 or the OP-7 lineage) runs at release.

Both must produce the same block-entry schema as the checked sidecar.

### F4. MEDIUM (PC3): the checker run's interpreter provenance was not preserved

**Pooling is proven.** `END-A5-pool-PC3-run.json` records:
- argv[0] `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python`;
- version `3.12.12 (main, Dec 17 2025, 21:10:06) [Clang 21.1.4]`;
- exit 0, empty stderr, `fleet_pool` 572ad682.

The venv links to the uv cpython-3.12.12 build, and `pyvenv.cfg` says 3.12.12. I verified both.

**The checker is not:**
- The receipt asserts `PC3_same_interpreter: true`, but no committed byte records the checker's own `sys.executable`. `clasher.t1.pool-check.v1` has no interpreter field.
- The private diagnostics directory is `END-A5-pool-check-success-diagnostics`. That doesn't match the checker's own `<output>.diagnostics` naming, so the checker's output path or diagnostics location was changed after the run, and that isn't recorded.

**Independent reproduction.** I ran the committed `check_reference.py` c848baa2 (origin/main bytes, extracted to scratch) under `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12, against the committed descriptor bytes (f4319e5f), the unchanged pool and the CANDIDATE e4v3 root:
- result `passes: true`;
- `output_files` identical;
- `input_files` identical (204, ignoring only my descriptor path);
- `pool_manifest_sha256` and `descriptor_sha256` identical.

Receipt: `/tmp/sdicks02/pcreview/indep/pool-check-indep.json`.

**Closes when** the regenerated check (R3) records argv, `sys.executable` and version, and the in-barrier replay runs under the same interpreter and records it (R6).

### F5. INFO (PC1, wording): D3 appears in two disclosures

The A5 old-code disclosure 13c3dbe4 lists D3 (08 r1) with disposition "RF1-exempt, uncounted, never pooled". The RF1 disclosure a22c17f3 also covers it.

Partitioned by disposition, the sets are disjoint. Applying A5 §5.2(3) as written:
- descriptor = {A5 r1};
- disclosed old code = {D2, D4, D5};
- RF1-exempt = {D3}.

That holds. I record this as the reading used.

### F6. INFO (PC2, attribution)

A5 §7 R2 calls the 17 unchanged entries "A3-reviewed E4 (732ea9bd)". In fact 732ea9bd reviewed the inventory at 6872f98e. Four files then changed under Amendment 3 (f6cebbaa, Sol APPROVE r4, review 18baa4ea):
- `tier_backend` b04d201d → 02e2139f;
- `prepare_bundle` → a1c59fa3;
- new `state_rows` 3899276b;
- new `convert_states` 7ce30683.

Every one of the 18 is still covered by an independent review: 13 by 732ea9bd, 4 by A3 Sol r4, and 1 (`fleet_validity` 0775b704) by A5 Sol r3. This is not a defect.

### F7. INFO (pre-release form)

The handoff's `full18_reviewed_measurement_inventory` is keyed by repo path. `release_reference.prerequisites` compares `measurement_source.files` against the e4v3 directory's basenames and against `fleet-identity.measurement_files`, which is basename-keyed. The pre-release `measurement_source` must therefore use basename keys at commit 8799a0d6, or at a descendant with identical bytes. The values themselves are verified equal (PC2).

### F8. INFO (hygiene)

T1's first pool run wrote `__pycache__/{fleet_pool,telemetry,tier_backend}.cpython-312.pyc` into the CANDIDATE e4v3 runtime at 07:55:24Z, without `PYTHONDONTWRITEBYTECODE`. This is outside the 18-file inventory, and the source bytes are unchanged and verified. It has no effect. My runs wrote nothing there; mtimes were checked.

### F9. INFO (context)

The per-host bundle manifests differ: 01 `6ce19106`, 08 `f81c9288`. This is expected under A5 (per-host `tiers-pins`). The pool context is 08's `f81c9288`, copied byte-exact to 05, and E4's pool-context checks passed in T1's run, in my rerun and through the 204 pinned inputs.

### F10. INFO (T4)

- The disclosure states `timing_content_opened: false` for D1–D5.
- No D path appears anywhere in the pool inputs (below).
- On 05, D2's timing files show atimes only at verifier hashing (04:21:38Z, `end-received`) and L1 copy (04:26:00Z, release copy). Under `relatime` this cannot prove a negative.
- T1's single permitted descriptive comparison marker `END-A5-T4-one-comparison-started.json` is dated 08:02:42Z. That is **after** the pool-check commit landed on origin at 07:59:33Z (GitHub activity), as A5 §4.1 and 46ab6923 allow. Its commit 5b6c4d23 is local to the T1 worktree and unpushed. I did not read it.
- That comparison may not feed any gate, pool, registration or release.

## PC1 evidence

**Detached launches.** All are taken from committed launch receipts; each matches `end-received/` on 05 one-for-one (exactly 8 entries).

| # | Attempt (job path) | Launch (UTC) | Placement | Disposition |
| --- | --- | --- | --- | --- |
| 1 | `end-a6-127x01-0a87166f-r1` (`BASE/`) | 01:13:36 | outside all roots | D1 old code, never pooled |
| 2 | `end-reference-127x08-0a87166f-r1` | 02:48:04 | 08 host root | D3 RF1-exempt. The disclosure was pushed at 03:17:55Z, before r2. Refusal copy is under `fleet-end-refusals-0108` |
| 3 | `end-reference-127x01-0a87166f-r1` | 02:57:15 | 01 host root | D2 old code. Release copy in the old root |
| 4 | `end-reference-127x08-0a87166f-r2` | 03:23:10 | 08 host root | D4 old code |
| 5 | `end-reference-127x08-0a87166f-r3` | 03:56:55 | 08 host root | D5 old code |
| 6 | `end-a5-smoke-127x08-0a87166f-r1` (`BASE/`) | 04:55:46 | outside all roots | A5 smoke, never pooled. ACK complete at 06:13:48Z |
| 7 | `end-reference-127x08-0a87166f-a5-r1` | 06:16:32 | 08 host root | A5 descriptor |
| 8 | `end-reference-127x01-0a87166f-a5-r1` | 06:26:27 | 01 host root | A5 descriptor |

I swept COORDINATOR and PROGRESS-T1 for attempt names; they reference no other attempt.

**My host-root listings (08:01Z, read-only):**
- `127x01:…/fleet-end-attempts-0108/127x01` = {`…-a5-r1`, `…-r1`}. The root directory's mtime is 04:57:58Z, which matches the A5 01 job preparation at 04:58:12Z. No entry has been added or removed since.
- `127x08:…/fleet-end-attempts-0108/127x08` = {`…-a5-r1`, `…-r1`, `…-r2`, `…-r3`}. The root's mtime is 06:15:20Z, matching preparation at 06:15:34Z.
- Each host's `fleet-end-attempts-0108` contains only its own host directory.
- Both listings equal T1's wrapper-gone source-preservation receipts.

**The union holds on both hosts:**
- 01 = {a5-r1}<sub>descriptor</sub> ⊔ {r1}<sub>D2</sub> ⊔ ∅<sub>RF1</sub>.
- 08 = {a5-r1}<sub>descriptor</sub> ⊔ {r2, r3}<sub>D4, D5</sub> ⊔ {r1}<sub>D3</sub>.

The sets are disjoint and exhaustive, with no unexplained directory. 01 has used no RF1 exemption; 08 has used one (D3), within RF1 C2.

**RF1 C1 re-evaluated for D3:**
- the ACK shows SEALED / failed / files = 1 / exit 1;
- the manifest keys are exactly {`failure.json`};
- `fleet_technical_cause` is null;
- the innermost `fleet_reference.py` frame is `run:34` (≤ 96);
- `detach.log` holds only the traceback, ending at `slot_layout` "Reference must inherit the pinned reporting host/priority/scheduler".

**Push time of the A5 roots file.** I trust the GitHub repository activity API (server-side ref-update log):

| Push | Before → after | Time (UTC) |
| --- | --- | --- |
| Disclosure | `86fda5a1→13c3dbe4` | 04:52:27Z |
| Roots | `13c3dbe4→4ff93a10` | 04:53:41Z |
| Push receipt | `4ff93a10→053f898d` | 04:55:05Z |

This is corroborated exactly by 05's `refs/remotes/origin/main` reflog ("update by push", 04:53:41Z).

The other two sources are weaker:
- `%cI` is 04:53:39Z. That is client-set, and it is the barrier's `registered_at`.
- T1's receipt says 04:54:12Z. That is self-reported and written after the push.

All of these precede the smoke (04:55:46Z) and both A5 references. The A5 identity UTCs are 06:17:53Z (08) and 06:27:53Z (01), both ≥ `registered_at`. The roots file has not changed since 4ff93a10 (sha bc90c1bd).

**The A5 release root (05) holds only A5 attempts and matches the descriptor exactly:**
- `fleet-end-attempts-0108-a5/127x0{1,8}` each holds a single directory, `end-reference-127x0N-0a87166f-a5-r1`.
- Each has 59 plain files, no symlinks, with full SHA equality to the L1 assembly receipts.
- `receipt-manifest.json` is d6bc1d4c (01) / 1ee1aaa9 (08), equal to the descriptor; status complete, 57 files, all matching.
- The DURABLE-ACK is 7ea9ae1d / 86eb8c11: SEALED, complete, exit 0, and bound to those manifests.
- `argv.nul` equals the launch receipts' `measurement_argv` (f6b82fd2 / e9d0fc07).

**Old attempts are preserved and never pooled:**
- D2, D4 and D5 are in the old release root `fleet-end-attempts-0108`; D3 is in `fleet-end-refusals-0108`; D1 is in `end-received` only.
- Every manifest and ACK equals the disclosure, with no missing or extra file names (D2 57, D3 1, D4 50, D5 50, D1 29).
- The smoke and A6 lived outside all roots, on the hosts and on 05.

## PC2 evidence

- The 18 `measurement_files` at 8799a0d6 equal origin/main, both A5 `fleet-identity.json` files, the pool runtime e4v3 and the handoff's inventory.
- `fleet_validity` = 0775b704. Sol r3 APPROVE names this exact SHA.
- The diff from A3 (f6cebbaa) to 8799a0d6 is **only** `fleet_validity.py` 94d0e7f2 → 0775b704.
- Both hosts have identical `runtime_files` (3785), native 44874fd6, nice 10, 11 slots, warmup 300, and `end_kind` `counted-reporting`.
- Both attempts include the END and pooling code: `fleet_end` 76d5ce31 and `fleet_pool` 572ad682.

## The pool itself

- `pooling.json`:
  - `included` = [127x01, 127x08] and `excluded` = [];
  - ratios 01 = 0.97890, 08 = 1.01751 (initial = retained), both within ±5%;
  - rule "END: all counted hosts within ±5%, no exclusion".
- `fleet_reference`: nice 10, 3 repeats, physical cores, `raw-host-times-repeat-v1`.
- I re-ran the A5 `fleet_validity.classify_attempt` under e4v3-venv. Both attempts give `passes = True`, `technical_repeat_candidate = False`, `exactness_failure = False`. This is a single first-passing attempt per host, matching `pooling.attempts`.
- The 204 `pool_inputs` contain only:
  - the descriptor;
  - the 0addf7c0 context bundle;
  - the two A5 attempt roots;
  - the CANDIDATE A5 e4v3.

  They contain **no** `fleet-end-attempts-0108/`, `end-received`, `end-a6`, refusals, A3-runtime or `0a87166f-r[0-9]` path.
- The pooled output hashes equal the manifest 0e517b96 and the pool check.

## PC4 offline cross-checks of the committed sidecar (descriptive; not the PC4 run)

- `blind_ledger_sha256` = 866e6f7f, equal to the committed ledger. Ledger: 54 events, 54 replacements, none null, no chained replacements.
- 3072 entries:
  - unique, sorted logical IDs, and unique source IDs;
  - logical IDs = `counted-inventory-final-op7-r3` (50f24dd6), and source IDs = `counted-inventory-END-op7-r3` (6f6f0007);
  - host, phase, population and cell all agree.
- **Exactly 2400 primary, 600 guard and 72 descriptive.**
- The 54 replacement rows all bind to their ledger event (`replaces` == logical), and no lost ID appears as a source.
- `flag_counts` are internally consistent per population and cell, and every entry carries `interference_sha256`.

**SSH-flagged blocks** (all on 127x08; 127x01 has 0). APT-flagged: 0. Meter stops: 0.

| Population | SSH-flagged |
| --- | --- |
| Primary | **379 / 2400** |
| Guard | **98 / 600** |
| Descriptive | **0 / 72** |

**SSH-flagged by cell:**
- **Primary (cells 0–49, 48 blocks each):** 6 8 8 7 8 8 8 8 5 6 | 7 8 8 8 8 8 7 6 9 7 | 7 8 8 8 6 8 8 7 8 8 | 9 9 7 8 7 9 8 6 8 6 | 6 10 8 6 9 9 8 7 7 8
- **Guard (cells 0–17):** 6 6 6 6 6 6 4 6 6 4 5 7 5 4 5 6 5 5
- **Descriptive:** 0 in every cell.

**Mixed regimes.** The phase is inferred from the inventory; I read no proofs.

| Phase | Blocks | Regime | SSH-flagged |
| --- | --- | --- | --- |
| Original `reporting` | 157 (01: 124, 08: 33) | legacy OP-4/OP-5 proofs, LAN-source replay path | 0 |
| `replacement-r1` | 554 (01: 155, 08: 399) | OP-6 source-proven ticks, `legacy-self-plus-reaped` accounting | 352 (279 primary, 73 guard), all 08 |
| `replacement-r2`/`r3` | 2361 | OP-7 `observed-child-credit-v2` | 125 (100 primary, 25 guard), all 08 r2; r3 has 0 |

Sensitivity remains DESCRIPTIVE_ONLY and never selects a tier.

## Remaining steps before either release route

All of these are required, in order where noted. No outcome access before R7.

1. **R1. Coordinator ruling (F3):**
   - name the PC4 CLI SHA (e643a342 or OP-7 bb124cc4);
   - name the reducer and integration lineage used at release;
   - require the reducer's `health_ledger` to emit the same block-entry schema as the checked sidecar;
   - if bb124cc4/OP-7, land it at a committed path the release uses.
2. **R2. PC4 run (F2):**
   - **Authority:** grant read-only execution of the ruled CLI on hub 127x01 at nice 19, or have T1 produce a byte-identical durable copy of the complete proofs plus `hub-ack.json` on 05.
   - **Root:** define the exact counted-block root, either one root holding all 3072 `*/complete.json` or per-phase runs with a declared merge.
   - **Run:** run `ssh_sensitivity.py --root <root> --ledger <blind-ledger-final-op7-r3.json 866e6f7f> --out <sidecar>`. Confirm durability, the proof and interference SHAs, the legacy-flag replay and dedup. Compare it to 48730da5, where all fields except `utc` must match.
   - **Commit:** commit the sidecar and a reviewer check receipt binding the sidecar SHA, the ledger SHA, the complete-proof SHAs, the CLI SHA and the interpreter.
3. **R3. Regenerate the pool check (F1):**
   - In the clean checkout `<R>` the barrier will use (the 18 e4v3 bytes equal to 8799a0d6), run `check_reference.py` c848baa2 under `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python` 3.12.12:
     - `--descriptor <R>/reports/explore/t1/receipts/END-A5-pool-descriptor.json`
     - `--measurement-root <R>/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3`
     - `--pool …/end-a5-pooled-reference-r1` (unchanged, manifest 0e517b96)
   - Record the argv, `sys.executable`, version and the diagnostics path.
   - Before committing, verify `input_files == release_reference.pool_inputs(<R>/descriptor, <R>/…/e4v3)` and `output_files` = the committed outputs.
4. **R4. Close PC3 (F4)** with R3's interpreter record.
5. **R5. Pre-release evidence:**
   - `measurement_source` = {commit 8799a0d6, the 18 entries keyed by basename (F7)};
   - `attempt_roots` = {`reports/explore/t1/receipts/reference-attempt-roots-0108-a5.json`, 4ff93a10, bc90c1bd};
   - descriptor f4319e5f, pool manifest 0e517b96, and the **new** pool-check SHA from R3.

   Then seal the A4 registration, binding the new `pool_check_sha256`. It is still unsealed.
6. **R6. Release barrier:** run the reviewed barrier, `release_reference.prerequisites` with the in-barrier recheck, from `<R>` under the same e4v3-venv 3.12.12, and record its `sys.executable`.
7. **R7. Production packet review r2** (narrow): verify R2–R6 close F1–F4, re-confirm that the PC1 host roots are unchanged (re-list), then coordinator authorization.

Keep the 01/08 host roots, the release roots, `end-received` and the refusal copies untouched until release.
