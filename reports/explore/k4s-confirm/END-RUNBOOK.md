# PREREG-K4S END reference runbook (r3 §4.5 (a)–(c); delta 8)

**Status:** r5 (fixes for the SOL re-review r4: one END job at FIXED repository paths, a names-only END namespace
boundary, complete-bytes JSON parsing; r4: finalized append-only attempt inventory, re-run rounds), written and
logic-tested (`test_end_reference.py`, `test_end_background.py`).
**Not executed.**
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
5. **END job authority** (`end_evidence.py` part 3; r3 §4.5, PC1 "all original attempt roots"). PREREG-K4S has
   exactly one reporting completion, so there is exactly **one END job**, at fixed repository paths (module constants
   in `end_evidence.py`; never derived from the evidence, the completion's repository path or a pool descriptor;
   there is no `--attempt-registry` option):

   | What | Fixed repository path |
   |---|---|
   | END namespace (`END_DIR`) | `reports/explore/k4s-confirm/end/` |
   | END job (`END_JOB_PATH`) | `reports/explore/k4s-confirm/end/END-JOB.json` |
   | Claims (`REGISTRY_ROOT`) | `reports/explore/k4s-confirm/end/registry/round-RR/<host>/attempt-NN.json` |
   | Finalizations | `reports/explore/k4s-confirm/end/END-FINAL-round-RR.json` |
   | Earlier nonconforming pools (`POOLS_ROOT`) | `reports/explore/k4s-confirm/end/pools/round-RR/` |
   | Optional committed attempt receipts (`RECEIPTS_ROOT`) | `reports/explore/k4s-confirm/end/receipts/round-RR/<host>/<receipt directory>/` |

   - **`END-JOB.json`** (`clasher.k4s.end-job.v1`): exactly the fields `schema`, `study = PREREG-K4S`,
     `end_evidence_sha256`, `completion_sha256`, `plan_sha256`, `counted_hosts` (= the committed counted-host set),
     `k4s_manifest_sha256` (the frozen manifest), `declared_utc`, `declared_by`. Added in exactly **one** commit
     **before the first attempt** and never modified, deleted or re-added. `--end-job-sha256` is its SHA. Any other
     path under `reports/explore/k4s-confirm/` whose name looks like an END job (`END-JOB*.json`, any case) or a
     finalization (`END-FINAL*.json` outside the fixed place) makes the producer and the pool refuse. A
     byte-identical copy of the completion with repackaged END evidence therefore cannot get a second authority:
     its evidence SHA differs from the one END-JOB's, and a second declaration is refused by name.
   - **Health-only read boundary.** The authority lists committed path **names** only (`git ls-tree --name-only`,
     tree metadata) and opens blobs only inside `END_DIR`. The END namespace layout is strict: a path under `END_DIR`
     must be the END-JOB, a finalization, a claim under `REGISTRY_ROOT`, a file of a pool directory under
     `POOLS_ROOT/round-RR/` or a file of a receipt directory under `RECEIPTS_ROOT/round-RR/<host>/<dir>/`. Any other
     path, and any attempt-claim-named file (`attempt-*.json`) outside `REGISTRY_ROOT`, is refused without being
     opened. Exception: a committed receipt's `attempt-claim.json` (in a receipt directory under `RECEIPTS_ROOT`) is
     parsed in full and must be exactly the registry's claim for that round, host and receipt directory.
   - **JSON parsing.** Every admissible document (END-JOB, claim, receipt copy, finalization, earlier pool seal and
     reference, sealed receipt files) is parsed from its **complete** bytes: compact and indented forms are
     equivalent; a malformed document is refused, never skipped.
   - **Claims.** Before its receipt directory exists, every run claims
     `REGISTRY_ROOT/round-RR/<host>/attempt-NN.json` (`clasher.k4s.end-attempt-claim.v2`: `job_sha256`,
     `end_evidence_sha256`, `round`, `host`, `attempt`, receipt directory name, launch UTC, pid, nonce; exclusive
     creation, contiguous NN from 00; committed claims must be a prefix of the local ones). The producer refuses
     unless the END-JOB is committed at its `--repository` HEAD, binds this completion/evidence/manifest and counts
     this host, the END namespace is well formed, and the round is open: no committed finalization for round RR or
     a later round, and for RR > 0 the finalizations of rounds 00..RR−1 are committed **and every earlier round
     re-validates** (`end_pool.predecessors`, the pool's own code path; see re-runs) as a ratio-only nonconforming
     pool. The receipt seals a copy
     (`attempt-claim.json` + its SHA; also `end_job_sha256`, `round` and the claim SHA in `end-identity.json`).
     Never delete or rewrite a claim; a precondition refusal before the claim (bad pin, wrong host, no END-JOB) is
     not an attempt.
   - **`END-FINAL-round-RR.json`** (`clasher.k4s.end-finalization.v1`), committed **after** the last attempt of round
     RR and in a later commit than every claim it lists: exactly `schema`, `job_sha256`, `round`,
     `claims {"0": {host: [claim SHA…]}, …, "RR": {…}}` (every claim of every round so far, in order),
     `prior_rounds [{round, pool_repository_path = POOLS_ROOT/round-RR, pool_manifest_sha256}]` (one per earlier
     round, see re-runs), `finalized_utc` (after every listed launch), `finalized_by`. Append-only like the END-JOB.
   - **All original attempts** are exactly the claims under `REGISTRY_ROOT` at HEAD, which must equal the latest
     committed finalization (and the registry at the finalization's own commit). Claims made on a host but never
     committed cannot be seen by any offline check: collecting every host's registry directory before finalizing
     is an END-time operator duty (operator order, step 3).

## Per host (every committed counted host; slot 0 is the reference slot)
Run at the reporting plan's priority (`nice 10`, SCHED_OTHER) on the fleet host:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 10 python -B \
  reports/explore/k4s-confirm/end_reference.py --bundle B --runtime-root R --native N \
  --corpus K4-states.pkl --corpus-inventory corpora.json \
  --k4s-manifest-sha256 FROZEN_K4S_MANIFEST_SHA --sd1-manifest-sha256 FROZEN_SD1_SHA \
  --end-evidence E/end-evidence.json --end-evidence-sha256 S --repository R \
  --end-job-sha256 END_JOB_SHA --round RR --out $JOB/end/raw-$HOST-$RR-$N
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

## Operator order (END job, rounds, finalization)
1. After the completion receipt is committed and before any END run: write
   `reports/explore/k4s-confirm/end/END-JOB.json` (above; the one END job of the study), `clasher-secret-scan`,
   commit it alone, push; every counted host pulls, so its `--repository` HEAD contains it. Never write another
   `END-JOB*.json` anywhere under `reports/explore/k4s-confirm/`.
2. Round 00: run every counted host with `--end-job-sha256 END_JOB_SHA --round 0` (one mechanically classified
   technical repeat per host at most; keep every attempt directory).
3. After the last attempt of the round: copy every host's `reports/explore/k4s-confirm/end/registry/round-RR/<host>/`
   claims into the repository unchanged (same path), `clasher-secret-scan`, commit. Then, in a **later** commit,
   write and commit `reports/explore/k4s-confirm/end/END-FINAL-round-RR.json` listing every claim of rounds 00..RR.
   No claim may be made for that round afterwards.
4. Pool round RR (below). If the pool conforms, re-check it. If it is sealed `nonconforming` (host ratio outside
   [0.95, 1.05]; r3 §4.5 "re-run until it conforms"), the pool's `--output` must be
   `reports/explore/k4s-confirm/end/pools/round-RR`; commit it there, push, let every host pull, and re-run every
   counted host with `--round RR+1`. Commit, in the same or an earlier commit than the pool and **before any claim of
   round RR+1**, every original attempt receipt directory of round RR, complete and unchanged, at
   `end/receipts/round-RR/<host>/<receipt directory>/` (exactly the round's claimed directories per host, none
   missing, none extra). The next finalization records that pool in `prior_rounds` (fixed path + seal SHA).
   A round that ended in an unrepeatable failure (e.g. exactness) has no nonconforming pool and can never be
   followed by a re-run round; then the coordinator declares the ratio unavailable (r3 §4.5). This is mechanical,
   not procedural: an earlier round's seal status, reference and Booleans are never trusted. The producer of round
   RR+1 (before its claim) and the pool of every later round (before pooling) copy each earlier round's committed
   pool and receipts from HEAD and re-run the full validation with the pool's own code (`validate_prior_round` →
   `pool_round`: membership, claims, seals, attempt classification incl. exactness, pins, slots, guard, warm-up,
   MHz, timing). The round must recompute as **nonconforming solely because a host ratio is outside
   [0.95, 1.05]** (every other defect raises) and equal the committed pool byte-for-byte (reference, sealed
   descriptor `pool-input.json`, ratio record, seal status/inventory; `pool-inputs.json` by digest). Any earlier
   unrepeatable failure therefore refuses the whole END job: no later round can claim or pool.
5. Never edit, delete, rename or re-add the END-JOB, any finalization, any claim, any committed pool or receipt
   file. Put nothing else under `reports/explore/k4s-confirm/end/` except the pools above and sealed attempt receipt
   directories under `end/receipts/round-RR/<host>/<receipt directory>/` (required for every round followed by a
   re-run; their `attempt-claim.json` must be the registry's claim). Never
   commit an `attempt-*.json` anywhere else in the END namespace. Game, outcome and other non-health files never go
   under `end/`.

## Pooling and recheck
- Descriptor `clasher.k4s.end-pool-input.v3`: `pooled_by`, `k4s_manifest {path, sha256}` (the frozen manifest),
  `corpus_inventory {path, sha256}`, `end_evidence {path, sha256}`, `kernel_rel`, `scorer_rel`,
  `end_job {sha256}`, `round` (the latest finalized round), `finalization {sha256}` (its `END-FINAL-round-RR.json`),
  and `hosts [{host, attempts [{directory, manifest_sha256}…]}]` (this round's attempts). The END-JOB, finalization,
  registry and earlier-pool paths are the fixed paths above, never supplied.
- `end_pool.py pool --pool-input D --pool-input-sha256 S --output NEW_POOL_DIR [--repository R]`:
  - the host list must equal the committed counted-host set (no exclusion after counting);
  - END job authority (`end_evidence.job_registry`), all read from git at **HEAD** (never an older snapshot or a
    caller-chosen commit): the one `END-JOB.json` at its fixed path (SHA, append-only, bound to this completion/
    evidence/plan/counted hosts/frozen manifest; no other END-JOB-like name under the study tree); the round's
    `END-FINAL-round-RR.json` (SHA, append-only, bound to the job and round); finalizations at HEAD are exactly
    rounds 00..RR; the END namespace is checked by path name only; the registry under `REGISTRY_ROOT` is append-only (no
    claim ever deleted/modified) and its claims at HEAD (rounds 00..RR, every counted host in every round, each
    claim bound to the job, evidence, round, host and index) equal the finalization's inventory, which also equals
    the registry at the finalization's own commit (finalized after every claim was committed); every claim was
    added after the END-JOB and launched before `finalized_utc`; every earlier round's finalization passes the same
    checks (claims of rounds 00..that round at HEAD and at its own commit, launches before it, its `prior_rounds`
    at the fixed pool paths with the committed seal SHAs); each earlier round is then **re-validated and
    recomputed** (`end_pool.validate_prior_round`, re-runs above), never trusted from its seal; no attempt-claim-named file exists in the END
    namespace outside `REGISTRY_ROOT`, and every committed receipt copy is the registry's claim (complete-bytes
    parse); no blob outside `END_DIR` is opened;
  - each host's attempt list must equal this round's registry entries **in order** (each receipt's sealed
    `attempt-claim.json` = the committed claim, same SHA and directory name; `end-identity.json` binds the END job
    and round): an omitted or reordered attempt is refused; more than two attempts (more than one repeat) are
    refused;
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
  - every local file read is recorded in the sealed `pool-inputs.json`; the descriptor's exact bytes are sealed as
    `pool-input.json` (so a later round can recompute this pool).
- **Ratio window vs TIERS.** r3 §4.5 says "[0.95, 1.05] inclusive"; K4S implements `0.95 <= r <= 1.05` on the
  nearest doubles. The frozen TIERS pool uses `abs(r-1) <= .05`, which rejects the exact doubles 0.95 and 1.05
  (both differences round above .05). The rules differ only at those two endpoint doubles; tests pin both
  endpoints and one ulp on each side for both forms. K4S does not change the TIERS rule.
- `end_pool.py recheck --pool-input D --pool-input-sha256 S --pool NEW_POOL_DIR --checked-by WHO --output R.json`
  reads the pool only through its seal, requires every `pool-inputs.json` entry to be in its own before/after input
  inventory (descriptor, descriptor-named files, the END evidence and every artifact it names, every file in every
  attempt directory) with the same SHA, re-executes pooling in a fresh `python -I`, compares every sealed byte,
  checks the inputs did not change (the re-executed pool re-validates and recomputes every earlier round from
  HEAD exactly as the pool did, so a pooler that skipped or trusted an earlier round is caught), and writes `clasher.k4s.end-recheck.v1` binding the reference SHA, descriptor,
  END evidence, every host seal, the END-JOB and finalization SHAs, the round and the checker bytes. `WHO` must differ from `pooled_by`
  (T1 `check_reference.py` pattern).
- Commit the pool directory and the re-check receipt; they are the Mac script's `--fleet-reference` and
  `--fleet-recheck` inputs (`mac/K4S-MAC-PROCEDURE.md` §3). The Mac admits the reference only if its common pins
  equal `end_frozen_pins` of the Mac's own frozen K4S manifest (same manifest SHA and END source pins).
