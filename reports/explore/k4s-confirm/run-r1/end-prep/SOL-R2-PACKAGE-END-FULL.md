# K4S END tooling — full package for Sol r2 (fixes for SOL-REVIEW-END-FULL-r1)

Commit: 9ecf50b1f7e3cb6f7dfcf01294db7ebcbdf41d25 (origin/main). Prior review: `reviews/SOL-REVIEW-END-FULL-r1.md` (6918d77a). Coordinator ruling: COORDINATOR 3542e4d6. Offline only; no host step has been taken.

## Candidates (all under `reports/explore/k4s-confirm/run-r1/end-prep/`)

| Dir | Contents | SHA256SUMS sha256 |
|---|---|---|
| `bootstrap-r1/` | | `99efd8a68a5f786c2bec9df560f2d266a9111593a0726010569baa9d31e683da` |
| `s1s2-r5/` | | `a98da16275b3e37232b74f36fb32e9c92cb24e9190d93cc31e09dd2305a1a16f` |
| `b3-r5/` | | `59e6387152e5b440ec5cf24ddc79613fa480a0a7c466ca830054b45c611ca07b` |
| `s3s9s10-r3/` | | `e50fb4624cd287c2583055f1c4889025005bf1f5588359be023830bc4fe03010` |
| `s5s6s7-r3/` | | `d8b7d215d2e95695b46f26424ea7c94b85252e75ecb9e8ae1e418e6fbaf2ae32` |

Contents, in order: canonical bootstrap + conformance kit (F1); S1 unchanged (APPROVED) + S2; S4; Part A C/S1b/S3/S9/S10; Part B S5/S6/S7 + host tool + wrappers. Unchanged and still pinned: safe_input r3 `806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00` (safe-input-r3/, daaf9d00). Each dir has RESPONSE-r<N>.md mapping finding -> file:line -> named tests, MUTATION-RESULTS json, README and PROGRESS.

## Finding -> where fixed

- **F1 (bootstrap):** `bootstrap-r1/` canonical stdlib loader (`k4s_bootstrap_r1.py` 5611c604…, `k4s_bootstrap_loader_r1.py` 378c2b13…, `k4s_bootstrap_shell_r1.sh` 1ed816fa…): already-normalized absolute path (no realpath), outcome-family name gate on every component, O_NOFOLLOW|O_DIRECTORY walk from /, leaf lstat + fstat (same inode, S_ISREG, nlink 1, pinned size) before any read, SHA pin, exec of the exact hashed bytes. Pasted byte-for-byte (tested) into S2, S4, end_prep_common and every Part A entrypoint (chained pins safe_input <- common <- s9 <- s1b <- s3 <- s10), and into HT/PF/LG/EV plus both shell wrappers (sha256sum removed; `python3 -I -S -c` loader; new `host_tool_size`). Conformance kit asserts zero canary consumption (inode recorders, O_PATH atime, execution markers); reproduces F1 on the r4b files.
- **F2 (guard repo):** contract kept as S3's depth-1 shallow repo (documented in s3s9s10-r3 README). Host clone checks take a mandatory role; only `guard-repo` allows (and requires) shallow; `repository` stays full; both refuse promisor/partial-clone config and `.promisor` packs. Integration test feeds real S3-built guard jobs (`s3s9s10-r3/tests/fixture_guard_job.py`) through S5 and S7.
- **F3 (XDG/HOME):** relative, empty-but-set or non-normalized XDG_CONFIG_HOME/HOME refused; sole exception: the fleet passwd home `//home/sdicks02` canonicalized to `/home/sdicks02` and that value installed. One function builds the executed env and derives the exact config files git 2.25 reads (GIT_CONFIG_NOSYSTEM=1 required); identity test; `git config --list --show-origin` cross-check; Sol's `git -C` probe is a regression at S5/S6/S7.
- **F4 (full clone):** `S9.require_full_clone()` runs live first in S9 locate/build/verify/equivalence, S3 build/verify, S1b on repo-full (S10 via S9/S3 verify, before any login).
- **F5 (RC-9):** native/corpus/corpus-inventory identities pinned and compared against launch argv (S5 and S7); bundle binding `exact` when the END bundle is the preflight compare bundle, else only `guard-job-equivalent` (bundle digest without the guard job recomputed from pinned tiers-pins.json; refuses on any difference), mode recorded; 04 launch requires 03 completion from the same round and lineage (same RC-6 declaration and preflight receipts; 03 launch receipt read under the ACK's SHA); bus evidence finite and band-consistent with 0.3/0.7. Preflight schemas v3.
- **F6 (shim modes):** shims and wrappers committed 100755 (verified in the tree); helpers fail loudly on non-executable shims.

## Runner verification (pristine /dev/shm copies; nice 19)

| Suite | 3.12 | 3.12 -O | 3.8 | 3.8 -O |
|---|---|---|---|---|
| bootstrap-r1 (immutable siblings present) | 375 | 375 | 279 | 279 |
| s1s2-r5 | 331 | 331 | 331 | 331 |
| b3-r5 (no K4S_FROZEN_ROOT; real-Q6 deselected) | 498 + 24 skip | same | same | same |
| s3s9s10-r3 | 706 | 706 | 706 | 706 |
| s5s6s7-r3 | 611 | 561 + 50 skip (verifier refuses -O) | 611 | 561 + 50 skip |

Worker-reported b3-r5 with the frozen-root export: 522 + 2 deselected in all four modes. Mutation: bootstrap snippet 60/66 (6 = 2 null + 4 equivalents with killed joints); Part A 103/106; Part B 125/127; S2/S4 adopter 59/59 with the canonical-text test.

## Disclosures

1. Runner edit after the Part A worker: vendored kit synced to bootstrap-r1's final kit (adds `ancestor-symlink-plain-target`, additive; snippet unchanged), KIT_SHA256 pin updated, SHA256SUMS regenerated (addendum in s3s9s10-r3/RESPONSE-r3.md). No production byte changed.
2. In one S4 3.12 run the two real-Q6 tests executed once (deselect path mismatch). They read only the Q6 index states-rows.json and two file sizes; no outcome, no games/. All later runs use `-k "not test_production_q6"`, verified with --collect-only.
3. Entrypoints must be invoked with a clean absolute path (e.g. `python ./x.py` is refused on 3.12). The interpreter itself reads the entry script by the typed path before any bootstrap runs (residual).
4. Wrapper `frozen-exec`: a host tool replaced mid-run refuses with exit 90, which is recorded as END exit 90 (not distinguished from other refusals).
5. Part A in-process importers must import s10_stage_host first; a sibling imported the plain way first is refused, never reused.
6. The Part A 3.8 mutation campaign reported outside_writes because another thread created /mpac/sdicks02/probe5 and /mpac/sdicks02/l26w in its window (unrelated; verified by the runner).
