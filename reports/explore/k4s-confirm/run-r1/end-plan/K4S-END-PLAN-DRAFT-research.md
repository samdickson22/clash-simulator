# PREREG-K4S END reference: plan draft (research input for the coordinator)

- **Written:** 2026-10-12, about 14:55–15:05Z (`date -u` at 14:55:26Z and 14:59:37Z during the read). Offline, read-only research sub-agent on 127x05.
- **Sources:** origin/main `50b519e6` (fetched at the start of the read). Frozen worktree `/mpac/sdicks02/repos/clasher-k4s-run` at `391d2006`. Runner directory `/mpac/sdicks02/k4s-runner/run-r1/`, file names and health files only.
- **Read boundary:**
  - Never opened: any `games/` directory, `complete.json`, hub-blocks, reducer or verifier output, or any outcome field.
  - No SSH and no host-touching command. The only command I ran was `analyze.py` on the local R4 `samples.txt`.
  - No commits. My only write is this file.
  - A T1-pattern sweep was delegated to a read-only Explore agent; I spot-checked its key citations (§2–§4 items marked "T1 sweep").
- **Conventions:** paths are repo-relative unless absolute. `X:N` means line N on origin/main, unless "391d2006" is given. **Inference** marks anything not read directly.

---

## 0. Summary for the coordinator

**Three blockers have to be fixed before any END attempt. None of them was in the brief.**

**B1. The committed counted inventory cannot pass the frozen END evidence reader.**
- `end_evidence.counting` requires all of the following (`k4s-confirm/end_evidence.py:83-87`, `INVENTORY_FIELDS` at `:60`):
  - `inventory["schema"] == "clasher.t1.counted-blocks.v1"`;
  - `inventory["outcomes_sealed"] is True`;
  - the key set is exactly `{schema, outcomes_sealed, blocks}`.
- The committed `run-r1/completion/counted-inventory.json` (`f10ab943`, bb7c7f88) instead has schema `clasher.k4s.counted-inventory.v1` and keys `{schema, study, sealed, outcomes_read, blocks}`. It was written by `run-r1/tools/final_pass.py:70`.
- The completion receipt binds that SHA (`REPORTING-COMPLETION.json` `counted_inventory_sha256 = f10ab943…`), and the reader requires the completion to bind the evidence's inventory (`end_evidence.py:224-226`).
- So **every END producer, background slot and pool fails closed** on the current completion. The runner's own completion plan (PROGRESS.md, 2026-10-12T14:08:03Z, step 2) said "counted-inventory.json in the frozen end_evidence format". The written file deviates from that plan.
- The 3,900 block rows themselves look compatible: every descriptor key is in `DESCRIPTOR_FIELDS` (`end_evidence.py:56-58`).
- **The fix needs a coordinator ruling.** The probable fix is a mechanical re-emission of the inventory, plus a completion receipt that binds it, committed before the END-JOB. Details in §1.4 and §8.

**B2. No per-phase `mhz.jsonl` or `census.jsonl` is in the repository or in the runner's directory.**
- The END evidence needs, for each of the 10 counted host/phases, `launch`, `supervisor_exit`, `mhz` and `census` items (`end_evidence.py:162-166, :210-213`). Each must be byte-equal to a committed blob (`fleet_end.artifact`, `e4v3/fleet_end.py:20-34`).
- `launch.json` and `supervisor-exit.json` are committed for all 10 (§1.4). The two telemetry files exist only on the hosts, inside each phase's output directory (`supervise.py:47, :111, :116`).

**B3. The END guard cannot use the K4S job freeze, and no fleet-reference bundle assembler is committed.**
- The frozen `fleet_validity.ReportingGuard` requires a T1-shaped freeze: `operational_delta_op5`, `operational_delta_op5_08` and `operational_delta_op6` all equal to `CONFIRM`, with guard modules keyed `reports/explore/t1/<module>.py` (`e4v3/fleet_validity.py:57-70`). It also requires a live `guard.job/FROZEN-T1.json` (`:88`) and an existing system-bus admission in that job (`:110-111`).
- `FROZEN-K4S.json` `416f6e51` has none of the three deltas, and keys its files under `reports/explore/k4s-confirm/`. Five of the nine K4S guard modules also differ from T1's (§1.6).
- So K4S END must use **T1's freeze `FROZEN-T1.json` (24817e16, aeeb3003) with the T1 guard modules, inside an approved, distinct END guard-job namespace on each host**. This matches what T1 did with `end-op6-guard-job-01-r1`.
- `prepare_bundle.py` can only emit the `linux-dry-run` and `mac-preregistered` profiles (`e4v3/prepare_bundle.py:115`). T1 derived its `fleet-reference` manifests with helpers that are not committed (§1.3). **K4S needs a reviewed assembler.**

**Other findings**

- **The DBus R4 interim looks clearly under 1%.** Over 870 s of the running baseline (samples sha `300fc533…`):
  - whole-window 0.0345% of a core; every 30-s window ≤ 0.066%; 0 windows above 0.7%;
  - the daemon identity is unchanged (PID 2005, start_ticks 1032), and the 45 uid-125 GDM processes are still present.
  - **Inference:** the ~1.47% seen in reporting was driven mainly by copier SSH logins, amplified on 04, not by the greeter on its own.
  - If the final 30-min result holds, R4's branch is "proceed as frozen". Add conditions: one launch SSH, closed before admission, and no other login to 04 for the whole attempt (§6).
- **Runtime.** The frozen worktree `391d2006` **cannot** run END: 5 of the 33 pins in the A3 manifest `74314eda` mismatch there (§1.1). The END runtime must be a tree at or after `133f3ae4`, byte-identical on 03 and 04.
- **Schedule.** Earliest realistic window: tonight or the overnight window into 10-13. Run 03 first (§5).

---

## 1. Bytes and pins an END runtime on 03/04 must hold

### 1.1 Frozen identity: the K4S Mac/END manifest of record

- **Manifest:** `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json`, sha256 `74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357`.
  - Adopted at merge `133f3ae4` (COORDINATOR.md:2523-2531).
  - Recomputed on origin/main: matches. `frozen: true`, `status: FROZEN`.
- **Pin check:** I hashed all 33 file pins it lists at origin/main (`end_files`, `k4s_files`, `reused_readonly`, kernel files, SD1 manifest, prereg). **0 mismatches.**
- **The same check at `391d2006` gives 5 mismatches:**
  - `mac/build_manifest.py`: 26932fa8, pin 2e255fb9;
  - `fleet_validity.py`: 94d0e7f2, pin 0775b704;
  - `measure_tiers.py`: 5d7de8e3, pin 6066228b;
  - `state_rows.py`: missing, pin 3899276b;
  - `tier_backend.py`: b04d201d, pin 02e2139f.
