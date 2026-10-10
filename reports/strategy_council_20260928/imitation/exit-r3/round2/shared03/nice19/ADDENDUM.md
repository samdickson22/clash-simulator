# Shared03 priority and PSI amendment

The coordinator07:06Z allocation delivered directly at09:38Z explicitly requires
nice19, max4processes on56–59, and a PSI guard. The previously deployed guard
required nice10. R3 drained only its own pool3111108 at09:39:24Z, preserving
8 complete command-exact games and whole-tree CPU1200.908737s; worker failures
on the newly owned STOP are retained and charged. G was never signalled.

Use nice19/SCHED_OTHER manager59/threeworkers56–58. In addition to existing
MemAvailable24GiB/G authentication/ownedSTOP/deadline checks, stop immediately
if memory PSI full avg10 exceeds10%, unavailable checks fail closed.

Before a reviewed version2 restart, commit/push/scan this exact source/seed
unchanged amendment, verify static pins, refresh admission and PSI/G audit.
Archive the owned STOP only after these checks; never clear G STOPs.

Reuse only the eight complete pre-stop seals explicitly SHA-pinned here, with
their unchanged JSONL and proposal hashes. Unsealed games replay fully. The
provenance checks accept these pinned older operational seals; score arithmetic,
command replay, roots, seeds, calibration, bootstrap and gates are unchanged.
All work, including interrupted games, is charged through complete pool meters;
do not add nested game CPU. All three arms remain killed; no Stage2 games.
