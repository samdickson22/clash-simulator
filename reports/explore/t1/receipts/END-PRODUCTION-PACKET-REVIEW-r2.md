# T1 / PREREG-SEARCH-TIERS END: production packet review r2 (R7)

- **Reviewer:** Claude Opus 5.5, independent production-packet reviewer (author of r1). I am not the T1 worker, the E4 author, the A5 drafter, the PC4 reviewer or the A4 builder.
- **Where and when:** on 127x05, 2026-10-12. R6 replay ran 10:53:02Z–10:55:14Z, host listings at 10:58:40Z/10:58:41Z, and this file was written after 11:00:43Z (all from `date -u`).
- **Inputs:**
  - origin/main `bbff541c` (fetched at the start of the review);
  - COORDINATOR entries after 8e814b78: 9897216c, 3c29de85, effb407b, fae252e1, 2969615c, 537ae059;
  - T1 commits 8fc25b2d, 3debb7b8, 1cb46a13, 041de810, fc0d74a6, bbff541c;
  - canonical `<R>` = `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source`. This is worktree `source1` of the shared repository `/mpac/sdicks02/repos/clasher`. Its HEAD is detached at `9bb349b1`, and `git status --porcelain --ignored` is empty before and after my run.
- **Scope kept:**
  - I opened no TIERS reporting outcome, game bytes, heldout data, old-code D-attempt timing or T4 comparison.
  - I made no edits to T1 files and no commits. This file is my only output; my scratch is in `/tmp/sdicks02/r7*` and one barrier-created scratch dir is in `/mpac/sdicks02/tmp/t1-release-recheck-_dcxt9xm` (pool check health only).
  - **SSH:** exactly two read-only listings, under the PC1 exception (§5). No other host contact. I did not use 03 or 04.
  - **Compute:** `nice -n 19 taskset -c 63`, with `-B`/`PYTHONDONTWRITEBYTECODE=1` throughout.

## Overall verdict: **CLEARED_WITH_CONDITIONS**

r1's blockers F1–F4 are closed. R5, registration, R6, the private commit and PC1 all verify. I found no outcome exposure.

One gap remains, and it must be closed **before the reducer is invoked**. The coordinator requires that the reducer's emitted sensitivity ledger equal the PC4 sidecar except for `utc`, failing closed otherwise. **Nothing in code and no written runbook enforces that check** (§2c). The coordinator may authorize release once conditions C1–C4 below are in place; C1 and C2 need committed, independently reviewed artifacts.

