# K4S END plan review r1 (science and procedure)

- **Reviewer:** independent Opus 5.5 (1M) reviewer on 127x05. The review was read-only: no SSH, no edits to the repository, no commits and no outcome data. Scratch files are in `/tmp/k4s-review-r1/` (exported git blobs plus `scripts/count.py`), and every script ran under `python3 -I`.
- **Written:** 2026-10-12T15:22:13Z (`date -u`). The review was done against origin/main `1fa7bacd`. That is later than the reviewed draft commit 754c43cd, because R4's final result and the coordinator's ruling 4af19c23 landed during the review; both were read.
- **Inputs:**
  - the plan draft `run-r1/end-plan/K4S-END-PLAN-DRAFT-research.md` (git blob 3a49b8eb; sha256 67ea1070 per the README) and `README.md` (754c43cd);
  - completion-v2 (23604d1c);
  - completion v1 (bb7c7f88);
  - PREREG-K4S r3 §4.4–4.5 and Amendment 3;
  - the K4S manifest 74314eda;
  - `END-RUNBOOK.md`, `end_reference.py`, `end_evidence.py` and `end_background.py`;
  - the e4v3 `fleet_validity.py`, `fleet_end.py`, `fleet_profile.py`, `prepare_bundle.py`, `prepare_fleet_smoke.py` and `FLEET-END-CONTRACT.md`;
  - T1's `FROZEN-T1.json` (24817e16) and its nine guard modules;
  - T1's `detach.sh`, `end_exit_push.sh` and `end_verify_push.py`;
  - T1's END-A5 smoke, reference and manifest receipts;
  - the `K4S-MAC-PROCEDURE.md`;
  - COORDINATOR rulings 133f3ae4, 26d68687, 50b519e6 and 4af19c23;
  - `K4S-DBUS-FLAG-INVESTIGATION-r1.md` and the R4 `RESULT.md` and `samples.txt`, which are health-only `/proc/2005/stat` rows.
- **Read boundary:** I never opened any `games/`, `complete.json`, hub-blocks, reducer or verifier output, or any outcome field. The counted-inventory rows I compared are health-only descriptors, `{host, phase, descriptor}`, with no result field.

## Verdict: **ADOPT_WITH_CHANGES**

**What the plan gets right:**
- Its three blockers are real, and I reproduced each one from code.
- Its reading of the frozen END code is accurate in every place I checked: pins, the evidence layout, the END-JOB fields and order, the claim registry, the two-strike consequence, and the C5, C2 and stamp carry-overs.
- Its ordering (END → pool → recheck → K4S Mac phase C → release) matches PREREG r3 §4.5 and the frozen code.

**Where it falls short.** It underestimates how many failures can happen **after the claim**. Under the frozen registry, each host gets at most 2 attempts for the whole END job:
- a round with no passing attempt on a host leaves no nonconforming pool;
- without that pool, no later round can claim or pool (END-RUNBOOK.md:176-185, :217-218).

**Several plausible configuration failures land after the claim** and so consume a strike:
- guard construction and admission, including T1's `parent_source_seed.admit` git lookups;
- topology validation;
- native and model loading;
- background workers;
- bus-under-load.

The plan's main mitigation, an "offline dry-run of the full producer path on 05", cannot reach any of them:
- `fleet_profile.slot_layout` refuses 05 before the claim (`fleet_profile.py:11-12`), because 05 is a forbidden host in `plan.json`;
- so on 05 only `frozen_identity` and the evidence checks run.

**The central change.** Add an on-host, **non-claiming, non-timing** END preflight per host before the END-JOB. This is T1's C3 / A5-smoke precedent. The other changes tighten B1's disclosure, B2's copier, the guard-job contents, the wrapper (claim files) and the 04 login and load hygiene.

---

## 1. B1: is completion-v2 a pure envelope correction?

**Yes. I checked it independently** (`/tmp/k4s-review-r1/scripts/count.py`, run on blobs exported from origin/main):

