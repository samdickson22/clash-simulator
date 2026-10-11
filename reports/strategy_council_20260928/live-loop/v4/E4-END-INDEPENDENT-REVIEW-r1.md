# Independent review r1: E4-v3 fleet/END code (T1 END prerequisite 2)

- **Reviewer:** Claude Opus 5.5, independent and read-only, on 127x05, 2026-10-11. I am not the E4 author or the T1 author.
- **Commits reviewed:** 90ccfef4, 6cd6b3b1, 4dbe3640, 24bfa017 and 5a25b0b3, as they stand on origin/main `6872f98e`, which includes the TIERS Amendment 2 merge `6afcbbab`.
- **Method:**
  - I worked in a detached scratch worktree of origin/main under `/mpac/sdicks02/scratch/` and deleted it afterwards.
  - The only git operations were `git fetch` (remote-tracking refs only), `worktree add` and `worktree remove`.
  - I made no commits, used no ssh, and read no sealed outcomes, hub blocks or heldout data.
  - Everything ran under `nice -n 19 taskset -c 63` with `/mpac/sdicks02/venvs/t1-verifier/bin/python` (CPython 3.12.12, pytest 9.1.1). The documented `e4v3-venv` on 05 has no pytest installed.
- **Note:** the shared 05 checkout `/mpac/sdicks02/repos/clasher` is still at `614186d7`, which is before the Amendment 2 merge. Its `measure_tiers.py` is the old `5d7de8e3`. See F4.

## Verdict: APPROVE_WITH_CONDITIONS

- **The code is mechanically correct and fails closed.** I found no path that releases outcomes before a committed pooled reference. No path pools a counted host set other than the one in the counted inventory, and no path reads outcome bytes. Measurement-file hashes are derived dynamically, so post-merge `6066228b` is picked up consistently everywhere.
- **Two integration mismatches would stop the END window tonight unless they are resolved first (F1, F2).** Both refuse rather than fail open, but each would surface on the first production attempt or on A6 staging.
- **A launch trap (F3) can permanently consume a host's reference.** A misconfigured attempt in a registered attempt root cannot be pooled and cannot be omitted.
- **None of the three needs a change to E4 code**, provided the bundle-side conditions below are adopted. A code fix would break K4S's frozen pins on `fleet_end.py` and `fleet_validity.py` (see F1).

## Test results (05, nice 19, core 63, Python 3.12.12, origin/main 6872f98e)

| Suite | Command | Result |
| --- | --- | --- |
| E4-v3 (all) | `python -B -m unittest discover -s tests` in `e4v3/` | **70/70 pass** (6.8 s) |
| T1 release barrier: `test_barrier.py`, `test_release_reference.py`, `test_reference_packet.py` | `python -B -m pytest -q` in `reports/explore/t1/` | **49/49 pass** (118 s). These run the real E4 pool CLI from the post-merge tree. |
| T1 guard modules E4 imports: `test_op5.py`, `test_op5_08.py`, `test_op6.py` | same | **65/65 pass** |

**Reviewer probes (scratch only):**
- **P1:** END `evidence()` against the real frozen T1 `plan.json` (`af6aeade`) with counted hosts {01, 08} is refused. See F1.
- **P2:** `ReportingGuard` staged from the OP-7 reporting freeze `ef4c073a` crashes with `ModuleNotFoundError: cpu_accounting`. See F2.

## Findings

### F1 (BLOCKER for END tonight): the reporting host set falls back to {01, 03, 08}, so the production END refuses {01, 08}

**Location:** `e4v3/fleet_end.py:150-152`.

```python
reporting_hosts = set(plan.get("reporting_hosts", sorted(allowed)))
if committed and set(expected) != reporting_hosts: raise ...
```