- **Consequence:** `end_reference.k4s_pins` → `L.load_k4s_manifest(..., require_frozen=True)` (`end_reference.py:127`) and `end_background.frozen_helpers` (`end_background.py:63-67`) would refuse on a 391d2006 runtime. Amendment 3 §7 also says END must run "from an amended runtime" (`PREREG-K4S-AMENDMENT-3-20261012.md:133`).
- **Fleet trees stay as they are.** The *reporting* overlay must keep d89cab16 and 26932fa8, and deploying main's `mac/` into a fleet reporting runtime is forbidden (A3 §7, l.125; COORDINATOR.md:2531). END uses a **separate** runtime tree, so this does not conflict.

**Pins that END checks (all from manifest 74314eda; verified at origin/main):**

| What | Path | sha256 |
|---|---|---|
| END sources (`end_files`; also executing-byte check `end_reference.py:144-156`) | `k4s-confirm/end_reference.py` | `5cb4751e…` |
| | `k4s-confirm/end_pool.py` | `069c22e7…` |
| | `k4s-confirm/end_background.py` | `a872bd2d…` |
| | `k4s-confirm/end_evidence.py` | `6337e4bc…` |
| K4S Mac/END logic (`k4s_files`; `END_MEASUREMENT_FILES` includes the first two) | `mac/k4s_backend.py` | `8c8da476…` |
| | `mac/k4s_logic.py` | `2e4d7a5c…` |
| | `mac/build_manifest.py` | `2e255fb9…` |
| | `mac/K4S-MAC-PROCEDURE.md` | `1b747d94…` |
| Kernel / scorer (`k4s_kernel.files`; must equal DELTA-MANIFEST, `end_reference.py:130-133`) | `k4s-confirm/sdefault.py` | `0448db50…` |
| | `k4s-confirm/anchor_x.py` | `cf528473…` |
| SD1 manifest (`--sd1-manifest-sha256`) | `k4s-confirm/SD1-MANIFEST.json` | `b8ce7b4c088e2758…` |
| e4v3, reused read-only (`v4/mac-e4-package/e4v3/`) | `fleet_validity.py` (A5 race fix) | `0775b704…` |
| | `tier_backend.py` (A3) | `02e2139f…` |
| | `state_rows.py` (A3) | `3899276b…` |
| | `measure_tiers.py` | `6066228b…` |
| | `fleet_end.py` | `76d5ce31…` |
| | `fleet_profile.py` | `5e482f0a…` |
| | `fleet_reference.py` | `c767a6e0…` |
| | `fleet_pool.py` | `572ad682…` |
| | `replay_load.py` | `1d0e12cc…` |
| | `receipts.py` | `839a43be…` |
| | `telemetry.py` | `808d6fab…` |
| | `classify_failure.py` | `9ab2f038…` |
| | `corpus_contract.py` | `e62b6df5…` |
| | `spec-pins.json` | `823d2e1d…` |
| Reused S1/E1 sources | `reports/explore/e1/planner.py` | `4f608829…` |
| | `reports/explore/s1/anchor.py` | `75a1b7d7…` |
| | `reports/explore/s1/cached_policy.py` | `559ad75c…` |
| | `reports/explore/s1/gc_window.py` | `0c743f3d…` |
| Native | `clasher_core.abi3.so` | `44874fd6047aa53f…`, checked three ways: `NATIVE_SHA` (`e4v3/tier_backend.py:17`) = `L.NATIVE_PROVENANCE_SHA` (`mac/k4s_logic.py:29`) = the file digest (`end_reference.py:103`) |
| Corpus | `K4-states.pkl` | `a97b1fbf6cbc33a7…` (`k4s_logic.py:53`; `end_reference.py:104, :438-439`) |
| Corpus inventory (`--corpus-inventory`) | T1 `corpora.json` | `3501e2ac…`; the manifest's `corpus.inventory` is `reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json` at commit 81f2483e |

**Bundle model pins** (checked by `validate_bundle`, `tier_backend.py:459-461`):
- `v1.pt` `d77005d5…`
- `R3a.pt` `37509a43…`
- `R3a-calibration.json` `e3003533…`
- threshold `0.5005528330802917` (`tier_backend.py:18-21`)

**Plan:** `reports/explore/k4s-confirm/plan.json` `38064dcd…`. The bytes are identical at 391d2006 and on main. Last changed in 201db04c.

**Where the copies already are**
- **Corpus:** the T1 K4 corpus copy (a97b1fbf) and `corpora.json` (3501e2ac) are staged at `$J/end-corpus/` on **both** 03 and 04, chmod 444 and SHA-verified. `$J` is `/mpac/sdicks02/jobs/clasher/k4s-confirm-r1` on 03 and `/mpac/sdicks02/jobs-k4s/k4s-confirm-r1` on 04 (runner PROGRESS.md:10-11, :52-54). The brief mentioned only 03.
- **Native:** the K4S staging copies `native/clasher_core.abi3.so` into each job (`stage_k4s.py:27, :34-35`).
  - **Inference:** that copy is the 44874fd6 provenance build (S1 runtime-pin lineage).
  - **Verify on-host before use.** T1 used `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/native/clasher_core.abi3.so` (44874fd6) (T1 sweep: `END-A5-reference-launch-preparation-01-r1.json`).

### 1.2 What the bundle must be (`tiers-pins.json`, schema `clasher.e4v3.inputs.v1`)

**`validate_bundle(bundle, root, dry_run=True, require_references=False)`** (`e4v3/tier_backend.py:450-469`) requires:
- schema `clasher.e4v3.inputs.v1`;
- `specification` equal to `spec-pins.json`;
- every `files` pin verified under the bundle, every `runtime_files` pin under `--runtime-root`, and every `measurement_files` pin **against the e4v3 directory actually imported** (`:456-458`);
- the three model SHAs and the threshold;
- for `require_references=False`, `states.pkl`, `states-rows.json` and `states-rows.bin` must be pinned (`:466-468`).

**K4S additions** (`end_reference.py:101-110`, `end_background.py:70-87`, `fleet_profile.py:9-29`):
- `profile = "fleet-reference"`.
- `reference_load_profile` with:
  - `host`: this host;
  - `reference_slot = 0`;
  - `slot_count = 11`. This is the plan's `compute.slots` when `console_rule = false`, and it must equal every counted launch's `slots`. All 10 committed `launch.json` files say 11;
  - `console_rule = false`, an explicit Boolean;
  - `warmup_seconds ≥ 300`;
  - `perception = "none"`;
  - `plan`: a bundle copy of the committed K4S `plan.json` (38064dcd);
  - `end_evidence`: a bundle copy of the committed END evidence, whose SHA equals `--end-evidence-sha256`;
  - `guard` (§1.6).
