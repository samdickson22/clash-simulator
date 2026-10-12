# K4S DBus-flag investigation r1 (127x04 OP-1 flags)

- **Written:** 2026-10-12T14:23Z (`date -u`). Independent read-only investigator, Claude Opus 5.5, running on 127x05 (the hub).
- **Trigger:** ROUND-r4-AUDIT.md note 5 (sha256 `311061f8…`). The coordinator HOLD is at run-r1/PROGRESS.md:339.
- **Sources:** origin/main `8f28101b0`. The prereg r3 bytes `9650972d…` were verified against freeze commit 391d2006.
- **Read boundary:**
  - I opened no outcomes, game files, `games/` directories or `complete.json` files.
  - Per-block meters come only from the hub copies of `interference.json` (`/mpac/sdicks02/jobs-k4s/*` for 04 and `/mpac/sdicks02/jobs/clasher/k4s-confirm-*` for 03).
  - Their schema is: utc, design descriptor, services, ssh_family, ubuntu_apt, system_dbus and allowlist_observations. None of these is an outcome.
  - Admission and process snapshots are committed health receipts.
- **Write and run limits:** no SSH, no edits to repo files, no commits. My only writes are this report and scratch files under `/tmp/sd-dbusinv/`.

## Bottom line

1. **What the flag is.** The OP-1 DBus flag is an operational meter. It is **not** a stop rule, **not** an exclusion rule and **not** part of the prespecified sensitivity analysis. The primary analysis includes these blocks. The frozen reducer only counts them (it excludes nothing), and that count's name is misleading. Reduction needs no amendment.
2. **Cause.** It is a constant 04 host property. 04 runs a GDM/GNOME login greeter (45 uid-125 processes, including Xorg and gnome-shell), and 03 does not.
   - 04's system dbus-daemon runs at a median **1.47%** of one core per block, against **0.40%** on 03.
   - The flag threshold is 1%, so it falls between the two hosts.
   - The level has been flat for 18 hours and the same in every round.
3. **Validity of the primary contrasts: not threatened.**
   - Each block's arms are paired, on the same host and slot.
   - Hosts are split exactly 50/50 within every cell and seat.
   - The excess is about 0.011 of one core, on a host with 64 physical cores.
4. **The real risk is END, not reduction.**
   - The frozen END guard (`fleet_validity`) **fails a reference attempt** if the system bus goes above 1%.
   - 04 must be in the END host set.
   - Even in each phase's first wave, 04 averaged 1.03–1.12%.
   - An outcome-blind ruling or measurement is needed **before END is scheduled**.
5. **Recommended ruling.** Proceed with reduction as frozen. Commit an outcome-blind disclosure now. Add **no** post-hoc DBus-exclusion analysis. Resolve the END exposure on 04 before END (see the Recommended ruling section).

## Q1. What does a DBus flag mean in the K4S guard?

**The mechanism**
- `reports/explore/k4s-confirm/system_bus.py` pins the UID-103 system `dbus-daemon` by exact PID, start ticks, exe, cmdline SHA and UID (`pin`, l.8–14).
- For each block it meters that process's CPU ticks (`begin`/`update`/`finish`, l.18–30).
- `interfered = ticks*100 > hz*elapsed` (l.30) means the daemon averaged **more than 1% of one core over the block's wall time**.
- `retired` is a separate field: it is set only if the pinned identity disappears. Across 3,830 blocks, `retired` was 0 everywhere and the PID never changed (04: 2005, 03: 2049).

**How the supervisor uses it**
- `supervise.py:84-85` writes `interference['system_dbus']` and ORs its flag into the block-level `interference['interfered']`.
- The stop logic, `guard_reason` (`supervise.py:23-24`), consults only `ssh_budget.stop_reason` and `apt_budget.stop_reason`. **DBus never stops a host.**
- The block is still marked complete, copied to the hub and counted (l.86-89).

