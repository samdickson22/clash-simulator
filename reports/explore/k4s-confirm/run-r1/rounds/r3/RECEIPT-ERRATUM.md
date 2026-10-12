# K4S run r1, round r3: receipt erratum (time labels; audit F2)

- **Recorded:** 2026-10-12T11:42:44Z (`date -u`) on 127x05, under the coordinator's cut-3 rulings on the round r3 audit.
- **Audit:** `audits/ROUND-r3-AUDIT.md`, retained verbatim, sha256 `1506eb25029adb6f53516e18c96cd0f68bba9bf18e8d43f51ecd920a19c1da00`. Verdict PASS_WITH_NOTES.
- **The receipt stays as committed.** `rounds/r3/RECEIPT.json` (`0fa8685f…`) is not edited. Where the two differ, this erratum supersedes it. No count, hash or launch fact changes; only these labels.

| Field | Receipt said | Corrected | Source |
|---|---|---|---|
| `cut` label | "P2 cut 2 (04 apt-daily 11:20:02Z)" | **04 apt-daily fired 2026-10-12T11:20:06Z** (11:20:02Z was the scheduled time) | timer LAST "Mon 2026-10-12 04:20:06 PDT" in `evidence/step6/127x04-timer-wait.txt`, read at 11:20:32Z |
| `times.copier_exit_03` | 11:10:10Z (copy-health `utc`) | **2026-10-12T11:10:02Z** | `finished_utc` in the hub and source admissions, `evidence/step2/127x03-{hub,source}-copier-admission.json` (copier 485959) |
| `times.copier_exit_04` | 11:10:08Z (copy-health `utc`) | **2026-10-12T11:10:01Z** | `finished_utc` in `evidence/step2/127x04-{hub,source}-copier-admission.json` (copier 494063) |
| `times.coordinator_go` | 11:22:52Z (my receipt time) | **go_utc 2026-10-12T11:22:39Z** (COORDINATOR c00317cf, committed 11:22:38Z) | GO receipt, per the audit |
| `times.timeout` | 11:52:52Z | **2026-10-12T11:52:39Z** (go_utc + 30 min) | Not reached: releases were relayed at 11:24:49Z (04) and 11:26:38Z (03). |
| stamps/timers read time | (none; file names only) | **03 2026-10-12T11:28:27.9Z, 04 11:28:28.3Z** | 05 write mtimes of `evidence/step6/{127x03,127x04}-stamps-timers.txt` (the reads finished just before). No `date -u` was captured at read time. |

**Copier-exit proof (audit F2c).** The copier-exit times in r3 are proved only indirectly: `active=false`, `finished_utc` and `revoked=true`. The `ps -p` wait loop printed "copier-exited" but was not persisted.

**From r4 on:**
- Every evidence file records the `date -u` of its read inside the file.
- The copier-exit wait output and the `ps` result are persisted.
- Each event gets exactly one time, taken from its primary record.
- The read-window timeout counts from the GO's `go_utc`.
