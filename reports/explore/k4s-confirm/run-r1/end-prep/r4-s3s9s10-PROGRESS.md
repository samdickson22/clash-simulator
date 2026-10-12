# r4 S1b/S3/S9/S10 safe_input adoption (s3s9s10-r2) — PROGRESS
started 2026-10-12T21:30:06Z on 127x05
## done
- created s3s9s10-r2 (cp -a s3s9s10-r1)
## next
- read reviews / safe_input README+ADOPTION / coordinator rulings
## test status
- none yet
- 21:45Z read: SOL PKG2 r1, S2S4-r3 must-preserve, safe-input-r2 README/ADOPTION/safe_input.py API, rulings 15:41Z..21:28Z (origin/main 27b54d9d), r1 README/common/S1b/S3
- 22:05Z design decided (see below); facts gathered: HISTORY_SHA256 94ee52e0 (health metadata only); D1 needs 6 support files (pin lists, K4S manifest, PROCEDURE.md, spec-pins.json, build_tiers.sh); Q5 source = T1 CANDIDATE/runtime exact paths; fake host = unshare -Urmu + bind /mpac/sdicks02 + hostname (works on 05)
## design
- common: pinned safe_input load (hashlib verify, exec verified bytes), renameat2 NOREPLACE, scrubbed env, output confinement
- S1b: si.remote_check per host (2 logins); output in E3 layout <dest>/end-guard-admissions/<host>-<name>
- S3: REPO_FULL source; git_show_file w/ expected SHAs; s1b manifest+sha required; -pfNN; guard repo via git_run init/fetch(file, upload-pack allowAnySHA1)/checkout; refs written as loose files via Writer; FETCH_HEAD unlinked in own partial
- S9: prepare-clone (run_checked https clone, verify), D1+support members via git_plan, R6, equivalence hard gate
- S10: P=remote_check+facts(status-preserving), skeleton receive, per-component receive, F=check+mv in one session, post check; bundles only; refuse SYNTHETIC
- 22:40Z written (untested): end_prep_common.py, s1b_copy_admissions.py, s3_guard_job.py, s9_end_runtime.py; vendored safe_input.py (r2 f9ca4926); removed r1-only artifacts (RUNNER-PATCH-E3.diff, s9-locate-caeeecdc.json, s10-dry-run-EXAMPLE, old SHA256SUMS)
- next: s10_stage_host.py, then tests (synthetic world: fixture repo, fake frozen modules, namespaced fake host)
- 23:05Z s10_stage_host.py written; all modules import on py3.8; removed r1 tests (rewriting: synthetic world, no real repo/T1 reads)
- 23:20Z tests/conftest.py (synthetic world + namespaced fake hosts) + tests/test_flow.py: 5/5 pass (k4s-freeze normal). Next: test_common/test_s1b/test_s3/test_s9/test_s10 incl. Sol probes
- 23:35Z test_common 26/26, test_s1b 27/27 (incl. Sol S1b-F1 hard-link probe), test_flow 5/5. Next test_s3, test_s9, test_s10
- 23:50Z test_s3 34/34 (S3-F1/F2 probes, pf form, replace/env/alternates/grafts/hooksPath/include/filter/gitfile); total 92 pass, no tmp leftovers. Next test_s9, test_s10
- (time typed earlier was a guess; see stamps below) test_s9 47/47 (S9-F1/F2 probes, D1 non-member never read, phase-1 refusals, E4 hash-only + OID pin, R6, equivalence gate, clone verification, env/replace/grafts/alternates). Next test_s10
- NOTE 2026-10-12T22:03:14Z: earlier hand-typed HH:MMZ stamps in this file are approximate; from here stamps come from date -u
- 2026-10-12T22:07:55Z test_s10 48/48; FULL SUITE 187 passed x4 (k4s-freeze normal/-O, py3.8 normal/-O; pytest 8.3.5 for 3.8 in /dev/shm/s3s9s10r2-pytest38). RC6-ROOTS-DRAFT.json written. Next: isolate-gate tests + prove_repo FETCH_HEAD check, then tests/mutate.py
- 2026-10-12T22:11:55Z mutation run1 VOID (NULL controls failed: RC6 json not copied); fixed driver; NULL now survives. Re-running.
- 2026-10-12T22:16:25Z mutation (r2 pin, py312 -O): 70/77 killed, NULL 4/4 survived, no outside writes; survivors C04 T13 N20 X12 X15 X17 X21 -> add tests / classify. safe-input-r3 DONE + sha256sum -c OK -> switching pin to r3 (806e5ebb) + E5 adoption
- 2026-10-12T22:21:24Z r3 adopted (pins 806e5ebb/33f594ed/2d2f212d/39a92e9d; r3 README receive sha 979b37a1 does not match bytes -> disclosed), E5 member in synthetic world; suite 211 pass (freeze normal); targeted mutants: survivors only N20/X17 (documented equivalents); removed leftover /tmp/k4s-r2t-ecoljz6d from crashed teardown. Starting final campaigns py312 -O and py38 -O
- 2026-10-12T22:27:50Z FINAL mutation r3 py312 -O: 80/82 killed, survivors N20 X17 (documented equivalents), NULL 4/4 survived, outside_writes false, no tmp leftovers. py38 campaign running. RESPONSE-r1.md + README.md drafted (TBD numbers).
- 2026-10-12T22:41:53Z FINAL: mutation r3 py38 -O 80/82 (N20,X17 equivalents), NULL 4/4; test matrix 211 passed x4 (freeze N/O, py38 N/O) 22:34-22:41Z; README filled. Next: SHA256SUMS, diff summary, cleanup /dev/shm scratch
- 2026-10-12T22:42:20Z SHA256SUMS written; /dev/shm scratch removed (kept /dev/shm/s3s9s10r2-pytest38). DONE pending final report.
