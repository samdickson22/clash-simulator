SA-2 follow-up sweep (read-only, 2026-10-13 ~05:47Z): every .py in J/base/repo (1,344 files) vs origin/main (55254853 tree)
- 1,298 byte-identical; 17 differ; 29 not on origin/main.
- Differ, import-traced in base/repo (grep of importers, tests excluded):
  * imitation/evaluation/paths.py — RUNTIME-IMPORTED (d1.py, fast_prior.py, emitter). The base adds
    SNAPSHOT_ROOT/imitation/evaluation/runtime_dependencies to setup()'s path list. It is byte-equal to the shared worktree's
    uncommitted edit; this is the frozen X4S-3 base that X4S-3's games ran on.
  * imitation/evaluation/{run_gate,register,run_p16,smoke,p16_adapter,seed_audit}.py — the gate harness. They import
    each other, plus s6 start_preflight/start_confirmation; no X4S-4 path imports them. Equal to the worktree's edits.
  * src/clasher/live/decision.py, src/clasher/vision/l1_v4.py — live/perception only.
  * src/clasher/analysis/loss_review/simulate.py — no importers.
  * reports/explore/{w-screen8/run.py, w-screen8/parity.py, e1/reduce.py, e1/write_report.py, w-confirm/write_report.py,
    x4s3/reduce.py, x4s3/verify_g.py} — report/driver scripts. No X4S-4 path imports them: x4s4/write_report's
    `import reduce` resolves to x4s4's own reduce.py (sys.path[0]), and e1/planner loads w-screen8/planner.py (equal to main).
- Not on main (29): untracked in the shared worktree and byte-equal to it, except the 8 student-source/exit_r3 files and
  imitation/__init__.py, which are absent there.
  * RUNTIME-IMPORTED: src/clasher/analysis/loss_review/delay_fixes.py (the emitter's CommandQueue), plus its siblings
    delay_runtime, delay_simulate, scheduling, search_ab, tempo, throughput_guard.
  * imitation/evaluation/runtime_dependencies/{sidecar_observer,derived_d1,own_cycle}.py, seed_compat.py, legacy_audit.py.
  * The rest are tests.
- Conclusion: no other W-screen8 / delay-path skew. delay.py was the only file on the emitter's W path that was older
  than main. The runtime-imported differences (paths.py and the untracked loss_review/runtime_dependencies modules) are
  the X4S-3 frozen base as qualified. Nothing was changed.
