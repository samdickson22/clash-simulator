# E4-v3 addendum r2 (DRAFT): search-tier capacity measurement

Draft r2 2026-10-10, PREREG revision author (Opus) for coordinator `0523ae6f`. It revises
`E4-V3-ADDENDUM-DRAFT.md` by applying conditions C4, C6, C7, C8 and C10 of
`../REVIEW-PREREG-SEARCH-TIERS-20261010.md` (map: `../C1-C14-RESPONSE.md`). Linux-prepared text only: no script has
been written yet, nothing has run on the Mac, and nothing is committed. This addendum **adds** one sub-session to
the existing [B6 runbook](RUNBOOK.md). It changes none of its pins, gates or scripts. It supplies the Mac inputs
of [PREREG-SEARCH-TIERS-r2-DRAFT §6–7](../PREREG-SEARCH-TIERS-r2-DRAFT.md) and **inherits every RUNBOOK
restriction**:
- replay only, of train recordings;
- no actuator, taps, login, client memory, networking to the client, ladder or heldout;
- no detection evasion;
- nice 10;
- a fresh checkout, build and output directory.

It runs only in a session Sam has specifically authorised. It measures; it changes no production default. Its
committed `tiers-summary.json` is what opens the fleet outcome barrier (PREREG §6.6).

## A. What it answers

For each tier — S and K0c (1 thread each, separate corpora), K2 (2 workers + main) and K4 (4 + main):
- the loaded speed ratio r_T against the loaded fleet reference, on complete decisions;
- deadline-mode equivalence at 200 ms against the fleet's 200 ms and 160 ms references (gate 6);
- whether perception keeps up while T runs;
- arm64 exactness, including belief and RNG;
- GC/poll overlap against scheduled polls;
- for S, the student forward's cost on CPU and on MPS.

Those inputs fully determine the PREREG's tier rule. The fleet game outcomes never enter the Mac session, and they
are still sealed when it runs (PREREG §6.6).

## B. Additional staging (adds about 10 min to RUNBOOK staging)

0. **Exclusive Mac.** Other agent threads use the Mac mini.
   - Take the **coordinator lock** for the session before staging; no other thread may run work on the Mac while
     it is held.
   - Run a **5-minute pre-session census** at 1 Hz: no foreign process above **0.2 core** (averaged over the 5 min).
     A failed census delays the session; it is not a technical failure and costs no repeat.
   - §F's in-session detector still applies.
1. **A tiers bundle,** pinned in `configs/tiers-pins.json`, frozen with the PREREG (in the TIERS manifest, before any
   fleet reporting game):
   - the tier source tree (the K2/K-v2 collector, S1 coarse-first/proposal code, `cached_policy.py`, `belief.py`,
     `gc_window.py`);
   - R3a EMA `37509a43…` with calibration `e3003533…`;
   - v1 `d77005d5…`;
   - the speed corpora (300 sealed public histories per tier, K0c and S separate), with the pooled loaded fleet
     reference walls (no-deadline), the fleet deadline-mode rates at 200 and 160 ms, and Linux reference
     actions/scores;
   - the 125 belief histories with Linux posterior, weights, cumulative order, resource ledger, samples and RNG
     state, deadline ON and OFF;
   - the 2,000-state student agreement set, with fleet-CPU logits;
   - the replay packet list for **§D7**.
2. **One new script,** `scripts/measure_tiers.py`, plus the frozen tiers reducer and the technical-failure
   classifier (§F). All three are written and independently reviewed, and frozen **before any fleet reporting
   game**. Constraints:
   - standard library + NumPy + Torch + **pinned `psutil`** (or per-CPU ticks read via `host_processor_info` with
     ctypes, if psutil is not pinned);
   - it imports the tier source exactly as pinned;
   - it **refuses** to run unless `--sam-authorized-replay` is set, the platform is Darwin/arm64, and every pin
     matches;
   - like `measure_mac.py`, it has no CLI for any live input or emulator address.
3. **The load generator:**
   - It reuses RUNBOOK's spawned paced replay perception process.
   - If the RUNBOOK's blocked v4 selection prerequisites are still unmet, it uses the qualified
     `v3-body-hud-only` MPS fallback, and every tier receipt is labelled **PROVISIONAL-LOAD**.
   - If Sam happens to have the reference emulator idle-running, its state is recorded **from the process table
     only (`ps`)**: no adb, gRPC, socket connection, window or screen capture. The harness never starts or touches
     it.

## C. Build (adds about 10 min; reuses RUNBOOK's toolchain)

- `build_mac.sh` already builds the GIL-release W library from source.
- The addendum adds the **tier native from the frozen tier Rust source** (the Linux provenance build is
  `44874fd6`), built `--locked`, aarch64-apple-darwin, with empty RUSTFLAGS, into a separate fresh build
  directory.