- Both copies must be pinned in `files` (`end_background.py:74-83`).
- `topology` for `telemetry.validate_topology` (`end_reference.py:333`).
- `sets.speed[tier]` for the background corpus loop (`end_background.py:90-103`). In T1's manifest these were the four own-tier sets K0c/S/K2/K4 (`END-A3-manifest-01-f6cebbaa.json`).

**How `measurement_files` gets its values** (an important detail):
- `prepare_bundle.py` pins *every* `.py`/`.sh` file plus `spec-pins.json` in the e4v3 directory at build time (`prepare_bundle.py:117`). `validate_bundle` then re-verifies them against the executing e4v3 directory.
- So the bundle must be built from, or re-pinned against, the **same e4v3 bytes the END runtime imports**, which is origin/main's A5 directory.
- T1's A3 bundle manifest `f6cebbaa` pins `fleet_validity` `94d0e7f2`. **It cannot be reused as-is.** T1 re-pinned it for A5 (T1 sweep: `END-A5-runtime-manifest-inventory-diff.json`, where the only change is `fleet_validity` → 0775b704).

**Common pins must be equal on both hosts.** `end_reference.shared_bundle_pins` (`:113-119`) puts the canonical SHA of `runtime_files`, the canonical SHA of `measurement_files` and the four model-file pins into the common pins. The pool requires those to be equal across hosts (END-RUNBOOK.md:32-34). So the 03 and 04 bundles must come from **byte-identical runtime and e4v3 trees** and the same model and state files. Only `reference_load_profile.host`, `guard.job`, and their pinned admission copies may differ.

**States-rows containers**
- Under A3 (tier_backend 02e2139f), `states-rows.json` and `states-rows.bin` are mandatory. `prepare_bundle.py --state-rows DIR` copies them and checks them through `StateRows` (`prepare_bundle.py:107-113, :233`).
- T1 converted once, on 01: `convert_states.py` 7ce30683, input `states.pkl` 0addf7c0, outputs `states-rows.json` bcd30777 and `states-rows.bin` 8cc2f611. The containers were then copied byte-identically (T1 sweep: `END-A3-authoritative-conversion-01-20261011T2213Z.json`, `END-A3-container-copy-05-…json`).
- **Inference:** K4S can reuse those exact bytes if its bundle uses the same `states.pkl` 0addf7c0. That needs a coordinator-authorized, SHA-verified read-only copy from T1 storage, as was done for the corpus.

### 1.3 How T1/E4 staged an END runtime (T1 sweep, §4)

**No fleet staging helper is committed.**
- `stage_nocopy.py` exists only as `reports/explore/mac-registration/stage_nocopy.py` (166a1636). That is the Mac/A4 no-copy helper (COORDINATOR.md:2163-2173, :2566), and T1 did not use it for fleet END.

**What T1 did:**
- **A3 runtime** (`END-A3-runtime-preparation-20261011T2210Z.json`, 933d68c33): a distinct namespace `…/t1-20261010-r1/end-a3-f6cebbaa-0108-r1/{runtime,source,bundle}` on each host. It held 3,785 runtime files at source f6cebbaa. Source pins recorded: `prepare_bundle.py` a1c59fa3, `tier_backend.py` 02e2139f, `state_rows.py` 3899276b, `convert_states.py` 7ce30683.
- **A5 runtime:** `…/end-a5-0775b704-0108-r1/runtime`. Base bundle manifests were 01 `5df0fa00` and 08 `93daf063`.
- **Per-attempt bundles** lived at `<attempt job>/bundle` (01 `6ce19106`, 08 `f81c9288`). Only `guard.job` changed, and the owned-copier admission was removed (`END-A5-reference-approved-argv-08-r1.json`).
- The per-attempt `fleet-reference` manifests were *derived* by small metadata helpers that live outside the frozen runtime. For example, `derive-smoke-08-CANDIDATE-metadata-only.py` `071a4328` is named only by SHA in `END-A5-CANDIDATE-offline-preparation-20261012T0439Z.json`. **They are not committed as reusable tools.**
- **Interpreter and environment** (`END-A5-reference-launch-preparation-01-r1.json`):
  - Python `/mpac/sdicks02/repos/clasher/.venv/bin/python` 3.12.13, run with `-B`;
  - `PYTHONPATH` = runtime `imitation/evaluation/runtime_dependencies` plus `reports/strategy_council_20260928/imitation`;
  - `OMP/OPENBLAS/MKL=1`.

**K4S equivalent (proposal, inference):**
- A per-host END namespace, e.g. 03 `/mpac/sdicks02/jobs/clasher/k4s-confirm-end-r1/{runtime,bundle,guard-job,attempts}` and 04 `/mpac/sdicks02/jobs-k4s/k4s-confirm-end-r1/{…}`.
- `runtime` = an immutable export of one commit at or after `133f3ae4`. The END-JOB commit is the natural choice.
- `--repository` = a separate git clone fast-forwarded to the HEAD that holds the END-JOB. `producer_claim` writes claim files into that working tree (`end_evidence.py:513`; END-RUNBOOK.md:93-96, :110-113).
- Run `end_reference.py` *from the runtime tree*. `ROOT = HERE.parents[2]` decides which e4v3 gets imported (`end_reference.py:56-57, :285-286`), so the executing tree, `--runtime-root` and the bundle's `measurement_files` must all agree.
- The bundle comes from a **new, reviewed K4S assembler**. It would wrap `prepare_bundle.py`, or re-pin T1's reviewed base manifest, then write the K4S `reference_load_profile` described above.

### 1.4 END evidence (`clasher.k4s.end-evidence.v1`) and the END-JOB

**Evidence document** (`end_evidence.py:162-232`; END-RUNBOOK.md:37-59). Top level: `schema`, `kind = "counted-reporting"`, `plan`, `completion`, `blind_ledger`, `counted_inventory`, and `phases[]`. Each phase entry has `host`, `phase`, `launch`, `supervisor_exit`, `mhz` and `census`.

**Every artifact item** is `{path, sha256, commit (40-hex), repository_path}`:
- `path` is relative to the evidence file, and `..` is forbidden (`fleet_end.py:13-17`).
- The bytes at `path` must equal `git show commit:repository_path`, and `commit` must be an ancestor of HEAD (`fleet_end.py:20-34`).
- **Layout consequence:** the evidence file must sit above every artifact. Either it sits at the repo level, e.g. `reports/explore/k4s-confirm/end-evidence.json` with `path` = repository subpath, or it sits in the bundle with copies at the same relative paths (T1 precedent: `end-evidence.json` plus `end-sources/<host>/<phase>/…` in bundle `files`, per `END-A3-manifest-01-f6cebbaa.json`).
- **It must not sit under `reports/explore/k4s-confirm/end/`**, because that namespace is strict (END-RUNBOOK.md:83-89, :186-191). **Inference** for the name: `end-evidence.json` does not match `JOB_LIKE` / `FINAL_LIKE` (`end_evidence.py:301-302`).

