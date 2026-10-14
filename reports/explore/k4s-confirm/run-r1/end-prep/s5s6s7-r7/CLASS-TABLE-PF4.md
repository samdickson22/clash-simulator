# PF-4 class table: every S5 check vs the frozen END (s5s6s7-r7)

Ruling PF-4 item 2 (COORDINATOR c14b40e8, 2026-10-14 00:59Z entry): every S5 `require()`/check against what the
frozen END actually does at the same point, with file:line on both sides; every check stricter than END is fixed in
this round or justified in writing. Written 2026-10-14T01:24:11Z on 127x05, offline (no ssh, host or network; nothing committed).

**Sources.**
- S5 = `s5s6s7-r7/k4s_end_preflight.py`; line numbers are r7's.
- The frozen END is read only, from `end-staging/runtime-98566c032d0b/runtime`:
  - `ER` = `reports/explore/k4s-confirm/end_reference.py`, `EB` = `end_background.py`, `KB` = `mac/k4s_backend.py`, `KL` = `mac/k4s_logic.py`.
  - e4v3 (`reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/`): `TB` = `tier_backend.py`, `FP` = `fleet_profile.py`, `FV` = `fleet_validity.py`, `FR` = `fleet_reference.py`, `TE` = `telemetry.py`, `RL` = `replay_load.py`, `RC` = `receipts.py`.
  - T1 guard modules (`reports/explore/t1/`): `host_audit.py`, `ssh_budget.py`, `system_bus.py`, `parent_source_seed.py`, `perception_confirmation.py`.
- Rulings: `audits/K4S-END-PLAN-REVIEW-r1.md` RC-2..RC-9; COORDINATOR P2-1, P2-3, P2-4, the frozen-reader ruling (21:28Z), U4, RO-1, PF-4; `reviews/SOL-REVIEW-END-PKG2-r1.md` S5-F1/S5-F2/S10-F4; `reviews/SOL-REVIEW-END-FULL-r1.md` F1/F2/F3/F5; README of this package.
- Host evidence (preflight metadata only):
  - 03 l01 (`preflight-received/127x03/preflight-127x03-l01`) failed `backend_and_corpus`; RO-1 fixed it.
  - 04 l00 (`.../127x04/preflight-127x04-l00`) passed every check through `guard_admission`, then failed `background_ready`.
  - No check after `background_ready` has ever run on a host. Those checks get the closest reading below.

**Verdicts.**
- SAME: the same rule at the same point, in effect.
- STRICTER: S5 refuses something END accepts.
- LOOSER: S5 accepts something END refuses.
- S5-ONLY: END has no counterpart (layout, pins, safe_input gates, RC-2 measurement requirements).

"Exercised" says whether the check has passed on a real host: 04 = 04 l00, 03 = 03 l01.

## Counts (r7 state; 51 rows)

| Verdict | Rows | Notes |
|---|---|---|
| SAME | 18 | includes C20 (MHz window) and D4 (error outside a check), fixed to SAME in r7 |
| STRICTER | 15 | all kept with a written reason (below); C15 is the PF-4 affinity check, now the ruled subset form |
| LOOSER | 0 | r6 had D4 (an error outside any check row sealed `passed`) and the other half of C20: both fixed |
| S5-ONLY | 18 | each cites the ruling that requires it |

**Fixed in r7.**
- C15: the r6 affinity equality check, the 04 l00 failure. The runner's edit is kept as ruled.
- C20: the MHz comparison window included the frozen warm-up.
- D4: an error raised while no check row is open no longer passes.
- No other row needed a code change.

---

## A. Before anything is opened (pure argument checks, pinned layers, output store)

