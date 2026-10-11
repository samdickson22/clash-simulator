# PREREG-K4S END reference runbook (r3 §4.5 (a)–(c); delta 8)

**Status:** r3 (fixes for the SOL re-review r2 findings 10–17), written and logic-tested (`test_end_reference.py`,
`test_end_background.py`). **Not executed.**
- The frozen T1 K4 speed corpus (`K4-states.pkl`, sha256
  `a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8`, T1 inventory `81f2483e`) is stored only under
  T1 job directories (`t1-20261010-r1/corpus-reviewed-03-r1/built-corpora` on 03 and
  `corpus-publication-staging-r1` on 05). The prep worker may not read those directories.
- The coordinator must authorise one SHA-verified, read-only copy into the K4S job before END.
- END runs only after the committed K4S reporting-completion receipt. Without the committed END evidence below,
  the producer, every background slot and the pooler fail closed.

## Inputs (all SHA-bound; nothing is chosen at END time)
1. **TIERS fleet-reference bundle** per host (`tiers-pins.json` schema `clasher.e4v3.inputs.v1`, `profile =
   fleet-reference`). Before the backend is constructed or any pickle runs, `end_reference.py` calls the frozen
   `tier_backend.validate_bundle(..., dry_run=True, require_references=False)` (bundle, runtime and measurement
   pins), checks the qualified native `44874fd6…`, and requires in `reference_load_profile`:
   `host` (this host), `reference_slot = 0`, `slot_count`, `console_rule`, `warmup_seconds >= 300`,
   `perception = none`, `plan` (a bundle-pinned copy of the **committed K4S** `plan.json`), `end_evidence` (a
   bundle-pinned copy of the K4S END evidence below; its SHA must equal `--end-evidence-sha256`) and `guard` (the
   frozen T1 OP-1…OP-6 reporting guard configuration for the K4S job, as in TIERS `FLEET-END-CONTRACT.md`).
   The bundle also pins `v1.pt`, `R3a.pt` (= SD1's bytes), `R3a-calibration.json` and `states.pkl`.
2. **Frozen K4S identity** (`end_reference.k4s_pins`, `executing_sources`): the frozen `mac/K4S-MAC-MANIFEST.json`
   (`--k4s-manifest-sha256`; `frozen = true`); kernel `sdefault.py` and scorer `anchor_x.py` equal to its
   `k4s_kernel.files` and to `DELTA-MANIFEST.json`; the scorer's normal form equal to the bundle's TIERS scorer pin;
   the SD1 manifest (`--sd1-manifest-sha256` = the manifest's) in its nested schema with every inference source;
   the corpus SHA; and every END measurement source (`k4s_logic.END_MEASUREMENT_FILES`: `end_reference.py`,
   `end_pool.py`, `end_background.py`, `end_evidence.py`, `mac/k4s_backend.py`, `mac/k4s_logic.py`) equal to its
   manifest pin, both under `--runtime-root` and **as actually executing**.
   - **Common pins** (`end-identity.json` / `end-raw.json` `pins`; equal on every host): the frozen keys
     (kernel, scorer, SD1, corpus, native, `k4s_manifest_sha256`, `measurement_files`) and the shared bundle keys
     (canonical SHAs of the bundle's `runtime_files` and `measurement_files`, and its model/state file pins).
   - **Host pins** (`host_pins`; per host, never compared across hosts): `bundle_manifest_sha256` (this host's
     `tiers-pins.json`, which names this host) and `bundle_profile_host`.
3. **Committed END evidence** `clasher.k4s.end-evidence.v1` (`--end-evidence`, `--end-evidence-sha256`,
   `--repository`). Paths are relative to the evidence file; every item is `{path, sha256, commit (40-hex),
   repository_path}` and is verified by the frozen `fleet_end.artifact` (byte equality with the committed blob, commit
   an ancestor of `HEAD`):
   - `plan`: the K4S `plan.json` (`study = PREREG-K4S`);
   - `completion`: `reporting_complete`, `outcomes_sealed`, `counted_primary_blocks = 3000`,
     `counted_guard_blocks = 900`, `completed_at_utc`, `counted_host_phases {host: [phase…]}` (phases
     `reporting` / `replacement-rN`, unique per host), `blind_ledger_sha256`, `counted_inventory_sha256`;
   - `blind_ledger` (`{utc, sealed = true, events}`, each event `{utc, lost, replacement, reason, evidence_sha256}`,
     as written by `replace.py`) and `counted_inventory` (`{schema = clasher.t1.counted-blocks.v1,
     outcomes_sealed = true, blocks}`, each block exactly `{host, phase, descriptor}`);
   - `phases[]`: per host/phase, the supervisor `launch.json` (`host`, `phase` = `reporting` or `replacement`,
     `slots`), `supervisor-exit.json` (`host`, `utc`, `completed`/`failed`/`unstarted` descriptors), the reporting
     `mhz.jsonl` rows (`utc`, `slots`, `physical_core_mhz [{cpu, mhz}]`) and `census.jsonl` rows (`utc`, `host`,
     `inflight`) — the raw `supervise.py` files, unmodified.
   - **Membership reconciliation** (`end_evidence.counting`, a port of the frozen `fleet_end.counting`): every
     counted descriptor appears verbatim in its phase's supervisor `completed` list; no lost block is counted; every
     `failed` block has a ledger loss whose `evidence_sha256` is that phase's supervisor-exit SHA and whose `lost`
     descriptor is the raw exit's; replacements keep population, cell and logical block, and a counted replacement
     equals its ledger bank descriptor (except host/dispatch); the logical `primary-0000…2999` / `guard-0000…0899`
     populations are complete; owners equal `counted_host_phases`. Health-only allow-lists reject any other field;
     the descriptor allow-list is the frozen one plus only the registered K4S fields `rotation`, `subsample`,
     `replacement_k`.
4. **Corpus:** `K4-states.pkl` at the SHA above and the T1 `corpora.json` (`--corpus-inventory`).
5. **END attempt registry** (`--attempt-registry REG`): before its receipt directory exists, every run claims
   `REG/<host>/attempt-NN.json` (exclusive creation, contiguous NN from 00, `clasher.k4s.end-attempt-claim.v1`:
   host, attempt, receipt directory name, launch UTC, pid, nonce). The receipt seals a copy (`attempt-claim.json`
   + its SHA, also in `end-identity.json`). Never delete or rewrite a claim; a precondition refusal before the claim
   (bad pin, wrong host) is not an attempt.

## Per host (every committed counted host; slot 0 is the reference slot)
Run at the reporting plan's priority (`nice 10`, SCHED_OTHER) on the fleet host:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python -B \
  reports/explore/k4s-confirm/end_reference.py --bundle B --runtime-root R --native N \
  --corpus K4-states.pkl --corpus-inventory corpora.json \
  --k4s-manifest-sha256 FROZEN_K4S_MANIFEST_SHA --sd1-manifest-sha256 FROZEN_SD1_SHA \
  --end-evidence E/end-evidence.json --end-evidence-sha256 S --repository R \
  --attempt-registry $JOB/end/attempts --out $JOB/end/raw-$HOST-$N
```

- Masks come only from the pinned plan (frozen `fleet_profile.slot_layout`): the reference on slot 0, census on the
  census CPU, and on **every other** reporting slot the frozen TIERS corpus loop through the K4S-owned adapter
  `end_background.K4SFleetBackground`. It subclasses the frozen `replay_load.FleetBackground` (spawn, readiness,
  `check`, error queue and close semantics unchanged) and runs the frozen `fleet_corpus_worker` work loop verbatim;
  only the worker's profile step differs: instead of the frozen `pinned_profile` → `fleet_end.evidence` (which
  accepts only the TIERS 2400/600 schema), each worker re-validates the bundle, the frozen K4S manifest and e4v3
  helper pins, the bundle-pinned K4S evidence (= the committed evidence, re-read from commits), the bundle plan =
  the committed plan, Linux SCHED_OTHER, `slot_layout`, `host_reporting`, and that its mask is a pinned background
  mask — before any work. `slot-evidence.json` records the affinity and priority read back from the reference and
  every background worker.
- The frozen `fleet_reference.reference_monitor` runs the T1 reporting guard at 1 Hz (`capacity.jsonl`, including
  per-processor MHz), the admission (`guard-admission.json`) and one checkpoint per 50-state work block
  (`guard-blocks.jsonl`: `warm-<lap>-<offset>`, `speed-<repeat>-<offset>`, `deadline-<repeat>-<cell>-<offset>`).
  A console user, SSH/dbus/idle interference or a flagged block fails the attempt (typed technical cause).
- ≥ 300 s all-slot warm-up, then 3 repeats: no-deadline K4 and K4S (exactness K4S == K4 on every state), then K4S
  at 200/180/160/140/120 ms with the 1/c poll charge.
- The reference 1 Hz MHz is compared with the committed **full-occupancy** reporting rows (frozen
  `fleet_end.host_reporting` + `fleet_profile.compare_mhz`); the signed ratio is kept in
  `reporting-mhz-comparison.json`; > 5% fails the attempt (`mhz_gate`).
- **Failure and cleanup** (`end_reference.run_attempt`): a failure writes `failure.json`
  (`fleet_technical_cause` only for the frozen `FleetTechnicalError`). Cleanup always runs and first sets the
  monitor's stop event, then joins/terminates it, closes both pipe ends and the backend. A cleanup exception writes
  `cleanup-failure.json`; if the measurement had succeeded it also writes a typed `crash` `failure.json`, so the seal
  is `failed`. An exactness failure is never masked by a cleanup failure. `end-complete.json`
  (`cleanup_succeeded = true`) is written only after cleanup succeeded, and only then is the seal `complete`.
- Output: one sealed directory (scope `K4S-END-REFERENCE`): `attempt-claim.json`, `end-identity.json`,
  `reporting-full-occupancy-mhz.json`, `slot-evidence.json`, `capacity.jsonl`, `guard-admission.json`,
  `guard-blocks.jsonl`, `reference-warmup.json`, `reporting-mhz-comparison.json`, `end-raw.json`
  (`clasher.k4s.end-reference-raw.v3`), `end-complete.json`; or `failure.json` (+ `cleanup-failure.json`).
  Keep **every** attempt directory. Do not add, edit or remove files after sealing.

## Pooling and recheck
- Collect every host's `REG/<host>/attempt-NN.json` into one repository directory, `clasher-secret-scan`, commit.
- Descriptor `clasher.k4s.end-pool-input.v2`: `pooled_by`, `k4s_manifest {path, sha256}` (the frozen manifest),
  `corpus_inventory {path, sha256}`, `end_evidence {path, sha256}`, `kernel_rel`, `scorer_rel`,
  `attempt_registry {commit (40-hex, ancestor of HEAD), repository_path}`, and `hosts [{host, attempts
  [{directory, manifest_sha256}…]}]`.
- `end_pool.py pool --pool-input D --pool-input-sha256 S --output NEW_POOL_DIR [--repository R]`:
  - the host list must equal the committed counted-host set (no exclusion after counting), and the committed
    registry must name exactly those hosts;
  - each host's attempt list must equal its committed registry entries **in order** (each receipt's sealed
    `attempt-claim.json` = the committed claim, same SHA and directory name): an omitted or reordered attempt is
    refused; more than two attempts (more than one repeat) are refused;
  - every attempt is read **only through its verified seal**: the directory must hold exactly the sealed files
    plus the seal and sidecar (an unsealed file is refused before the frozen classifier, which opens files
    directly, can read it); every consumed receipt, JSON or JSONL, is re-hashed from the bytes actually parsed;
  - seal status is reconciled with the receipts: `complete` requires every receipt above, `end-complete.json` with
    `cleanup_succeeded`, and no `failure.json`/`cleanup-failure.json`; `failed` requires `failure.json` and no
    `end-complete.json`; any other status is refused. Then the frozen `fleet_validity.classify_attempt`: only the
    last may pass; an earlier one must be a typed technical repeat candidate (exactness never earns a repeat);
  - each passing receipt is re-validated: common pins (exact key set; frozen keys = `end_frozen_pins` of the
    descriptor's frozen manifest, including its SHA and every END source; equal across hosts), per-host
    `host_pins` (own bundle SHA, profile host = host; retained in provenance), counted-host set and plan, slot masks
    and priority, the frozen guard validators, warm-up, the recorded full-occupancy rows, and the recomputed MHz
    comparison;
  - timing: exact 300-state inventory, exactly 3 finite positive timings per state and cell (a)/(c) series, each
    deadline (cell, state, repeat 0–2) exactly once with Boolean flags, registered budgets and charge scales;
  - host ratio: the frozen `fleet_pool.py` statistic and direction (geometric mean of pooled / host per-state
    medians) with K4S's **inclusive** [0.95, 1.05] (see below); otherwise the pool is sealed `nonconforming` and
    fails closed. Then re-run, or the coordinator declares the ratio unavailable (r3 §4.5);
  - every local file read is recorded in the sealed `pool-inputs.json`.
- **Ratio window vs TIERS.** r3 §4.5 says "[0.95, 1.05] inclusive"; K4S implements `0.95 <= r <= 1.05` on the
  nearest doubles. The frozen TIERS pool uses `abs(r-1) <= .05`, which rejects the exact doubles 0.95 and 1.05
  (both differences round above .05). The rules differ only at those two endpoint doubles; tests pin both
  endpoints and one ulp on each side for both forms. K4S does not change the TIERS rule.
- `end_pool.py recheck --pool-input D --pool-input-sha256 S --pool NEW_POOL_DIR --checked-by WHO --output R.json`
  reads the pool only through its seal, requires every `pool-inputs.json` entry to be in its own before/after input
  inventory (descriptor, descriptor-named files, the END evidence and every artifact it names, every file in every
  attempt directory) with the same SHA, re-executes pooling in a fresh `python -I`, compares every sealed byte,
  checks the inputs did not change, and writes `clasher.k4s.end-recheck.v1` binding the reference SHA, descriptor,
  END evidence, every host seal, the registry commit and the checker bytes. `WHO` must differ from `pooled_by`
  (T1 `check_reference.py` pattern).
- Commit the pool directory and the re-check receipt; they are the Mac script's `--fleet-reference` and
  `--fleet-recheck` inputs (`mac/K4S-MAC-PROCEDURE.md` §3). The Mac admits the reference only if its common pins
  equal `end_frozen_pins` of the Mac's own frozen K4S manifest (same manifest SHA and END source pins).