**Status of each input:**

| Item | Committed? | SHA / commit | Status |
|---|---|---|---|
| plan | yes | `plan.json` 38064dcd (201db04c; same bytes at 391d2006) | OK; `study == "PREREG-K4S"` |
| completion | yes | `run-r1/completion/REPORTING-COMPLETION.json` `ed7d11b7…` (bb7c7f88) | fields OK (`reporting_complete`, `outcomes_sealed`, 3000/900, `counted_host_phases` {03, 04: reporting, replacement-r1..r4}, `completed_at_utc` 2026-10-12T14:45:34Z), **but it binds the B1 inventory** |
| blind_ledger | yes | `run-r1/ledger/blind-ledger-final.json` `649272bd…` (= `blind-ledger-r4.json`) | keys `{utc, sealed, events}`, 99 events with keys exactly `{utc, lost, replacement, reason, evidence_sha256}`; the evidence SHAs are the 8 failure-bearing supervisor-exit SHAs. OK |
| counted_inventory | yes | `completion/counted-inventory.json` `f10ab943…` | **B1: wrong schema and keys for `end_evidence.counting`** |
| phases[].launch | yes, all 10 | `run-r1/phase-meta/<host>-<phase>/launch.json`. 03: reporting 116f1ed5, r1 b864703e, r2 1d917968, r3 6c49a667, r4 e8f72fb4. 04: reporting 7cd6b140, r1 420f7ec1, r2 ea88e4d5, r3 9cd6bc37, r4 38730d44 | OK (host, phase `reporting`/`replacement`, slots 11) |
| phases[].supervisor_exit | yes, all 10 | same directories. 03: 88debddf, bffde5d4, 834fc247, cccb8683, c9066d63. 04: c0a935f6, c11ae500, 37aafa6a, 91475244, 21269aa0 | All equal the completion's `supervisor_exits` SHAs. OK |
| phases[].mhz, census | **no** | on the hosts only | **B2** |

**Where `mhz.jsonl` and `census.jsonl` are**
- `supervise.py` appends both, once per loop iteration, to `out = <phase job>/<phase>[-<attempt>]/` (`supervise.py:47, :109-116`).
- K4S ran each phase in its own job directory: `k4s-confirm-reporting-r1` and `k4s-confirm-replacement-r1..r4` under each host's jobs root (runner PROGRESS.md:148 and others).
- So the files should be at `<jobs root>/k4s-confirm-<phase job>/<phase>/{mhz,census}.jsonl`. **Inference:** this layout is not verified; it needs an on-host name listing.
- The local `phase-meta/` copies hold only `launch.json`, `stop-reason.json`, `supervisor-exit.json`, `descriptors/`, `exits/` and `pids/`.
- **Format check (from code):**
  - census rows carry `utc`, `host` and `inflight`, plus health-only counters;
  - mhz rows carry `utc`, `slots` and `physical_core_mhz` for `physical_cpus[:5*slots]`, which is all 55 slot CPUs;
  - `fleet_end.host_reporting` requires a one-to-one utc join and at least 2 full-occupancy rows with `inflight == slots` (`fleet_end.py:189-222`);
  - `compare_mhz` requires all occupied CPUs (`fleet_profile.py:48-58`).
- These are health files, but they sit **next to block folders that hold `complete.json` and game files**. A copier must fetch exactly those two names by full path, never by glob or recursive copy (§8).
- **Size (inference):** T1 committed its raw phase sources under `reports/explore/t1/receipts/END-raw-phases-20261011/<host>/<phase>/` at up to 27.8 MB per file. K4S replacement-r1 ran about 10 h per host, so its `mhz.jsonl` may be 40–60 MB. That is under GitHub's 100 MB per-file limit, but large.

**END-JOB** (`clasher.k4s.end-job.v1`; `end_evidence.py:287-307, :415-432`; END-RUNBOOK.md:75-82, :159-162):
- Exactly these fields: `schema`, `study = "PREREG-K4S"`, `end_evidence_sha256`, `completion_sha256`, `plan_sha256`, `counted_hosts`, `k4s_manifest_sha256`, `declared_utc`, `declared_by`.
- Field values:
  - `counted_hosts` must equal the evidence's sorted counted hosts, which is `["127x03","127x04"]` (`end_evidence.py:228, :425-427`);
  - `k4s_manifest_sha256` must be `74314eda…` (`:428`; A3 §7);
  - `completion_sha256` is the corrected completion's SHA if B1 is fixed by re-issue;
  - `plan_sha256 = 38064dcd…`.
- Path: exactly `reports/explore/k4s-confirm/end/END-JOB.json`. Add it in **one commit, alone**, before the first attempt, and never change it.
- No other `END-JOB*.json` may exist anywhere under `reports/explore/k4s-confirm/` (`end_evidence.py:385-394`).
- Push it, and every counted host's `--repository` must contain it at HEAD.
- **Order matters:** the END-JOB binds `end_evidence_sha256`. So the evidence, B2's committed sources and the B1 fix must all be committed **before** the END-JOB.

---

## 2. Wrapper and verifier

**The K4S END-RUNBOOK specifies no launch wrapper, detacher, copier or post-exit verifier.**
- It gives the bare `nice -n 10 python -B end_reference.py …` command (END-RUNBOOK.md:116-125) and the operator order (`:158-191`).
- Its only independent check is the pool `recheck` (`:242-249`). That is built into `end_pool.py` (`:589-651`), with `checked_by != pooled_by` enforced at `:596`.

**What T1 used** (T1 sweep §1; SHAs on origin/main):

