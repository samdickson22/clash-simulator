# T1 review r2: Amendment 1 release barrier, re-review of C1–C4

| Subject | Verdict |
|---|---|
| Candidate `11dcb03466340ef2ba342282ebfd9d0711b02229` (branch `worker/t1-amendment1-release-20261010`, parent 64608f6f, unadmitted) | **APPROVE_WITH_CONDITIONS** |

- **Scope.** C1–C4 are each fixed in code, and no code change is required. The conditions below apply to admission and to the first production packet review.
- **Reviewer.** Independent T1 reviewer, running on 127x05 with git and local files only. I made no ssh connection to 01, 03, 04 or 08.
- **No outcome or production data read.** I read 0 reporting games and produced no pool, check, registration or release. All fixtures were synthetic.
- **Coordinator:** 0523ae6f.
- **Prior review:** `REVIEW-T1-RELEASE-BARRIER-AND-CORPUS-20261010T1700Z.md` (06dab1ea), part A.

## Provenance
- **Packet** `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/review/11dcb034…/`. `release-c14.diff` has SHA `e876687c…2424` and equals `git diff 64608f6f 11dcb034` byte for byte. `release-c14.stat` matches too (`f3e45cb2…`).
- **Source SHAs.** The six source SHAs in the checkout (`barrier.py`, `release_reference.py`, `check_reference.py` and the three test files) equal `receipts/amendment1-release-c14-tests.json`.
- **Ancestry.** E4 END commit `24bfa017` is **not** an ancestor of the candidate (base 3d6e2a56). Admission therefore needs a merge (see AC1).
- **Merge with main.** A trial merge into origin/main conflicts only in `PROGRESS-T1.md`, which is documentation. Every code file merges cleanly.

## Tests (127x05, nice 19, e4v3-venv Python 3.12)

| Run | E4 source | Result |
|---|---|---|
| Candidate's 49 tests | Clean worktree at main `bd230eb1`, which contains 24bfa017 (not the dirty shared checkout) | **49 passed** in 119 s |
| My 24 bypass probes (below) | Same | **24 passed** in 86 s |
| 49 tests plus 24 probes on the trial merge (origin/main plus candidate), with no E4 override | Merged tree | **73 passed** in 205 s |

- **Probe file:** `/mpac/sdicks02/jobs/clasher/t1-release-r2-review-20261010/probes/test_probes_r2.py` (SHA `e0d35dc5…95fb`). It is not committed, so T1's own pytest collection won't pick it up.
- **Run logs:** stored alongside the probe file.
- **Scratch:** I deleted my recheck scratch from `/mpac/sdicks02/tmp`. The author's 6 earlier directories are untouched.

## C1–C4

| Cond. | Result | Evidence |
|---|---|---|
| **C1:** barrier trusted a hand-writable check receipt | **FIXED** | `prerequisites()` ends by calling `check_reference.check()` itself into a fresh `/mpac` scratch. It then requires the fresh `pool_manifest`, `descriptor`, `checker`, `output_files` and `input_files` identities to equal the committed receipt. Both routes call `prerequisites()` first. **P1:** I hand-edited the pooled `fleet_reference.json` (still within ±5%), resealed the pool, and hand-wrote a fully consistent `pool-check.json` and registration lineage. Both routes were **denied** with "E4 pooled outputs differ on recheck". **Control:** with `check` replaced by "return the committed receipt" (the 64608f6f behaviour), the same forgery **opens** both routes. The rerun is therefore what stops it. |
| **C2:** failed attempt omitted from the descriptor | **FIXED, with residuals (PC1)** | The committed `attempt_roots` must list exactly the counted hosts. Each root must be an absolute, non-symlink directory containing only non-symlink directories, and the set of its children must equal the descriptor's attempts. Every attempt's `fleet-identity.utc` must be ≥ the declaration commit time. The listing is re-taken after the rerun. Author tests cover an extra directory and a symlinked attempt. My probes **denied** each of the following: an archived failed attempt as a file (P2a); a hidden `.r-failed` directory (P2b); a directory created during the rerun (P2c); a declaration bound to a commit after launch (P2d); a symlinked root (P2e). **Residuals (P2f and P2g both open):** (i) a failed attempt deleted, or never copied into the release-side root, leaves no trace; (ii) the declaration time is the self-attested git committer date, so a back-dated commit passes. Both require deliberate action, and a root listing cannot see either. |
| **C3:** recheck against final E4 END (24bfa017) | **FIXED** | The barrier requires completion `blind_ledger_sha256` and `counted_inventory_sha256` to equal the END ARTIFACT SHAs, with both artifacts committed. The ledger must be `sealed:true`. The inventory must have schema `clasher.t1.counted-blocks.v1` and `outcomes_sealed:true`, and its host/phase set must equal `counted_host_phases`. Additional valid END phases are retained. Every phase's launch, exit, MHz and census files are committed. The full E4 source inventory must equal the `measurement_source` commit and current bytes. The in-barrier rerun goes through E4 `pool_context` → `fleet_end.evidence`, which enforces 24bfa017's `reporting_hosts`, logical coverage, ledger, stopped-phase and admission/block rules. **Probes:** P5a (unsealed ledger with all SHAs made consistent) **denied**. P5b (inventory missing a host, made consistent) **denied**. P5c (an extra ledger event, made consistent) **denied** on pool lineage. The fixture uses the real E4 `end_fixture` from main. |
| **C4:** checker success path never ran | **FIXED** | `make_packet` builds the pool with the unmodified E4 CLI and `check()`; the receipt is never synthesized. Both routes rerun real E4 in the barrier. Failures keep `stderr.txt`, `e4-failure.json` and `failure-health.json`, and write no receipt. **Probes:** E4 exiting non-zero after writing correct bytes is **denied** (P6a). E4 "success" with no output is **denied** (P6b). A **real** E4 failure, forced by running the rerun under `/usr/bin/python3` 3.8, is **denied** on both routes (P6c). That failure came from E4's own check: "Exactness mismatch: signed reporting MHz comparison". `e4-failure.json`, stderr and health were retained; a copy is in `…/evidence/P6c-real-e4-failure-diagnostics/`. |