| # | S5 check (r7) | Frozen END at that point | Verdict | Exercised | Disposition / reason |
|---|---|---|---|---|---|
| A1 | `load_layers` :325-335: canonical bootstrap r1 (:167-322) of `safe_input.py` and `k4s_end_host_tool.py` (normalized path, outcome-name gate, no-follow walk, single-link leaf of the pinned size, SHA); `constants_fingerprint` :331; `tool.check_safe_input` :334 | none (END imports frozen modules by path) | S5-ONLY | 03, 04 | keep: END-FULL-F1 / P2-1 (the shared pinned input layer). Refuses only staged tools that differ from TOOLS-FINAL |
| A2 | `refusals` host ∈ {127x03, 127x04} :387-388 (`si.hostname_checked`, :1048) | `FP:11-12` host ∈ plan hosts and not forbidden; `ER:301` profile host == `platform.node()` | STRICTER | 03, 04 | keep: the END runs only on the two counted hosts (RC-6 roots, RC-9). Cannot refuse an END-shaped run |
| A3 | nice == 10 and SCHED_OTHER :389-390 | `EB:84` Linux SCHED_OTHER; `FP:13` nice == plan `compute.nice` (10: 04 l00 `reporting_profile` passed at nice 10) | SAME | 03, 04 | — |
| A4 | refuses `-O` :391-392 | none | S5-ONLY | 03, 04 | keep: U4. S7 composes and validates exactly `HOST_PYTHON -B` (gate `validate_argv` refuses `-O`), so an S7-launched run never has `-O` |
| A5 | hold ≥ 120 s (03) / 900 s (04) :393-394 | END's own warm-up is ≥ 300 s (`FP:27`), a different quantity | S5-ONLY | 03, 04 | keep: RC-2 ("on 04, ≥ 15 min of full background load"); open decision 6 (03 ≥ 120 s). The same minimum is applied by S7 (gate :447-448) |
| A6 | `min_samples` ≥ 60 :395-396 | none | S5-ONLY | 03, 04 | keep: RC-2 ("≥ 60 1 Hz samples") |
| A7 | block seconds in [1, 300] :397-398 | none | S5-ONLY | 03, 04 | keep: an argument sanity range used only by the `--no-reference-work` diagnostic; default 30 |
| A8 | `--k4s-manifest-sha256` == fixed 74314eda :399-400 | `ER:127` `L.load_k4s_manifest(a.k4s_manifest, a.k4s_manifest_sha256, …)` (caller-supplied SHA) | STRICTER | 03, 04 | keep: identity pin, Sol PKG2 S5-F1 (BLOCKING): the anchor is a code constant, never caller-supplied |
| A9 | `layout` :408-442 (runtime-<commit12>, bundles/<name>, repository, attempts, `--out`, inventory, native/corpus location, evidence inside the bundle, SHA forms, inventory 3501e2ac) | none (END's `--out` is any fresh dir, `KL:1143-1146`) | S5-ONLY | 03, 04 | keep: RC-6 roots declaration; S5-F2; F5 (inventory identity) |
| A10 | `bundle_stamp` :510-522 (pinned `tiers-pins.json` + sidecar; no S4 synthetic stamp; production assembly receipt; profile fleet-reference) | `ER:101-102` / `EB:76` profile fleet-reference (SAME part); no stamp/receipt check | STRICTER | 03, 04 | keep: S10-F4 / S5-F2 (a test-only or non-production bundle must never reach a host run) |
| A11 | `guard_job_of` :525-534 (`<Q4>/k4s-end-guard-r1-pfNN`; compare bundle `-rdRR-aNN`) | none (`FV:57-58` only reads `profile.guard.job`) | S5-ONLY | 03, 04 | keep: RC-3, S3-F3 / runner decision 2 |
| A12 | `policy_for` + `Store` :445-504 (exclusive `mkdir_excl` of the job dir, `O_EXCL` writes, seal) | `ER:311` `K4SStore` (`KL:1143-1152`: fresh dir, `open("x")`, scope added: same discipline) | S5-ONLY | 03, 04 | keep: P2-1 (every read and write through safe_input). Same freshness rule as END's store |

## B. `run()` checks before the frozen import

| # | S5 check (r7) | Frozen END | Verdict | Exercised | Disposition / reason |
|---|---|---|---|---|---|
| B1 | `listings_before` :1085-1087 (attempt parent and claim registry, names only) | none | S5-ONLY | 03, 04 | keep: RC-2 ("never … write under the attempt parent or the registry"), RC-9 (preflights precede every claim) |
| B2 | `bundle_stamp` row :1088-1099: compare bundle stamped and `-rdRR-aNN`; profile host == host :1092; `--end-evidence` == the bundle-pinned path :1097 | `ER:301` profile host == node (SAME); `EB:77-79` the bundle-pinned evidence SHA == spec SHA == file (SAME in effect) | STRICTER | 03, 04 | keep: RC-3 (compare bundle), S5-F2 (evidence path identity) |
| B3 | `input_locations` :1100-1102 (native and corpus pass the descriptor gate: no symlink, single link, outcome-name gate; not read) | `ER:103-104` `L.sha(path)` follows links | STRICTER | 03, 04 | keep: P2-1 / S5-F2 (BLOCKING: no aliased inputs). Passed on both hosts with the production files |
| B4 | `guard_repo` :1103-1106 (`verify_clone` role guard-repo: shallow Q3 repo, no alternates/grafts/replace/hooks/driver config; `git cat-file -e` b2f9e25e, ce042b97) | the guard's `parent_source_seed.admit` (`FV:138-142`) runs `git show` for every binding at admission and fails the guard if any is missing | STRICTER | 03, 04 | keep: frozen-reader ruling (21:28Z) + P2-4 (frozen git runs only on pre-verified clones); Q3 |
| B5 | `repository_clone` :1107-1108 (`verify_clone` role repository, full) | `EB:80` `E.end_evidence` and `ER:305` `E.end_job` git reads, unverified | STRICTER | 03, 04 | keep: frozen-reader ruling + P2-4 |
| B6 | `frozen_git_env` :1109-1114 (scrubbed `GIT_*`, P2-4 env, config files checked; `os.environ` replaced by that object) | the END runs under `frozen-exec` with the identical checked env (README open decision 4) | SAME | 03, 04 | — (the env differs from T1's only in `GIT_*`, by ruling) |
| B7 | `pre_import_pins` :537-561 + inventory :1117-1118 (74314eda bytes; closure == `FROZEN_CLOSURE`; 32 files by SHA; DELTA-MANIFEST 34eca2b7; corpora.json 3501e2ac) | `EB:66` / `KL:131-157` verify the same closure; `ER:128` reads DELTA-MANIFEST unpinned; `ER:327` reads the inventory unpinned | STRICTER | 03, 04 | keep: S5-F1 (BLOCKING: verify before any import), r4 L6 (DELTA), F5 (inventory identity) |
| B8 | `frozen_import` :705-719 (END modules are the verified runtime files; `closure_only`) | `ER:144-156` `executing_sources` (six END files, after import) | STRICTER | 03, 04 | keep: S5-F1 |

## C. `preflight()` in `end_reference.reference()` order (`ER:284-413`)

| # | S5 check (r7) | Frozen END | Verdict | Exercised | Disposition / reason |
|---|---|---|---|---|---|
| C1 | `frozen_helpers` :765-768 | `ER:289-291`, `EB:58-67` | SAME | 03, 04 | — |
| C2 | `frozen_identity` :769-778: `ER.frozen_identity` itself, plus the bundle manifest canonical-equal to the pinned bytes :772, native/corpus == the K4S END identities :773 | `ER:96-110,292-294`; `ER:103-104` already require native == `L.NATIVE_PROVENANCE_SHA` and corpus == `L.T1_K4_CORPUS_SHA` | STRICTER | 03, 04 | keep: identity pins (F5); the added equalities restate END's own identities as constants |
| C3 | `bundle_parity` :782-785, :977-988 (identical except `guard.job`; jobs differ) | none | S5-ONLY | 03, 04 | keep: RC-3 (T1 A5 per-attempt bundles) |
| C4 | `guard_job_fresh` :786-790: the four side files and `STOP`, `STOP-<host>` absent | the guard **appends** to side files (`host_audit.py:175`, `ssh_budget.py:123`, `perception_confirmation.py:131`: `open('a')`) and stops on STOP when present (`FV:189`); existing *admission* files must be pinned (`FV:112-114`) | STRICTER | 03, 04 | keep: RC-3 (a fresh guard job per attempt so its side files can be attributed to it alone); `copy_guard_sources` exports them as this run's. **Dynamic-state flag:** 04 l00's guard wrote `allowlist-occurrences.jsonl` and `parent-source-seed-admission.json` into `/mpac/sdicks02/jobs-k4s/k4s-end-guard-r1-pf00` (both copied into its seal). A 04 l01 on the pf00 bundle will refuse here, and should. It needs a fresh `-pf01` guard job and bundle (runner) |
| C5 | `reporting_profile` :791-802 (`k4s_reporting_profile` + profile host == node == `hostname`) | `ER:297-301`, `EB:70-87` (`hostname` and `platform.node()` are both the uname nodename) | SAME | 03, 04 | — |
| C6 | `physical_cpus` :803-806 (`validate_physical_cpus`, `sched_setaffinity(0, search)`) | `ER:302-304`, `TE:74-88` | SAME | 03, 04 | — |
| C7 | `end_job_read_only` :807-811 (only with `--end-job-sha256`; else skipped) | `ER:305` | SAME | skipped | — (preflights run before the END-JOB) |
| C8 | `backend_and_corpus` :813-816 | `ER:159-165,326-328` | SAME | 04 (03 after RO-1) | — (RO-1 handled the read-only-runtime write) |
| C9 | `topology` :821-822 | `ER:333`, `TE:60-71` | SAME | 03, 04 | — |
| C10 | `check_monitor` / `checkpoint` (60 s) / `guarded` / `set_phase` :827-857 | `ER:338-362` (verbatim) | SAME | 04 | — |
| C11 | `guard_admission` :858-865 (+ `guard-admission.json` read through safe_input) | `ER:363-365` | STRICTER | 04 | keep: P2-1. The frozen-written file passed the descriptor gate on 04 |
| C12 | `background_ready` readiness :866-872 (`K4SFleetBackground` `__enter__`, 600 s) | `ER:366-370`, `RL:131-145`, `EB:141-151` | SAME | 04 | — |
| C13 | slot evidence :873-877, recorded in `result["slot_evidence"]` before any slot check | `ER:371-374` writes the same dict to `slot-evidence.json`, compares nothing | SAME | 04 | **AST-equal** to the frozen expression (`test_r7.py::test_pf4_slot_evidence_is_recorded_exactly_as_the_frozen_end`, frozen file hashed against its closure pin); recorded even when a check below fails (negative tests). Same four fields |
| C14 | priority readback: reference and every background nice == 10 :878-879 | END records it only; it enforces nice == plan nice (10) in the parent (`ER:298` → `FP:13`) and in every worker before readiness (`EB:113` → `FP:13`) | STRICTER | 04 (all 10) | keep: the pinned reporting priority (`FP:13`). After the workers' own checks the readback can differ only through an external renice, which changes the load END would measure under. Test `test_pf4_priority_readback_still_required`; mutant PF06 |
| C15 | affinity readback :880-887: one readback per mask, each a **non-empty subset** of its pinned mask, masks pairwise disjoint (r6 :876: *equal* to the mask) | `ER:371-374` records only. Workers are pinned to their mask (`EB:115-116`, mask ∈ the pinned layout), then narrowed per tier to `search_cpus[:width]` (`TB:237-238`, widths 1/1/1/3/5; `KB:99-100`, width 5). Disjoint masks: `FP:21`, `TE:77-78` | STRICTER (r6: refused the legitimate 04 run) | 04 failed on r6 | **FIXED** (runner edit, kept as ruled in PF-4 item 1). Every readback the frozen code can produce passes; a worker outside its slot (it would load the reference slot or another slot) is refused. Tests: observed 04 readbacks pass; full-mask readbacks pass; next-slot CPU, reference CPU, empty readback, overlapping masks and a count mismatch all refuse. Mutants PF01-PF05 |
| C16 | `loaded_hold` :890-918: END's warm-up loop verbatim (`warm-{lap}-{offset}` guarded blocks, `k4s_work`) for `--hold-seconds`; phase label `preflight-hold`. Diagnostic: guarded sleep blocks | `ER:375-387` for `warmup_seconds`, then `measure()` (never called here; RC-2); phase `reference-warmup` | SAME | never | — (the guard and validators ignore phase names: `TE:185` only records them; `FV:230-283` never reads them) |
| C17 | `monitor_stop` :919-922 | `ER:392-394` | SAME | never | — |
| C18 | `guard_samples` :923-928: ≥ `min_samples` rows with `utc` ≥ admission `utc`, read through safe_input (cap 1 GiB) | none | S5-ONLY | never | keep: RC-2 (≥ 60 1 Hz samples). Field exists (`TE:185`). Size: 04 l00 wrote 11,452,165 B for 81 rows (≈ 141 KB/row), so ≈ 185 MB for a 1200 s hold, about 5× under the cap. Fewer than 60 rows in a ≥ 120 s hold means the monitor stopped, which END fails too (`ER:338-340`) |
| C19 | `frozen_guard_validators` :929-935 | `ER:395-399`, `FV:230-283` | SAME | never | — |
| C20 | `mhz_comparison` :936-956: r7 compares hold rows from (first hold row + `warmup_seconds`) on; fewer than 2 such rows → recorded `unavailable`, not gated; gate only for reference-work runs | `ER:375-403`: compares only the `measure()` rows (`reference-speed`/`-deadlines`, `FP:59-60`), which start after the ≥ 300 s warm-up; fails closed (`ER:402-403`) | SAME (r6: STRICTER and LOOSER) | never | **FIXED.** r6 relabelled **all** hold rows, so it compared the warm-up rows END leaves out ("an idle reference core would begin its timed work at a different clock", `FR:135-136`). There was no measurement-integrity reason for that. What remains is unavoidable: RC-2 forbids `measure()`, so the comparison runs over warm-up-type `k4s_work` load. The gate is END's own Amendment 1 rule. Hosts use 600 s (03) and 1200 s (04) holds, which leave 300 s and 900 s of compared rows. Tests `test_pf4_mhz_*`; mutants PF08-PF11 |
| C21 | `post_pins` :957-961 (`validate_bundle`, native re-hash, `executing_sources`) | `ER:404-406` | SAME | never | — |
| C22 | `loaded_modules_check` :962, :583-595: every runtime module loaded in this process is a closure file or a bundle `runtime_files` member re-read through safe_input with its pin | none (`TB:450-469` `validate_bundle` hashes `runtime_files` on disk, `RC:22-33`) | S5-ONLY | never | keep: S5-F1 + P2-1. **Offline proof for this runtime** (`pf4-evidence/loaded-modules-scan.txt`): all 4052 `.py`/`.so` under the staged runtime are pinned (closure or `runtime_files`). safe_input's read gate over all 4023 non-closure `.py` refuses only 8 `*_games.py` (outcome-name family `games`), and none of them is imported by the END chain (grep of import edges). This is a superset of what can load, so the check cannot refuse the production run |
| C23 | `cleanup` :966-974 (frozen `cleanup_steps`; a primary failure is never replaced) | `ER:252-279`, `ER:231-239` | SAME | 03, 04 | — |

## D. After the body (`run()` tail, `verdict`)

| # | S5 check (r7) | Frozen END | Verdict | Exercised | Disposition / reason |
|---|---|---|---|---|---|
| D1 | listings after; registry and attempt parent unchanged; attempt parent empty :1126-1130, :1021-1023 | none | S5-ONLY | 04 (unchanged) | keep: RC-2 / RC-9 |
| D2 | `summaries` :1132-1136 (bus, blocks, MHz, sshd; never fail) | none | S5-ONLY | 04 | non-gating health record (RC-2: "recording the cumulative and windowed bus and per-core MHz") |
| D3 | `copy_guard_sources` :998-1013, :1137-1141; a refused copy fails the run :1025 | the K4S END does not copy them (the TIERS `FR:217-226` does, following links) | S5-ONLY | 04 (2 files) | keep: RC-2 (push the results), P2-1 descriptor gate. Size: `allowlist-occurrences.jsonl` was 22,386 B after 81 s, so ≈ 0.35 MB at 1200 s against the 64 MiB role cap |
| D4 | `verdict` :1028: an error recorded with no check row open fails the run | any body exception writes `failure.json` and the seal is `failed` (`ER:222-230,240-248`) | SAME (r6: LOOSER) | — | **FIXED.** r6 sealed `passed` with exit 0 when, for example, the frozen background `__exit__` (`RL:249-256`) raised after `loaded_hold` ended: no row was open and the rest of the checks never ran. Test `test_pf4_error_outside_any_check_fails_the_run`; mutant PF12 |
| D5 | 04 only: no sshd-count rise during the hold, `sshd_summary` :688-694, :1024, :1029 | the guard flags `console_user`, foreign compute/activity and ssh-family **CPU budget** (`ssh_budget.py:111-117`, `FV:223`); it does not count sshd processes | STRICTER | 04 (vacuous: no hold) | keep: RC-2 ("with no login in between"), RC-7. The P2-3 bus band must be measured without a login. **Residual false-positive mode (not changed; coordinator's call):** the census has process names only (`TE:131-138`, comm), so a pre-auth `sshd` fork from any TCP connection to :22 (a scanner, another user) counts as a login. It fails the 04 preflight without consuming an END attempt. 04 l00 showed sshd = 1 in all 81 rows |
| D6 | `binding` :1035-1039 (reference work, all slots ready, measured loaded span ≥ 60 s / 900 s) | none | S5-ONLY | — | keep: P2-3 (it sets the mode, not pass/fail; S7 requires binding). Note: a 04 hold of exactly 900 s can never be binding (the span is < 900 s). The runner uses 1200 s |
| D7 | `bus_band` / `bus_gate` :640-645, :1040-1043 | none, but the guard itself fails at > 1 % cumulative bus (`system_bus.py:26-30` → `FV:192-193,224` `op1_interference`) | S5-ONLY | — | keep: P2-3 (≤ 0.3 proceed, ≥ 0.7 stop, between: coordinator). Applied by S7 |
| D8 | seal, scope `K4S-END-PREFLIGHT`, exit code :1145-1149 | `ER:240-248` seal `complete`/`failed` | S5-ONLY | 03, 04 | keep: the RC-9 receipt S7 consumes. `verify-received` (05-side, :1154-1213) is outside this table: it is no host check |

---

## E. Dynamic-state assumptions (the class that failed twice)

| Kind | Where in S5 | Assumption | Status |
|---|---|---|---|
| CPU affinity readback | C15 :875, :880-887 | readback == mask (r6) | **wrong**, fixed: frozen code narrows per tier |
| CPU affinity set | C6 :805 | parent narrowed to `search` before spawn | SAME as END (`ER:303`); workers re-pin (`EB:116`) |
| nice / scheduler | A3 :389-390 (start); C14 :878-879 (readback) | 10 / SCHED_OTHER throughout | END enforces at start in the parent and every worker. The readback is kept (C14) |
| hostname | A2 :1048 (`/usr/bin/hostname`, rc-checked); C5 :797 | equals `platform.node()` | both read the uname nodename; exercised |
| file existence | C4 (guard side files and STOP absent); B1/D1 (attempt parent empty); A12 (out dir absent) | fresh guard job, empty parent, fresh out | ruled (RC-3, RC-2/RC-9). **04's pf00 guard job is no longer fresh** (C4 flag) |
| file permissions / writes | C8 (frozen code writing in the runtime) | the runtime is read-only | the RO-1 host step made the es_common `results` dir; 04 l00 passed `backend_and_corpus` |
| frozen-written files read through safe_input | C11, C18, C20 (`F.P.read_lines`), D3, seal | regular, single link, under the caps | exercised: `guard-admission.json`, the 2 side files, `capacity.jsonl` (sealed) on 04; sizes in C18/D3 |
| process tables | D5 sshd count; C10/C12 owned PIDs for the guard | a count rise means a login | kept with a written residual (D5) |
| clocks | C10 60 s checkpoint timeout; C16 `time.monotonic` hold; C18 wall `utc` vs admission `utc`; C20 census `timestamp` (system-wide monotonic) for the warm-up cut | — | SAME as END, or monotonic. The C20 cut uses only census timestamps (one clock) |
| durations | A5 hold minimum; D6 measured span ≥ MIN_LOADED | — | the 04 hold must exceed 900 s by a margin (1200 s in use) |
| environment | B6 `os.environ` replaced | the END runs under the same checked env | SAME (frozen-exec) |
| loaded modules | C22 | every loaded runtime module is pinned and passes safe_input | proved offline for this runtime (`pf4-evidence/`) |
| MHz source | C20 | `/proc/cpuinfo` has every occupied CPU | same frozen `compare_mhz` (`FP:56-59`) |

## F. Every STRICTER row and its disposition

| # | Check | Disposition |
|---|---|---|
| A2 | host ∈ {03, 04} | kept: END runs only there (RC-6/RC-9) |
| A8 | fixed 74314eda anchor | kept: identity pin S5-F1 |
| A10 | bundle stamp / production receipt | kept: S10-F4/S5-F2 |
| B2 | compare-bundle stamp, evidence path | kept: RC-3, S5-F2 |
| B3 | native/corpus descriptor gate | kept: P2-1/S5-F2 (passed on both hosts) |
| B4 | guard repo verified + Q3 seeds | kept: frozen-reader ruling, P2-4, Q3 |
| B5 | repository clone verified | kept: frozen-reader ruling, P2-4 |
| B7 | closure, DELTA and inventory pinned before import | kept: S5-F1, r4 L6, F5 |
| B8 | END modules are the verified files | kept: S5-F1 |
| C2 | identity equalities | kept: F5 identity pins |
| C4 | fresh guard job | kept: RC-3. 04 needs a fresh `-pf01` job and bundle |
| C11 | admission file through safe_input | kept: P2-1 (passed on 04) |
| C14 | nice readback == 10 | kept: pinned priority `FP:13` |
| C15 | affinity readback | **fixed** to the ruled subset + disjoint form (PF-4 item 1) |
| D5 | 04 sshd-count rise | kept: RC-2/RC-7. False-positive residual recorded for the coordinator |

Fixed rows that were not "STRICTER" in r7: C20 (r6 STRICTER and LOOSER), D4 (r6 LOOSER).
