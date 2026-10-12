## 2026-10-12 03:40Z: 08 r2 diagnosis (E4 guard ownership race); ruling RG1: r3 as-is now, code-fix amendment drafted in parallel

**Diagnosis** (`END-08r2-DIAGNOSIS-r1.md`, T1 job dir): a race in E4's guard adapter, not host interference. `ReportingGuard.__call__` decides ownership on one `/proc` snapshot (`fleet_validity.py:135/144`) but runs the census on a later one (`:155`). The first 1 Hz sample after admission landed in the burst that spawns the 10 FleetBackground workers, so 4 of E4's own children were flagged `foreign_compute`.
- **Why it is near-deterministic on 08:** the admit guard call takes 1.24 s on 08 against 0.928 s on 01. A6 passed by about 0–20 ms.
- **Risk on an as-is repeat:** about 80–95% failure, always before warmup or timing, so a failure carries no information.
- **01 is not exposed.** `background_load` is entered once, and 01 is past the exposure point.
- **Rules:** r2 is attempt[0], counted, with `technical_repeat_candidate=True`. r3 is the only repeat left. If r3 fails, `fleet_pool` blocks the whole END pool until an outcome-blind amendment.
- **No procedural mitigation helps.** A code fix in `fleet_validity.py` is the only real fix. Because the pool binds code across hosts and attempts, the fix implies re-running both hosts.

**RG1 ruling:**
1. **08 r3 as-is.**
   - Run it under the full procedure (C5/C6, RF1, L1; fresh C2; V2 prepare proof; argv pin).
   - Have no SSH or ControlMaster session open to 08 at admission.
   - Launch after r2's C-d, its verifier ACK (failed status) and its L1 assembly, and within 08's C2 window.
   - **If r3 fails with the same signature** (E4 spawn children whose ppid is E4 flagged `foreign_compute` at the first post-admission sample): STOP and go to step 3. Any other failure: STOP and escalate.
2. **01 continues unchanged.**
3. **Parallel draft, not adopted.** Prepare the code-fix amendment now:
   - the minimal `fleet_validity.py` re-derivation fix, plus a unit test, on an isolated branch;
   - an impact inventory: E4 pins, the K4S manifest, Mac/A4 bundles, A3 staging, PC2;
   - an outcome-blind amendment text: disclose all old-code attempts, run a fresh reference series on both hosts under the fixed code, with deferral windows per c6387611.

   Sol reviews the Claude-written code. Nothing is adopted or staged on any host unless r3 fails.
