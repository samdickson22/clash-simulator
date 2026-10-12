# PREREG-K4S END reference: plan v2 (adopted with changes)

- **Status:** plan only. Nothing here has been run. Every new script (S1–S8) needs Sol review, and every host step needs a coordinator authorization, before it runs.
- **Authority:**
  - coordinator ruling after 4af19c23 (COORDINATOR 7270b5fa), which adopts `audits/K4S-END-PLAN-REVIEW-r1.md` (b69f015d, retained verbatim);
  - R4 PASS (fbcf1a67; ruling 4af19c23);
  - DBus ruling R1–R5.
- **Base document:** `K4S-END-PLAN-DRAFT-research.md` (67ea1070). This v2 supersedes it wherever the two differ. Citations to frozen code are in the draft and the review.

## 0. What is fixed

| Item | Value |
|---|---|
| **Completion of record** | `completion-v2/REPORTING-COMPLETION.json` 3794d953 with counted inventory 22c41cb7 (23604d1c). It is bound by the END evidence, END-JOB `completion_sha256`, the PC4 sidecar, the verifier receipt and release item 1. v1 (ed7d11b7/f10ab943) is superseded and stays committed. RC-1 disclosure: `completion-v2/RC1-DISCLOSURE.md`. |
| **Ledger** | `ledger/blind-ledger-final.json` 649272bd (99 events) |
| **Manifest of record** | `mac/K4S-MAC-MANIFEST.json` **74314eda** (A3). END-JOB `k4s_manifest_sha256` and every `--k4s-manifest-sha256` name it |
| **END runtime** | One `git archive` export of a **single commit at or after 133f3ae4 that contains the B2 telemetry and the END evidence** (so the evidence commit is an ancestor). Copied byte-identically, read-only, to both hosts. Never the 391d2006 reporting overlay (5 of its 33 pins mismatch) |
| **Guard** | T1's OP-1..OP-6 freeze `FROZEN-T1.json` 24817e16 with the T1 guard modules (`fleet_validity.py:57-70`). It is **not** the K4S reporting guard: there is no OP-7 apt budget and no observed-child CPU credit. This follows the frozen END contract and is disclosed |
| **DBus** | The frozen OP-1 threshold applies (R4 PASS: 0.036% idle on 04). On 04, `op1_interference` means **STOP** and a coordinator re-ruling ((a) GDM off for the window, (b) a reviewed baseline-relative OP-1 amendment, (c) ratio unavailable) before the second strike |
| **Strikes** | At most 2 attempts per host for the whole END job (END-RUNBOOK.md:176-185, :217-218). A round with no passing attempt on a host blocks later rounds |

## 1. New code (offline; Sol review before use)