| Tool | SHA | Role | Reuse for K4S |
|---|---|---|---|
| `detach.sh` | 1648dfdc (frozen in FROZEN-T1) | `setsid -f`, stdin closed, PID/PGID receipt | **Reuse unchanged.** It is generic. T1 staged it as `END-frozen-detach-aeeb3003.sh` |
| `end_exit_push.sh` | 0a87166f (Sol r3 approved; frozen for the campaign, COORDINATOR.md:2200) | Runs the command once in the foreground with no trap, poll or network. After exit it writes `exit.json` and pushes metadata and the measurement to 05 with bounded rsync (1200 s) | **Narrow K4S variant.** Hard-coded values to change: `base`, which needs per-host values (03 `/mpac/sdicks02/jobs/clasher/…`, 04 `/mpac/sdicks02/jobs-k4s/…`); hosts `127x01\|127x08` → `127x03\|127x04`; the attempt-root parent pattern; the receive base on 05; `--output` → `--out`. Its argv check looks for `--output` (`:21-33`), and `end_reference.py` uses `--out`. |
| `end_verify_push.py` | 753722c9 (Sol r5 approved with conditions C-a to C-d, COORDINATOR.md:2213-2231) | 05-only, outcome-blind: prepare an empty receive directory, then verify seal and hashes and write `DURABLE-ACK.json` | **Narrow K4S variant**: change `BASE`, the host tuple, and the wrapper-SHA literal (`:21, :26, :77`). It checks a T1 E4 seal layout, so check its seal reader against `K4SStore`'s `receipt-manifest.json` / `.sha256` (`end_evidence.py:240-258`). **Inference:** not verified line by line. |
| `end_owned_copier.py` | ecf4ad62 (REQUEST_CHANGES; withdrawn, COORDINATOR.md:2177) | in-run polling copier | **Do not reuse.** Polling a timed host breaks C5 and risks OP-6 SSH budgets, and on 04 it risks the DBus burst |
| `check_reference.py` | c848baa2 | re-runs E4 TIERS pooling | **Not applicable.** `end_pool.py recheck` is the K4S counterpart (r3 §4.5 item 2, "T1 `check_reference.py` pattern") |
| `release_reference.py`, `prepare_release_descendant.py` | f8b61c60, dd644cdc | T1 release barrier / Mac route | Not applicable; TIERS/T1-specific (hosts, 2400/600, tiers) |

**Recommendation:** reuse the T1 *pattern*:
1. detached launch, with the launch SSH closed before admission;
2. exit-push to 05;
3. verify on 05 no earlier than exit + 1300 s;
4. no observation SSH during timing.

Use `detach.sh` unchanged. Write minimal K4S deltas of `end_exit_push.sh` and `end_verify_push.py` that change only constants and argv names, and keep the diff small enough to review line by line.

**What needs Sol review** (memory rule: host-touching scripts are reviewed *before* running, even read-only):
1. the K4S exit-push wrapper delta and the verifier delta;
2. the fleet-reference bundle assembler (§1.3);
3. the END guard-job construction, including which admissions are copied or pinned (§1.6);
4. the B1 inventory re-emitter and the corrected completion;
5. the B2 two-file copier (host-touching);
6. the END evidence builder;
7. the launch-preparation and prelaunch-check script (quiet-read v3 reuse is fine; it is already approved).

The END-JOB document is data only. It can go to the coordinator without Sol, but a quick Sol pass is cheap.

---

## 3. Attempt roots

**T1** (T1 sweep §2):
- **Declaration:** `reports/explore/t1/receipts/reference-attempt-roots-0108.json` (3c811584, 2026-10-10T18:47:28Z; COORDINATOR.md:1879). Its A5 re-declaration is `reference-attempt-roots-0108-a5.json` (4ff93a10). Both were committed **and pushed** before the first A5 launch (`END-A5-roots-push-time-receipt.json`).
- **Enforcement:** `release_reference.py:120-137` checks that the roots commit time is ≤ each attempt's identity UTC, and that the host-root children equal the descriptor's attempts.
- **PC1** (`RELEASE-PRODUCTION-CHECKS-20261010.md:5`): "every original reference attempt: cross-check the descriptor against all detached launch/coordinator dispatch receipts, original measuring-host attempt-root listings, and the actual origin push time of the root declaration…"
- **RF1** (`receipts/END-RF1-verbatim-536bf5bd.md:10`): a pre-identity refusal is exempt only if its file set is exactly `{failure.json}` and the traceback ends before `fleet_reference.py:97`.
- **RG2** (COORDINATOR.md:2440-2455): a new roots declaration before the first fixed-code launch, and every old-code attempt disclosed and never pooled.

**K4S equivalent: built in and mechanical.** No separate roots file is required by the code.
- The single committed END-JOB, plus per-run claims `end/registry/round-RR/<host>/attempt-NN.json` (`clasher.k4s.end-attempt-claim.v2`). Claims are created exclusively, numbered contiguously from 00, before the receipt directory exists, and carry the `receipt_directory` name and launch UTC (END-RUNBOOK.md:93-104; `CLAIM_FIELDS`, `end_evidence.py:308-309`).
- `END-FINAL-round-RR.json` is committed after the round, in a later commit than every claim it lists (`:105-113`).
- The pool refuses an omitted or reordered attempt and refuses more than two attempts (`:215-218`).
- **Unlike T1's RF1:** "a precondition refusal before the claim (bad pin, wrong host, no END-JOB) is not an attempt" (`:103-104`). A failure *after* the claim, such as a guard-admission error, **is** an attempt.

**Proposal (inference), for PC1 parity and host-side hygiene:**
- Fix one on-host attempt parent per host *before* the END-JOB, e.g. `<END namespace>/attempts/`, and record it in the coordinator ruling or a small receipt.
- Use `--out <parent>/end-<host>-r<RR>-a<NN>`.
- The runbook's `$JOB/end/raw-$HOST-$RR-$N` (`:124`) is fine if `$JOB` means the END namespace. Avoid any on-host directory named `end/` inside a git checkout used as `--repository`, because it could be confused with `END_DIR`.

---

## 4. Launch conditions

**C5 (no SSH)**
- `END-exit-push-REVIEW-r2.md:157`: "**C5 (F10).** For each timing window, the coordinator confirms that no thread SSHes into the timed host. That includes T1's own END timer, health probes and mirror."
- COORDINATOR.md:2180: "**no SSH into a timed host from any thread during its window**, including T1's own probes."
- COORDINATOR.md:2295: "**C5 applies per timed host.** No SSH into a host while its reference is timing. Finish all of a host's prep SSH before that host launches. SSH to the other, untimed host is allowed."
- COORDINATOR.md:2230 (C-d): "verify no earlier than `exit_utc` + 1300 s (the wrapper's maximum lifetime). C5 holds until then…"

**C5 pre-exec gate** (COORDINATOR.md:2367): "In the exec shell: parent nice is 0, the scheduler is SCHED_OTHER, and the argv is byte-identical with no outer prefix (the frozen inner `nice -n 10 taskset` is unchanged). Afterwards, record wrapper and E4 nice = 10."
- The RF1 item 2 lesson: the launch SSH must not be wrapped in `nice`/`taskset` (COORDINATOR.md:2320-2321).
- K4S END inherits the plan's nice 10 (`plan.json` `compute.nice = 10`, scheduler SCHED_OTHER). `fleet_profile.slot_layout` refuses any other nice (`fleet_profile.py:13-14`), and so does `end_background` for Linux SCHED_OTHER (`end_background.py:84`).