**Why it fails:**
- The frozen reporting plan `reports/explore/t1/plan.json` has SHA `af6aeade`, and the r3 manifest `488f6c8d` still pins those bytes.
- That plan has **no `reporting_hosts` key**, and its `compute.hosts` is {127x01, 127x03, 127x08}, with 03 not forbidden.
- The {01, 08} host set lives only in `FROZEN-T1.json.reporting_hosts` and in `host-set-0108-20261010.json`.
- The fallback therefore yields {01, 03, 08}. Every real completion with `counted_host_phases` = {01, 08} raises `END host set must equal every pinned reporting host`. Probe P1 reproduced this.

**What it blocks:**
- `fleet_reference.run`, through `pinned_profile` → `evidence` (`fleet_profile.py:186`, `fleet_reference.py:34-35`);
- A6 staging (`prepare_fleet_smoke.py:40`, which checks the production 01 bundle as `counted-reporting`);
- `fleet_pool.pool_context` (`fleet_end.py:234`).

**Why the tests miss it:** every E4 test fixture sets `compute.hosts` equal to the counted hosts (`tests/test_fleet_contract.py:33-38`, `tests/test_fleet_end.py:24`).

**Fail-closed status:** yes. The pool host-set equality (`fleet_end.py:237`) is still derived from the committed counted inventory and completion, which is correct under A1b. Only the extra plan cross-check is mis-bound.

**Condition C1 (before A6 staging):** take one of two routes and record it outcome-blind.
- **(a) No code change (recommended for tonight).**
  - T1's END bundle pins a derived plan that equals `af6aeade` plus `"reporting_hosts": ["127x01","127x08"]`.
  - The END record must carry a mechanical proof that the derived plan, with that one key removed, parses equal to `af6aeade`, bound to the host-set receipt.
  - The A6 smoke plan then derives from it automatically.
- **(b) Code change.** Bind `reporting_hosts` and the plan SHA to the already pinned `guard.freeze` (`FROZEN-T1.json`), and drop the `compute.hosts` fallback.
  - This edits `fleet_end.py`, which K4S has frozen (`k4s-confirm/mac/K4S-MAC-MANIFEST.json:92`, pin `76d5ce31`; `end_pool.py:65` `FROZEN_HELPERS`).
  - It therefore needs a K4S re-pin amendment as well as review, so it is not feasible tonight.
- **Either route:** nothing currently binds the bundle's `profile["plan"]` to the frozen reporting plan bytes. Today that binding exists only by T1's construction, so say so in the END record.

### F2 (BLOCKER for END tonight): the END guard regime is unspecified, and the OP-7 freeze both crashes and is not strict

**Location:** `e4v3/fleet_validity.py:10-12, 56-68`.

**How E4 admits a freeze:**
- `ReportingGuard` accepts any staged freeze whose `operational_delta_op5`, `operational_delta_op5_08` and `operational_delta_op6` say `CONFIRM`.
- It SHA-checks only the nine `GUARD_MODULES` against that freeze.
- **Current T1 reporting** (replacement-r2 and r3) runs under the **OP-7 freeze `ef4c073a`, FROZEN-T1 `488f6c8d`. That commit is not an ancestor of main.**

**What OP-7 changes:**
- `host_audit.py` (`5717d01c` → `f25ef204`) imports `apt_budget`.
- `ssh_budget.py` (`0c2759f5` → `0ef24fac`) imports `cpu_accounting`.

**Consequences:**
- **If the "final frozen" OP-7 guard is staged with the nine documented modules:**
  - The guard monitor crashes on import (probe P2).
  - `check_monitor` turns this into `FleetTechnicalError("crash")` *after* `fleet-identity.json` exists, so `classify_attempt` grants a technical repeat.
  - The repeat crashes deterministically too, so the host is lost pending an amendment.
- **If `apt_budget.py` and `cpu_accounting.py` are also staged:**
  - They run without an E4 SHA check against the freeze.
  - OP-7's `apply()` re-labels apt processes `allowlist_kind='ubuntu_apt_budget'`, so they leave `foreign`.
  - E4 never calls the apt meters, and `end_block` and `validate_blocks` check only ssh, system_bus and idle_services.
  - So apt load during a reference block is **neither stopped nor flagged**. That breaks the strict-validity decision of 2026-10-10 19:38.