**The inherited rule**
- `reports/explore/t1/FREEZE-T1.md:7` (OP-1): "Dbus CPU ticks are measured per block; >1% core average flags interference and **does not stop or silently exclude** that block."
- The pin receipt that `system_bus.pin` writes carries `coordinator_ruling='OP-1 14:45Z; … >1% core flags only'`.

**The prereg text (r3, frozen at 391d2006)**
- §3, l.553: per block, "T1 census and interference meters (**OP-1 DBus**, OP-4/6 SSH, OP-7 apt, idle services)" are recorded.
- §4.2, l.617: "The OP-1 system DBus pin" is an inherited ownership and pinning lesson.
- §4.2, l.623-624: "**Interference flags.** OP-6-style flags are recorded per block and disclosed. **The primary analysis includes flagged blocks**; a sensitivity analysis excludes them (§5.3)."
- §5.3 item 2, l.734: "Interference: exclude blocks with any **OP-6/OP-7** interference flag (sidecar ledger, separate RNG stream)." OP-6 is SSH and OP-7 is apt. **OP-1 DBus is not named.**
- §4.2, l.612: "T1's END contract also rejects SSH- and DBus-flagged reference work". This applies to END, not reporting; see Q4.
- Amendments 1–3 say nothing about interference or DBus. K4S-SPEC §6.6 item 2 says only "the flagged-block sensitivity" and defers to r3 §5.3.

**Classification:** **descriptive, disclosed, retained.** It is not a stop rule, not an exclusion rule and not a sensitivity criterion during reporting.

**Precedent:** T1 reporting had the same pattern. Its 08 host was DBus-flagged on 400 of 400 blocks against 0 on 01 (PROGRESS-T1.md:99), and T1 retained and disclosed those blocks. The smoke disclosure (COORDINATOR.md:2082, "04 had 3 dbus-interfered blocks (disclosed)") followed the same practice for K4S.

## Q2. How do the frozen reducer and the prereg analysis use flagged blocks?

**`reduce.py` (frozen)**
- `load_blocks` (l.129-173) stores `interference` per row and never filters on it. The primary analysis, the H1–H7 sequence, admission, the veto and the validity window (l.317-319: the K4-200 primary loss window only) all ignore interference.
- The prespecified sensitivity is at l.219-229. It is built from `ssh_sensitivity.health_ledger` and keeps blocks where `not b['ssh_or_apt_flagged']`, under the rule text "exclude source-proven SSH-or-apt flagged blocks (OP-6/OP-7 sidecar)". This matches r3 §5.3 item 2.
  - **DBus flags do not enter it** (see `ssh_sensitivity.py` l.69 and 88-97).
- The `interference_any_flag_excluded` field (l.231) is **only a count**, per population, of blocks whose top-level `interference.interfered` is true, and that value includes DBus. Despite the field name, **nothing is excluded**.

**What happens with ~50% of blocks flagged**
- The primary and admission results are unchanged.
- The §5.3(2) sensitivity removes **0** blocks, because SSH and apt flags are both 0 on every counted block so far. It is therefore identical to the primary analysis, which should be disclosed as vacuous.
- `interference_any_flag_excluded` will read about half of each population (currently ≈1,427 primary and 438 guard on 04). If the report doesn't explain that this is a count, a reader would take it to mean half the data was dropped.
- No verifier or release-check code references `interfered`. A grep of `reports/explore/k4s-confirm/**.py` finds it only in health.py, the meters, supervise.py and reduce.py.

## Q3. Likely cause on 04, from health metadata only

### Per-block meters (hub `interference.json`, `system_dbus` and `ssh_family` fields only)

