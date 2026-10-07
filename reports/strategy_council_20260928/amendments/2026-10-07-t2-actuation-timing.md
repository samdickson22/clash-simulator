# Amendment 2026-10-07: v4 actuation timing on the offline renderer (coordinator decision, 127x05)

Decided by the 127x05 coordinator thread after reading `live-loop/v4/T2-RESULTS.md` (Mac copy, 16:16 PDT) and
`live-loop/v4/DESIGN.md` §2.5, §2.7, §2.8 and §5.3. Owner mode: no question to Sam.

## The finding

- Persistent gRPC touch injection: 320/320 accepted, two-tap p95 26.9 ms. Transport is not the problem.
- The pinned probe hook schedules each touch at current tick + 2 and adds the 20-tick live-command age, so native
  acceptance lands about 22 ticks (~1.1 s) after submission. Pixels then see the HUD change quickly:
  316/320 detections within 600 ms of the probe's first observed acceptance, pixel-minus-native p95 39.9 ms.
- The 600 ms verifier and 800 ms rollback in DESIGN were written as if acceptance were near-instant. On this backend
  they would declare every play failed and retry it: the R2 double spend again, in a new form.

## Decision: keep the hook, make the timing contract backend-relative (option B)

Do **not** change the APK, the hook or its command age, and do not re-attest.

1. **Verify window.** Measure from native acceptance, not from submission. Per backend `b`, T2 measures
   `D_b`, the submission→acceptance latency (p50, p99), from the retained trials. The verifier deadline is
   `submission + D_b,p99 + 600 ms`. The pending-spend rollback fires at `deadline + 200 ms`. The retry rule
   (at most one, only if the card is still present and affordable) applies only after the deadline.
2. **T2 gate, restated.** "Pixel verification detects acceptance within 600 ms at ≥99% sensitivity and specificity"
   now means within 600 ms of native acceptance, evaluated inside the window above. Recompute it from
   `actuation/trials.jsonl`; no new trials are needed for sensitivity. The current 316/320 (98.75%) is just below
   the bar. Report the four misses individually (late frame, HUD reader miss, or genuine slow acceptance) before
   anyone calls the gate met or failed. Specificity and the stale re-tap reproduction come from the experiment
   still running.
3. **Ledger.** The pending-command ledger (DESIGN §2.5) already spends at submission. Its rollback timer becomes
   the backend-relative value from item 1. One outstanding command at a time is unchanged, so a 1.1 s window
   costs tempo only if a second play is wanted in that window. Measure how often that happens; don't assume it.
4. **Planner.** The search must know its actions land `D_b` later. Rollouts from a decision at tick `t` apply our
   chosen action at `t + D_b` (in ticks), with the pending command already in the root state. This is a player
   change. Validate it in the simulator first: sim games with a 22-tick command delay, delay-aware vs
   delay-unaware planning, pre-registered.
5. **L2-v4 arms (DESIGN §5.3).** O and P share the renderer and P4, so the delay cancels in the primary P − O.
   Add arm **S-d**: the simulator with the same 22-tick command delay (and the delay-aware planner). Then O − S-d
   is the engine gap and S − S-d the latency cost. This is cheap and removes a confound the L2 analysis did not
   price.

## Why not option A (shorten the hook's command age)

- It modifies and re-attests the private-server client, the ToS/IP-sensitive artifact, for a timing that would then
  match nothing real.
- The official client also schedules commands ahead of the server tick. Its delay is unknown and probably not
  near zero. A player that can't handle ~1 s command latency would fail at L3 anyway. The contract has to be
  per backend and measured; L3 measures its own `D_b`.
- It would break comparability with L1/L2 evidence collected under the same hook.

## Consequences

- `actuator.py` stays unintegrated until items 1–3 are implemented and T2's restated gate is recomputed. The
  implementation is assigned after the current T2/T1 worker (Mac thread child) finishes, to avoid two writers on
  `actuator.py`.
- T1 collection is unaffected: it records schedule receipts and exact execution ticks, not verifier outcomes.

## Addendum: T1 Phase A heldout coverage (prospective, before any Phase A match)

T1-PROGRESS projects about 1,050 heldout opponent events at the 24 emulator-hour cap, below DESIGN's 1,500 minimum.
Decision: Phase A runs until the frozen heldout split holds **at least 1,500 opponent events and at least 20
matches**, or until **36 active emulator-hours**, whichever comes first. The stopping rule counts events only; it
never looks at labels' content or any model output, and heldout membership stays fixed by the frozen seed split. The
80/10/10 split is unchanged. If 36 hours pass without meeting coverage, report it; any further acquisition needs
a new decision.