- **The tests cover only the OP-6 freeze:** `tests/test_guard_seeds.py:17` uses `REVIEWED_FREEZE = aeeb3003`.

**Condition C2 (before A6 staging):**
- **The coordinator rules that the END reference guard is the OP-6 freeze**: FROZEN-T1 `24817e16`, which is main's, with modules from `aeeb3003`. T1 stages that freeze into the distinct reference job namespace (`guard.job/FROZEN-T1.json`).
- **Effect:** this is strict and tested, and apt maintenance becomes `foreign_compute`, which stops the attempt and makes it a typed validity_census repeat.
- **Operational note:** 01 already hit `apt-daily` / `unattended-upgrade` at 21:03Z on 10-10. Check the apt timers (read-only) and place both attempts away from them, because only one repeat is allowed.
- **Alternative:** using OP-7 for references needs an E4 change: add the two modules to `GUARD_MODULES` and treat any apt flag as non-qualifying. That also touches K4S-pinned `fleet_validity.py` (`94d0e7f2`).

### F3 (MAJOR, operational): a failure before `fleet-identity.json` exists permanently blocks that host's pool and release

**The mechanism:**
- `fleet_reference.run` writes `fleet-identity.json` (`fleet_reference.py:97`) only after `validate_bundle`, `pinned_profile`/`evidence`, `host_reporting`, the row checks and the capture receipt (lines 29-96).
- `measure_tiers.main` also refuses earlier, for the OMP, OPENBLAS and MKL environment and the manifest SHA (`measure_tiers.py:668-685`). It still creates the output directory and seals `failure.json`.
- If that directory sits under the registered attempt root `fleet-end-attempts-0108/<host>` (`reference-attempt-roots-0108.json`), two checks collide:
  - T1 `release_reference.attempt_roots` (`release_reference.py:126-137`) requires every child to be listed and to have `fleet-identity.json`.
  - E4 `fleet_pool.run` (`fleet_pool.py:104`) reads it unconditionally.
- The attempt can be neither pooled nor omitted. F1 and F2 are exactly the kind of failure that would trigger this on the first launch.

**Condition C3:**
- Before the first launch into a registered root on **each** host, run an offline preflight from a scratch output that is *not* under the attempt root. It must cover:
  - `validate_bundle(…, dry_run=True, require_references=False)`;
  - the `tiers-pins.json` SHA;
  - `fleet_end.evidence` + `host_reporting`;
  - `fleet_profile.slot_layout(profile, plan, host, 10)`;
  - construction of `ReportingGuard` against the staged freeze;
  - the environment variables in the launcher.
- A6 staging covers most of this for 01 only. Run the same preflight for 08.
- A6 measurement output must not be placed under the registered attempt roots.

### F4 (MAJOR, Amendment 2 condition 1): post-merge bytes are enforced by equality, not by a positive pin

**Verified consistent:**
- Measurement hashes are never hard-coded. `5d7de8e3` appears only in historical receipts and docs.
- Every consumer re-hashes the live e4v3 directory against the recorded `measurement_files`:
  - `tier_backend.validate_bundle:425`, called by `fleet_reference.py:29,199`;
  - `prepare_fleet_smoke.py:29`;
  - `fleet_pool.py:107,137`, plus cross-host `binding.measurement_files` at `fleet_pool.py:171-176`;
  - T1 `release_reference.py:240-247,267`, where the commit-bound inventory equals the live directory set and each attempt's files;
  - `check_reference.pool_command`;
  - the Mac `validate_bundle`.
- **So:** a mixed old/new population cannot pool, and a bundle prepared on old bytes cannot run on a post-merge tree.

**The gap:**
- Nothing asserts that `measurement_files["measure_tiers.py"] == 6066228b…` or that the measurement-source commit descends from `6afcbbab`.
- A bundle prepared *and* run on stale trees would be internally consistent.
- The 05 shared checkout is in exactly that state today, still at `5d7de8e3`.