| host | phase | blocks | DBus-flagged | % | core-fraction p10 / p50 / p90 / max (%) | dbus CPU s per block (p50) | SSH / apt / idle flags | retired |
|---|---|---|---|---|---|---|---|---|
| 04 | smoke (excluded) | 8 | 3 | 37.5 | 0.76 / 1.00 / 1.13 / 1.13 | 3.90 | 0/0/0 | 0 |
| 04 | reporting | 186 | 175 | 94.1 | 1.19 / 1.37 / 1.47 / 1.58 | 5.43 | 0/0/0 | 0 |
| 04 | replacement-r1 | 1194 | 1189 | 99.6 | 1.35 / 1.48 / 1.59 / 1.77 | 4.84 | 0/0/0 | 0 |
| 04 | replacement-r2 | 266 | 263 | 98.9 | 1.33 / 1.49 / 1.62 / 1.82 | 4.84 | 0/0/0 | 0 |
| 04 | replacement-r3 | 217 | 214 | 98.6 | 1.35 / 1.49 / 1.62 / 1.76 | 4.73 | 0/0/0 | 0 |
| 04 | replacement-r4 (running) | 27 | 24 | 88.9 | 0.93 / 1.37 / 1.62 / 1.68 | 4.53 | 0/0/0 | 0 |
| 03 | all phases | 1932 | **0** | 0.0 | ~0.37 / **0.40** / 0.42 / 0.47 | ~1.27 | 0/0/0 | 0 |

**Counted phases (reporting plus r1–r4, as of the read):**
- 04: **1,865 of 1,890 blocks flagged (98.7%)**.
- 03: 0 of 1,924.
- Overall, about **49%** of the counted inventory is flagged.
- The flag is almost perfectly aliased with host: every flagged block is a 04 block.

The flag is also balanced across the design:
- Primary: 1,427 of 1,450 flagged. Guard: 438 of 440.
- Seat 0: 937 of 950. Seat 1: 931 of 948.

### It is constant
- Hourly means on 04 ran **1.30–1.53%** from 2026-10-11T20Z to 2026-10-12T14Z, with no trend. 03 ran 0.37–0.41% over the same hours.
- Every phase shows the same shape:

  | host | first-wave blocks (first 11 per phase) | later blocks |
  |---|---|---|
  | 04 | mean 1.03–1.12%; 6–8 of 11 flagged | mean ~1.48%; 100% flagged (169 of 175 in reporting) |
  | 03 | 0.335% | 0.40% |

- This shape explains why each phase's health showed exactly 3–6 unflagged 04 blocks.
- The audit's "~97%" is consistent with this. The exact figure is 98.7% for counted phases and 98.4% including smoke.

### It is a 04-resident process inventory difference
I diffed the committed admission snapshots (stop-drill-raw `host-admission-smoke.json`, 2026-10-11T18:58Z), then rechecked the r3 and r4 step-7 host admissions (2026-10-12T11:28Z and 14:04Z).

- **04 only:**
  - A GDM greeter session as uid 125 (gdm): `gdm-x-session` and `Xorg vt…`, `gnome-shell`, `gnome-session-binary`, a session bus and the at-spi bus, about 20 `gsd-*` daemons (power, rfkill, housekeeping, sharing, media-keys, color, smartcard…), the `gvfs-*` volume monitors, `goa-daemon`, `pulseaudio`, `ibus`, `tracker-miner-fs`.
  - Also: `plymouthd`/`plymouth --wait`, `nvidia-persistenced` and the CUPS `dbus://` notifier.
  - All 45 uid-125 processes are present in all three snapshots.
- **03:** zero uid-125 processes.
- Many of these clients are system-bus clients that subscribe to logind, UPower, rfkill and udisks signals. Each broadcast gets fanned out to them by the system dbus-daemon.
- **Probable reason for the asymmetry:** 04 has a working RTX A6000 and 03 has no working GPU (fleet notes). A graphical greeter that comes up only on 04 fits that. This is plausible, not proven.

### Rates outside blocks agree
These are from the cumulative `cpu_ticks` of the pinned daemon in the admission snapshots:
- **Lifetime since boot:** 04 0.47% of a core, 03 0.15% (×3.2).
- **18:58Z to 11:28Z, phase gaps included:** 04 1.32%, 03 0.36% (×3.7).

The host difference was there before K4S ran, and it stays the same throughout.

