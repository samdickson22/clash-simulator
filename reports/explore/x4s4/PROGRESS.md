# X4S-4 PROGRESS (exploration, NEVER ADOPTABLE)

Pins: QUALIFY-RUNBOOK 7b3ec27b (SHA-256 c55ba41d1ddf5e9a7d283d23622f1f53d336f40ccfd9aaf9fa4a6dbf9da0b763),
scripts d09bdef9aecc416cb83b002fcff002ff57579fde. GO: COORDINATOR commit 4b33d68d. This is the single combined
qualification + conditional production GO (Q-D1).

## 2026-10-13T03:37:03Z — Q0 seed audit (127x05, offline): PASS

- Command: exactly as in the runbook, from a git-archive export of d09bdef9 at /dev/shm/x4s4-q0. Pinned commit
  7f82af0d present; nice 19, cores 0–3.
- Exit 0. intersections = [], own_reservation_echoes = [], raw literal scan hits = [].
- 7,705 sources; source-list SHA-256 844ab58918b8e56ed6e367e21073e796fcc4ee90d7901584207add27c8e3f5af (the pinned v2
  inventory); 128 declarations parsed; omitted {not_text 458, outcome_path 812, sealed 2687, own 28, not_regular 1,
  alias_of_excluded 55}.
- Receipt: receipts/qualification/seed-audit.json, SHA-256 9275f2b6cf62535ee14a13bedfad06c674a5f360456e3a8249a07fbe8fb46f64.

## 2026-10-13T03:37:03Z — waiting for "U2 drained" (coordinator)

U2 finishes R3a-rep2's S-200 phase, then drains. There is no contact with 127x01 until the coordinator forwards
"U2 drained". After that come S-U2 (read-only verification), then S0–S3, then W0.