**Condition C4:**
- The END and A6 bundle builders and launchers must assert `sha256(measure_tiers.py) == 6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e`.
- T1's `measurement_source.commit` must be a descendant of `6afcbbab`. Record both in the END record.
- Update the fleet-host checkouts before preparing anything.
- The committed-evidence check (`fleet_end.py:30-33`) runs `git show` and `merge-base --is-ancestor … HEAD` against `end-evidence.repository` **on the measuring host**. So 01 and 08 each need a checkout that contains the completion and inventory commits.

### F5 (MINOR): `fleet-identity.nice` records the plan's nice, not the measured one

`fleet_reference.py:97` writes `nice=plan["compute"]["nice"]`.
- The real priority is enforced at `fleet_profile.py:184` (`slot_layout(..., os.getpriority(...))`), so this is not a correctness hole.
- However, the pool's `identity["nice"] == plan nice` check at `fleet_pool.py:152` is tautological.
- Record `os.getpriority` as well at the next code revision.

### F6 (MINOR/INFO): the A6 smoke host is hard-coded, and its synthetic inventory is labelled correctly

**Hard-coding:** `prepare_fleet_smoke.py:30,44,46,63` hard-code 127x01 and nice 10. That matches the coordinator's assignment (6cd6b3b1). The smoke is unpoolable in four separate ways:
- `kind=unpoolable-smoke`;
- `plan.profile=e4v3-unpoolable-smoke`, which also gives it a different plan SHA;
- `poolable=false`;
- the pool and `release_reference.py:164-165` refuse it.

**Synthetic inventory:** the counting IDs are normalized and labelled `synthetic`. The original committed sources stay SHA-bound (`source_end_evidence_sha256`). This is acceptable.

**Coverage:** A6 exercises only 01. 08's first real fleet-mode run will be its production attempt, so C3 matters for 08.

### F7 (INFO): exactness classification errs toward no-repeat

`fleet_validity.py:282` treats failure text containing words like "posterior" or "rng" as an exactness failure. A crash whose traceback mentions such a word therefore loses its repeat. This is conservative and acceptable, since it never turns an exactness failure into a repeat. Typed causes are restricted to crash, host_loss, mhz_gate and validity_census, and the mhz_gate and validity_census causes require corroborating sealed evidence (`fleet_validity.py:296-307`).

### F8 (INFO, T1-owned): the barrier's own asserts vanish under `python -O`

`barrier.outcome_release` uses bare `assert` for the coordinator, reason and escape checks. Under `-O` those vanish. `release_reference.prerequisites` uses `require()`, and it runs first for **both** routes (`barrier.py:12-13`), so the Amendment 1 gate survives `-O`. This is not blocking; never invoke the reducer with `-O`.

### F9 (INFO, scheduling): 08's reference must finish before B claims 08

`plan.json.fleet_reference_schedule` says the 08 reference is allowed "only if B window not declared". The coordinator's 14:06Z plan places B on 08 *after* the pooled reference. Keep that order. Losing 08's reference after it has contributed counted blocks fails the END pool closed (A1b) and needs an amendment.

## Focus checklist