### The copier and SSH component is real but secondary
- In the first wave, the copier on 05 only lists the job over SSH every ~10 s. Later, every completed block adds several SSH logins: block rsync, `complete.json` rsync and the ACK return. `mirror_k4s.py` uses no ControlMaster, so each is a new sshd/logind session.
- After the first wave, both hosts rise, but 04 rises far more (+0.07 points on 03, +0.41 points on 04, about 6×).
- The OA-1 integration watch shows the same thing. With copier rsync active, the system dbus-daemon was "active" in the census on 04 only (`guard-watch2-127x04.json` `active`). With listing only, it was active on neither (`guard-watch-127x0{3,4}.json`).

So our own SSH sessions are amplified on 04 by the greeter's subscribers. But 04 is already near or above 1% without that traffic.

### Ruled out or unlikely
- **Perception storage on 04:** no perception processes appear in any 04 snapshot. Storage is passive disk.
- **A 04-specific copier:** the copier runs on the 05 hub against both hosts symmetrically, and it explains only the increment above.
- **Apt, SSH budget or idle services:** 0 flags of each on both hosts.
- **Pin churn:** `retired` was 0, and the PID and start time never changed.

**Caveat:** I have no per-sender DBus accounting (no root and no system-bus monitor), so the greeter attribution is inferential. It rests on the process diff plus a stable ×3–4 rate ratio at every activity level.

## Q4. Does it threaten validity? Is a ruling or disclosure needed before reduction?

### Reporting validity: no threat under the prereg
1. **The prereg classes it as descriptive.**
   - The primary analysis includes flagged blocks (r3 l.623-624).
   - The sensitivity is OP-6/OP-7 only (l.734).
   - The OP-1 rule explicitly does not stop or exclude (FREEZE-T1:7).
   - The reducer implements exactly this.
2. **The design neutralizes a host-level background.**
   - All arms of a block run sequentially on the same slot and host, and the contrasts are paired within each block.
   - The reporting dispatch is exactly balanced: 1,500/1,500 primary and 450/450 guard per host, 750 per host×seat, and zero host imbalance in any of the 68 population×cell strata.
   - A constant 04 background therefore cannot bias arm contrasts. At most it could create a host×arm interaction, and **§5.3 item 4 already prespecifies the per-host contrasts and the host×arm heterogeneity table**.
3. **The size is negligible for timing.**
   - The excess is ~1.07% of **one** core, on a host whose K4S slots use 55 of 64 physical cores with SMT siblings idle.
   - It is flat over time and doesn't interact with phase.
   - In the excluded smoke health, timing was at parity: overruns 7 on 03 vs 6 on 04, fallbacks 126 vs 128.
   - The prespecified speed safeguards are unchanged: the K4@1.0 validity window and the END per-host ratio gate [0.95, 1.05] (r3 l.660).
4. **There is precedent.** T1 retained and disclosed 100%-flagged 08 blocks.

**Before reduction, the coordinator needs to:**
- **Make a disclosure, not an amendment.** Commit it outcome-blind before any reducer run. It should cover the counts per host and phase, the cause, the constancy, the aliasing of flag with host, the meaning of `interference_any_flag_excluded`, and the fact that the §5.3(2) sensitivity is vacuous (0 SSH or apt flags; re-verify at the final inventory).
- **Not add a post-hoc DBus-exclusion sensitivity.** Excluding flagged blocks would be "03 only plus ~25 first-wave 04 blocks": the §5.3(4) host contrast with half the N. It would be an analysis chosen after the flag distribution is known. The report should label §5.3(4) as the DBus-sensitivity equivalent.

### END: a real availability risk that needs action before END is scheduled
- The K4S END runs the frozen `fleet_reference.reference_monitor` with the T1 reporting guard (END-RUNBOOK.md:138-140: "A console user, SSH/**dbus**/idle interference or a flagged block fails the attempt").
- In `mac-e4-package/e4v3/fleet_validity.py`, a reference attempt fails with `op1_interference` in two cases:
  - per 50-state work block, if the bus goes above 1% (`end_block`, l.222-224: "A flagged reference cannot qualify; retain it and fail the attempt");
  - on the **cumulative bus meter over the attempt** (l.177, l.192-193).
