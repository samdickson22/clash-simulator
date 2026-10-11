# K4S Mac measurement procedure (PREREG-K4S r3 §1.4; freeze checklist F-8)

- **What this is.** The operator procedure for the separate K4S Mac script `measure_k4s.py`, its manifest
  `K4S-MAC-MANIFEST.json`, the load-selection rule and the failure classifier `classify_k4s_failure.py`. Together
  they make up release item 5 of r3 §4.5 (CONFORMANCE-r2 N2/F-8, RECHECK-r3 R3/R5).
- **Status.** Draft r2 (fixes for the SOL review r1 findings 1–9), not frozen; integration re-review pending. No Mac has been contacted. Nothing here authorises
  live play: the script is replay only and has no actuator, client, emulator, network or live-input option.
- **Governing text.** `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` (sha256 `9650972d…`).
  Where this file and r3 differ, r3 governs. TIERS's own Mac rules come from `PREREG-SEARCH-TIERS-r3-DRAFT.md` §6–§7
  and `mac-e4-package/E4-V3-ADDENDUM-r3-DRAFT.md` §B–§G.
- Paths are repo-root relative. `MAC` means `reports/explore/k4s-confirm/mac`; `E4V3` means
  `reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3`.

## 1. Hard boundaries with TIERS

1. `E4V3/measure_tiers.py`, the TIERS manifest (`tiers-pins.json`), `spec-pins.json` and every e4v3 file are
   **reused read-only and never edited**. Their SHA-256 values are recorded in `K4S-MAC-MANIFEST.json` under
   `reused_readonly`, and `measure_tiers_unmodified` states that `measure_tiers.py` is unmodified (its SHA equals
   the committed blob). `measure_k4s.py` re-verifies every pin before it imports any e4v3 module.
2. K4S runs **only after TIERS's complete §7 list** in the same session, or in standalone mode (§5.2).
3. K4S writes **only** to its own fresh output directory. The script refuses (exit 3, before creating anything) if
   the output overlaps any of: the TIERS package tree, `reports/explore/t1`, the TIERS bundle, or any TIERS receipt
   directory passed in. The output may not be inside them, equal to them, or a parent of them.
4. A K4S-only failure **never** writes into, triggers, invalidates or reclassifies a TIERS session or receipt, and
   never adds a session to TIERS's minimum across sessions. The K4S classifier calls only the pure `classify()`
   function of TIERS's `classify_failure.py`, read-only, and never its CLI.
5. Reused TIERS inputs are **read from TIERS's committed, sealed receipts, never re-measured** (r3 §1.4, N2).
   The script verifies the receipt-manifest SHA-256 and sidecar, every sealed file, and then the commit: a full
   40-hex commit that is an ancestor of the repository's `HEAD`, whose tree at the given repo-relative directory
   holds exactly the sealed inventory (every manifest file plus `receipt-manifest.json` and its sidecar), with every
   committed blob byte-equal to what is read. Uncommitted, locally revised or re-sealed receipts are refused:
   - `c_M = 1.0` iff TIERS's `tiers-summary.json` has `feasibility.K4.feasible = true` with `cell = 1.0` (TIERS's
     r_5, p10 ≥ 0.70 and gates 2–6);
   - gate 0's TIERS part is the §7.2 verdict: `exactness-tiers.json` (125 states, `workers_equal` and
     `zero_budget_immutable` on every record, i.e. 1/2/4-worker equality), `belief-exactness.json` (125 histories,
     belief/RNG exact), `exactness_class` ∈ {EXACT, ARM64-NEAR-EXACT}, and K4's gate 3.
   - A TIERS session that TIERS itself terminated on a §7.2 exactness failure is read as a gate 0 failure.
     A trace whose only mismatches end in `/1=2` or `/1=4` is a 2/4-worker-only failure; any other exactness
     failure fails every tier. K4S then writes a no-measurement summary with `c_M = null`.