## Other bypass probes requested
- **Smoke or partial pool.** Smoke END is denied (author test). A pool seal missing `pooling.json` is **denied** (P4a). A completion with 2399 primary blocks is **denied** (P4b). Host omission and exclusion are denied (author tests).
- **14-day escape before the pool is committed.** All four probes were **denied**:
  - no `amendment_1_prerelease` (P7a, `KeyError`);
  - HEAD at a commit before the pool/check/registration commits (P7b);
  - an uncommitted edit to a pooled file (P7c);
  - an escape completion different from the checked END completion (P7d).
- **Gate ordering.** `outcome_release` runs `prerequisites()`, including the real rerun, before the escape's 14-day clock is even evaluated.

## No outcome reads before release: PASS
- **Barrier and checker reads:** completion (health), END, the blind ledger (loss events), the counted inventory (public descriptors only), descriptor, attempt seals and identities, pool outputs and the registration packet. None of these hold game outcomes.
- **E4 pooling:** `fleet_end.py` reads only committed health evidence ("never reads game/outcome bytes").
- **Reducer order:** `reduce.main` calls `outcome_release` (line 120) before `load_blocks` (line 123).
- **No-change files:** `reduce.py`, `common.py` and `barrier.py` are unchanged since 64608f6f.

## Amendment 1 and E4 compatibility: PASS
- **Amendment 1:** SHA `b35bd4e5…2775` is pinned. The pool fails closed: no exclusions, every counted host present, and both ratios within inclusive ±5%. No route opens before the pool and check are committed and rechecked.
- **E4 field contracts:**
  - `fleet-identity.utc` is `time.time()`, a float, matching the integer commit-time comparison.
  - Identity `host` is `platform.node()`, which is bare `127x0N` on the fleet.
  - The `fleet-pool.v2` attempts, first-passing classification and the at-most-one technical-repeat rule all match `fleet_pool.run`.

## Conditions
- **AC1 (admission).** Admit by merging onto current main so that E4 24bfa017 or later is in the tree. Do not admit the branch tip alone, which carries the pre-24bfa017 E4.
  - Resolve the `PROGRESS-T1.md` conflict.
  - Re-run the 49 tests on the admitted tree with no `T1_E4_REVIEWED_SOURCE_ROOT` override. They pass on my trial merge.
- **PC1 (production packet review, closing the C2 residuals).** The reviewer of the first production packet must cross-check `descriptor.hosts[].attempts` against evidence independent of the release-side filesystem:
  - the detached-launch receipts or coordinator dispatch records for every END reference launch on 01, 03 and 08;
  - a directory listing of each original measuring host's attempt root;
  - the push time of the `attempt_roots` declaration on origin, not its committer date.

  Any launch with no descriptor attempt fails the packet.
- **PC2 (production packet review).** `measurement_source.files` must equal the inventory of the final **reviewed** E4 commit. The barrier binds E4 bytes to the attempts' identities but not to a reviewed commit, so a committed E4 edit used consistently by the attempts would pass the code checks.
- **PC3 (operational).** Run the release under the same interpreter that produced the pool (e4v3-venv, Python 3.12). P6c shows that the rerun is interpreter-sensitive. It fails closed, and the check receipt does not record the interpreter.

## Notes (non-gating)
- **N1.** `from check_reference import check` resolves through `sys.path`, while `checker_sha256` hashes the file next to `release_reference.py`. Loading the checker by path (`importlib.util.spec_from_file_location`) would make that binding exact. The barrier code already shares the same `sys.path` trust, so this is hygiene.
- **N2.** Each release attempt leaves a `t1-release-recheck-*` scratch directory under `/mpac/sdicks02/tmp`. That is intentional, for reproduction. Clean them up after review.
- **N3.** As before, the coordinator-field `assert`s in `barrier.py` vanish under `python -O`. `prerequisites()` is a call, so the Amendment 1 gate survives `-O`.

## Summary for coordinator
**APPROVE_WITH_CONDITIONS.** C1–C4 are each fixed and verified on 05: 49/49 tests, 24/24 independent probes, and 73/73 on a trial merge with main.
- **C1:** a forged pool with a consistent hand-written check is denied by the in-barrier E4 rerun, and opens when that rerun is removed.
- **C2–C4:** omitted, hidden, archived or symlinked attempts, END ledger and inventory mismatches, and both fake and real E4 failures are all denied.
- **14-day escape:** it cannot run before the pool is committed and rechecked.
- **Outcomes:** none are read.

Conditions: admit via a merge with main that includes E4 24bfa017 (AC1). At the production packet, cross-check attempts against independent launch records (PC1), pin the reviewed E4 inventory (PC2) and use the same interpreter (PC3).