- The END host set cannot drop 04: "hosts cannot be excluded after counting", from r3 l.660-661 and T1 A1.1.
- 04's bus averaged 1.03–1.12% even in first waves. Without the copier it may sit lower, but the lifetime average was 0.47% with no load, so this is unmeasured.
- Short 50-state windows make some above-1% blocks likely.
- **If END fails repeatedly on 04,** r3 §4.2 leads to "re-run until it conforms, or the coordinator declares the K4S Mac speed ratio unavailable", which would make the tier Mac-infeasible for deployment.
- T1 hit the same END rule on 08. It was cleared there only because 08's DBus load came from perception transports that later went away (COORDINATOR.md:2284 and 2543: zero DBus at END). **04's cause is resident.**

## Recommended ruling (for the coordinator; outcome-blind)

**R1. Classification.** OP-1 DBus flags in PREREG-K4S reporting are descriptive. They are retained in the primary analysis and outside the §5.3(2) sensitivity (OP-6/OP-7 only), as frozen. They do not affect inclusion, admission or the validity window. **Lift the DBus part of the reducer/verifier hold** at 14:16Z, once R2 is committed.

**R2. Disclosure (commit before any reduction).** Record the following:
- 04 had 1,865 of 1,890 counted blocks flagged (98.7%); 03 had 0 of 1,924. Re-count at final inventory.
- The 04 system dbus-daemon median was 1.47% against 0.40% on 03. The threshold is 1%. The level was constant across rounds.
- The probable cause is the GDM greeter resident on 04, amplified by copier SSH logins.
- The flag is aliased with host.
- `interference_any_flag_excluded` is a flagged-block count, and nothing is excluded.
- The §5.3(2) sensitivity excludes 0 blocks.
- The §5.3(4) per-host table is the place to read any 04 effect.

Report text only. No frozen bytes change.

**R3. No new DBus-exclusion analysis.** If the coordinator wants one anyway, add it **now, outcome-blind**, labelled descriptive with its own RNG stream and never touching admission, and state that it is approximately the 03-only analysis.

**R4. END gate on 04 (before END is scheduled):**
- Authorize an outcome-blind, read-only baseline of 04's pinned bus `/proc/2005/stat` under END-like conditions: no copier, reporting drained, and one long-lived session or a detached local sampler so the probe doesn't add logind sessions. Sample at 1 Hz for ≥30 min, and summarize over whole-window and 50-state-length windows.
- If the baseline is clearly below 1% (say, every window ≤0.7%), END can proceed as frozen. Disclose the measurement.
- Otherwise, rule outcome-blind before END. In order of preference:
  - **(a)** Ask Sam or a lab admin to stop or disable the gdm greeter on 04 for the END window. We have no root and must not touch gdm or root processes. This matches T1's "clean window" precedent.
  - **(b)** A reviewed outcome-blind END amendment for 04: a baseline-relative OP-1 threshold, with the baseline frozen from the probe.
  - **(c)** Pre-declare the "K4S Mac ratio unavailable" path.

**R5. Monitoring (non-binding).** In round audits, record 04 DBus as "known, disclosed, constant", and alert only on a change in level or on `retired`. The health tool needs no change.

## Appendix: method and artifacts
- **Scripts:** `/tmp/sd-dbusinv/agg.py`, run with `python3 -I`. It reads only `*/hub-blocks/*/*/interference.json` and extracts host, phase, utc, population, seat, subsample, `system_dbus`, `ssh_family.core_fraction`/`block_seconds` and the flag booleans.
- **Output:** `/tmp/sd-dbusinv/rows.json`, which contains no outcomes.
- **Committed health series:** `run-r1/health/*.json` (hub `flags.dbus` against `durable` per host) agrees with these counts at every read.
- **Design balance:** from `run-r1/dispatch/reporting-dispatch.json`, design fields only.