| Focus item | Result |
| --- | --- |
| **1. A6 smoke, END reference, pooling, release route** | **Correct and fail-closed, except for F1–F3.** No release by either route (Mac summary or `fourteen_day_escape`) can happen before PC1–PC4. Before reading any game byte, `prerequisites` requires all of these: a committed pool seal, an executed pool recheck, a committed registration and all attempt roots (`release_reference.py:142-294`, `barrier.py:12-13`, `reduce.py:120`). |
| **1. Pool host list** | The pool host list equals the counted host set, with no duplicates (`fleet_end.py:237`). That set equals the completion's `counted_host_phases`, which equals the counted inventory's owners (`fleet_end.py:120-122`). END mode never excludes a host (`fleet_pool.py:59-60`), and `release_reference.py:206-210` requires `excluded == []`. |
| **1. Reference slot** | Slot 0 is fixed per host (`fleet_end.py:193`) and is part of the cross-host binding (`fleet_pool.py:174`). Every reporting launch on 01 and 08 had `slots: 11`, which is consistent with `slot_count` 11 and `console_rule` false. |
| **2. OP-5 seed/join** | The frozen `parent_source_seed.admit` is called once, before the first census, using the same `ssh_budget.FAMILIES` instance. Both seeds and the 08 server/client join are pinned against the freeze, the bundle and `job/repo` (`fleet_validity.py:90-107,129-131,136-140`). I verified all four bindings against FROZEN-T1. |
| **2. Labelling** | `GUARD_RULES = frozen-t1-op1-…-op6-v1`. No OP-4-only text remains. OP-7 is unaddressed (F2). |
| **2. Strict validity** | Any dbus/idle interference or retirement, any SSH-flagged (>0.5%) block, any console user and any ssh stop each fail the attempt (`fleet_validity.py:178-182,209-216,219-272`). This matches the 19:38 decision **for the OP-6 regime**. |
| **3. Outcome sealing** | The E4 END, A6 and pool code reads only these: the committed completion, the blind ledger, the counted inventory (with an allowlisted descriptor schema), launch, supervisor-exit, MHz/census, the bundle corpus, E4 receipts and guard health files. There are no `hub-blocks` or game reads. |
| **4. Tests** | 70/70 E4-v3; 49/49 T1 release; 65/65 T1 OP-5/OP-6 guard. |
| **5. Tonight blockers** | F1 (C1) and F2 (C2) must be settled before A6 staging. F3 (C3) and F4 (C4) must be done before the first production launch. Prerequisites 1, 3 and 4 still stand. |

## Status of the r2 (efa54f44) conditions

| Condition | Status |
| --- | --- |
| **A1a: END placement after reporting completion** | **Met.** `fleet_end.py:142-145,173` |
| **A1b: no exclusion; host set = counted hosts** | **Met in the pool.** The plan cross-check is mis-bound (F1). |
| **A1c: committed completion, ledger, inventory and exits with SHA + commit + ancestry** | **Met.** `fleet_end.py:20-34,177-184` |
| **A1d: every release route needs the committed pool and registration** | **Met.** This is on the T1 side: `release_reference.prerequisites` |
| **A2: host-set and profile binding, slot 0, warmup, perception, slot_count from launch, plan nice** | **Met.** `fleet_end.py:189-222`, `fleet_pool.py:151-176`. The nice record is tautological (F5). |
| **A3a: full-occupancy MHz join** | **Met.** `fleet_end.py:204-221` |
| **A3b: signed ratio carried through** | **Met.** `fleet_pool.py:228,234`, `measure_tiers.py:520` |
| **A3c: one repeat, all attempts listed, first pass wins** | **Met.** `fleet_pool.py:94-124` |
| **A4: validity census** | **Met.** Stricter than asked: the T1 OP-1–OP-6 guard |
| **A5: Linux EXACT, zero difference** | **Met.** `fleet_pool.py:142-145`, `measure_tiers.py:188,210` |
| **A6: real smoke and classifier** | **Classifier met.** The smoke is staged but not run yet. It is END prerequisite 1. |

## Conditions summary (all outcome-blind)

| Condition | When | What |
| --- | --- | --- |
| **C1** | Before A6 staging | Bind the END reporting host set to {127x01, 127x08}. Recommended: a derived plan with `reporting_hosts` plus a recorded equality proof to `af6aeade`. |
| **C2** | Before A6 staging | A coordinator ruling that the END guard is the OP-6 freeze `24817e16`/`aeeb3003`, or a reviewed E4 OP-7 change, which would also trigger a K4S re-pin. Check the apt timers on 01 and 08. |
| **C3** | Before the first production launch on each host | An offline preflight outside the registered attempt roots. Keep A6 output out of those roots. |
| **C4** | Before preparing anything | A positive pin of `measure_tiers.py` to `6066228b`. The measurement-source commit descends from `6afcbbab`. Update the fleet-host checkouts, and make sure they contain the completion and inventory commits. |

**Also recommended (not blocking):** F5, and an explicit note that `-O` must never be used for the reducer (F8).
