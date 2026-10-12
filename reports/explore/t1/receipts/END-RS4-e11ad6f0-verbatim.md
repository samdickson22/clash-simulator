
## 2026-10-12 16:37Z: RS-3 stopped at driver preflight (inherited setgid on release-private); RS-4 one launch

**What stopped.** T1's preflight passed every pin:
- driver 9ffbd2e1, release 6a767ffb, R5 3b7d2295 at the worker path, copy receipt d433dd54;
- canonical R at 2473c0a9 and clean;
- the worker tool directory exactly tracked.

It then created `t1-20261010-r1/release-private/` and asserted `mode & 0o7777 == 0o700`. The parent directory is mode 2755 (setgid), so the new directory inherited the setgid bit and is **2700**, and the assertion failed. The driver never launched. `release-private/` exists and is empty (coordinator read-only replay).

**Assessment.** This is harmless. The setgid bit only sets group ownership of new files; with permission bits 0700 there is no group or other access. The reviewed driver checks `st_mode & 0o777 == 0o700`, which passes. The runbook says "plain 0700", so the bit is cleared rather than waived.

**Ruling RS-4 (exactly once).**
1. T1 runs `chmod 0700` on the existing empty `release-private/` and records before/after modes. Do not delete or recreate it.
2. T1 relaunches its preflight once. Replace `mkdir` with: exists, is a directory, not a symlink, owned by the operator, empty, and `mode & 0o7777 == 0o700`.
3. T1 launches the driver once with the RS-3 arguments.

Do not repeat the cache move, builder or switch. Any failure is a STOP with no retry. `A3PRequiresRuling` comes back to the coordinator. There is still no 14-day route.
