# T5 technical resource amendment r2

Recorded before any retry; no held-out model inference. Original PREREG and
source snapshots remain unchanged and retained. The five scientific runs,
seeds, objectives, effective batch8192, primary microbatch7168, architecture,
selection/calibration rules and A1–A4 bars are unchanged. This amendment is
solely for observed technical failures, not tuning.

At10:26Z, the lease wrapper stopped13 and14 after aggregate process RSS reached
153,296,777,216 and154,109,530,112bytes. Both exited0 after saving resumable
checkpoints (main03 step61; noD1 latest checkpoint to be recorded). Read-only
random mmap pages are represented in every loader's RSS, so four workers breach
the shared-host64GB limit. Use one loader worker and evict read-only mmap pages
from each process after a batch has been copied into independent tensors. This
uses MADV_DONTNEED, changes neither files nor tensors, and retains OS page cache.
Validate exact features and bit-exact optimizer/EMA replay across worker counts.
T4's covered source remains hash-identical. Measure actual resumed throughput
from these same declared runs; do not run a new fitting/throughput trial.

GRU08 exited1 at10:26:46Z: CUDA OOM allocating1008MiB with184.56MiB free during
step3 backward. Steps1–2 completed, but no scheduled1000-step checkpoint existed.
Retain the failed segment and restart the same seed as an explicitly justified
technical retry. Reduce ONLY the added historical-context encoding chunk to1024;
retain current-endpoint primary microbatch7168 and effective8192. All32 historical
CLS states remain differentiable and causal. Save GRU checkpoints every10steps
in addition to every epoch to bound future technical loss. No run outcome was
used to choose this operational change.

Freeze revised source and registration BEFORE resume. To keep one coherent
execution manifest, gracefully checkpoint the healthy04/11 runs, then rebind
only checkpoint provenance hashes under a recorded migration receipt; verify
every model/EMA/optimizer/scheduler/RNG/sampler/config value bit-for-bit unchanged.
All original checkpoints and snapshots are retained. These are continuations
of the same five runs, not additional trials. No new T4 shakedown or optimization.
