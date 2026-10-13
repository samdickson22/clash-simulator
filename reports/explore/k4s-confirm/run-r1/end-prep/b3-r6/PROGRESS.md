2026-10-13T05:42:44Z START b3-r6 = copy of b3-r5 (SHA256SUMS verified OK before copy); worker on 127x05
2026-10-13T05:43:39Z STEP1 assembler edited: members() accepts dict keys (or list items) per frozen set(); per-file SHAs not compared; assembler_sha256 also in stderr summaries (receipt field assembler_sha256 already present)
2026-10-13T05:45:50Z STEP2 frozen root: 43 paths (si.name_gate 0 refused) git archive 6313e14b -> /dev/shm/b3r6/frozen-9H0loK
2026-10-13T05:47:16Z STEP3 tests: fixture -> dict (test_assemble_fleet_reference.py:145, :589-590; test_s4_r4_git.py:564); new test_s4_r6_runtime_pin.py (21 pass on 3.12 alone)
2026-10-13T05:48:10Z STEP4 production proof started: scratch /dev/shm/b3r6-proof-wggrxn, driver /dev/shm/b3r6/proof.py, S4 sha 76b7b7cf4b9a7ebf9cbcaa46a6d6f1baefca36b40148f6f104d5055cafa4dd63
2026-10-13T05:50:20Z STEP3b suites (pre-REPO_FULL-absolute-path edit, interim): py312 normal 543 passed/2 deselected; py312 -O 543 passed/2 deselected. Final reruns after all edits pending
2026-10-13T05:52:54Z STEP5 mutation (mutate_s4_r6.py, 3.12 -O): 13/13 KILLED (each by all its named tests + suite), 2/2 NULL survived -> MUTATION-RESULTS-r6.json
2026-10-13T05:54:28Z STEP4b production proof done: 6/6 PASS rc 0 (S4 76b7b7cf…, e4v3-venv -I -B, env -i, nice 19, taskset 8-15), runtime_files 4307 canonical = S9 fc3dbeb4…; every bundle deleted; scratch /dev/shm/b3r6-proof-wggrxn removed -> PROOF-r6.json
2026-10-13T06:00:57Z STEP6 final suites on final bytes: 543 passed, 2 deselected (test_production_q6*), 0 skipped, on k4s-freeze 3.12 normal/-O and /usr/bin/python3 3.8 normal/-O; --collect-only verified before each
2026-10-13T06:01:36Z STEP7 scratch /dev/shm/b3r6 (frozen export, logs, drivers) removed; README r6 section + RESPONSE-r6 proof/mutation tables written
2026-10-13T06:01:36Z DONE b3-r6: tests 543 passed / 2 deselected / 0 skipped x4 (3.12 + 3.8, normal + -O); mutation 13/13 KILLED by named tests, NULL 2/2 survived; production proof 6/6 PASS (bundles deleted); S4 sha256 76b7b7cf4b9a7ebf9cbcaa46a6d6f1baefca36b40148f6f104d5055cafa4dd63; SHA256SUMS covers 30 files (every file here except SHA256SUMS, incl. this PROGRESS.md)
