# safe-input-r2 PROGRESS (resume file)

Started 2026-10-12T20:23Z on 127x05. Copied from safe-input-r1 (cp -a). origin/main seen: 1059663e (fetch), 1a0eb1d5 (later fetch).

## Done
- [x] M0 copy r1 -> r2
- [x] M1 read r1 README/ADOPTION/safe_input.py/tests, SOL-REVIEW-END-S2S4-r3, SOL-REVIEW-END-PKG2-r1, COORDINATOR (Q2-Q6, 16:00Z scope, E1-E3, E4, R6/R7, P2-1..3, P2-4 18:03Z, D1-D4 18:19Z)

## Design decisions (r2)
- git 2.25.1 on 05: GIT_CONFIG_GLOBAL unsupported (set anyway; HOME=empty temp + XDG_CONFIG_HOME inside it makes it moot). GIT_CONFIG_COUNT unsupported in 2.25 (positive control may not reproduce; record).
- Families (casefold, per component, fnmatch-style), two classes:
  OUTCOME (never grantable; only E4 exact, D3 hash-only): games / hub-blocks tokens (delimited by start/end/[._-]); *complete*.json*; *interference*.json*; *hub[-_]ack*.json*; *end[-_]raw*.json*.
  END-CLAIM (grant end-claim-exact, exact names only): end-job*, end-final*, *attempt[-_]*.json* (S6 registry/attempt-NN.json and durable-measurement/attempt-claim.json need it).
  Plus existing: k4s-confirm-* (reporting-job-exact), k4s-end-guard-* (guard-job), strict END pair (end-json-exact), T1 launch namespaces, 04 perception, v4 cache.
- GitRepo declaration + _git() single helper; scrubbed env allowlist; --no-replace-objects, -c core.hooksPath=/dev/null, core.fsmonitor=false, protocol.allow=never (unless declared protocols), GIT_NO_REPLACE_OBJECTS=1, GIT_OPTIONAL_LOCKS=0; --git-dir explicit; refuse alternates/http-alternates/grafts/shallow/commondir unless declared.
- Two-phase: git_plan() = ls-tree -r -l -z --full-tree + all screening -> GitPlan; phase 2 via cat-file --batch (type+oid+size header verified, OID recomputed) ; counter GIT_BLOB_READS.
- E4 blob OIDs pinned from ls-tree metadata (names/oids only), so changed exact-path E4 refuses pre-read (S4-R3-F3). Flag for coordinator ratification.
- E1 materialised (D2): link oid computed from link text, checked in phase 1; link blob read+compared; target blob; verify shipped regular file bytes == target.
- D3: exemption "D3", role name s6-*, root == END_RECEIVED/<03|04>, rel <attempt>/durable-measurement/.../end-raw.json|end-complete.json, seal files must exist; hash only vs caller seal sha.
- D4: receive mode via fixed single-quoted bootstrap `python3 -I -S -c '<reads N program bytes from stdin.buffer, checks sha argv, exec>' N SHA HEXREQ`; framed stream: 8-byte len + manifest JSON, then file bytes in order, then EOF.

## Next
- [x] M2 (code written, untested): families in _CORE; constants (E4_GIT_BLOB_OIDS, E1_LINK_OID, D3_*); Role D3 checks; _gate d3; hash_sealed_end_member; Writer via mkdir_excl_at/create_excl_at; run_checked iterable stdin; git section replaced (GitRepo, git_run, _git_object, _screen_tree, git_plan/GitPlan, git_e1_check/verify_shipped, git_export copy-only)
- [x] M3 receive mode (_RECEIVE_MAIN, RECEIVE_BOOTSTRAP, build_receive_manifest, remote_receive, parse_receive_receipt) + CLI receive-program-sha256 (untested)
- [x] M4a r1 tests patched (canaries END grant, names lookalikes/grants, git fakes -> batch format, subprocess .git dir); 245/246 pass on 3.12 (only fingerprint pin pending)
- [x] M4b test_families.py (123 pass), test_git_r2.py (34 pass) on 3.12. Probe finding: git 2.25 --no-replace-objects does NOT disable info/grafts (grafts refusal load-bearing); GIT_CONFIG_COUNT unsupported on 2.25.
- [x] M4c test_d3.py (18), test_receive.py (31); added repo-config indirection gate (_check_git_config) + tests; removed 'log' subcommand. Real checkout is a partial clone (promisor) -> missing blobs refuse (no lazy fetch): ADOPTION note. Real checkout passes static preflight.
- [x] M5 (prelim) matrix 463/464 x 6 runs (only fingerprint pin unset). pytest in /dev/shm/si-r2-pytest38 (8.3.5), /dev/shm/si-r2-pytest312 (9.1.1); runner /dev/shm/si-r2-matrix.sh
- M5 run suites (3 interpreters x normal/-O)
- [x] M5b fingerprint extended (git/receive constants) + pinned 6661ca0b...; extra controls added; matrix 470/470 x 6 (py38, k4s-freeze, e4v3; normal and -O)
- M6 mutants: mutate.py now has --jobs/--check-edits; NEXT: add EQUIVALENT dict, fix r1 edit targets, add new mutants, run --jobs 16 on 3.8 -O and 3.12 -O -> MUTATION-RESULTS-py38-O.json / -py312-O.json
- M7 README/ADOPTION/D5 list/SHA256SUMS; final report