**Launching SSH**
- `A6-END-RUNBOOK.md:65-67` and `FLEET-END-CONTRACT.md:192-194`: "The launching SSH must close before admission… ordinary SSH inspections during timing violate the guard."
- T1 used `ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes <host> "<python> -B -"`, recording `C5_no_further_SSH: true` (`END-A5-reference-launch-receipt-01-r1.json`).
- **The fleet `~/.ssh/config` uses ControlMaster** (CLAUDE.md fleet notes). Any lingering master to 03/04 must be closed before launch. RG1 (COORDINATOR.md:2404, :2557): "no SSH or ControlMaster session open … at admission".

**Gates inside the code** (all fail closed):
- **Before the claim:** bundle, native, corpus, manifest and source pins; executing bytes; END evidence; END-JOB; namespace; open round (`end_reference.py:289-310`).
- **After the claim:** a guard admission at `checkpoint("admit")` before loading workers (`:364-366`).
- **During the attempt:** the guard checks every 1 Hz sample and every 50-state block (`fleet_validity.py:135-228`), plus the background slot health check.
- **Validation at the end:** census, admission, blocks, and the MHz gate at 5% (`:395-403`).
- **Guard stop and fail reasons:**
  - owned STOP, console user, MemAvailable < 24 GiB;
  - foreign compute or foreign active process;
  - OP-6 SSH budgets;
  - `op1_interference`: bus or idle above 1% over a block or cumulatively, or a retired pin (`fleet_validity.py:186-193, :218-226`). The 1% rule is in the T1 `system_bus.finish`, `ticks*100 > hz*elapsed` (`reports/explore/t1/system_bus.py:30`).

**Pre-launch checks from earlier rounds** (operator duties, not code):
- **Quiet-read v3** (`run-r1/rounds/r4/quiet-read-v3.cmd`): both apt units inactive, no maintenance processes, `who = 0`. Take **two consecutive reads 30 s apart** (COORDINATOR.md:2767-2772). v3 adds `apt-config` and `apt.systemd.dai` (COORDINATOR.md:3015).
- **C2** (COORDINATOR.md:2061): read `systemctl list-timers`, and launch only with **≥ 2 h** of timer clearance.
- **C2 extension** (COORDINATOR.md:2114): read the ages of `/var/lib/ubuntu-release-upgrader/release-upgrade-available` and `/var/lib/update-notifier/updates-available`. If a stamp is stale, let one ordinary login trigger the check **before** launch and wait for it to exit.
  - This is the exact failure that hit K4S 04 at 21:32:49Z on 10-11: a root `check-new-release` counted as `foreign_compute` (COORDINATOR.md:2112).
- **Copier off.** The OA-1 copiers finished at 14:44:54Z and are revoked, with STOP-COPY removed (runner PROGRESS.md, 14:44:10Z entry). No copier may run against a timed host. The B2 copy and every prep SSH must finish before launch.
- **Idle services on 03.** The plan's idle-service exception covers 03, and the frozen pin is perception v4 validation cache service PID 2180947. It was still present at the r4 admission at 14:04Z (`rounds/r4/evidence/step7/127x03-host-admission.json`). The END guard job on 03 must pin the same `idle-services.json`, or the guard will fail on "Every existing guard admission must be pinned" or on foreign compute (`fleet_validity.py:112-114`). If that service exits during END, idle `retired` fails the attempt (`fleet_validity.py:242-243`).
- **No other thread on 03 or 04** during a window. Perception's B exports used 03/04 as late as 14:03Z (COORDINATOR.md:3219-3247). The coordinator must confirm C5 across threads.

---

## 5. Schedule

**How long an attempt takes**
- PREREG r3 budgets "END reference: ≈ 2–3 h" in total (`PREREG-K4S-DRAFT-r3.md:78, :703`).
- T1's A5 references, which have the same lifecycle (≥300 s warm-up, 3 repeats, spawned background), ran 01 06:26:27→07:20:20Z (53 m 53 s) and 08 06:16:32→07:11:09Z (54 m 37 s). After that came a C-d wait of 1300 s (`END-A5-reference-launch-receipt-*-r1.json`, `END-A5-reference-approved-verification-*-r1.json`; T1 duration basis 3358 s).
- **Inference:** K4S runs (a) K4 + K4S at 2 × 300 × 3 units, then (b) 5 cells × 300 × 3 deadline runs at ≤ 200 ms, plus the 1/c charge. Its per-attempt wall time is probably 45–90 min. Plan for **≤ 1.5 h + 22 min C-d per attempt**, which fits inside C2's 2 h clearance.

**Timers** (read at 2026-10-12T14:04Z, `rounds/r4/evidence/step6/127x0{3,4}-stamps-timers.txt`; PDT converted to UTC):

| | 03 | 04 |
|---|---|---|
| apt-daily | **2026-10-12T20:36:30Z** | 2026-10-13T00:25:02Z |
| motd-news | 2026-10-13T01:35:47Z | 2026-10-13T02:15:31Z |
| apt-daily-upgrade | 2026-10-13T13:33:52Z | 2026-10-13T13:55:31Z |
| release-upgrade stamp turns 24 h old | 2026-10-13T00:57:44Z | **2026-10-12T21:32:48Z** |

apt-daily re-randomizes after each run. **Re-read the timers after every run.** The next apt-daily times after these are not knowable now.

**Windows.** Latest launch = next timer − 2 h (C2).
- **W1, today:** 03 launch ≤ 18:36Z; 04 launch ≤ 22:25Z.
  - **Inference:** probably infeasible. B1–B3, the wrapper and assembler reviews, the B2 copy and commit, the END-JOB commit and host staging all have to land first.
- **W2, tonight:**
  - 03: after the 20:36Z apt-daily has finished and a fresh timer read, roughly 20:50Z to launch ≤ 23:35Z (motd-news 01:35Z). Also bounded by any newly scheduled apt-daily.
  - 04: launch ≤ 22:25Z. After 21:32:48Z, pre-trigger the stale release-upgrade check with one ordinary login and wait for it to exit (C2 extension).
  - Overlap for both hosts: about 20:50–22:25Z.
- **W3, overnight into 10-13:**
  - 03: about 01:45Z (after motd-news) to launch ≤ 11:33Z. A login after 00:57:44Z needs the stamp pre-trigger.
  - 04: about 02:25Z to launch ≤ 11:55Z.
  - Both are subject to the re-randomized apt-daily, which must be re-read. **This is the most realistic window** (inference).

