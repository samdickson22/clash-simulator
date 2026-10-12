# r4 S5/S6/S7 safe_input adoption (s5s6s7-r2) — PROGRESS
started 2026-10-12T21:30:29Z on 127x05
## done
- created s5s6s7-r2 (cp -a s5s6s7-r1)
- read SOL PKG2 r1, S2S4-r3 preserve list, safe-input-r2 README/ADOPTION, COORDINATOR (origin/main bb1d4472; 15:16Z=4af19c23 attempt rules, 15:23Z plan, 15:41Z Q2-Q6, 16:55Z E1-E3, 17:12Z E4, 17:23Z R6/R7, 17:30Z P2-1..3, 18:03Z P2-4, 18:19Z D1-D4, 21:28Z E5/full clone/frozen-reader), END-PLAN-v2, PLAN-REVIEW RC-2..RC-9
- vendored safe_input r2 (f9ca4926) into s5s6s7-r2/
- wrote k4s_end_host_tool.py (registry listing/snapshot, verify_clone, frozen_git_env, frozen-exec)
- wrote k4s_end_preflight.py r2 (FROZEN_CLOSURE 32 pins, layout, bundle_stamp, Store via si.Writer, verify_received via si)
- wrote k4s_end_exit_push.sh r2, k4s_preflight_push.sh r2 (host-tool si CLI, frozen-exec, TRANSFER-DONE, registry-snapshot)
- wrote k4s_end_verify_push.py r2 (C-d, D3, registry via end-claim-exact, sealed_names, fixed launch paths)
- wrote k4s_end_launch_remote.py r2 + k4s_end_launch_gate.py r2 (RC-6 decl, fixed role paths, RC-9 schema/provenance, P2-3 bands, C-d, RC-7 ADMISSION)
- tests/repin.py (dependency-ordered pin rewrite; --check)
- tests: helpers r2 (ok/raises, fakepy uname shim), s5_fixture, fake_frozen r2
- test_s7_gate.py 106 pass x4 (G.optimized patched in Site; real -O refusal tested); full suite 262 normal on py312+py38 at ~22:40Z
- added closure_only() + test, verifier member-sha case
- tests/mutate.py written (74 mutants + 6 NULL; check-edits OK); py312 -O campaign started ~22:50Z -> /dev/shm/s567r2-MUT-py312.json
- r2-pinned py312 -O mutation: 61/74 killed, 6/6 NULL survived; gaps closed by new tests (P02,P03,P07-P10,P19,P23,P25,G15,R05 re-killed); P14/P22 documented equivalent
- README r2 drafted (placeholders @@PIN@@ @@TESTS@@ @@MUTATION@@ @@END@@); RESPONSE template at /dev/shm/s567r2-RESPONSE.template.md
- ~22:31Z SWITCHED PIN TO r3: safe-input-r3 SHA256SUMS OK + DONE; safe_input 806e5ebb, fp 33f594ed; repin done
- final matrix (r3 pin): py312 276 / -O 254+22skip; py38 276 / -O 254+22skip; logs /dev/shm/s567r2-final-*.log
- RESPONSE-r1.md generated (75 file:line refs; resolver /dev/shm/s567-resolve.py, template /dev/shm/s567r2-RESPONSE.template.md); diffs regenerated; unused static shims removed
- final mutation campaigns running -> /dev/shm/s567r2-MUT-final-py{312,38}.json
- final mutation (r3 pin): py312 -O 72/74, py38 -O 72/74 (P14,P22 equivalent), 6/6 NULL; installed MUTATION-RESULTS-*.json
- README filled, TEST-RUN.txt, diffs regenerated, SHA256SUMS (48 files) verified; /dev/shm scratch removed (kept s567r2-pytest38 + s567r2-runtests.sh)
- DONE 2026-10-12T22:45:17Z. Nothing committed/pushed; no ssh.
- (old) tests: rewrite fixtures (fake runtime w/ patched FROZEN_CLOSURE, fake python w/ uname patch, shims ps -e -ww), then S5/S6/S7 suites + Sol probes
## test status
- runner: /dev/shm/s567r2-runtests.sh py38|py312 [-O] (pytest 8.3.5 for 3.8 at /dev/shm/s567r2-pytest38)
- test_host_tool.py 26 pass x4 modes; test_s5_preflight.py 54 pass x4 (after -O verify-received fix); test_s6_wrapper.py 50 pass x4; test_s6_verifier.py 22 normal / 1+21 skipped -O (x2 interp)

## design decisions (2026-10-12 ~21:50Z)
- vendor safe-input-r2/safe_input.py byte-identical into s5s6s7-r2/; every py component loads it via stdlib O_NOFOLLOW/nlink/sha gate + constants_fingerprint pin (lazy, in main, not at import)
- S7 host program = prelude(base64 safe_input bytes, sha checked on host, exec as module) + CONFIG + body; body pinned
- TRANSFER-COMPLETE.json matches never-grantable complete-json family -> renamed TRANSFER-DONE.json (wrappers, verifier, preflight)
- strict END namespace dirs cannot be listed by si API (root/rel_dir inside k4s-confirm/end refused): names-only listing helper composed of si.open_root/open_dirs/os.listdir/si.name_gate (registry); flag for Sol
- D3 sealed dir cannot be walk_tree'd (end-raw.json refuses walk): names-only listing with name_gate(d3_leaf only for exact manifest D3 names)
- frozen-reader env: scrub GIT_*, set GIT_FIXED_ENV GIT_* keys + GIT_CONFIG_PARAMETERS(core.hookspath=/dev/null, core.fsmonitor=false, protocol.allow=never) [tested on git 2.25]; HOME kept (END parity) -> ~/.gitconfig + XDG git config statically checked via si._check_git_config; host clones checked via si.git_run(for-each-ref refs/replace/ == empty; _git_preflight), hooks dir only *.sample
- new host tool k4s_end_host_tool.py (registry-snapshot via si) for S6 wrapper (RC-5 push through si)
- S5: MANIFEST constant 74314eda; closure = k4s_files+end_files+reused_readonly+k4s_kernel.files+sd1 path, hashed via si before any import; post-run loaded-module check; new args --bundle-pins-sha256 --compare-bundle-pins-sha256 --corpus-inventory-sha256; 03 min hold 120s (no live top-up reads: growing file refuses in si); mode binding|diagnostic; bus band proceed/coordinator-decision/stop/unavailable
- RC-6 roots declaration schema clasher.k4s.end-roots-declaration.v1 consumed by S7 (fixed path RUNNER/end-launch/ROOTS-DECLARATION.json, pinned sha)
- S7 local inputs at fixed role paths under RUNNER/end-launch/<host>/<attempt>/ (no free paths)
