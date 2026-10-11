# Response to SOL-REVIEW-CORE-r5 (APPROVE_WITH_FIXES)

Author: K4S prep worker (Opus), 2026-10-11.

| # | Fix |
|---|---|
| 21 | `source_binding.snapshot` now re-validates the **complete** runtime pin each time it runs: every `files` entry against `job/repo` (all 1557 inherited files plus the pinned K4S overlay files; 1709 entries in total on a real staged job), every `native_source` entry against `job/native-source` (77), and every `inputs` entry against `job`, as before. It uses the same rule as the inherited `pin.verify`. Mismatches are collected as diagnostic errors, so `t1_matches_ef4c073a` becomes false. Record, verify and assembly therefore all fail with FAIL and nonzero exit, because assembly recomputes the snapshot. On the real dev4 job on 127x03 the snapshot passes: 1709 + 77 entries, 0 errors, 0.5 s. A mutation of a shared source such as `reports/explore/e1/policy.py`, `student-source/exit_r3/network.py` or `src/clasher/rl/c56_rollout_planner.py` is caught, because each is a pinned `files` entry. |