**Which host first: 03.**
- The hosts are independent, and C5 applies per host (COORDINATOR.md:2288-2295). Running them concurrently is allowed; T1 launched 01 and 08 ten minutes apart.
- **Why 03 first** (recommendation):
  1. 03's bus is clean, at 0 flagged blocks of 1,969.
  2. Any shared configuration error in the bundle, the guard job or the wrapper then costs only 03's single technical repeat. A failure after the claim is an attempt, and each host gets at most 2 attempts per round (END-RUNBOOK.md:217-218).
  3. 04 can launch after 03's exit + C-d + verification shows a `complete` seal, or after the R4 final result if that comes later.
- Running them in sequence costs about 2 h of wall time. That fits inside W3.

---

## 6. DBus branch (R4; COORDINATOR.md:3264-3268)

**Interim baseline:** `end-gate/04-dbus-baseline-r1/`, launched 2026-10-12T14:45:19.8Z, ending about 15:15Z. It uses one long-lived SSH at nice 19 and reads `/proc/2005/stat` once a second.

At 870 s:

| Measure | Value |
|---|---|
| whole window | 0.0345% of a core |
| 30 s windows | p50 0.033%, max 0.066% |
| 60 s windows | max 0.066% |
| 300 s windows | max 0.040% |
| windows above 0.7% | 0 |
| PID / start_ticks | 2005 / 1032, unchanged |
| uid-125 (GDM) processes | 45 |

Source: `analyze.py` output, samples sha `300fc533…`. The investigation had a lifetime average of 0.47% and 1.03–1.12% in first waves with copier listing (`K4S-DBUS-FLAG-INVESTIGATION-r1.md:104, :123-124`).

**Inference:** one copier SSH login costs very roughly 0.1 s of bus CPU on 04, given about 1% extra at one listing login per 10 s. The greeter amplifies logins; it is not itself a load above 1%.

**Mapping outcomes to options**

| Final R4 result | Branch | What it needs |
|---|---|---|
| **Clearly below 1%.** Investigation criterion: every window ≤ 0.7% (`:196`). The interim is about 10× under that. | **Proceed as frozen.** No amendment. | (1) Commit the R4 result as an outcome-blind disclosure: samples SHA, analysis output, conditions (no copier, no load, one session). (2) Operational conditions on 04: exactly one launch SSH, closed before admission; no other login to 04 from any thread until exit + C-d; no ControlMaster; `who = 0` at both quiet reads. **Reason (inference):** at about 0.1 s of bus CPU per login, two logins inside a 30–60 s guard block could reach 0.3–0.7%. The cumulative meter starts at admission (`fleet_validity.py:153-155`), so the launch session's close should land mostly before it. (3) Keep (c) as a written fallback. |
| **At or near 1%**, or any 30–60 s window > 0.7% | **(a)** Sam or a lab admin stops GDM on 04 for the window | Root action by Sam or an admin; we have no root and must not touch gdm (`:198`). Then re-run the R4 baseline after GDM stops. **Risk:** if the admin *reboots* instead, the dbus PID/start changes. The END guard then refuses, because the system-bus admission must be an existing exact pin, with "no refresh" (`fleet_validity.py:110-111`; `FLEET-END-CONTRACT.md:94-96`). That would need a coordinator ruling on a new admission. |
| (a) not possible | **(b)** Reviewed outcome-blind amendment with a 04-relative OP-1 threshold | Heavy. The threshold lives in the frozen T1 `system_bus.finish` and `fleet_validity` (`:186-193, :218-226`). Changing it means K4S-owned guard bytes, which no longer match the "final reviewed frozen T1 source" (`fleet_validity.py:64-70`). That needs a K4S amendment, a manifest re-pin, tests and a Sol review, all **before any attempt**. |
| Neither | **(c)** Declare the K4S Mac ratio unavailable in advance | r3 §4.5 (`:665-667`): the tier becomes Mac-infeasible for deployment; fleet-claim outcomes stay releasable. Release item 2 becomes `ratio_unavailable_declaration` (`barrier.py:34-38`; K4S-SPEC.md:328-332). |

**Rule to state explicitly to the coordinator:** two technical failures on a host in round 00 leave no nonconforming pool. In that case "no later round can claim or pool" (END-RUNBOOK.md:176-185), so the ratio is unavailable unless an amendment is adopted. In practice 04 gets **two OP-1 strikes in total**. That is why the R4 decision has to be firm before the first 04 launch.

---

## 7. Ordering, prerequisites and authorizations

**Who authorizes what**
- **C** = coordinator, thread `0523ae6f-baa3-4d4e-b233-b392671670db`.
- **Sol** = code review.
- **S/A** = Sam or a lab admin.

| # | Step | Gate / evidence | Authorizes |
|---|---|---|---|
| 0 | R4 final result + DBus branch ruling (§6) | committed disclosure | C (S/A for (a); C + Sol for (b)) |
| 1 | B1 ruling + fix: re-emit the inventory as `{schema: clasher.t1.counted-blocks.v1, outcomes_sealed: true, blocks: <same 3,900 rows>}` and a corrected completion receipt that binds it | Sol review of the re-emitter; a byte-check that rows are unchanged; commit | C + Sol |
| 2 | B2: narrow copy of the 20 files (`{mhz,census}.jsonl` × 10 phases) from 03/04, by exact path only; commit outside `end/` | script reviewed **before** running (memory rule); `clasher-secret-scan`; commit | C (host access + script) + Sol |
| 3 | B3a: END guard-job namespace per host (FROZEN-T1 24817e16 copy, system-bus admission copy, 03 idle-services pin, T1 seed inputs under `repo/`); B3b: reviewed fleet-reference bundle assembler; bundles built from one runtime export at or after 133f3ae4 | Sol review; offline preflight outside the attempt roots (C3, COORDINATOR.md:2062) | C + Sol |
| 4 | END evidence document (`clasher.k4s.end-evidence.v1`) built and committed; dry validation with `end_evidence.end_evidence(...)` offline on 05 | commit | C |
| 5 | K4S exit-push wrapper and verifier deltas | Sol | C + Sol |
| 6 | **END-JOB** commit (alone, scanned, pushed); hosts' `--repository` fast-forwarded | END-RUNBOOK.md:159-162 | C |
| 7 | Window declaration per host + C5 confirmation across threads + quiet-read v3 ×2 + timers/stamps + `who` | prelaunch receipt | C |
| 8 | Round 00: 03 attempt, then 04 (§5); exit-push; verify at ≥ exit + 1300 s | launch and verification receipts | C (GO per launch) |
| 9 | Collect every host's `end/registry/round-00/<host>/` claims unchanged → commit; **then** in a later commit `END-FINAL-round-00.json` | END-RUNBOOK.md:165-168 | C |
| 10 | Pool: `end_pool.py pool --pool-input D …` (descriptor `clasher.k4s.end-pool-input.v3`, `k4s_manifest.sha256 = 74314eda…`) | END-RUNBOOK.md:194-237 | pooled_by = K4S runner |
| 11 | Independent recheck: `end_pool.py recheck … --checked-by WHO`, where WHO ≠ `pooled_by` (`end_pool.py:596`); same interpreter (PC3) | `clasher.k4s.end-recheck.v1` | an independent verifier, not the pooler |
| 12 | Nonconforming → commit the pool at `end/pools/round-00` + every round-00 receipt directory, then round 01 (END-RUNBOOK.md:169-185). Unrepeatable failure → C declares the ratio unavailable | — | C |
| 13 | Commit the pool + recheck. These become the Mac `--fleet-reference` / `--fleet-recheck` inputs (END-RUNBOOK.md:250-252) | commit | C |
| 14 | **K4S Mac phase C** (manifest 74314eda) after the TIERS Mac session (COORDINATOR.md:3291) | P12 requires the pooled reference on the same frozen END identity (`K4S-MAC-PROCEDURE.md:67`). If the TIERS session has ended or more than 2 h have passed, it runs **standalone** (§5.2, `:207-214`) with a coordinator authorization file `clasher.k4s.mac-standalone-authorization.v1` (`:71-72`) | Sam (replay authorization, P1) + C |
| 15 | PC1–PC4 production checks (r3 §4.5 item 3): all original attempt roots, i.e. registry + finalizations + on-host attempt listings; the reviewed E4 source inventory; one pinned interpreter; the interference-sensitivity sidecar over the final counted inventory and blind ledger | Note: PC4 consumes the counted inventory, so align it with the B1 decision | C (independent check) |
| 16 | **Release:** coordinator-signed receipt (`barrier.outcome_release`, `barrier.py:20-42`) | Required items: `completion`, `production_checks`, `verifier_receipt` (independent verifier, author ≠ reducer author), `mac_procedure_manifest`; plus `end_reference` + `end_recheck` **or** `ratio_unavailable_declaration`; plus `tiers_summary` or `tiers_release`. Each must be committed and hash-equal at the receipt commit (K4S-SPEC.md:321-338). Release is **not** gated on the K4S Mac summary (r3 §4.5, `:682-685`). | C (explicit GO; "No automatic release", r3 `:687`) |

