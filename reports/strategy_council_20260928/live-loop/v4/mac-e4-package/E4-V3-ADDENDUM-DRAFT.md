# E4-v3 addendum (DRAFT): search-tier capacity measurement

Draft 2026-10-10, research planner (Opus) for coordinator `0523ae6f`. Linux-prepared text only: no script has
been written yet, nothing has run on the Mac, and nothing is committed. This addendum **adds** one sub-session to
the existing [B6 runbook](RUNBOOK.md). It changes none of its pins, gates or scripts. It supplies the Mac inputs
of [PREREG-SEARCH-TIERS-DRAFT §6–7](../PREREG-SEARCH-TIERS-DRAFT.md) and **inherits every RUNBOOK restriction**:
- replay only, of train recordings;
- no actuator, taps, login, client memory, networking to the client, ladder or heldout;
- no detection evasion;
- nice 10;
- a fresh checkout, build and output directory.

It runs only in a session Sam has specifically authorised. It measures; it changes no production default.

## A. What it answers

For each tier — S/K0c (1 thread), K2 (2 workers + main) and K4 (4 + main):
- the loaded speed ratio r_T against the fleet;
- whether perception keeps up while T runs;
- arm64 exactness;
- GC/poll overlap;
- for S, the student forward's cost on CPU and on MPS.

Those inputs fully determine the PREREG's tier rule. The fleet game outcomes never enter the Mac session.

## B. Additional staging (adds about 10 min to RUNBOOK staging)

1. **A tiers bundle,** pinned in `configs/tiers-pins.json`, frozen with the PREREG:
   - the tier source tree (the K2/K-v2 collector, S1 coarse-first/proposal code, `cached_policy.py`, `belief.py`,
     `gc_window.py`);
   - R3a EMA `37509a43…` with calibration `e3003533…`;
   - v1 `d77005d5…`;
   - the speed corpora (3 × 300 sealed states), with per-state fleet reference walls and Linux reference
     scores/actions;
   - the 2,000-state student agreement set, with fleet-CPU logits;
   - the replay packet list for §D5.
2. **One new script,** `scripts/measure_tiers.py` (to be written and independently reviewed before the session).
   Its constraints:
   - standard library + NumPy + Torch only;
   - it imports the tier source exactly as pinned;
   - it **refuses** to run unless `--sam-authorized-replay` is set, the platform is Darwin/arm64, and every pin
     matches;
   - like `measure_mac.py`, it has no CLI for any live input or emulator address.
3. **The load generator:**
   - It reuses RUNBOOK's spawned paced replay perception process.
   - If the RUNBOOK's blocked v4 selection prerequisites are still unmet, it uses the qualified
     `v3-body-hud-only` MPS fallback, and every tier receipt is labelled **PROVISIONAL-LOAD**.
   - If Sam happens to have the reference emulator idle-running, its state is recorded; the harness never starts
     or touches it.

## C. Build (adds about 10 min; reuses RUNBOOK's toolchain)

- `build_mac.sh` already builds the GIL-release W library from source.
- The addendum adds the **tier native from the frozen tier Rust source** (the Linux provenance build is
  `44874fd6`), built `--locked`, aarch64-apple-darwin, with empty RUSTFLAGS, into a separate fresh build
  directory.
- `build-tiers.json` records the measured Mac SHA, the toolchain, and the output of `file` and `otool`.
- No Linux or fleet binary is copied.

## D. Measurement steps (in order; stop rules in brackets)