- `build-tiers.json` records the measured Mac SHA, the toolchain, and the output of `file` and `otool`.
- No Linux or fleet binary is copied.

## D. Measurement steps (in order; stop rules in brackets)

**Work unit** (D3, D5): the complete no-deadline decision from sealed public history — belief preparation, candidate
generation, root, scoring with the tier's workers, Python reduction and action selection, and for S/K0c the cached
forward and top-8 proposals. Exactness covers the final action and scores. For S and K0c, a corpus state whose Mac
forward output (gate decision or top-8 list for S; top-8 list or T=1 fallback sample for K0c) differs from Linux
within PREREG §7.3's tolerances is still timed but exempt from action equality. Such states are counted per tier. If
they exceed 0.5% of a tier's corpus, that tier fails gate 3. Any other corpus action mismatch, or a score mismatch
beyond ARM64-NEAR-EXACT, fails gate 3 for that tier (for all tiers if it is in the single-thread scorer).

| Step | What | Size | Approx. time |
|---|---|---|---:|
| D0 | Identity: `hw.model`, chip, `hw.perflevel0/1.physicalcpu`, RAM, macOS, `pmset -g therm`, Python/Torch/rustc versions | — | 2 min |
| D1 | **Exactness:** 125 states of screen8 actions/candidates/scores against Linux; 1/2/4-worker equality; zero-budget root immutability. [A single-thread action, candidate, score or root mismatch ⇒ **all** tiers infeasible. A mismatch only in 2/4-worker equality ⇒ K2/K4 infeasible.] | 125 × 3 | 8 min |
| D1b | **Belief/RNG exactness:** 125 histories, posterior, weights, cumulative order, resource ledger, samples and RNG state, deadline ON and OFF, as in the K-v2 belief qualification. [Any mismatch ⇒ **all** tiers infeasible, subject to the near-exact rule below.] | 125 × 2 | 4 min |
| D2 | **Student agreement:** gate decision + ordered top-8 against fleet-CPU logits, on CPU (1 thread) and on MPS (synchronised). [<99.5%, or a gate disagreement not within 1e-4 of the threshold or an exact tie, or a top-8 order swap whose fleet logits differ by >1e-4 ⇒ that backend fails; both fail ⇒ S infeasible] | 2,000 × 2 | 3 min |
| D3 | **Unloaded speed:** no-deadline complete-decision work for S, K0c, K2 and K4 | 100 states each | 8 min |
| D4 | **Free capacity:** start the replay load; 5-min thermal warm-up; then 3 min of 1 Hz per-core idle sampling (per-CPU ticks mapped to P/E clusters), load average, thermal, and replay FPS/processed % | — | 8 min |
| D5 | **Loaded speed,** still under load: corpus work for S, K0c, K2, K4, each ≥300 states and ≥5 min, in **rotated tier blocks of 50 states**; replay FPS/processed % recorded *during each tier*. [FPS <18 or processed <95% during T ⇒ T infeasible] | 300 × 4 | 22 min |
| D5b | **Deadline-mode corpus check (gate 6),** under load: each tier's corpus at **200 ms** / 8 ms reserve, honest timer; per-state cutoff, fallback and no-complete-play | 300 × 4 | 10 min |
| D6 | **Loaded student forward:** CPU and MPS, p50/p95/p99/max, with a separate cold first forward; perception p95 recorded during each. [CPU and MPS both p99 >20 ms ⇒ S infeasible] | 2,000 × 2 | 4 min |
| D7 | **Deadline-mode tier cells** under load: 1,000 replay packets × {K0c, S, K2, K4}, 200 ms / 8 ms reserve, honest timer from packet entry. Record p50/p95/p99/max, cutoff, fallback, no-complete-play, >200 ms overruns and >208 ms cut returns. **GC trace:** every collection's start/end monotonic time, generation, scheduled poll time, opportunity flag and resulting poll delay | 4,000 decisions | 15 min |
| D8 | **GC variant:** repeat D7's GC trace with `gc.freeze()` for **every tier that passes gates 1–3 and 5**; record retained RSS and peak RSS | up to 4 × 1,000 | ≤15 min |
| D9 | Stop the load; run the frozen reducer; write `tiers-complete.json` and `tiers-summary.json` | — | 2 min |

**Near-exact rule (D1, D1b).** If actions and candidates match 125/125 and every score differs by ≤ 1e-12 relative,
the result is **ARM64-NEAR-EXACT**: it passes, with disclosure. For D1b the same applies to belief floats (posterior,
weights) iff every discrete output (support, i.e. which hypotheses have nonzero weight; cumulative order; ledger;
samples; RNG state) matches exactly, and every nonzero float satisfies |mac − linux| ≤ 1e-12 · max(|mac|, |linux|).
The maximum relative difference is reported per history, against history length. Anything else fails.