---

## 8. Open questions and risks for the coordinator

1. **B1: how to fix the counted-inventory format.**
   - Option (i): a corrected completion receipt (r2) plus a t1-format inventory, committed before the END-JOB. Item 1 of the release receipt would then name the corrected completion.
   - Option (ii): an amendment that changes `end_evidence.py`. Heavy, and the file is a frozen END source pinned by 74314eda.
   - Option (i) looks right (inference). **Still to check:** whether any other consumer reads `f10ab943` in its current schema, such as `verify_k4s`, the PC4 sidecar or `reduce`. I did not open those outputs.
2. **B2 copy safety.** The 20 telemetry files share directories with block folders. The copier must name exact paths and run outside any timing window. It touches 03, which holds T1's read-only corpus copy, and 04, which holds perception storage, so it must not use globs. **Size:** possibly 40–60 MB for each replacement-r1 `mhz.jsonl` (inference). Decide whether to commit them in full, as T1 did, or in git-lfs. LFS is not tested with `fleet_end.artifact`'s `git show` byte check, so **full blobs are recommended**.
3. **B3 guard config details.**
   - The END guard is T1's freeze and modules (24817e16). Ruling needed: are T1's OP-5 seed dependencies acceptable on hosts 03 and 04? Those are the 03 parent-source receipt (167cbe71) and the 08 receipt (7081bb44) with its 08-server/04-client join. **Inference:** for sources that no longer exist, `admit` returns no seed. Not verified.
   - Which K4S job's `system-bus-admission.json` does each host's END guard job copy? Its pinned identity must still match: 04 PID 2005 / start_ticks 1032 per the R4 probe. Confirm against the committed admission.
   - Should 03's `idle-services.json` (PID 2180947) be pinned? I recommend yes; it matches reporting.
4. **Runtime tree.** Which commit? It must be at or after 133f3ae4. Should it be the END-JOB commit itself? The same export must go to both hosts, so that `runtime_files` and `measurement_files` canonical SHAs are equal.
5. **Interpreter.** T1 used `/mpac/sdicks02/repos/clasher/.venv/bin/python` 3.12.13 on its hosts and `e4v3-venv` 3.12.12 on 05 for the pool. Does that venv exist on 03 and 04 with torch and the runtime dependencies? I could not check this read-only. PC3 requires one pinned interpreter for the pool and the recheck.
6. **States and sets for the bundle.** Should K4S reuse T1's `states.pkl` 0addf7c0, `states-rows.{json,bin}` bcd30777/8cc2f611 and own-tier300 `sets` (inference: yes)? That needs an authorized read-only copy from T1 storage, as was done for the corpus.
7. **04 login hygiene during END.** One extra login inside a guard block can matter at about 0.1 s of bus CPU per login (inference). This needs a C5 broadcast to every thread, including perception and roader. Also close the Mac-side ControlMaster for 127x0{3,4}.
8. **The 04 release-upgrade stamp** expires at 21:32:48Z today. Any launch after that needs a pre-trigger login and a wait for `check-new-release` to exit. 03's stamp expires at 00:57:44Z on 10-13.
9. **The disclosure narrative may need an addendum.** The interim R4 data suggests the reporting-time ~1.47% came mostly from copier SSH logins amplified by GDM clients, not from GDM alone. That contradicts the investigation's "04 is already near or above 1% without that traffic" (`:133`). It doesn't affect the frozen classification, but the R2 disclosure may deserve a factual addendum after R4 finishes (inference).
10. **Two strikes per host, per END job.** A second technical failure on either host makes the ratio unavailable without an amendment (§6). Consider an offline dry-run of the full producer path on 05 before any claim:
    - Use a scratch git repo and a fake END-JOB, never under `reports/explore/k4s-confirm/end/` on origin.
    - That catches bundle and evidence errors before they become attempts. Precondition refusals before the claim are not attempts (END-RUNBOOK.md:103-104), but on-host config errors after the claim are.
11. **TIERS Mac timing.** The K4S Mac P12 needs the pooled END. The TIERS session is already in its final stage (991f8e5f), so K4S phase C will almost certainly be **standalone**. That needs a Sam replay authorization and a coordinator authorization file (`K4S-MAC-PROCEDURE.md:56-60, :71-72`).
12. **Hosts reserved.** 03 and 04 stay reserved for K4S END (COORDINATOR.md:3294). Every host action in steps 2–8 needs an explicit coordinator window. This document authorizes nothing.

---

*End of draft. No host was touched and no commit was made while writing it. Only one file was written: this one.*