| Step | What | Size | Approx. time |
|---|---|---|---:|
| D0 | Identity: `hw.model`, chip, `hw.perflevel0/1.physicalcpu`, RAM, macOS, `pmset -g therm`, Python/Torch/rustc versions | — | 2 min |
| D1 | **Exactness:** 125 states of screen8 actions/candidates/scores against Linux; 1/2/4-worker equality; zero-budget root immutability. [Any mismatch ⇒ K2/K4 infeasible; continue with S/K0c] | 125 × 3 | 8 min |
| D2 | **Student agreement:** gate decision + ordered top-8 against fleet-CPU logits, on CPU (1 thread) and on MPS (synchronised). [<99.5%, or a disagreement not within 1e-4 of the threshold or an exact tie ⇒ that backend fails; both fail ⇒ S infeasible] | 2,000 × 2 | 3 min |
| D3 | **Unloaded speed:** no-deadline corpus work for r_1 (incl. the student forward), r_3 and r_5 | 100 states each | 6 min |
| D4 | **Free capacity:** start the replay load; 5-min thermal warm-up; then 3 min of 1 Hz per-core idle sampling (psutil per-CPU mapped to P/E clusters), load average, thermal, and replay FPS/processed % | — | 8 min |
| D5 | **Loaded speed,** still under load: corpus work for r_1, r_3, r_5, each ≥300 states and ≥5 min, in rotated order; replay FPS/processed % recorded *during each tier*. [FPS <18 or processed <95% during T ⇒ T infeasible] | 300 × 3 | 18 min |
| D6 | **Loaded student forward:** CPU and MPS, p50/p95/p99/max, with a separate cold first forward; perception p95 recorded during each. [CPU and MPS both p99 >20 ms ⇒ S infeasible] | 2,000 × 2 | 4 min |
| D7 | **Deadline-mode tier cells** under load: 1,000 replay packets × {K0c, S, K2, K4}, 200 ms / 8 ms reserve, honest timer from packet entry. Record p50/p95/p99/max, cutoff, fallback, no-complete-play, >200 ms overruns and >208 ms cut returns. **GC trace:** every collection's start/end monotonic time, generation, scheduled poll deadline, opportunity flag and resulting poll delay | 4,000 decisions | 15 min |
| D8 | **GC variant:** repeat D7's GC trace for the feasible tier with the most cores, with `gc.freeze()` after warm-up; record retained RSS and peak RSS | 1,000 | 5 min |
| D9 | Stop the load; write `tiers-complete.json` | — | 2 min |

**Total: about 70 min.** With staging and build, the addendum adds about **1.5 h** to the 60–90 min RUNBOOK
session, so **about 2.5–3 h** for both. Run alone (if the v4 selection is still blocked), it takes about 1.5–2 h.

**Configuration fidelity:**
- Priority and QoS are exactly what the live runtime uses: nice 10, inherited QoS, as in the 2026-10-08 Mac
  qualification.
- Torch, BLAS and OpenCV run on 1 thread.
- The workers are native threads.
- If K4's r_5 is below 0.8, an extra **descriptive** K4 run with search threads at `QOS_CLASS_USER_INTERACTIVE`
  is allowed, to tell scheduling apart from capacity. It cannot change r_5 without a new reviewed amendment.

## E. Receipts and derived values

- **Raw data:** `tiers-identity.json`, `build-tiers.json`, `exactness-tiers.json`, `student-agreement.json`,
  `speed-unloaded.jsonl`, `capacity.jsonl`, `speed-loaded.jsonl`, `student-forward.jsonl`,
  `decisions-tiers.jsonl`, `gc-trace.jsonl`, `gc-freeze.jsonl`, `failure.json` (if any), `tiers-complete.json`.
- **Derived values** go in `tiers-summary.json` and are computed by a frozen reducer:
  - r_1, r_3 and r_5, each with p10/p90;
  - free P / free E;
  - per-tier feasibility flags, with the reason for each;
  - the chosen student backend;
  - GC-delayed-poll rate and maximum in-opportunity pause, for default GC and for freeze.
- Exit 0 means the session completed, not that the gates passed. Nothing is overwritten. Partial runs keep all
  raw data.

## F. Pre-listed technical failures that allow one repeat session

A repeat session is allowed only for these failures:
- a crash or exception in the harness or load generator;
- a host sleep or reboot;
- `pmset` reporting a CPU speed limit <100% **before** D4 begins;
- a foreign process using >1 core for >60 s, identified by the 1 Hz census;
- a pin mismatch caused by staging.

The repeat uses fresh output directories. The PREREG then uses the **minimum** r_T across valid sessions. Low
speed, failed gates or "noisy" results are **not** technical failures.

## G. Not in scope

- Any production default change, including the W default, root count, deadline, fallback, decoder admission or
  `planner_total_delay_ticks`.
- Any game outcome.
- Formal E4 / T9.
- Emulator control.
- Live play.

The selected tier's activation still needs:
- the formal E4 (emulator-on) re-measurement of r_T, where the lower value governs;
- the L2-v4 amendment (one root; the tier's fallback policy and adapter);
- coordinator review.
