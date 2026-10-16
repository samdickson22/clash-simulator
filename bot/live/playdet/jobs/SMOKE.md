# 127x05 smoke receipt

2026-10-15 host environment; Python
`/mpac/sdicks02/repos/clasher-bot/.venv/bin/python`, `PYTHONPATH=.`,
`PYTHONDONTWRITEBYTECODE=1`, `nice -n 19 taskset -c 6-7`, BLAS/Torch one thread.
No bulk job launched, no commits, no existing source files edited.

Final integration invocation (before adding the final isolated augmentation
test): `PLAYDET_SMOKE=1 ... python -m pytest -q -s bot/live/playdet/test_build.py`:
**9 passed in 38.95 s**. It generated two complete T1 train recordings, one
complete sim and two 250-tick sim prefixes; the prefixes were byte-identical
and checked `--perfect` behavior. The subsequent lightweight suite, including
the new forced class-only/burst/frame-drop test: **6 passed, 4 integration
tests skipped in 0.31 s**. Tests also cover registered split SHA/membership,
heldout loader rejection, no dataset directory enumeration, origin/FP joins,
different Python hash seeds, atomic resume, orphan recovery and configuration
rejection. `bash -n jobs/commands.sh` passed. No 100-match run was performed.

Machine-readable timing/file hashes: [smoke-results.json](smoke-results.json).
Artifacts remain at `/tmp/pytest-of-sdicks02/pytest-2137/playdet-smoke0`.

* T1 `v4-phase-a-1975100700`: 2104 frames, 368805 bytes, 1.907 CPU / 1.917 wall
  seconds; exact main 187; child_unresolved 22; 6 non-spell deployments have no
  observed main body. 721 FP detections and 56 dropped frames.
* T1 `v4-phase-a-1975100701`: 874 frames, 117033 bytes, .747 CPU / .756 wall
  seconds; exact main 33; child_unresolved 15; 4 non-spell deployments have no
  observed main body. 279 FP detections and 44 dropped frames.
* Sim seed 2718281828, `v1` vs `scripted-pressure`: terminal at tick 3250,
  1301 frames, 176485 bytes, 15.126 CPU / 15.151 wall seconds; exact main 70,
  spawn 17, death 2; 7 accepted ability commands and 3 exact reappearance
  events. Zero unresolved origins or missing non-spell mains. 255 FPs and
  45 dropped frames. Perfect UnitTracker sanity: **34 plays vs 31 non-spell
  truth deployments** (no accuracy gate).

No smoke match sampled class-only mode on; the isolated test forces it on and
checks true_uid survives conversion. Main/spawn/death/ability origin joins and
FP flags validate. T1 main bodies use accepted spawned_native_ids; T1 non-main
children have source card known but parent/index null and origin child_unresolved.
There is no certified objectIndex/secondaryIndex parent interpretation in the
inspected collector/label code, so none was assumed. Sim source/parent comes
from synchronous engine insertion context, including delayed spell carriers.
Ability returns use engine hidden-to-visible transitions and stable unit IDs.

Per **100 T1 matches**, normalized from only these **two** recordings: **11000
exact main bodies, 1850 child_unresolved bodies, 500 accepted non-spell plays
without an observed main body**. This is a small-sample projection, not a
100-match measurement. Spawn/death/ability subdivisions of T1 children remain
unresolved; their apparent zero exact counts must not be read as zero actual
occurrences. The missing-main issue reflects snapshot/receipt coverage and is
reported rather than repaired with fabricated units.

Single-core process CPU cost, excluding initialization: T1 **1.327 s/match**
average; sim **15.126 s/match** for this terminal 3250-tick game. Runtime startup
was **14.649 CPU / 14.698 wall s per process**. For 1920 train + 240 validation
+ 2000 sim matches, using these small samples:

* Train .708 core-hours; validation .088 core-hours; sim 8.403 core-hours.
* Generation total **9.199 core-hours**; 48 independent shard startups add
  **.195 core-hours**, giving **9.395 core-hours** (1 core × 9.4 h, or ideally
  8 cores × 1.17 h). Actual parallel wall time depends on lease and contention.
* Compressed output approximately **877675040 bytes = .88 GB (.82 GiB)**,
  including perfect copies. Startup/build temporaries and manifests are extra.
* Tick-normalizing the sim cost to the full 6001-tick cap gives 15.516
  sim core-hours, or roughly **16.5 total core-hours** including T1/startups;
  similarly tick-scaled output is about **1.18 GB**. This is an allowance from
  one run, not a strict upper bound (unit density and bot pool affect cost).

Exact 03 commands, lease requirements, all 48 plain invocations, file schema,
noise details, lineage semantics and resume behavior are in [README.md](README.md).
`bash bot/live/playdet/jobs/commands.sh /mpac/sdicks02/jobs/clasher/playdet-r1 16`
prints the complete commands without starting any of them.