| Item | Verdict |
| --- | --- |
| 1. **F1** (pool check roots) and **F4** (checker interpreter) closed; R6 PASS from `<R>` | **PASS** (independently reproduced) |
| 2a. **F2:** PC4 runs r1 and r2-landed committed verbatim | **PASS** |
| 2b. **F3:** CLI bb124cc4 and reducer aebb2017 landed on main and present in `<R>` | **PASS** |
| 2c. Reducer-ledger check moved to release (2969615c) and **enforced** | **NOT ENFORCED.** The move is correct, but the enforcement is missing (condition C1) |
| 3. R5 seal, registration bindings, golden-order evidence | **PASS** |
| 4. Private commit 9bb349b1: never pushed, content, ancestry, bundles, inventory | **PASS** (the 08 bundle rests on T1's recorded remote hash, I6) |
| 5. PC1 re-list: A5 host roots on 01 and 08 unchanged since r1 | **PASS** |
| 6. Outcome exposure | **NONE FOUND** |

## 1. F1 and F4 are closed; R6 PASS

**Pool check cf3be4dd** (`receipts/END-A5-pool-check-r3.json` at 041de810; sha256 of the committed bytes = `cf3be4dd…27c7c2`):
- Its R3 receipt `END-A5-R3-final-landing-checker-r3.json` records the checker run with every path under `<R>`, at `<R>` HEAD = landing 1cb46a13:
  - argv `e4v3-venv/bin/python -B -I -c <runpy bootstrap> <R>/reports/explore/t1 <R>/…/check_reference.py --descriptor <R>/…/END-A5-pool-descriptor.json --measurement-root <R>/…/e4v3 --pool …/end-a5-pooled-reference-r1 --output <R>/../evidence/pool-check-r3.json`;
  - `checker_sys_executable` = `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python`, `checker_version` = `3.12.12 (main, Dec 17 2025, 21:10:06) [Clang 21.1.4 ]` (this is the checker process itself, printed by the bootstrap before `runpy`);
  - `dont_write_bytecode` true, exit 0, empty stderr;
  - diagnostics path is the checker's own `<output>.diagnostics` (not moved).

  **This closes F4.**
- **Independent recompute (closes F1).** Under e4v3-venv 3.12.12 (`-B -I`), I imported `release_reference` from `<R>` (f8b61c60) and computed `pool_inputs(<R>/reports/explore/t1/receipts/END-A5-pool-descriptor.json, <R>/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3)`:
  - it gives 204 entries, **equal** to cf3be4dd's `input_files` and to the R6 fresh check 79ccbc21's;
  - all keys lie under `<R>`, the A5 pool context (`end-a5-pool-context-20261012-r1`) or the A5 release roots (`fleet-end-attempts-0108-a5`);
  - the 18 measurement keys lie under `<R>/…/e4v3`;
  - no key matches `0a87166f-r[0-9]`, `end-received`, `end-a6`, refusals or `fleet-end-attempts-0108/`.

**R6** (`END-A5-R6-prerequisites-r1.json`):
- `release_reference.prerequisites` with its in-barrier recheck ran from `<R>` HEAD 9bb349b1, under `e4v3-venv/bin/python` 3.12.12, with `-B` and `PYTHONDONTWRITEBYTECODE=1`. It gave passes/exit 0, empty stderr and `outcome_read_attempts: []`; the reducer was never invoked.
- **Fresh check 79ccbc21.** The committed public copy equals the barrier's original `/mpac/sdicks02/tmp/t1-release-recheck-umm5u555/check.json` byte for byte (sha 79ccbc21). Its diagnostics `stderr.txt` is empty.
- Against cf3be4dd, `pool_manifest_sha256`, `descriptor_sha256`, `checker_sha256`, `output_files`, `input_files`, `passes` and `outcome_access` are all equal. `checked_at_utc` is 10:44:39Z, against R3's 08:44:36Z.
- T1's R6 driver used `END-A5-R5-private-registration-prepared-r1.json`. Its `amendment_1_prerelease` is **identical** to the committed sealed R5 (3b7d2295), so the driver input is immaterial (I1).

**My independent R6 replay.** I ran the same `prerequisites(<R>, {authorized_at_utc: now, amendment_1_prerelease: <committed R5>})` under e4v3-venv 3.12.12:
- `release_reference` was f8b61c60 and `check_reference` c848baa2.
- **Result:** PASS (10:53:02Z–10:55:14Z), and `<R>` stayed clean at HEAD 9bb349b1.
- **Instrumentation.** T1's audit hook covered only the parent process, and only blocked paths with a `games` component. Mine logged *every* `open` in the parent, and I injected the same logging hook into the E4 pooling child's `-c` bootstrap, in my run only.
- **What was opened (1,242 opens in total):**
  - descriptor, completion, END evidence, blind ledger and counted inventory (metadata);
  - the 8 phases' launch, supervisor-exit, mhz and census files (health);
  - the A5 release-root files, the A5 context bundle pins (states/rows fixture, v1.pt, R3a.pt, calibration, amendments, seed-input receipts) and the pool outputs;
  - the private registration packet;
  - the venv/stdlib.
- **Zero paths** contain `games`, heldout, outcome, `end-received`, `0a87166f-r[0-9]`, `fleet-end-attempts-0108/`, refusals, `end-a6`, `reporting-frozen` or `replacement-frozen`.

## 2. F2 and F3 are closed; the reducer check is not yet enforced

**a. PC4 files are verbatim.** All 7 files in `receipts/PC4/` are byte-identical to the reviewer originals in `t1-20261010-r1/PC4/`:

| File | sha256 |
| --- | --- |
| PC4-REVIEW-r1.md | 11bbfc9a |
| PC4-REVIEWER-CHECK-RECEIPT.json | 48fe1011 |
| ssh-sensitivity-pc4.json | ea3d44d3 |
| pc4_reviewer_check.py | 5c4cdada |
| PC4-REVIEW-r2-landed.md | 71e491c1 |
| PC4-REVIEWER-CHECK-RECEIPT-r2-landed.json | 98e980ff |
| ssh-sensitivity-pc4-landed.json | 16e1b34f |

`LANDING-OP7-REVIEW-r1.md`, `RELEASE-INTEGRATION-977c4dfb-ADDENDUM-r1.md`, `END-PC4-LINEAGE-INVESTIGATION-r1.md` and my r1 are also verbatim.

With top-level `utc` masked, the three sidecars 48730da5, ea3d44d3 and 16e1b34f are **identical** (schema `clasher.t1.ssh-sensitivity-ledger.v1`, keys `blind_ledger_sha256, blocks, flag_counts, schema, sealed`).

**b. Lineage on main.** origin/main, tag `t1-op7-freeze-ef4c073a` (= ef4c073a) and `<R>` all carry identical bytes for:
- `ssh_sensitivity.py` bb124cc4;
- `reduce.py` aebb2017;
- `apt_budget.py` c1578535;
- `cpu_accounting.py` 5ecae99d;
- `RELEASE-PRODUCTION-CHECKS-20261010.md` 9b0704e2.

1cb46a13 is on origin/main and is an ancestor of 9bb349b1. No T1 `.py` file, release-checks file or e4v3 file changed between 1cb46a13 and 9bb349b1. `<R>` keeps main's `barrier.py` 346d3c05, `release_reference.py` f8b61c60, `check_reference.py` c848baa2 and `common.py` 36e5eec3.

**c. The reducer-ledger check moved to release, but nothing enforces it.**
- **Where the gap is.**
  - `reduce.py` aebb2017 `main()` calls `outcome_release` (which reruns `prerequisites`), then `load_blocks` (game bytes, line 123), then computes all statistics.
  - At line 132 it calls `health_ledger(a.root, ledger, sha(a.ledger))`. At line 133 it writes `<out>.ssh-sensitivity-ledger.json`.
  - At line 143 it writes `<out>` (outcomes) and prints `selection` to stdout.
  - It has **no** sidecar argument and **no** comparison. `barrier.py` and `release_reference.py` have none either; a grep of all T1 code finds no sidecar/PC4 reference.
  - The requirement exists only in prose: PC4 in 9b0704e2 ("The reducer rechecks the same health content before writing results…") and COORDINATOR 9897216c, 3c29de85, effb407b, fae252e1 and 2969615c.
  - No release runbook exists.
- **Consequence.** As written, a reducer run with a divergent ledger would write and print outcomes without failing.
- **The premise of 2969615c, corrected.** 2969615c says the check "can't run beforehand" because the *reducer* reads games first. That is true of the reducer's statement order. But `ssh_sensitivity.health_ledger` (bb124cc4 lines 58–71) reads only `*/complete.json`, interference proofs and `hub-ack.json`, never game bytes: it is the same function the health-only PC4 CLI runs. So the **identical** ledger can be computed and compared on the exact release root and ledger *before* any game byte is read. That makes a true fail-closed guard possible without opening outcomes. See C1.

## 3. R5 and registration seal

**R5** (`END-A5-R5-sealed-prerelease-evidence.json`, 3b7d2295, `R5_sealed: true`, `release_authorized: false`) binds:

| Binding | Value | Verified |
| --- | --- | --- |
| `measurement_source` | commit 8799a0d6; 18 **basename** keys (closes r1 F7) | equal to R3's `full18_unchanged`; `committed()` passes for all 18 in my replay |
| `attempt_roots` | 4ff93a10, bc90c1bd | yes |
| `descriptor` | 95774e86, f4319e5f | yes |
| `pool_manifest` | 0e517b96 at private 9bb349b1 `…/pool/receipt-manifest.json` | the 7 pool files are byte-equal to `end-a5-pooled-reference-r1` |
| `pool_check` | 041de810, cf3be4dd | yes |
| `end_evidence` | dc4b1986 at 9bb349b1 | yes |
| `completion` | d651b52c, 4dd191b6 | yes |
| `registration_manifest` | e4618cc3 at 9bb349b1 | yes |
| `amendment` | f6cebbaa, b35bd4e5 | yes |
| `landing_commit` | 1cb46a13 | yes |
| `canonical_release_checkout_HEAD` | 9bb349b1 | ancestry verified |

**Registration** (`packet/registration.json` a9a5d741, sealed by `packet/receipt-manifest.json` e4618cc3, scope T1-REGISTRATION, complete). All 126 manifest entries equal the private bytes.

It binds the A4 inputs:
- `sets` and `packet_schedule` are **deep-equal** to the handoff's `mac-sets.json` 72d83033 from **73d9ac68**, in every list: golden 125, speed 4×300, agreement 2,000, packets 1,000, schedule 1,000.
- `HANDOFF.md` (cd4c33f3) and `independent-reproduction-comparison.json` (3df877bd) are byte-equal to 73d9ac68.
- **B.7** `mac-sets-selection.json` = **f3b87ce5** is in the manifest and byte-equal to 73d9ac68.
- `fixture_canonical_fingerprint` = **0de69958…3e05e05**.
- **student-reference** = **7a90fa7a** is in the manifest.
- `pool_check_sha256` = cf3be4dd and `pooled_reference_manifest_sha256` = 0e517b96.
- `fleet_reference` host receipts are d6bc1d4c/1ee1aaa9, with ratios 0.97890/1.01751.
- `golden.json` 1e4cea28, `belief-reference.json` 74fc447b and `corpora.json` 3501e2ac equal the A5 context-bundle pins. `speed-reference` fe534ec0 and `deadline-reference` fdc29814 equal the pooled outputs.
- The handoff pin verification receipt binds `states.pkl` afdbd237, rows bin/json dc92bf45/49cbe56c, mac-sets 72d83033 and student 7a90fa7a (read-only, no conversion).
- `registration.json` does not name 73d9ac68 in text. The binding is by bytes, which is sufficient (I5).

**Golden order** (50cd117b; ruling 537ae059). I spot-checked every cited file:line in `<R>` (whose bytes equal 8799a0d6/main):
- `measure_tiers.py` 6066228b:
  - **45–55:** counts and uniqueness only.
  - **179–203:** `for identity_ in sets["golden"]`, `backend.by_id[identity_]`, `refs[identity_]`, records carry `id`.
  - **204–219:** belief, the same keying, with `(id, deadline_on)` records.
  - **257–275:** speed `refs[tier][identity_]`.
- `tier_backend.py` 02e2139f **137–161:** `by_id` and the `golden_only` *set*.
- `fleet_reference.py` c767a6e0 **118–120:** count 125, then `Session.exactness`.
- `fleet_pool.py` 572ad682 **140–145:** checks unique IDs, `(id, deadline_on)` set and ID-set equality. Nothing is positional.
- `prepare_bundle.py` a1c59fa3 **208–216:** copies `sets` and the reference files unchanged.
- `release_reference.py` f8b61c60 **64–72** (file-SHA seal) and **250–267** (only speed compared, as sets).

**Order independence of the computed values.** `belief_result` seeds `default_rng(row["seed"])` (line 286). `golden()` restores `row["root_rng_state"]` (298–299). The history cache is keyed by state ID (244–263). So per-ID results do not depend on iteration order.

I found no other positional consumer of `golden` (grep of e4v3). The evidence is **sound**, and speed keeps exact A5 order.

## 4. Private commit 9bb349b1

- **Never pushed.** I ran `git ls-remote origin` (40 refs). The SHA is absent, and no ref is named `private`. For all 40 remote SHAs (present locally, peeled), `merge-base --is-ancestor 9bb349b1 <sha>` is false.
  - As a backstop, GitHub would reject the push outright: the commit holds blobs over 100 MB (332 MB/287 MB `capacity.jsonl`, 226 MB `belief-reference.json`).
- **Metadata.** Tree 31c4b4c8, parent 537ae059 (public), message "PRIVATE: … never push". It is under `refs/private/t1-registration-20261012` only.
- **Content.**
  - 138 files are added, with no modifications or deletions, all under `reports/explore/t1/private-registration-a5-20261012-r1/` (1,158,850,908 bytes).
  - 118 `packet/sources/…` files are byte-equal to the A5 release roots on 05 (`fleet-end-attempts-0108-a5`). These are health and reference metadata: capacity, mhz, census, launch, supervisor-exit, exactness, warmup and validity records.
  - The 7 `pool/` files equal the pooled reference.
  - The rest are the A4 handoff, B.7, student, golden, belief, corpora, registration, end-evidence and pin-verification files.
  - There are no games, outcomes or fixture pickle/rows copies.
- **Ancestry.** 9bb349b1 *is* `<R>` HEAD (detached). 1cb46a13 and 041de810 are ancestors, so `release_reference.committed` holds; my replay passed through it.
- **Bundles.**
  - **05:** `t1-20261010-r1/private-registration/t1-registration-20261012-r1.bundle`, sha256 **4b3f8de5…a42b621**, 124,120,791 B. `git bundle verify` says "okay"; it contains 9bb349b1 `refs/private/t1-registration-20261012` and requires public 537ae059.
  - **08:** the receipt records T1's remote command (`ssh … sha256sum && stat`, exit 0) with the same sha 4b3f8de5 and the same size. I did not touch 08 beyond the PC1 listing (I6).
- **Durability receipt matches the tree.** `END-A5-private-registration-durability-r1.json` (774f7391) has `private_files`: its 138 keys equal the commit's added paths, and every `sha256` and `bytes` value equals the blob. Tree, commit, ref, base and HEAD all match.

## 5. PC1 re-list (10:58:40Z / 10:58:41Z)

`ssh -o ControlMaster=no -o BatchMode=yes 127x0N 'nice -n 19 find /mpac/sdicks02/jobs/clasher/t1-20261010-r1/fleet-end-attempts-0108 -maxdepth 2 -printf …'`

`find %T` prints host-local PDT; the values below are converted to UTC.

| Host | Root mtime | Entries |
| --- | --- | --- |
| 127x01 | `127x01/` **04:57:58Z** (as in r1) | {`end-reference-127x01-0a87166f-a5-r1`, `end-reference-127x01-0a87166f-r1`} |
| 127x08 | `127x08/` **06:15:20Z** (as in r1) | {`…-a5-r1`, `…-r1`, `…-r2`, `…-r3`} |

Each `fleet-end-attempts-0108` holds only its own host directory. The union in r1 still holds exactly: 01 = A5 ⊔ D2; 08 = A5 ⊔ {D4, D5} ⊔ D3 (RF1). **Unchanged.**

## 6. Outcome exposure

None found:
- R3, R6, the R5 seal, registration, the private commit and my replay all opened no outcome path (§1).
- No reducer output (`*.ssh-sensitivity-ledger.json`, results) exists under the T1 job dirs or `/mpac/sdicks02/tmp` since 2026-10-12 00:00.
- No new public receipt in bbff541c carries win/loss, selection, interval, bootstrap or population keys.
- PC4 reviewers read no `games/`.
- T4 is untouched by this round.

## Conditions (must hold before the reducer runs)

**C1. Enforce the reducer-ledger equality, fail closed.** This blocks release execution. Commit and independently review one of the following:

- **(preferred, no change to the reviewed reducer) Release driver** `reports/explore/t1/release_run.py`, run from `<R>`:
  1. **Pre-outcome guard.** Import `ssh_sensitivity` (bb124cc4) from `<R>` and compute `health_ledger(<root>, read(<ledger>)['events'], sha(<ledger>))` with the **exact** `--root` and `--ledger` that will be passed to the reducer. Assert:
     - the result with `utc` removed equals the committed `receipts/PC4/ssh-sensitivity-pc4-landed.json` (16e1b34f, the same as ea3d44d3 and 48730da5) with `utc` removed;
     - the sidecar file's sha256 ∈ {16e1b34f, ea3d44d3, 48730da5};
     - `sha(<ledger>)` = 866e6f7f.

     On any mismatch or exception, exit non-zero **before** invoking the reducer. No game byte has been read at that point.
  2. **Invoke** `reduce.py` aebb2017 with `--out` inside a new private 0700 directory and stdout and stderr captured to files in it. **Nothing is displayed**: the operator never runs the reducer bare.
  3. **Post-check (the coordinator's 2969615c check).** Assert:
     - `<out>.ssh-sensitivity-ledger.json` with `utc` removed equals the sidecar with `utc` removed;
     - `<out>`'s `ssh_sensitivity`, `apt_sensitivity` and `ssh_or_apt_sensitivity` `ledger_sha256` all equal the sha of that ledger file;
     - `apt_sensitivity` and `ssh_or_apt_sensitivity` are present.

     On failure: `chmod 000` the private directory, report only the failure health record (no field of `<out>` or stdout), and stop. Only on success is `<out>` handed to the coordinator.
- **(alternative) Narrow reducer change.** Add required `--pc4-sidecar`/`--pc4-sidecar-sha256` and move the `health_ledger` computation and comparison to immediately after `outcome_release`, before `load_blocks`. This replaces aebb2017, so it needs a new R1-style ruling, re-landing, tests and an Opus diff review.

**C2. Counted-block root logistics ruling.** The release must run on **05** from `<R>`:
- `common.ROOT` = `<R>`;
- `prerequisites` needs 05-local paths: the A5 release roots, the pool context, the private packet and `/mpac/sdicks02/tmp`.

But the counted blocks with `games/` exist only in 01's `…/replacement-frozen-op7-0108-r3/hub-blocks` (frozen; the mirror is paused). A ruling must authorize one of:
- **(a)** a byte-identical copy of that root to a **new dedicated prefix** on 05, nice 19 and never opened before release. C1 step 1 then re-certifies every `complete.json` and interference SHA against PC4, and `load_blocks` verifies every game SHA against its proof;
- **(b)** replicating `<R>` and its 05-local inputs at identical absolute paths on 01.

I recommend (a).

**C3. `<R>` state at release.**
- HEAD is 9bb349b1, or a **local-only** descendant. The Mac route needs `release['commit']` (the Mac summary) to be an ancestor of HEAD, so it needs a local merge of 9bb349b1 with the public Mac-summary commit, never pushed.
- The working tree is clean, and `refs/private/t1-registration-20261012` is intact.
- `<R>` is a worktree of the **shared** repository, so no thread may push `--mirror`/`refs/*` from it, check out in `<R>`, or delete the ref.

**C4. Interpreter pin.** Run the reducer and the C1 driver as `/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B` (3.12.12, numpy 2.2.6) with `PYTHONDONTWRITEBYTECODE=1`, from `<R>/reports/explore/t1`. Record `sys.executable`, the version and argv.

## Exact release-time procedure

The order is binding. Any failure stops the procedure, and nothing is reported.

0. **Before authorization:**
   - C1 is committed and reviewed;
   - the C2 ruling is made and its copy completed with a SHA receipt;
   - the coordinator writes the release receipt JSON:
     - `coordinator_thread` = 0523ae6f-…, `authorization_message_id`, `authorized_at_utc` (≥ cf3be4dd `checked_at_utc` 08:44:36Z);
     - `reason`: either `committed_mac_summary`, with `mac_summary_path`, `mac_summary_sha256` and `commit` (an ancestor of `<R>` HEAD), or `fourteen_day_escape`, with completion path, commit and sha. The escape is not available before 2026-10-25T19:31:38Z (completion 2026-10-11T19:31:38Z + 14 d);
     - `amendment_1_prerelease` = **exactly** R5 3b7d2295's `amendment_1_prerelease`.
1. **Pre-flight** (health only):
   - `<R>` HEAD/ref/clean checks (C3);
   - `sha256` of the release receipt;
   - `<ledger>` = 866e6f7f, equal to the committed `receipts/blind-ledger-final-op7-r3.json`;
   - `<root>` = the C2 root.
2. **Pre-outcome guard** (C1 step 1). The health ledger on `<root>`/`<ledger>` must equal sidecar 16e1b34f except `utc`.
3. **Barrier.** The reducer's first statement, `outcome_release(<R>, <receipt>)`, reruns `release_reference.prerequisites`, including:
   - all committed bindings (measurement 8799a0d6 ×18, roots 4ff93a10/bc90c1bd, descriptor f4319e5f, pool manifest 0e517b96, pool check cf3be4dd, registration e4618cc3/a9a5d741, completion, END evidence);
   - the attempt-root listing;
   - the fresh in-barrier E4 recheck, which must match cf3be4dd on manifest, descriptor, checker, outputs and 204 inputs;
   - the second attempt-root listing.

   Keep its scratch `check.json` and diagnostics.
4. **Reducer** `reduce.py` aebb2017 (C4 interpreter):
   - `--root <root> --release <receipt> --ledger <866e6f7f file> --out <private>/reduce.json`, plus `--mac-summary <committed path>` for the Mac route;
   - stdout and stderr go to private files.
5. **Post-check** (C1 step 3, which is 2969615c's check). The emitted ledger must equal the PC4 sidecar except `utc`. All three sensitivity `ledger_sha256` values must equal the emitted file's SHA. The OP-7 `apt_sensitivity` and `ssh_or_apt_sensitivity` must be present. Fail → quarantine and report the failure only.
6. **Record.** A release receipt binding: the receipt SHA, `<R>` HEAD, interpreter, argv, the barrier fresh-check SHA, the pre-guard and emitted ledger SHAs, the sidecar SHA, the `<out>` SHA and exit codes. Only then may the coordinator read or report `<out>`. Sensitivity stays DESCRIPTIVE_ONLY and never selects a tier.
7. **Until step 6 completes, keep frozen:** 01's four job dirs, the host roots, the release roots, `end-received`, the refusal copies, `<R>` and both bundles.

## Informational findings

- **I1.** The R6 driver ran (10:41:28Z) from the prepared R5 file, before R5's `sealed_utc` of 10:43:26Z. The content is identical to the committed R5, so this is immaterial.
- **I2.** T1's R6 audit hook covered only the parent process and only `games` path parts. My replay covered both processes and all opens, and is clean (§1).
- **I3.** `<R>` and its private ref live in the shared repository's object store (`.git/worktrees/source1`), which other threads use. `git push --all` would not send `refs/private/*`. The GitHub 100 MB limit is a second barrier. See C3.
- **I4.** The pooling child in my replay ran an instrumented bootstrap: an audit hook prepended to the `-c` string, logging opens only. The pooled outputs still matched the seal, because `prerequisites` passed.
- **I5.** Registration binds 73d9ac68 by bytes (mac-sets deep-equal, HANDOFF byte-equal, B.7 and student in the seal), not by a commit field. This is sufficient for the barrier, which seals files.
- **I6.** I did not re-hash the 08 bundle; that is outside my SSH exception. T1's receipt records the exact remote `sha256sum`/`stat` argv, exit 0 and the same sha and size as 05's verified bundle. Re-verify it only if 08's copy has to be relied on.