**Total: about 100 min.** With staging and build, the addendum adds about **2 h** to the 60–90 min RUNBOOK
session, so **about 3–3.5 h** for both. Run alone (if the v4 selection is still blocked), it takes about 2–2.5 h.

**Derived definitions (computed by the frozen reducer, full float precision, no rounding):**
- **Per-state Mac wall** = the median over that state's repeats in D5.
- **r_T = min(median per-state ratio, Σ fleet wall / Σ Mac wall, fleet p90 wall / Mac p90 wall)**, with the
  fleet wall the pooled loaded reference; p10 of the per-state ratio is also reported (gate 1 needs ≥ 0.70).
- **Gate 6:** T's D5b cutoff and no-complete-play rates are each ≤ the fleet deadline-mode rate at the cell's
  deadline (200 ms for 1.0, 160 ms for 0.8) + 2 pp absolute; failure in the 1.0 cell moves T down one cell; below
  0.8, T is infeasible.
- **Opportunity:** a scheduled poll at the live search/policy cadence, computed from packet timestamps. A
  **maintenance-delayed poll** starts >25 ms after its schedule. **Gate 4:** delayed polls ≤ 1% of opportunities,
  and no in-window pause that would add a charged tick (a poll start >50 ms past schedule), with default GC or with
  the `gc.freeze()` variant.
- **`gc.freeze()` variant:** `gc.freeze()` is called **once, after warm-up** (after D4's warm-up and before the
  tier's first D8 decision), with **default thresholds** unchanged.

**Configuration fidelity:**
- Priority and QoS are exactly what the live runtime uses: nice 10, inherited QoS, as in the 2026-10-08 Mac
  qualification.
- Torch, BLAS and OpenCV run on 1 thread.
- The workers are native threads.
- If K4's r_5 is below 0.8, an extra **descriptive** K4 run with search threads at `QOS_CLASS_USER_INTERACTIVE`
  is allowed, to tell scheduling apart from capacity. It cannot change r_5 without a new reviewed amendment.

## E. Receipts and derived values

- **Raw data:** `tiers-identity.json`, `presession-census.jsonl`, `build-tiers.json`, `exactness-tiers.json`,
  `belief-exactness.json`, `student-agreement.json`, `speed-unloaded.jsonl`, `capacity.jsonl`,
  `speed-loaded.jsonl`, `deadline-corpus.jsonl`, `student-forward.jsonl`, `decisions-tiers.jsonl`,
  `gc-trace.jsonl`, `gc-freeze.jsonl`, `failure.json` (if any), `tiers-complete.json`.
- **Derived values** go in `tiers-summary.json` and are computed by the frozen reducer:
  - r_S, r_K0c, r_K2, r_K4, each with the three component statistics and p10/p90;
  - gate-6 rates and the resulting cell per tier;
  - free P / free E;
  - per-tier feasibility flags for gates 1–6, with the reason for each;
  - the exactness class (EXACT, ARM64-NEAR-EXACT or FAIL);
  - the chosen student backend;
  - GC-delayed-poll rate and maximum in-opportunity poll delay, for default GC and for freeze.
- Exit 0 means the session completed, not that the gates passed. Nothing is overwritten. Partial runs keep all
  raw data.

## F. Pre-listed technical failures that allow one repeat session

A repeat session is allowed only for these failures:
- a crash or exception in the harness or load generator;
- a host sleep or reboot;
- `pmset` reporting a CPU speed limit <100% **before** D4 begins;
- a foreign process using >1 core for >60 s, identified by the 1 Hz census;
- a pin mismatch caused by staging.

**Classification is mechanical.** The frozen classifier reads it from receipts only (exception trace, `pmset`/uptime
log, the census). A human cannot declare a technical failure. If fleet outcomes have already opened under the
14-day escape (PREREG §6.6), an independent reviewer confirms the classifier's output before any repeat runs.

The repeat uses fresh output directories. The PREREG then uses the **minimum** r_T and the worst value of every
other gate input across valid sessions. Low speed, failed gates or "noisy" results are **not** technical failures.

## G. Not in scope; provisional status

- Any production default change, including the W default, root count, deadline, fallback, decoder admission or
  `planner_total_delay_ticks`.
- Any game outcome.
- Formal E4 / T9.
- Emulator control.
- Live play.

**A selection made from a replay-only session is PROVISIONAL (emulator-off).** It cannot be activated until
formal E4/T9, with the emulator running, re-measures r_T, gate 6, FPS/processed, GC and the student p99 on the same
corpora with the same frozen scripts. Every §6.3 gate is re-applied, using the worst value of each across all valid
sessions. Formal E4 must be amended to include these measurements before it runs.

The selected tier's activation therefore needs:
- the amended formal E4 (emulator-on) re-measurement above;
- the L2-v4 amendment (one root; the tier's fallback policy and adapter), before any L2-v4 confirmatory game;
- coordinator review.
