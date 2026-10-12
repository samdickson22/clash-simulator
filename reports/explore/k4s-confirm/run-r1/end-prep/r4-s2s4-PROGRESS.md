# r4 S2/S4 safe_input adoption — PROGRESS
started 2026-10-12T21:28:42Z on 127x05
## done
- created s1s2-r4 (cp -a s1s2-r3) and b3-r4 (cp -a b3-r3b)
## next
- read reviews / safe_input README+ADOPTION / coordinator rulings
## test status
- none yet
- 21:33Z read Sol S2S4-r3, safe_input r2 README/ADOPTION, coordinator E1-E5/R6/R7/P2-1..4/D1-D4 + 21:28Z (E5 exact path+OID; full clone; frozen-reader wrapper)
- vendored safe_input.py (f9ca4926) byte-identical into s1s2-r4/ and b3-r4/
- baseline: S2 suite in s1s2-r4 (unchanged copy) passed rc=0 (k4s-freeze, normal)
## design decisions (S2)
- per-invocation si.Policy (host = this node; production requires 127x05) with roles derived from the operator's explicit, lexically pre-gated paths: repo (git+worktree), code, s1/s1-dest, profile, out
- frozen git reads (fleet_end.artifact) run inside frozen_git_env(): os.environ = GIT_FIXED_ENV + fresh HOME + declared GIT_DIR/GIT_WORK_TREE; preceded by si preflight + empty refs/replace + si.git_show_file of every artifact with its expected SHA
- si.Refusal -> S2Error("<label>: safe_input refused [code]: reason")
- 21:46Z S2 r4 code adopted (loader+pin, gate_paths->si.Policy/roles, Checkout/si.git_run, frozen_git_env, bootstrap/validate/diagnose/build via si). tests/test_s2.py 53/53 pass (normal). Next: fix test_s2_gate_profile.py (~35 failures: messages + removed helpers)
- 21:55Z S1/S2 suite incl. new tests/test_s2_r4_git.py (41): 264 passed normal + 264 passed -O (k4s-freeze). S1 sha unchanged b987ab97.
- next: S2 docstring r4 text; then S4 adoption; then mutation S2+S4; RESPONSE-r3.md, README, SHA256SUMS; py3.12 e4v3 smoke
- 22:05Z S4 r4 code written (b3-r4/assemble_fleet_reference.py: loader+pin, Sources roles, RuntimeInventory via si.walk_tree + E5 hook walk, Committed via si.git_plan, Output via si.Writer + publish rename). World fixture updated (D2 regular E1, synthetic_e4 monkeypatch of si E4 dicts, new pin keys). Suite: 148 pass / 146 fail / 17 errors -> triaging (mostly messages + removed helpers)
- 22:15Z S4 existing suite adapted: 313 passed, 25 skipped (no K4S_FROZEN_ROOT), normal. Test harness fix: audited fixture now wraps os.open (inode of returned fd; dir_fd-resolved path) because si opens relative to dir fds (audit 'open' event alone was blind). Renamed tests whose pytest tmp dir would contain 'games'.
- next: b3-r4/test_s4_r4_git.py (replace refs, GIT_* env, alternates/grafts/hooks/config/gitfile, late unlisted complete.json zero object reads, S4-R3-F2 names + case variants, E5 hook); then frozen run with temp worktree; -O; py3.12 e4v3 smoke; mutation; docs
- 22:20Z S4 new tests test_s4_r4_git.py: 101 pass. Frozen run (K4S_FROZEN_ROOT=/dev/shm export of 43 exact origin/main 15048bd4 files via git archive; no worktree, no games/ written): 439 passed normal.
- 22:20Z S4 frozen -O: 439 passed
- 22:37Z added loader/pre-read/ordering/SHA tests: S2 test_s2_r4_git.py 46, S4 test_s4_r4_git.py 111 (both pass normal). Next: mutation drivers mutate_s2_r4.py / mutate_s4_r4.py (scratch /dev/shm, basetemp tempfile /tmp for S2)
- 22:39Z S2 mutation campaign started (tests/mutate_s2_r4.py, 63 mutants + 3 NULL, -O, jobs 16, scratch /dev/shm/k4s-r4-s2s4/mut-s2, log mut-s2.log)
- 22:40Z S4 mutation campaign started (mutate_s4_r4.py, 37 + 3 NULL, -O, jobs 12, frozen root; log /dev/shm/k4s-r4-s2s4/mut-s4.log)
- 22:45Z S2 mutation: 60/63 killed (3 documented equivalents, joints killed; NULL 3/3 survived). S4 first campaign 31/37: fixed (manifest-mode test, --out JOINT, classifier counts fixture errors); final S2/S4 matrices + S4 mutation re-run started
- 22:53Z FINAL: S1/S2 269 pass x4 (2 interps x normal/-O); S4 449 pass x4 frozen + 424/25 skip; mutation S2 60/63, S4 34/38 (all survivors documented equivalents, joints killed, NULL survive). Docs written; SHA256SUMS written. Remaining: cleanup /dev/shm/k4s-r4-s2s4
- 22:54Z DONE. /dev/shm/k4s-r4-s2s4 and frozen export removed. Final SHAs in s1s2-r4/SHA256SUMS and b3-r4/SHA256SUMS.