| Check | Result |
|---|---|
| sha256 of the files | v1 inventory `f10ab943…`, v1 completion `ed7d11b7…`; v2 inventory `22c41cb7…`, v2 completion `3794d953…`. All match the committed blobs and the ERRATUM |
| v1 vs v2 envelope keys | v1 `{schema: clasher.k4s.counted-inventory.v1, study, sealed, outcomes_read, blocks}`; v2 `{schema: clasher.t1.counted-blocks.v1, outcomes_sealed: true, blocks}` (= `INVENTORY_FIELDS`, `end_evidence.py:60`) |
| Rows | Parsed-equal, 3,900 = 3,900. The raw `"blocks": [...]` byte span is **byte-identical**. Canonical rows SHA `2e18ce34e955ad19…` in both |
| Re-serialisation | `json.dumps({schema, outcomes_sealed, blocks=v1 rows}, indent=1) + "\n"` gives **exactly** `22c41cb7…`. So v2 is v1's rows under the new envelope, with nothing else changed |
| Row content | Every row is `{descriptor, host, phase}`. Descriptor keys are exactly the 15 allowed fields (frozen 12 plus `rotation`, `subsample`, `replacement_k`). No result field |
| Per host/phase | 03: 206/1205/268/219/71; 04: 186/1194/266/217/68 (reporting, r1..r4). Equal to `per_host_phase.counted` in both completions |
| Frozen `counting()` (end_evidence 6337e4bc, the same blob at 391d2006, 133f3ae4 and main), with the committed `blind-ledger-final.json` 649272bd and the 10 committed `supervisor-exit.json` files (each SHA = the completion's `supervisor_exits`) | **v1 REFUSES** with `EvidenceError('END requires the sealed blind ledger and counted inventory')`. **v2 ACCEPTS** with `{blocks: 3900, losses: 99, host_phases: all 10}` |
| Negative controls on v2 | Dropping a row is refused ("lacks the complete logical primary population"). An extra envelope key is refused. A duplicate row is refused |
| Completion diff v1 → v2 | Only `counted_inventory_sha256` changes, and a `revision` block is added. Every other byte-level field is identical, including `completed_at_utc` 14:45:34Z |
| Other consumers of the completion | `end_evidence`, `end_pool`, `barrier.outcome_release` and `verify_k4s` all read named fields with `.get`/index. None checks the exact key set, so the extra `revision` key is harmless. No consumer reads the counted-inventory file in v1's schema (`git grep`). The `k4s_logic.py:801` `outcomes_read` check is on the T1 **corpus** inventory, not on this file |

"99 losses" here means the 99 blind-ledger events (lost blocks: 73 primary and 26 guard). It is not game results.

**Amendment:** none is needed.
- The inventory schema is fixed by frozen END code and by END-RUNBOOK.md:46-47, not by a prereg decision rule.
- v2 brings the producer into line with the frozen reader.
- No arm, cell, seed, N, hypothesis, gate or analysis changes, and no block is added, removed or reordered.

**Selection and outcome-exposure risk: none.**
- The rows are byte-identical.
- The envelope values are constants.
- The trigger was a schema check in frozen code, found by an offline reader that opened no outcomes.

**Disclosure needed beyond the revision block** (RC-1 below). It is small:
1. **How v2 was produced.** v2 keeps `script_sha256` `94f3e405…`, which is v1's `final_pass.py`. The committed `final_pass.py` is now `47f93505…` after the one-line envelope fix in 23604d1c. v2 was evidently produced by re-serialising v1's rows; my check above reproduces it exactly. It was not produced by re-running the edited script. Record this, and record that `script_sha256` names the producer of the rows rather than of the envelope.
2. **Ledger path.** `VALIDATION.txt` names `ledger/blind-ledger.json`, the runner's local name. The committed path is `ledger/blind-ledger-final.json`, with the same SHA 649272bd.
3. **DBus disclosure.** The R2 disclosure 128d66a0 and `dbus-recount.json` cite the v1 SHA f10ab943. They stand because the rows are identical; cite the canonical rows SHA `2e18ce34…` as the bridge.
4. **Which completion is of record.** The coordinator's ruling must state that v2 (`3794d953`, inventory `22c41cb7`, commit 23604d1c) is the completion of record for every downstream binding: the END evidence `completion`/`counted_inventory`, END-JOB `completion_sha256`, the PC4 sidecar, the verifier receipt and **release item 1**. v1 stays committed, unchanged and superseded. `barrier.outcome_release` does not cross-check that release item 1 equals the END-JOB's completion, so this must be stated in the ruling and checked at release.

---

## 2. Is the plan complete and correct against PREREG-K4S and the frozen END code?

I re-verified the following independently:
- **Pins:** all 33 path pins of manifest `74314eda` match at origin/main. At 391d2006 exactly the 5 mismatches the plan lists appear: `build_manifest` 26932fa8, `fleet_validity` 94d0e7f2, `measure_tiers` 5d7de8e3, `state_rows` missing, `tier_backend` b04d201d.
- **No drift:** e4v3 is unchanged since A5 (8799a0d6) and has the 18-file `.py`/`.sh`/`spec-pins` inventory. The END sources, `mac/`, `DELTA-MANIFEST`, `SD1-MANIFEST`, `plan.json` and `FROZEN-T1.json` are unchanged since 133f3ae4. In `DELTA-MANIFEST`, `sdefault.py` 0448db50 and `anchor_x.py` cf528473 match.
- **Guard modules:** the T1 guard module SHAs at main equal the `FROZEN-T1` pins (24817e16, last touched aeeb3003), and its three operational deltas are all `CONFIRM`. Five K4S modules differ from T1's: `common`, `host_audit`, `owned_supervisor`, `ssh_budget` and `parent_source_seed`.

| Item | Plan | Assessment |
|---|---|---|
| **Attempt roots** | The registry and END-FINAL are built in. Proposes one fixed on-host attempt parent per host | Correct about the code. **Make the roots declaration mandatory** (RC-6): a committed, pushed declaration of the per-host runtime, bundle, guard-job, `--repository` clone, attempt parent and preflight directory, made before the END-JOB. The wrapper should enforce the parent, as T1's `end_exit_push.sh:13-17` does. This gives PC1 parity with T1 (3c811584/4ff93a10) and a reference for "all original attempt roots" |
| **Runtime at or after 133f3ae4, identical on both hosts** | Correct (§1.1). 391d2006 cannot run END | Agree. **Specify:** one `git archive` export of a single commit that contains the B2 telemetry and the END evidence, so that the evidence commit is an ancestor. Copy it byte-identically to both hosts, read-only. Prove equality by equal canonical SHAs of the bundles' `runtime_files` and `measurement_files`, which the pool requires anyway. `--repository` is a separate clone, because claims are written into its work tree (`end_evidence.py:493-508`) |
| **Guard freeze** | Use T1's `FROZEN-T1` (24817e16) and modules in a distinct guard-job namespace | Correct; it is forced by `fleet_validity.py:57-70`. **Incomplete** on what the guard job must contain and which failures it can cause after the claim (RC-3). See §2a |
| **Wrapper and verifier** | Reuse `detach.sh` 1648dfdc unchanged, plus narrow K4S deltas of `end_exit_push.sh` 0a87166f and `end_verify_push.py` 753722c9 | Right pattern. Confirmed: `detach.sh` is the same in t1/, k4s-confirm/ and the FROZEN-T1 pin; the wrapper checks `--output` (`:27-31`) and hard-codes the hosts (`:9`), the base (`:5`) and the receive path (`:36`). **Missing:** the K4S producer writes the claim **outside `--out`**, into `<repository>/reports/explore/k4s-confirm/end/registry/round-RR/<host>/attempt-NN.json`. The wrapper delta must push that registry directory as well, always and even when no measurement directory exists. Otherwise collecting claims needs an extra SSH, and a claim-without-receipt case (a failure between the claim and `K4SStore` creation) could go unseen (RC-5) |
| **C5 (no SSH during timing)** | Quotes C5, C-d and RG1 correctly; one `ControlMaster=no` launch SSH, closed before admission | Agree, and it matches ruling 4af19c23. **Add** for 04 (and preferably both hosts): run quiet-read #2, timers and stamps, `who`, the pre-exec gate and the detach in **one** SSH session, so there is no separate login just before admission. Record the launch-SSH close UTC and the guard admission UTC in the launch receipt (RC-7) |
| **Pre-exec gates** | C5 pre-exec gate (parent nice 0, SCHED_OTHER, byte-equal argv, no outer prefix), the gates in code | Correct. `slot_layout` requires `nice == 10`, read back live (`fleet_profile.py:13`), so an outer `nice` makes a pre-claim refusal. That is not a strike, but it costs the window |
| **Quiet-read v3** | Two reads 30 s apart; v3 adds `apt-config` and `apt.systemd.dai` | Correct (COORDINATOR:2767-2772, :3015). The END guard is T1's OP-1..OP-6 freeze **without** K4S's OP-7 apt budget, so any apt or maintenance process during timing counts as `foreign_compute` and fails the attempt. That makes v3 more important here than in reporting |
| **apt timers and stamps** | C2 ≥ 2 h clearance and the stamp pre-trigger | Correct for apt and motd. **Gap:** the r4 timer read (`step6/127x0{3,4}-stamps-timers.txt`) was **filtered** to three apt/motd timers. Under T1's guard any CPU-active non-owned root or system process is foreign. Read `systemctl list-timers --all` unfiltered, and require ≥ 2 h clearance for every system timer, or justify each exception from K4S reporting evidence (RC-8). The local-midnight (07:00Z) daily timers fall inside the plan's W3 window |
| **Pool** | `end_pool pool` then `recheck` with `checked_by ≠ pooled_by` (`end_pool.py:596`); PC3 interpreter | Correct. Add that the pool and recheck `--repository` must be at a HEAD containing the END-JOB, every claim, END-FINAL and the B2/evidence commits, and that PC3 pins one interpreter for both |
| **Mac phase C after the TIERS Mac session** | Almost certainly standalone (§5.2): Sam's P1 authorization plus a `clasher.k4s.mac-standalone-authorization.v1` file | Correct (`K4S-MAC-PROCEDURE.md:56-72, :207-214`). Add: P3 needs the TIERS session receipts **committed**. Sam's 2026-10-11 authorization was for the TIERS/E4 replay; the coordinator must confirm it covers the K4S replay or record a new one. macOS 27.0.1 is pending a restart (COORDINATOR:3110), which is a session risk. Release does not wait for the K4S Mac summary (r3 §4.5) |
| **Release barrier** | `barrier.outcome_release` items; `end_reference`+`end_recheck` or `ratio_unavailable_declaration`; `tiers_summary`/`tiers_release`; explicit coordinator GO | Correct (`barrier.py:11-44`). Add the v2 binding (RC-1 item 4) |
| **Sequencing** | 03 first, 04 after 03 verifies | Agree. **Make it binding** for round 00 (RC-9). A shared config error that shows up after the claim would otherwise burn a strike on both hosts |
| **Offline dry run on 05** (§8.10) | "full producer path" in a scratch repo | **Overstated.** On 05 the producer refuses at `slot_layout` (05 is forbidden), so only `frozen_identity` and evidence are exercised. Keep it as an offline validator (RC-4b), and add the on-host preflight (RC-2) |

### 2a. Failures after the claim that the plan does not cover

In `end_reference.reference()`:
- **Before the claim:** lines 289-304, then `end_job` (:305) and `producer_claim` (:309).
- **After the claim:** `backend(a)` (:326), `check_corpus` (:327), `validate_topology` (:333), the guard construction and `admit` inside `reference_monitor` (:334-365), and the K4SFleetBackground spawn and readiness (:366-370).

Each of the following would consume one of a host's two strikes:

1. **The T1 `parent_source_seed.admit` git lookup.** `parent_source_seed.py:62-69` calls `committed_binding` for **every** frozen seed binding (03 b2f9e25e, 08 ce042b97) **before** the hostname check.
   - That runs `git show <commit>:<path>` in `<guard job>/repo` if that is a git checkout, and otherwise in `/mpac/sdicks02/repos/clasher` **on the host**.
   - On 03/04, neither is known to contain those commits.
   - Separately, `ReportingGuard` needs `seed_inputs` for all four seed and join files: the 03 and 08 receipts, the 08 server, and the 04-client transport identity. They must be in the bundle and byte-identical under `<guard job>/repo/<path>` (`fleet_validity.py:92-108`; T1 01 manifest `END-A3-manifest-01-f6cebbaa.json:112-116`).
2. **Admission pins.**
   - `system-bus-admission.json` must be present and byte-equal in both the bundle and the guard job (`:110-111`, `:127-130`).
   - Any `idle-services.json`, `owned-copier-admission.json` or `owned-supervisor-admission.json` that exists in the guard job must be pinned (`:112-114`).
   - 03 needs `idle-services.json` for PID 2180947. Without it, the validation-cache service becomes foreign compute.
3. **Topology.** `manifest["topology"]` is validated against the live `cpu_counters()` only after the claim. If it is copied from T1's 01/08 bundles rather than taken from 03/04, it may not match.
4. **Interpreter, native and models.** These load after the claim, in `backend(a)` and in each background worker. Whether the T1 venv and torch exist on 03/04 is unverified (plan §8.5).
5. **Bus under load on 04** (§3).
6. **The MHz gate** (`mhz_gate`, after the claim, at :400-403). Reference MHz under END load against the committed full-occupancy reporting rows.

**Guard-job writes.** The T1 modules write to the guard job:
- `allowlist-occurrences.jsonl` (`host_audit:175`);
- `op2-confirmations.jsonl` (`perception_confirmation:131`);
- `ssh-family-occurrences.jsonl` (`ssh_budget:123`);
- `parent-source-seed-admission.json` (`parent_source_seed:83`).

T1 used a **fresh guard job per attempt**: its per-attempt bundles differed only in `guard.job` (`END-A5-reference-approved-argv-08-r1.json`). Do the same (RC-3), so that each attempt's guard side-files can be attributed to it alone.

---

## 3. DBus

**Facts:**
- R4 final (fbcf1a67): 0.0359% over the whole window, with a worst 30-s window of 0.099%.
- Coordinator 4af19c23: END runs with the frozen threshold, under these attempt rules: one launch SSH closed before admission, no copier, and C5.
- My tick analysis of the health-only samples: 59 ticks of 10 ms each in 1,608 s, about **1 tick per 30 s**. There was at most 1 tick in any 1–2 s window, at most 2 in 10 s and at most 3 in 30 s. No visible burst followed the probe's own login (the first tick came at +8 s).

**Does the plan handle the END threshold? Mostly, yes.** The frozen meter is T1 `system_bus.finish`: `interfered = ticks*100 > hz*elapsed` (`system_bus.py:26-30`). The guard applies it in two places:
- **Cumulatively from admission:** `bus_meter` begins at the first guard call (`fleet_validity.py:154-156`), and any sample above 1% fails (`:189-193`).
- **Per 50-state block** (`:213-227`); one flagged block fails the attempt.

At 0.036% this is roughly 30× under the bar for any window of a few seconds or more. Two residual risks exist, both inherent in the frozen meter and present on both hosts:
- **Very short windows.** One tick (10 ms) trips any window under 1 s. A truncated last warm-up block (`end_reference.py:378-386` breaks at `until`) can be that short. At about 1 tick per 30 s, the chance is roughly (block seconds)/30 per short block. It is small, but it is a strike. Disclose it; it cannot be changed without an amendment.
- **No measurement under load.** R4 was an idle host. END runs all 11 slots loaded. The runner's RESULT.md says so itself ("not a measurement under END load"). The "session churn" explanation of the reporting-time ~1.47% fits the investigation's numbers: first-wave listing logins at about one per 10 s gave about 1.0–1.1%, which is about 0.1 s of bus CPU per login. But no committed observation has reporting-level **load with zero logins**, so a load-driven component is not ruled out. On 04, one strike lost to bus interference leaves only one.

**Should END run with no copier or SSH activity? Yes, and it is already ruled (4af19c23).** The plan should make it concrete:
- No copier anywhere near 03/04 from the first quiet read until the attempt's exit. The exit-push is outbound and runs after exit, so it is fine.
- On 04, a single combined launch session (RC-7). No ControlMaster to 03/04 from any machine (also close the Mac-side masters). A C5 broadcast to every thread. Prefer the overnight W3 window, which also minimises student console logins (a console user is a technical failure).
- **Before the first 04 claim**, the 04 preflight (RC-2) runs the frozen background load on all non-reference slots for ≥ 15 min, with the frozen guard sampling at 1 Hz, launched by one SSH and collected after exit, with no login in between. That is the measurement R4 lacked. If the loaded cumulative bus stays at or below about 0.3%, proceed. If it is at or above 0.7%, the coordinator re-rules (a), (b) or (c) **before** any 04 claim.
- If a 04 attempt still fails with `op1_interference`, STOP: there is no automatic repeat. The coordinator re-rules before the last strike.

---

## 4. Missing pieces, Sol review, authorizations, critical path

### 4a. New code that needs Sol review before it runs

Coordinator rule 4af19c23 now requires review before running any new host-touching script.

| # | Script | Touches hosts? | Notes |
|---|---|---|---|
| S1 | **B2 exact-path copier** | yes, read-only | See RC-4 |
| S2 | **END evidence builder plus offline validator** | no (05) | Writes the `clasher.k4s.end-evidence.v1` document, then runs the frozen `end_evidence.end_evidence()` + `fleet_end.host_reporting(profile)` + `fleet_profile.slot_layout(profile, plan, host, 10)` for each host on 05 |
| S3 | **Guard-job builder** | yes | Per host and per attempt: FROZEN-T1 copy; system-bus admission copied from the K4S job; 03 `idle-services.json`; `repo/` as a git checkout holding the seed commits plus the four seed and join files; no owned-copier or owned-supervisor files |
| S4 | **Fleet-reference bundle assembler** | yes (staging) or 05 | Re-pins T1's A5 base manifests (01 5df0fa00, 08 93daf063) or wraps `prepare_bundle`. Sets `reference_load_profile` (host, slot 0, 11 slots, `console_rule:false`, warmup ≥ 300, perception none, the plan and evidence copies, `guard`). Takes **topology from the target host**. Uses `sets.speed` = T1 own-tier300, `states.pkl` 0addf7c0 and the rows bcd30777/8cc2f611 |
| S5 | **On-host END preflight** (new; RC-2) | yes | Non-claiming and non-timing. See RC-2 |
| S6 | **K4S exit-push wrapper delta and 05 verifier delta** | yes | A narrow diff against 0a87166f and 753722c9: host tuple, per-host bases, `--out`, receive base, the declared attempt parent, plus the registry-claim push (RC-5) |
| S7 | **Launch and prelaunch-gate script** | yes | The single-session quiet-read v3 ×2, unfiltered timers, stamps, `who`, ControlMaster absence, the pre-exec gate and the detach. Quiet-read v3 itself is already approved |
| S8 | Claim collector / registry commit helper | no (05) if the wrapper pushes claims | — |

**Not needed for B1:** v2 already exists and is reproduced byte-for-byte above. A Sol pass on the one-line `final_pass.py` change is optional, since that script was not used to produce v2. The END-JOB is data; a coordinator check is enough.

### 4b. Host actions needing your (coordinator) authorization

| Action | Who authorizes |
|---|---|
| A1. Run the B2 copier (read-only exact-path reads on 03/04) | coordinator |
| A2. Staging on 03/04: END namespaces, runtime export, `--repository` clones, bundles, guard jobs. Plus a **read-only SHA-verified copy of T1's `states.pkl`/`states-rows.{json,bin}`** from T1 storage, a T1-owned tree. Per the no-writes rule, copy into the K4S namespace only, and confirm with the T1 owner | coordinator, T1 owner |
| A3. Venv/interpreter provisioning on 03/04 if missing | coordinator |
| A4. Preflight runs on 03 and 04 (≥ 15 min load on 04) | coordinator |
| A5. Stale-stamp pre-trigger logins (03 after 00:57:44Z; 04 after 21:32:48Z) | coordinator |
| A6. The END-JOB commit and push, and each END launch (GO per launch); the C5 broadcast to all threads | coordinator |
| A7. Commits of the claims, END-FINAL, pool and recheck | coordinator |
| A8. Mac phase C | Sam (P1 replay authorization explicitly covering K4S), coordinator (standalone authorization file and lock) |
| A9. Only if the 04 preflight fails the bus check: R4 branch (a), GDM stopped by Sam or an admin | Sam or a lab admin |

### 4c. Critical path (ordered; times are estimates of wall time)

1. **Coordinator rulings** (~15 min): v2 is the completion of record, with the RC-1 disclosure; adopt this plan with these changes; DBus stays per 4af19c23, with the 04 preflight gate.
2. **Author S1+S2 and S3+S4+S5+S6+S7** in parallel (~2–3 h). **Sol review** (~1–1.5 h per round; plan on 2 rounds) → ~4–6 h.
   - S1 and S2 go first, because B2 → evidence → END-JOB is the dependency chain.
3. **A1: B2 copy** (~20–30 min).
   - Check on-host `launch.json`/`supervisor-exit.json` SHAs, then copy the 20 files.
   - Check sizes: refuse any file over 95 MB; escalate rather than use LFS.
   - Secret-scan, commit, push (~30 min).
4. **Build and commit the END evidence; run the S2 offline validation on 05** (~30–45 min).
5. **A2/A3: stage** the runtime export of the evidence commit, the clones, bundles and per-attempt guard jobs. Commit the roots declaration (~1–1.5 h).
6. **A4: preflights.** 03 (~20 min), then 04 (~30–40 min including ≥ 15 min loaded). Push after exit; commit an outcome-blind disclosure. Gate: both pass, and 04's loaded bus is clearly under 1%.
7. **END-JOB:** commit alone, scan, push; fast-forward both `--repository` clones (~15 min).
8. **03 round 00:** prelaunch gates (~15 min), run (~45–90 min), C-d (≥ exit + 1300 s), verify (~10 min). About 1.5–2.3 h.
9. **04 round 00:** only after 03's seal is `complete` and verified. Same steps, about 1.5–2.3 h.
10. **Collect claims** (pushed by the wrapper) → commit → a later commit with `END-FINAL-round-00` (~20 min).
11. **Pool and independent recheck on 05** (~30–60 min), then commit.
12. **K4S Mac phase C**, standalone (A8; Mac session time plus authorization lead time).
13. **PC1–PC4, verifier receipt, release receipt** (coordinator GO).

**Timing.**
- From now (~15:20Z), steps 1–7 take about 9–13 h. W1 and W2 (tonight) are not realistic.
- The realistic window is **W3, overnight into 10-13.** Launch 03 at about 02:00–04:00Z once apt-daily has run and the timers have been re-read; then 04.
- Aim to finish both attempts before 07:00Z local midnight, unless the unfiltered timer read clears that time.
- Expect a pooled END by about mid-morning 10-13 if nothing fails.

---

## 5. Required changes (to adopt)

- **RC-1 (B1 record and disclosure).** The coordinator rules that completion-v2 is the completion of record: inventory `22c41cb7…`, completion `3794d953…`, commit 23604d1c. It is bound by the END evidence, END-JOB `completion_sha256`, the PC4 sidecar, the verifier receipt and release item 1. v1 is retained as superseded. Record:
  - (a) v2 was produced by re-serialising v1's rows under the frozen envelope, and `script_sha256` 94f3e405 is the producer of the rows; `final_pass.py` 47f93505 was not re-run;
  - (b) `VALIDATION.txt`'s ledger path is the committed `ledger/blind-ledger-final.json` 649272bd;
  - (c) the canonical rows SHA `2e18ce34e955ad19608d6a704408d8d9b60019bb5486e9fbcce2f6efb55d3a29` is equal in v1 and v2, so the R2 DBus disclosure and recount stand.

  No amendment.
- **RC-2 (on-host, non-claiming END preflight; T1 C3 / A5-smoke parity).** Before the END-JOB, run on each host from the final runtime and the final bundle (with its own fresh guard job):
  - the frozen `validate_bundle`;
  - `validate_physical_cpus` and `validate_topology(manifest["topology"], cpu_counters())`;
  - construction of the K4S backend (native and models);
  - frozen `ReportingGuard` construction, admission and ≥ 60 1 Hz samples;
  - a spawn of the frozen-adapter background slots to readiness;
  - on 04, ≥ 15 min of full background load under the guard, with no login in between, recording the cumulative and windowed bus and per-core MHz.

  It must **never** call `measure()`, claim, or write under the attempt parent or the registry. Launch it with one SSH, push the results after exit, and commit them as an outcome-blind disclosure. A failure is fixed before the END-JOB. Correct plan §8.10: the 05 dry run cannot exercise anything past `slot_layout`.
- **RC-3 (guard-job specification).** A fresh guard job per **attempt**, under the declared namespace, containing:
  - `FROZEN-T1.json` (24817e16);
  - `system-bus-admission.json`, copied byte-identically from the K4S job, with identity re-checked against PID 2005 / start_ticks 1032 on 04 and the 03 equivalent;
  - on 03, `idle-services.json` for PID 2180947;
  - `repo/` as a **git checkout** containing b2f9e25e, ce042b97 and the 08 join commits, holding all four seed and join files (`parent_source_seed.py:62-69` runs `git show` for every binding before the host check);
  - no other admission files (or they must be pinned).

  State in the END ruling that the END guard is T1's OP-1..OP-6 freeze, not K4S's reporting guard. It has no OP-7 apt budget and no observed-child CPU credit; that is per the frozen END contract, and it is disclosed.
- **RC-4 (B2 copier and validation).**
  - (a) For each of the 10 phases, locate the phase directory by checking that the on-host `launch.json` and `supervisor-exit.json` SHAs equal the committed `phase-meta` SHAs.
  - Then read exactly `<dir>/mhz.jsonl` and `<dir>/census.jsonl` by full path: no glob, no recursion, no other name. Record sizes and SHAs on the host and locally.
  - Refuse any file over 95 MB and escalate; do not use LFS, because `fleet_end.artifact` needs real blobs (`fleet_end.py:20-34`).
  - Run outside any timing window, then secret-scan and commit outside `end/`.
  - (b) Before the END-JOB, validate on 05 with the frozen `end_evidence` + `host_reporting` (exact utc join, ≥ 2 full-occupancy rows, `slots == 11`) + `slot_layout` for each host.
- **RC-5 (wrapper delta).** In addition to the plan's constant and argv changes, push `<repository>/reports/explore/k4s-confirm/end/registry/round-RR/<host>/` after exit, always, and even when no measurement directory exists. The 05 verifier records claim-without-receipt cases. Collecting claims for the registry commit then uses this pushed copy, with no extra SSH.
- **RC-6 (roots declaration).** Commit and push, before the END-JOB, the per-host paths: runtime, bundle(s), guard-job parent, `--repository`, attempt parent and preflight directory. The wrapper refuses any `--out` outside the declared attempt parent.
- **RC-7 (login hygiene; required for 04, recommended for 03).**
  - One SSH session with `ControlMaster=no` and `ControlPath=none` carries quiet-read #2, the gates and the detach.
  - Record the session-close UTC and the guard admission UTC.
  - No ControlMaster to 03/04 anywhere, and a C5 broadcast.
  - On 04, an `op1_interference` failure means STOP: the coordinator re-rules (a)/(b)/(c) before the second attempt.
- **RC-8 (timers).** Read `systemctl list-timers --all` unfiltered. Require ≥ 2 h clearance for every system timer, or record a per-timer exception backed by K4S reporting evidence. Re-read after every run.
- **RC-9 (sequencing).** Round 00 is binding in this order: 03 attempt, then a `complete` seal verified at ≥ exit + 1300 s, then 04. Both preflights must pass before the first claim on either host.

## 6. Non-blocking notes

- PC1 for K4S is: the registry at HEAD = the latest END-FINAL = the on-host listings of the declared attempt parents, plus the committed preflight disclosures. Keep the preflight output outside the attempt parents so the two never mix.
- PC3: one interpreter for pool and recheck (T1 used `e4v3-venv` 3.12.12 on 05). The host interpreter is pinned implicitly by `runtime_files`, so check that the venv exists on 03/04 at staging (A3).
- The plan's R4 inference is now the coordinator's reading in 4af19c23. RC-2's loaded 04 probe is a cheap test of it; it does not re-open the ruling.
- END evidence location: keep `end-evidence.json` outside `end/`, for example at `reports/explore/k4s-confirm/end-evidence.json` with repo-relative artifact paths. The bundle carries a byte copy pinned in `files`. The workers read the `--end-evidence` path and resolve its artifacts relative to it.
- The R4 probe (`probe.sh`) was accepted after the fact. That is not a precedent: S1–S8 must all be reviewed before they run.

## Appendix: commands run (all read-only; outputs in `/tmp/k4s-review-r1/`)

- `git show` of every blob named above, at origin/main, 391d2006, 133f3ae4, bb7c7f88 and 23604d1c.
- `scripts/count.py`: the frozen `end_evidence.counting` on the v1 and v2 inventories, with three negative controls.
- An inline row and envelope comparison, and a re-serialisation check giving `22c41cb7`.
- A hash of all 33 manifest path pins at main and at 391d2006.
- T1 vs K4S guard-module SHAs against the FROZEN-T1 pins.
- The R4 `samples.txt` tick histogram (health-only `/proc/2005/stat`).
- `git diff --stat` for drift since A5 and since 133f3ae4.