## Facts gathered (metadata only)
- E4 blob OIDs at origin/main 1a0eb1d5 (ls-tree): E2 7c9502037a75263dcfaaf5ab33666d2b8382a201, emulator-host a2f94dd0ce1ab1f4b233d63201a454318dc0ecff, gap 9e15e1f73e4f3dd05fa635da0f621851a52c873a, supp 1a73d2e1c54ab69fac9433047a8c957c3693d055 (last 3 == Sol PKG2 review).
- E1: 120000 a79f7391145ebef5f3715c763e399d3536ed1c0c == sha1("blob 28\0examples/visualize_battle.py"); target 100644 b39cbbcd...
- r1 mutation run ~3 s/mutant.
- S6 layout: end-received/<host>/<attempt>/{registry/attempt-NN.json, durable-measurement/{receipt-manifest.json,.sha256, attempt-claim.json, ...}}
- [x] M6a mutate.py: 244 mutants (r1 re-targeted + r2 gates), EQUIVALENT documented, NULL controls (must survive), --jobs. Edits all valid.
- M6b RUNNING: py38 -O -> /dev/shm/si-r2-mut38.json ; then py312 (k4s-freeze) -O -> /dev/shm/si-r2-mut312.json (copy into dir as MUTATION-RESULTS-*.json when done)
- [!] M6b first py38 campaign VOID: test_helper_home_is_fresh_and_removed compared the shared tempdir listing (racy under --jobs) -> 5/6 NULL controls failed, 122 kills attributed to it. Test fixed (per-call HOME checks only). S10 mutant fixed (pass body). Re-running.
- [x] ADOPTION.md r2 written. D5-TRACKED-FAMILY-MATCHES.txt written (origin/main f15691b5: 371 matches, 10 D1 members, 9 not E-listed -> refused until ruling).
- [x] M6b py38 run2 valid (6/6 NULL survived): 238/244; survivors Q11,SD01,SD08 = masked (equivalent; joint Q11J/SD01J/SD08J added), GH14/RV20/RV21 = test gaps (fixed). 15 kills only by fingerprint pin -> --recheck-without added. Suite 472.
- M6c RUNNING final: py38 -O and py312 (k4s-freeze) -O, --jobs 12, --recheck-without test_cli_publish_ps.py::test_constants_fingerprint_is_pinned -> /dev/shm/si-r2-mut38-final.json, /dev/shm/si-r2-mut312-final.json
- [x] M6c FINAL: py38 -O 244/247, py312 -O 244/247 (not killed = documented equivalents Q11/SD01/SD08; joints Q11J/SD01J/SD08J killed); 6/6 NULL survived each; 15 fingerprint-only kills re-killed without the pin. Results installed (annotated) as MUTATION-RESULTS-py38-O.json / -py312-O.json; safe_input.py f9ca4926...
- [x] M5 FINAL matrix: 472 passed x 6 (3.8.10, k4s-freeze 3.12.12, e4v3 3.12.12; normal and -O)
- [x] M7 README filled (fingerprint 6661ca0b..., remote ff6f9fa4..., receive d259318a...)
- [x] M8b /tmp/si-git-home-* leftovers (400, only 'planted') removed; test hermetic. FINAL re-run: matrix 472 x 6; py38 -O 244/247, py312 -O 244/247 (equivalents Q11/SD01/SD08; joints killed; 6/6 NULL survived; 15 rechecks killed); 0 leftover homes. Results reinstalled.
- [x] M9 SHA256SUMS written; /dev/shm scratch removed. DONE - candidate ready for Sol review. Nothing committed/pushed; no ssh.
