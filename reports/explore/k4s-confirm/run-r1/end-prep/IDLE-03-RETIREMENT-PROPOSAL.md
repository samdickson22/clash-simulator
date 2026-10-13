# Proposal IR-03: retire 03's idle-service pin for K4S END (no idle resident on 127x03)

Written 2026-10-13T07:51:15Z by the K4S runner for COORDINATOR 687bd6d0 (07:49Z entry). Offline analysis only; 03 was not touched.

## Facts

- Pinned resident: perception v4 validation cache service `v4-validation-cache-renewed-20261010-03r1`, PID 2180947 / start_ticks 139691386, PGID 2180934 (trio 2180934/2180946/2180947). Admitted for K4S by the 2026-10-11 18:22Z ruling under plan.json `compute.idle_service_exception.hosts` = [127x03, 127x08]. Copied by A1b; committed on branch k4s-end-r1 at A' 7fc4aff6545e7f5932b39e545da7af59204f4bac as `end-guard-admissions/127x03-idle-services.json`.
- Present and idle 03:12Z–03:15Z; absent at 07:31Z (COORDINATOR 07:49Z).
- Likely cause, for the perception owner to confirm: the renewed cache services had a hard stop at **2026-10-13T04:00Z** (COORDINATOR "04:24 UTC: cap clarified … Authorized a seamless cache-service renewal to 2026-10-13T04:00Z" and "Cache services renewed to Oct 13 (04:41Z)"). That falls inside the 03:15Z–07:31Z gap.

## What the frozen END guard does (T1 OP-1..OP-6 via e4v3/fleet_validity.py and t1/idle_services.py, read from the S9 runtime)

| Frozen site | With the pin still in the 03 guard job (service gone) | With no `idle-services.json` in the 03 guard job (proposal) |
|---|---|---|
| fleet_validity.py:112–114 admission rule: a guard admission file that exists must be pinned | pinned, passes | file absent: no requirement (absence is allowed; only `system-bus-admission.json` is mandatory, :110–111) |
| idle_services.begin (fleet_validity.py:156, :210) | meter created, `retired=True` (PID absent) | `pins()` = [] (idle_services.py:9): no meter |
| idle_services.update (:176, :184) | `retired=True`; RuntimeError if a different process holds the PID with another identity | no-op |
| idle_services.finish → block record (:179, :219) | `services=[{…, retired: true}]`, `interfered=false` | `services=[]`, `interfered=false` |
| op1_interference reason (:192, :224) | not set by idle (only bus `retired` triggers it) | not set by idle |
| reference qualification (:243–244) | **FleetTechnicalError "Flagged dbus/idle reference cannot qualify"** (idle `retired`) | never raised by idle |
| work-block qualification (:271–272) | **FleetTechnicalError "Flagged dbus/idle work block cannot qualify"** | never raised by idle |
| host_audit.census idle exemption (host_audit.py:147, :155) | processes matching the pin are `idle_cache` (allowlisted) | no idle exemption: any cache-service process on 03 is ordinary foreign (counts toward foreign_compute if active) |
| ssh_budget idle exemption (ssh_budget.py:6, :52–54) | `approved_idle_service` for pin members | always false |

So keeping the stale pin would make every 03 END block fail qualification (FleetTechnicalError). Removing the file restores the 04 situation (bus admission only) on 03. This is the same state as 08 after its cache service was retired (no idle resident).

## Proposed change (smallest)

**Ruling IR-03 (proposed):** for K4S END, 127x03 has no idle resident. The 03 guard jobs and 03 bundles carry `system-bus-admission.json` only. The committed A' copy of `127x03-idle-services.json` stays on the branch (append-only, BR-1) as a retired historical admission and is never placed in a guard job or bundle. If the perception owner restarts any cache service on 03 before or during END, it is not exempt: it is foreign, and a restart needs a new coordinator ruling before the next 03 step. The frozen plan's `idle_service_exception.hosts` is unchanged; with no pin file it is simply not exercised.

**Code (fix round, offline):**
1. S3 (`s3s9s10-r4/s3_guard_job.py`): build/verify the guard-job admission set from an END admission constant (03: bus only; 04: bus only) instead of `S1B.NAMES[host]` (`committed_inputs`, ~:355). S1b's copy contract (`NAMES`) is unchanged, because A1b already ran under it; S3 ignores the extra S1b manifest row.
2. S4 (`b3-r7` from b3-r6): `PRODUCTION_PINS["admissions"]["127x03"]` = system bus only (:306–330). The request's `guard.admissions` for 03 and the `--committed-admission` triples drop the idle entry. Docstring :56–57.
3. Rebuild the 03 guard jobs (pf00, rd00-a00, rd00-a01) and the 03 bundles; the 04 ones are unaffected apart from the general rebuild.
4. Tests: a 03 guard job and bundle with bus only passes; a 03 request that still names `idle-services.json` refuses; the frozen fleet_validity admission check accepts a 03 job without the file (fake-host chain).

## Every END check that reads idle-services or retired, and its behaviour after IR-03

| Check | Reads | After IR-03 |
|---|---|---|
| frozen fleet_validity (admission, meters, op1 reason, reference/work-block qualification) | job `idle-services.json`, `idle_services.retired` | no file → no meter → never `retired`/`interfered` from idle; bus checks unchanged |
| frozen host_audit.census / ssh_budget | idle pin membership | no exemption on 03 (as on 04) |
| S1b (A1b, done) | copied 03 idle file under the old pin | unchanged; historical copy only |
| S3 build/verify | S1B.NAMES → END admission constant | 03 = bus only |
| S4 assemble | PINS admissions, request `guard.admissions`, plan idle hosts (:958, :989) | 03 = bus only; :989 stays (it only refuses an idle admission on a non-exception host) |
| S5 preflight summary | `idle_services.interfered` count (k4s_end_preflight.py:665) | always 0 on 03 |
| S7 / S6 / S10 / S11 / S9 / S2 | none (S10 relies on S3 verify) | unchanged |