| # | Component | Touches hosts | Required content (review RC) | Prep |
|---|---|---|---|---|
| S1 | B2 exact-path copier | yes, read-only | Locate each of the 10 phase dirs by on-host `launch.json` + `supervisor-exit.json` SHA = committed `phase-meta`. Read exactly `<dir>/mhz.jsonl` and `<dir>/census.jsonl` by full path (no glob, no recursion). **Refuse > 95 MB** and escalate (no LFS). Record SHAs and sizes both ends. Never during a timing window. Never read 04's perception paths (RC-4a) | `end-prep/s1s2-r1/` |
| S2 | END evidence builder + offline validator | no (05) | `clasher.k4s.end-evidence.v1`, kind `counted-reporting`, at `reports/explore/k4s-confirm/end-evidence.json` (outside `end/`). Repo-relative artifacts bound to one commit. Validate on 05 with frozen `end_evidence.end_evidence()` + `host_reporting` (exact utc join, ≥ 2 full-occupancy rows, `slots == 11`) + `slot_layout` (RC-4b) | `end-prep/s1s2-r1/` |
| S3 | Guard-job builder (per host, **per attempt**) | yes | **Fresh guard job per attempt** (RC-3), containing:<br>- `FROZEN-T1.json` 24817e16;<br>- `system-bus-admission.json`, byte-copied from the K4S job, with identity re-checked (04 PID 2005/1032; 03's pinned daemon);<br>- 03 only: `idle-services.json` for PID 2180947;<br>- `repo/` as a **git checkout** containing b2f9e25e, ce042b97 and the 08 join commits, with the four seed/join files;<br>- no other admission files.<br>**T1 state files are read only from 05, never from 03's T1 corpus copy** | `end-prep/b3-r1/` (+ follow-up) |
| S4 | Fleet-reference bundle assembler | yes (staging) / 05 | `reference_load_profile`: host, slot 0, 11 slots, `console_rule:false`, warmup ≥ 300, perception none, plan, evidence copy, guard. **Topology taken from the target host.** `sets.speed`, `states.pkl` and states-rows per T1's A5 base. Deterministic, fails closed | `end-prep/b3-r1/` |
| S5 | On-host END **preflight** (non-claiming, non-timing) | yes | Runs from the final runtime, final bundle and its own fresh guard job:<br>- `validate_bundle`;<br>- `validate_physical_cpus` and `validate_topology` vs live `cpu_counters()`;<br>- K4S backend construction (native, models);<br>- `ReportingGuard` construction, admission and ≥ 60 1 Hz samples;<br>- background slots spawned to readiness;<br>- **on 04, ≥ 15 min of full background load under the guard with no login**, recording the cumulative and windowed bus % and the per-core MHz.<br>It never calls `measure()`, never claims and never writes under the attempt parent or registry. One launch SSH; results pushed after exit (RC-2) | `end-prep/s5s6s7-r1/` |
| S6 | K4S deltas of T1's `end_exit_push.sh` (0a87166f) and `end_verify_push.py` (753722c9) | yes | Changes:<br>- host tuple 03/04, per-host bases, `--out`, the 05 receive base;<br>- **refuse any `--out` outside the declared attempt parent** (RC-6);<br>- **always push `<repository>/reports/explore/k4s-confirm/end/registry/round-RR/<host>/`**, even with no measurement dir (RC-5);<br>- the verifier records claim-without-receipt.<br>`detach.sh` 1648dfdc is used unchanged | `end-prep/s5s6s7-r1/` |
| S7 | Launch + prelaunch gate | yes | **One SSH session** (`ControlMaster=no`, `ControlPath=none`) carries, on 04 (and also 03):<br>- quiet-read v3 #2;<br>- **unfiltered `systemctl list-timers --all`** with ≥ 2 h clearance for **every** timer, or a per-timer exception backed by reporting evidence (RC-8);<br>- stamps and `who`;<br>- the C5 pre-exec gate (parent nice 0, SCHED_OTHER, byte-equal argv, no outer prefix);<br>- the detach.<br>Records the session-close UTC and the guard admission UTC (RC-7) | `end-prep/s5s6s7-r1/` |
| S8 | Claim collector / registry commit helper | no (05) | Uses the wrapper-pushed registry copy, with no extra SSH | later |

## 2. Host steps (each needs coordinator authorization first)

| Step | Action | Authorization |
|---|---|---|
| A1 | Run S1 (B2 copy). Secret-scan, commit, push the end-sources (outside `end/`) | coordinator |
| — | S2: build and commit the END evidence; offline validation on 05 | (05 only) |
| A2 | **Staging on 03/04:**<br>- END namespaces;<br>- runtime export (byte-identical);<br>- separate `--repository` clones (claims are written into their work trees);<br>- bundles via S4;<br>- per-attempt guard jobs via S3;<br>- a read-only, SHA-verified copy of T1's `states.pkl` / states-rows **from 05 storage only**, into the K4S namespace, confirmed with the T1 owner | coordinator + T1 owner |
| A3 | Interpreter/venv provisioning on 03/04, if missing (checked at staging) | coordinator |
| RC-6 | **Attempt-roots declaration, committed and pushed before the END-JOB.** Per host: runtime, bundle(s), guard-job parent, `--repository`, attempt parent, preflight dir. The wrapper enforces the parent | (commit) |
| A4 | **Preflights (S5):** 03 (~20 min), then 04 (~30–40 min, including ≥ 15 min loaded, no login). Push after exit; commit an outcome-blind disclosure. **Gate:** both pass, and 04's loaded cumulative bus is ≤ about 0.3% (≥ 0.7% → coordinator re-rules (a)/(b)/(c) before any 04 claim) | coordinator |
| A5 | Stale-stamp pre-trigger logins: 03 after 00:57:44Z; 04 after 21:32:48Z. Then wait for the checks to exit and re-read | coordinator |
| A6 | **END-JOB** (`reports/explore/k4s-confirm/end/END-JOB.json`, exactly the frozen fields; `completion_sha256` = 3794d953, `k4s_manifest_sha256` = 74314eda, `counted_hosts` = [127x03, 127x04]) **alone in one commit**. Scan, push, fast-forward both `--repository` clones. Then each END launch, **GO per launch**, with the C5 broadcast | coordinator |
| A7 | Commits of the claims, END-FINAL, pool and recheck | coordinator |
| A8 | Mac phase C (standalone; after the TIERS Mac session receipts are committed) | Sam's 10-11 authorization (coordinator confirms it covers K4S) + coordinator standalone authorization file |

## 3. Attempt rules (every attempt)

1. **One launch SSH, closed before admission.** No copier from the first quiet read until the attempt exits (the exit-push is outbound, after exit). **C5:** no SSH from any thread to the host being timed. No ControlMaster to 03/04 from any machine, Mac included.
2. **Quiet-read v3** (`rounds/r4/quiet-read-v3.cmd` a293207e): two consecutive quiet reads 30 s apart. The second read happens inside the S7 launch session. Under T1's guard, any apt or maintenance process during timing is `foreign_compute`, so v3 matters more here than in reporting.
3. **Timers:** unfiltered, with ≥ 2 h clearance for every timer or a recorded exception; re-read after every run (RC-8). Local-midnight (07:00Z) daily timers fall inside the overnight window: finish before 07:00Z unless the read clears them.
4. **Stamps:** `release-upgrade-available` younger than 24 h minus the window; `updates-available` newer than the apt lists. Otherwise pre-trigger (A5).
5. **Sequencing, binding for round 00 (RC-9):** 03 attempt, then its `complete` seal verified at ≥ exit + 1300 s (C-d), then 04. Both preflights pass before the first claim on either host.
6. **DBus:** any bus-interference failure (`op1_interference`) on either host → **STOP** and a coordinator ruling. No automatic repeat.
7. **Short-block meter disclosure:** the frozen OP-1 meter (`interfered = ticks*100 > hz*elapsed`) means a single 10 ms tick trips any window under 1 s. A truncated last warm-up block (`end_reference.py:378-386`) can be that short. At the measured ~1 tick per 30 s the per-block risk is about (block seconds)/30. It is small, but it would cost a strike. It is inherent in the frozen meter and cannot be changed without an amendment. Disclosed.

## 4. Critical path and target

1. **Author S1–S7** (in progress; three offline implementers). Post a combined Sol review package with SHAs. S1+S2 first, because B2 → evidence → END-JOB is the dependency chain.
2. A1 B2 copy → S2 evidence commit and validation.
3. A2/A3 staging → RC-6 roots declaration commit.
4. A4 preflights 03, then 04 → disclosure commit → gate.
5. A6 END-JOB commit → **03 round 00 in the overnight window (target launch about 02:00–04:00Z on 2026-10-13, after the 03 timer read)** → seal verified → 04 round 00 → finish before 07:00Z unless cleared.
6. Collect claims → END-FINAL → `end_pool pool`, then independent `recheck` (`checked_by ≠ pooled_by`). One pinned interpreter for both (PC3). The `--repository` HEAD contains the END-JOB, claims, END-FINAL, B2 and evidence.
7. K4S Mac phase C (standalone) → PC1–PC4, verifier receipt → release receipt (coordinator GO; check release item 1 = completion-v2).

## 5. Timers and stamps (read 2026-10-12; re-read unfiltered before use)

| Host | apt-daily | apt-daily-upgrade | Stamp expiry (`release-upgrade-available`) |
|---|---|---|---|
| 127x03 | 2026-10-12T20:36:30Z | ~2026-10-13T13:33Z | 2026-10-13T00:57:44Z |
| 127x04 | 2026-10-13T00:25:02Z | ~2026-10-13T13:55Z | 2026-10-12T21:32:48Z |

motd-news: 03 at about 01:35Z, 04 at about 02:15Z (10-13). The overnight launches need an unfiltered read to place every other timer.