6. **Binding (RECHECK-r3 R5).** Reusing gate 0 is valid only if K4S runs the 4-worker scorer and native that TIERS
   qualified on the same Mac. The script refuses unless all of the following hold:
   - the native passed to K4S has the SHA in the TIERS session's `build-tiers.json` (a locked
     aarch64-apple-darwin build whose `source_manifest_sha256` is the TIERS bundle manifest). K4S never rebuilds
     it. The Linux provenance native is `44874fd6…`;
   - the K4S scorer module either is byte-identical to TIERS's pinned `reports/explore/s1/anchor.py` (`75a1b7d7…`),
     or is the declared stats-only `anchor_x` derivative. For the derivative, reverting exactly its two declared
     hunks (docstring header; extra `deadline_stats` keys) must give those bytes. It must also sit in
     `reports/explore/<dir>/`, so its `e1/planner.py` base is TIERS's pinned file;
   - the host, machine and sysctl identity (`hw.model`, CPU brand, memory, P/E counts) equal those in TIERS's
     `tiers-identity.json`.

## 2. Preconditions (all checked by the script before any measurement; a failure is a refusal, not a session)

| # | Precondition | Evidence passed to the script |
|---|---|---|
| P1 | Sam has authorised this Mac replay session | `--sam-authorized-replay`, Darwin/arm64, nice 10, OMP/OPENBLAS/MKL = 1 |
| P2 | The K4S manifest is frozen and matches | `--k4s-manifest-sha256` (the frozen manifest SHA); every K4S and reused file re-hashed |
| P3 | TIERS's complete §7 list (or a §7.2 exactness termination) in a sealed, **committed** TIERS session that TIERS's classifier does not mark technically invalid | `--tiers-receipts DIR --tiers-receipt-sha256 SHA --tiers-receipt-commit C --tiers-receipt-repo-path REL` (repeat the group for every valid TIERS session) and `--repository GIT_CHECKOUT` |
| P4 | Same session: K4S starts within 2 h of `tiers-complete.json`, under the same coordinator lock file | `--coordinator-lock` (+ the inherited `--coordinator-lock-fd`) |
| P5 | Or standalone: explicit flag plus coordinator authorization file | `--standalone --coordinator-authorization F --coordinator-authorization-sha256 S` |
| P6 | Release state declared; if K4S outcomes are released, an independent reviewer has confirmed the mechanical session-validity classification (r3 §1.4, TIERS §6.6(b)) | `--k4s-release-state sealed\|released`, `--independent-review F --independent-review-sha256 S` |
| P7 | Repeat admission: every prior attempt was a pre-listed technical failure, at most one counted repeat | `--prior-classification F --prior-classification-sha256 S` per prior attempt |
| P8 | TIERS bundle is the one the TIERS session measured | `--tiers-bundle`, `--tiers-manifest-sha256` (= TIERS `tiers-identity.json` `manifest_sha256`) |
| P9 | R5 binding (§1 item 6) | `--native`, `--k4s-scorer`, `--k4s-kernel-rel` (both pinned in the manifest's `k4s_kernel.files`) |
| P10 | SD1 manifest frozen (`clasher.k4s.sd1-manifest.v1`): nested `checkpoint {job_path inputs/R3a.pt, sha256 37509a43…}`, `calibration {job_path inputs/R3a-calibration.json, sha256 e3003533…}`, threshold 0.5005528330802917, the inference mode, and the complete `inference_sources` map (exactly the 8 SD1 source files, each re-hashed under the runtime root); the TIERS bundle's R3a bytes are SD1's | `--sd1-manifest`, `--sd1-manifest-sha256` (equal to the manifest's `sd1_manifest.sha256`) |
| P11 | Frozen T1 K4 speed corpus (inventory `81f2483e`, `K4-states.pkl` `a97b1fbf…`, 300 states) | `--corpus/-sha256`, `--corpus-inventory/-sha256`, `--corpus-publication/-sha256` |
| P12 | Pooled fleet END reference (a)–(c), conforming, with machine-checked reporting-load provenance, measured and pooled on this session's complete frozen END identity (kernel/scorer/SD1/corpus/native, the frozen K4S manifest SHA and every END measurement source), and independently re-checked (r3 §4.5; §3 below) | `--fleet-reference`, `--fleet-reference-sha256`, `--fleet-recheck`, `--fleet-recheck-sha256` |
| P13 | The recorded c\* | `--c-star 0.9` (c\* record, COORDINATOR 11:46Z / `6ef5e2ff`) |
| P14 | 5-minute quiescence census: no foreign process above 0.2 core | measured at K0. A failure delays the session; it is not a technical failure |

The standalone authorization file is JSON with `schema = clasher.k4s.mac-standalone-authorization.v1` and the
fields `coordinator`, `sam_authorized_session: true`, `utc`, `reason`, and `tiers_receipt_manifest_sha256` (the
exact TIERS receipts used). Alternatively it may set `descriptive_only_without_tiers_inputs: true` with no TIERS
receipts; the result is then descriptive and has no cell. The independent review receipt has
`schema = clasher.k4s.mac-classification-review.v1`, `independent_of_author: true`,
`confirmed_classification_sha256` (every prior classification receipt) and `confirms_session_validity_rule: true`.

## 3. Fleet END reference contract (`clasher.k4s.mac-fleet-reference.v1`)

The K4S END reference (K4S-SPEC §8, r3 §4.5) is pooled by `reports/explore/k4s-confirm/end_pool.py pool` (pinned in
`K4S-MAC-MANIFEST.json` `end_files`) as `end-reference.json` in a sealed `K4S-END-POOL` directory, and re-checked
by `end_pool.py recheck`. Fields:
- `corpus_sha256` = the T1 K4 corpus SHA; `repeats = 3`; `hosts` (sorted) = every committed counted host;
- `host_ratio_to_pool[host]`, `ratio_statistic` (the frozen TIERS `fleet_pool.py` statistic: geometric mean over
  the 300 corpus states of pooled per-state median / host per-state median of the no-deadline K4S work unit),
  `ratio_window = [0.95, 1.05]` (inclusive), `pool_conforms = true`;
- **Ratio window semantics.** K4S follows r3 §4.5's "inclusive" literally: `0.95 <= r <= 1.05` on the nearest
  doubles (`k4s_logic.in_host_ratio_window`). This deliberately differs from the frozen TIERS check
  `abs(r-1) <= .05` (`e4v3/fleet_pool.py`), which rejects the exact doubles 0.95 and 1.05 because both
  differences round above .05. The two rules disagree only at those two endpoint doubles (tests pin both forms at
  both endpoints and one ulp outside); K4S never edits the TIERS rule;
- `pins` (common identity, equal on every counted host): the frozen keys `kernel_sha256`, `scorer_sha256`,
  `sd1_manifest_sha256`, `corpus_sha256`, `native_sha256`, `k4s_manifest_sha256` and `measurement_files` (every
  `k4s_logic.END_MEASUREMENT_FILES` source → its K4S-manifest pin), plus the shared bundle keys
  `bundle_runtime_files_sha256`, `bundle_measurement_files_sha256`, `bundle_model_files`. The Mac requires exactly
  this key set and every frozen key equal to `k4s_logic.end_frozen_pins` of **its own** frozen K4S manifest (same
  manifest SHA, same END source pins); the pooler requires the same against the pool descriptor's frozen manifest.
  Each host's own bundle manifest (which names that host) is a per-host receipt, never compared across hosts:
  `provenance.host_receipts[host].host_pins = {bundle_manifest_sha256, bundle_profile_host = host}`;
- `states[id]` for every corpus state:
  - `k4s_wall_seconds`: the pooled per-state median no-deadline K4S work unit, item (a);
  - `sd1_poll_seconds`: the pooled per-state median SD1 poll span, item (c);
  - `result {action, candidates, scores}`: the no-deadline K4S result, which equals K4's;
  - `k4_wall_seconds` and `v1_poll_seconds`, which are descriptive;
- `deadline[cell]` for exactly the cells "1.0"/"0.9"/"0.8"/"0.7"/"0.6", item (b), K4S at b(c) with the 1/c charge,
  in the **canonical naming shared by the producer (`k4s_logic.deadline_cell_record`), this contract and the
  gate-6 reader**: `budget_ms` (200/180/160/140/120), `charge_scale` ("1", "10/9", "5/4", "10/7", "5/3"), integer
  `n` (= 3 × 300 × hosts), and for each of `cutoff`, `no_complete_play`, `fallback`: the integer `<key>_count` and
  the rate `<key>` = count / n. No `_rate` suffix exists;
- `reporting_load_profile = true` **only** when `provenance.reporting_load_profile_evidence` has every check true:
  `committed_completion`, `all_counted_hosts`, `all_original_attempts_classified`, `slot0_and_every_background_slot`,
  `reporting_priority`, `reporting_guard`, `full_occupancy_reporting_mhz`;
- `provenance`: `pool_input_sha256`, `end_evidence_sha256`, `completion_sha256`, `plan_sha256`, `counted_hosts`,
  `pooled_by`, `pooler_sha256`, and `host_receipts[host]` = {`manifest_sha256`, `attempts` (frozen
  `classify_attempt` verdicts, in the committed END attempt-registry order), `host_pins`, `search_cpus`,
  `background_masks`, `nice`, `reference_to_reporting_mean` (the signed MHz ratio), `mhz_comparison_passes`,
  `ratio_to_pool`}; `attempt_registry {commit, repository_path, claims}` and `k4s_manifest_sha256`.

The re-check receipt (`clasher.k4s.end-recheck.v1`) must have `passes = true`, `outcome_access = false`,
`reference_sha256` = the SHA of the reference file passed to the script, and the same `pool_input_sha256`,
`end_evidence_sha256` and per-host receipt seals as the reference's provenance; `checker_sha256` = the SHA of the
manifest-pinned `end_pool.py`; `checked_by` non-empty and different from `pooled_by`. An arbitrary SHA string is
not accepted.

## 4. Load-selection rule (frozen)

- **Profile.** The replay perception load is **TIERS's own**: the `load` block of the TIERS bundle manifest
  (`tiers-pins.json`) that TIERS recorded in `tiers-identity.json` for the qualifying session. That fixes `kind`,
  `label`, `target_fps = 20`, `config.device = mps`, the TRAIN `matches` and `split`.
- **Nothing is chosen afresh.** The script refuses a different bundle, a label mismatch, a non-MPS Mac
  configuration or a non-20 FPS pace. A `v3-body-hud-only` profile carries the `PROVISIONAL-LOAD` label into every
  K4S output, as in TIERS.
- **Priority and threading** equal TIERS's live configuration: nice 10 with inherited QoS and no affinity on the
  Mac; Torch, BLAS and OpenCV at one thread; perception in its own spawned `replay_load.load_worker` process
  (TIERS's code, read-only); the K4S search in the main process with its 4 native scorer threads. Linux dry runs
  use nice 19 and TIERS's `LinuxBackground`.
- **Gate 4 window.** Perception is aggregated, as in TIERS D5, over the loaded K4S speed blocks (K3): processed
  frames per active second ≥ 18, and processed / expected ≥ 0.95.

## 5. Commands

Set the TIERS session's variables (README "Exact Mac session command") and these K4S ones. Every path is absolute
and every output directory is fresh.

```bash
export K4S_OUTPUT=/absolute/new-k4s-measurement          # never inside any TIERS path
export K4S_MANIFEST_SHA=FROZEN_K4S_MAC_MANIFEST_SHA256
export K4S_SD1=/absolute/SD1-MANIFEST.json K4S_SD1_SHA=FROZEN_SD1_HASH
export K4S_CORPUS=/absolute/K4-states.pkl
export K4S_INVENTORY=$E4_RUNTIME/reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json
export K4S_PUBLICATION=$E4_RUNTIME/reports/explore/t1/corpora/corpus-03-a51ea64c/publication.json
export K4S_FLEET=/absolute/k4s-end-pool/end-reference.json K4S_FLEET_SHA=COMMITTED_SHA256
export K4S_RECHECK=/absolute/end-recheck.json K4S_RECHECK_SHA=COMMITTED_SHA256
export E4_REPO=/absolute/clasher-git-checkout              # operator's checkout (not the frozen runtime)
export TIERS_RECEIPT_REL=COORDINATOR_ASSIGNED/repo-relative/tiers-session-dir
export CLASHER_SECRET_SCAN=/absolute/clasher-secret-scan          # the repo's staged-diff secret scanner
export K4S_KERNEL=reports/explore/k4s-confirm/FROZEN_KERNEL.py K4S_SCORER=reports/explore/k4s-confirm/anchor_x.py
export K4S_RELEASE_STATE=sealed                           # or released (then add --independent-review ...)
```

### 5.1 Default: inside the TIERS session, after TIERS's complete §7 list

Append this to the TIERS heredoc **after** the `measure_tiers.py` call has returned 0. It inherits the same locked
descriptor, so the coordinator lock is held from TIERS staging through the commit and K4S cleanup. TIERS's receipt
directory is already sealed at that point. **First the sealed TIERS receipts are committed** (secret scan, then a
local commit in `E4_REPO`, still under the lock; pushing may happen later). K4S then reads the committed copy and
proves it against that commit. If the commit step fails, K4S does not start and TIERS is unaffected.

```python
import shutil
tiers_sha = open(e['E4_OUTPUT'] + '/receipt-manifest.sha256').read().split()[0]
committed_dir = pathlib.Path(e['E4_REPO']) / e['TIERS_RECEIPT_REL']
shutil.copytree(e['E4_OUTPUT'], committed_dir)            # exact sealed bytes; the directory must be new
git = ['git', '-C', e['E4_REPO']]
subprocess.run(git + ['add', '--', e['TIERS_RECEIPT_REL']], check=True)
subprocess.run([e['CLASHER_SECRET_SCAN']], cwd=e['E4_REPO'], check=True)   # staged-diff scan; exit 1 stops
subprocess.run(git + ['commit', '-m', 'TIERS Mac session receipts (sealed ' + tiers_sha[:12] + ')'], check=True)
tiers_commit = subprocess.run(git + ['rev-parse', 'HEAD'], check=True, capture_output=True, text=True).stdout.strip()
k4s = pathlib.Path(e['E4_RUNTIME']) / 'reports/explore/k4s-confirm/mac'
subprocess.run([sys.executable, '-B', str(k4s/'measure_k4s.py'), '--sam-authorized-replay',
    '--output', e['K4S_OUTPUT'], '--runtime-root', e['E4_RUNTIME'],
    '--k4s-manifest-sha256', e['K4S_MANIFEST_SHA'], '--c-star', '0.9',
    '--tiers-receipts', str(committed_dir), '--tiers-receipt-sha256', tiers_sha,
    '--tiers-receipt-commit', tiers_commit, '--tiers-receipt-repo-path', e['TIERS_RECEIPT_REL'],
    '--repository', e['E4_REPO'],
    '--tiers-bundle', e['E4_BUNDLE'], '--tiers-manifest-sha256', e['E4_MANIFEST_SHA'], '--native', str(native),
    '--k4s-kernel-rel', e['K4S_KERNEL'], '--k4s-scorer', e['K4S_SCORER'],
    '--sd1-manifest', e['K4S_SD1'], '--sd1-manifest-sha256', e['K4S_SD1_SHA'],
    '--corpus', e['K4S_CORPUS'], '--corpus-sha256', 'a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8',
    '--corpus-inventory', e['K4S_INVENTORY'], '--corpus-inventory-sha256', SHA_OF_CORPORA_JSON,
    '--corpus-publication', e['K4S_PUBLICATION'], '--corpus-publication-sha256', SHA_OF_PUBLICATION_JSON,
    '--fleet-reference', e['K4S_FLEET'], '--fleet-reference-sha256', e['K4S_FLEET_SHA'],
    '--fleet-recheck', e['K4S_RECHECK'], '--fleet-recheck-sha256', e['K4S_RECHECK_SHA'],
    '--k4s-release-state', e['K4S_RELEASE_STATE'],
    '--coordinator-lock', e['E4_LOCK'], '--coordinator-lock-fd', str(lock.fileno())],
    pass_fds=(lock.fileno(),), check=False)   # a K4S exit never changes the TIERS session
```

`check=False` is deliberate: a K4S refusal or failure must not make the TIERS wrapper report a TIERS failure. TIERS's
receipts are already sealed before K4S starts.

### 5.2 Standalone (a separate Mac session)

Use this when the TIERS session has already ended, more than 2 h have passed, or TIERS ran in an earlier session on
the same Mac. Use the same command with `--standalone --coordinator-authorization F
--coordinator-authorization-sha256 S`, and pass every valid TIERS session receipt with its commit and repo-relative
path (the receipts must already be committed). Sam's authorisation and the
coordinator lock are still required. The same-Mac identity and native checks still bind K4S to the Mac TIERS
qualified.

### 5.3 After the session (any machine, offline)

```bash
python3 MAC/classify_k4s_failure.py classify --receipts $K4S_OUTPUT --output NEW_CLASSIFICATION_DIR \
    --tiers-receipts $E4_REPO/$TIERS_RECEIPT_REL --tiers-receipt-sha256 $TIERS_SHA
python3 MAC/classify_k4s_failure.py reduce --session S1 --session-sha256 H1 --classification C1 \
    --classification-sha256 G1 [--session S2 ...] --c-star 0.9 --output NEW_FINAL_DIR
```

## 6. Steps (about 30–45 min in session; about 1.5 h standalone with census and warm-up)

| Step | What | Size (Mac) |
|---|---|---|
| K0 | Preconditions (§2), staging pins, lock, 5-min quiescence census, identity, ps table | — |
| K1 | Unloaded: no-deadline K4S on all 300 corpus states vs the fleet END (a) result (ARM64-NEAR-EXACT, TIERS `score_exactness`); SD1 agreement on TIERS's 2,000 frozen agreement states, CPU, one Torch thread, TIERS `agreement()` tolerances. A gate 0 failure ends measurement (summary still written) | 300 + 2,000 |
| K2 | Start TIERS's replay load (§4); 5-min thermal warm-up | — |
| K3 | Loaded K4S speed: work unit = TIERS §6.1 decision + SD1 poll + top-8 ranking, 50-state blocks, ≥ 300 states and ≥ 5 min; per-call `poll_seconds`; perception windows per block | ≥ 300 |
| K4 | Deadline mode: each corpus state at 200 ms / 8 ms reserve under load, honest timer, no extra charge (the Mac's own speed is measured): cutoff, no-complete-play, fallback counts | 300 |
| K5 | 1,000 TIERS replay packets × K4S at 200 ms with the GC trace (default GC) | 1,000 |
| K6 | The same with `gc.freeze()` once after warm-up, if some cell passes gates 0–4 | ≤ 1,000 |
| K7 | Stop load and telemetry; mechanical reduction; `k4s-mac-summary.json`; re-validate bundle and native; `k4s-complete.json`; seal | — |

## 7. Statistics, gates and the cell mapping (r3 §1.4; computed by `k4s_logic.py`)

- **r_K4S** = min(median per-state ratio, Σ fleet / Σ Mac, fleet p90 / Mac p90). Per-state Mac wall is the median
  over the K3 repeats; the fleet wall is END (a). **p10_K4S** is the 10th percentile of the per-state ratios.
  The quantiles are TIERS's linear interpolation.
- **r_inf** = (median over states of the fleet END (c) per-state SD1 poll span) / (median over states of the Mac
  per-state median warm poll span). **Poll p99** is taken over every warm K3 poll observation. The session's first
  (cold) poll never enters.
- **Gates for c ∈ {0.9, 0.8, 0.7, 0.6}:**
  0. **Exactness:** TIERS §7.2 verdict (read), K4S corpus exactness (K1), SD1 agreement ≥ 99.5% with no
     unexplained disagreement (K1, and TIERS's CPU agreement receipt if present: worst of the two), and R5 binding.
  1. r_K4S ≥ c and p10_K4S ≥ c − 0.10.
  2. r_inf ≥ c².
  3. Poll p99 ≤ 20 ms.
  4. FPS ≥ 18 and processed ≥ 95%.
  5. TIERS §6.3 gate 4, with TIERS's `gc_summary` (default GC, or freeze if that passes).
  6. Mac 200 ms cutoff and no-complete-play rates each ≤ fleet END (b) at b(c) with the 1/c charge, + 2 pp.
- **Comparison semantics.** Thresholds are inclusive exactly as written. Each threshold is an exact rational (for
  example 0.8 − 0.10 = 7/10 and 0.9² = 81/100), rounded once to the nearest double for comparison, which is TIERS's
  float semantics. Gate 6 compares integer counts exactly: count/n ≤ count_ref/n_ref + 2/100. Non-finite inputs
  fail closed.
- **Mapping.**
  - The provisional cell is the largest c passing gates 0–5.
  - If gate 6 fails, move down one cell and re-check every gate there. Repeat until a cell passes.
  - c_M (K4S) is therefore the largest c ≤ 0.9 passing gates 0–6. If none passes, the result is K4S Mac-infeasible.
- **Final c_M.**
  - c_M = 1.0 if TIERS found K4 Mac-feasible in its 1.0 cell (§1 item 5). No SD1 gate applies there.
  - c_M = null if TIERS found an all-tier exactness failure.
  - Otherwise c_M is the K4S mapping.
  - The summary also reports `k4s_eligible_c_M_le_c_star`. The §1.5 deployment itself needs the released fleet
    outcomes and the TIERS selection, and is not computed here.

## 8. Session validity, integrity and repeats (TIERS §6.5; addendum §F)

- **One valid session.** `classify_k4s_failure.py classify` assigns exactly one category from receipts:

  | Category | Meaning | Valid | Repeat |
  |---|---|---|---|
  | `valid` | Complete; no technical evidence | yes | no |
  | `gate-failure` | Exactness mismatch, zero-budget or agreement gate failure, **including one raised after a summary was written** (e.g. the post-run bundle re-validation); a cleanup exception or a disagreeing seal status is recorded in its reasons but never turns it into a pass or a repeat | yes | **no** |
  | `technical-failure` | Harness/load exception, including a sealed `cleanup-failure.json` (load, telemetry or backend cleanup failed, even after `k4s-complete.json`); a sealed status that disagrees with the receipts (e.g. `failed`/`refused` with a completion receipt); host sleep/reboot (boot time change or > 3 s wall/monotonic jump); `pmset` CPU speed limit < 100% before the K4S load starts (K0/K0-census/K1); a foreign process > 1 core for > 60 s; a staging pin mismatch; an incomplete session without a gate failure | no | one |
  | `invalid-tiers-session` | The K4S block ran inside a TIERS session that TIERS's own classifier marks technically invalid (R3) | no | yes, without using the K4S allowance |
  | `precondition-refusal` | Nothing measured | not a session | not needed |

- **What never counts as technical.** Low speed, failed gates and noisy values. A human cannot declare a technical
  failure.
- **Repeat allowance.** At most one counted technical repeat. Beyond that, a coordinator amendment is needed. Every
  repeat uses a fresh output directory and passes its prior classification receipts (P7).
- **After K4S release.** If K4S outcomes are released, an independent reviewer confirms the mechanical
  classification before any K4S Mac session runs (P6). This applies to the first session as well as repeats.
- **Sealed inputs to `reduce`.** Each classification directory is read by path + seal SHA: its seal must be
  `complete`, its scope the classifier's, and it must list `classification.json`, whose bytes are re-hashed against
  the seal before reading; the classification must name the session's seal SHA and status. Session summaries and
  preconditions are read only if listed in the session's own verified inventory.
- **Admission reconciles classification and receipts.** A `valid` classification is admitted only if the session's
  own seal is `complete` with `k4s-complete.json` and holds no `failure.json`, `cleanup-failure.json` or
  `refusal.json`. A `gate-failure` is admitted only with a sealed exactness failure trace, and its gate 0 is
  **forced false**: any summary written before the failure is superseded (its measurements are not reduced; only
  its TIERS inputs and gate 0 parts are kept, plus `k4s_exactness_gate_failure = false`). `reduce` also refuses a
  gate-failure classification paired with a passing gate 0.
- **Across valid sessions** (`reduce`): minimum r_K4S, p10 and r_inf; maximum poll p99 and deadline rates; minimum
  FPS and processed fraction; gate 0 and GC must pass in every valid session. Then apply the §7 mapping. A gate 0
  failure in any valid session makes K4S Mac-infeasible. Sessions must read the same TIERS inputs.
- **TIERS's minimum.** No K4S session, failure or repeat ever enters TIERS's minimum across sessions.
- **PROVISIONAL.** A replay-only result is `PROVISIONAL (emulator-off)` until formal E4/T9 re-measures every input
  with the emulator running, under an amended formal E4. The label comes from the `ps` process table at start and
  end; the script never contacts an emulator. Dry runs are labelled `DRY-RUN (not Mac evidence)`.

## 9. Outputs (all in `$K4S_OUTPUT`, exclusive creation, SHA-sealed even on failure)

| File | Contents |
|---|---|
| `k4s-preconditions.json`, `k4s-staging.json`, `k4s-coordinator-lock.json` | Mode, TIERS inputs read, repeat and release state, load rule, binding, pins |
| `k4s-identity.json`, `k4s-runtime-versions.json`, `capacity.jsonl`, `k4s-pre-session-census.json` | Identity, ps table, 1 Hz census/thermal/boot time |
| `k4s-corpus-exactness.jsonl`, `k4s-speed-unloaded.jsonl`, `k4s-sd1-agreement.jsonl` | K1 |
| `perception-replay.jsonl`, `k4s-speed-loaded.jsonl` | K2–K3 |
| `k4s-deadline-corpus.jsonl` | K4 |
| `k4s-decisions.jsonl`, `k4s-gc-freeze.jsonl`, `k4s-gc-freeze-rss.json`, `k4s-gc-trace.jsonl` | K5–K6 |
| `k4s-mac-summary.json` | Every gate input, per-cell gate table, gate 6 trail, c_M, c\*, eligibility, kill flags, TIERS inputs, binding, `status`, `provisional`, `provisional_label`, `dry_run`; `final`, `mac_qualified`, `formal_E4_qualified` and `live_actions` are all false |
| `k4s-complete.json` | Completion (exit 0 means completed, not passed) |
| `refusal.json` / `failure.json` / `cleanup-failure.json` | A refusal (no session), a failure trace, or a cleanup exception (always sealed; a cleanup failure after completion seals `failed`) |
| `receipt-manifest.json` + `.sha256` | The seal |

Commit the sealed directory, its classification and the reduction (after `clasher-secret-scan`). The coordinator
then applies r3 §1.5 against the TIERS selection.

## 10. What kills or lowers the tier on this Mac (r3 §5.4)

- **Kills K4S on this Mac (gate 0 or gate 3; no K4S cell can pass):**
  - SD1 cross-platform agreement below 99.5%, or any unexplained disagreement;
  - poll-span p99 above 20 ms;
  - a TIERS 2/4-worker-only equality failure (K4S is a 4-worker search);
  - any other gate 0 failure: belief/RNG, corpus exactness, or R5 binding.
- **Kills every tier:** an arm64 single-thread or belief exactness failure (TIERS §7.2), read from TIERS's
  receipts.
- **Lowers the cell or makes the tier infeasible:**
  - r_K4S/p10 (gate 1);
  - r_inf < c² (gate 2);
  - deadline-equivalence failure (gate 6, which steps down one cell at a time);
  - the cell-independent gates 4 and 5, which make the tier infeasible.
- **Not affected:** c_M = 1.0 depends only on TIERS's K4 1.0-cell verdict. A K4S kill then leaves plain K4 as TIERS
  selected.
