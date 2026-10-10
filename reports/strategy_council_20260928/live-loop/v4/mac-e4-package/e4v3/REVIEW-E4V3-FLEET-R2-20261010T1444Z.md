# Review round 2: E4-v3 fleet-reference mode and raw host pooling

Independent reviewer for coordinator `0523ae6f`, 2026-10-10 ~14:44 UTC. This continues the E4 part of the T1
round-2 review (`reports/explore/t1/REVIEW-T1-DELTA-REDUCER-20261010T1403Z.md`, `3f2f6a85`), which **rejected** fleet
mode on F1–F4. I am not the E4-v3 author or the T1 author, and I edited none of their files. I worked from the repo
only, with no ssh to 127x01, 03 or 08. The suite ran locally (`python3 -B -m unittest discover -s …/e4v3/tests`):
**44/44 pass**. No game, outcome or fleet host was touched.

**Binding text:** freeze `PREREG-SEARCH-TIERS-FREEZE-20261010.json`. I re-hashed both frozen files and they match:
PREREG r3 `ef0db97a…`, addendum r3 `fc54507d…`, and `spec-pins.json` agrees. I also used review r1 conditions C4–C7
and r2-conformance E2/E4.

## Verdict: **APPROVE_WITH_CONDITIONS**

- The code fixes every round-2 blocker (F1–F4) and both required non-blockers (F5, F6).
- Conditions **A1–A6** must land **before the first reporting-host reference runs**. None of them needs a new
  measurement design.
- A1 is an amendment the coordinator must sign. The code part of A1 and A2 is small, and the rest is binding and
  validation.
- **Rulings on the three amendment-pending items:**
  1. END placement: **accept by signed amendment, with A1.**
  2. MHz gate: **accept, with A3.**
  3. Committed-posterior deadline replay: **accept.** This ratifies round 2; its conditions are verified in code.

## Reviewed bytes: commit `aefc607a9c226cc2f11c1fe9f92cfc21251dda5c`

- The working tree under `e4v3/` equals `aefc607a`. The only extra file is an untracked `REVIEW-RESPONSE.md`, which I
  read but did not review as code.
- 16-hex SHA-256 prefixes:
  - `corpus_contract e62b6df5`, `fleet_pool 5aaa6e1c`, `fleet_profile c6895f0d`, `fleet_reference 06accc55`;
  - `replay_load 2a8da523`, `tier_backend b04d201d`, `measure_tiers ee0fa31a`, `receipts 839a43be`;
  - `telemetry d17c3891` (unchanged since round 2), `FLEET-INPUT-SCHEMA 9ddcc9e1`.
- **T1 bytes cross-checked (read-only):**
  - `ba3dc8b0:receipts/corpus-contract-draft.json`;
  - the working-tree versions of `plan.json` (`compute`, `fleet_reference_schedule`), `supervise.py` (slot masks and
    `mhz.jsonl`) and `barrier.py` (`outcome_release`).

## 1. Round-2 findings

| Item | Status | Evidence |
|---|---|---|
| **F1**: fleet mode cannot start | **Fixed** | See F1 below. |
| **F2**: load is not reporting-equivalent | **Fixed** | See F2 below. |
| **F3**: pooling and the ±5% rule | **Fixed as math** | Two binding gaps remain (A1, A2). See F3 below. |
| **F4**: corpus contract enforcement | **Fixed** | See F4 below. |
| **F5**: in-timer replay setup | **Fixed** | See F5 below. |
| **F6**: S/CPU wrapper | **Fixed** | See F6 below. |

**F1: fleet mode cannot start.**
- `admit_background` (03/05 at nice 19) is now reached only from `corpus_load_worker`, and that worker refuses any
  profile other than `linux-dry-run`.
- `FleetBackground` spawns `fleet_corpus_worker`. Each worker re-runs `pinned_profile`, which takes the host from the
  plan's `compute.hosts` minus `forbidden_hosts`, nice equal to `compute.nice` (10, inherited), SCHED_OTHER, and the
  host's END marker.
- No host name is hard-coded.
- **But fleet mode still has never run end to end** (see A6).

**F2: load is not reporting-equivalent.**
- `slot_layout` slices `physical_cpus[:count*5]` into consecutive 5-core groups. That is byte-for-byte T1's
  `supervise.py` mapping (`physical_cpus[5*slot:5*slot+5]`).
- Normal mode gives 1 + 10 slots; console mode gives 1 + 7.
- Each background slot rotates K0c/S/K2/K4 in 50-state blocks over the full 300 states per tier.
- `activate` narrows each tier to the first 1, 1, 3 or 5 cores of its own mask, which is the reporting arm width.
- There is no perception process, which matches reporting: the simulator games run no perception.
- `--background-cpus` and `--load-cpu` are rejected.

**F3: pooling and the ±5% rule.** This is fixed as math. Two binding gaps remain (A1, A2).

**F4: corpus contract enforcement.**
- `validate_row` is an exact 20-key allowlist, the same set as T1 `ba3dc8b0`'s `row_fields`.
- `strata` is an exact 3-key set, and its bins are recomputed against [3,6] and [1,128].
- `belief_resume` is rejected by the allowlist and again in `history_before`.
- The `"d1" in row` shortcut is reachable only under `linux-dry-run`.
- The Mac path now runs the same `validate_row` on packet rows and speed rows.

**F5: in-timer replay setup.**
- `prepare_work` deep-copies the posterior, `info`, `pending` and `d1_before` before `start`.
- `replay_setup_seconds` is recorded per row.
- `check_d1` runs after `elapsed`.
- The opponent, the pre-root RNG and the root-digest checks also run after the timer.

**F6: S/CPU wrapper.**
- S on CPU uses the frozen `CachedPolicy(student, THRESHOLD)`.
- The forward capture is a pass-through wrapper on `cached_policy.outputs`, and formatting happens after the timer.
- K0c uses `CachedPolicy(v1)`.

## 2. Conformance checks requested

**Addendum r3, C4 and E4.**
- The work unit is the complete no-deadline decision, in this order: D1 update and mask, fallback sample, belief
  update, proposals, candidates, sample/root, scoring with the tier's workers, and reduction. That is the order
  verified against S1 `run_game` in round 2.
- The fleet reference is measured with the same `TierBackend.work` that the Mac uses.
- There are 3 repeats, with tier order rotated per repeat and 50-state blocks interleaved.
- Deadline references are taken at 200 and 160 ms, with an 8 ms reserve and an honest timer from `packet_entry`.
- Fleet-to-fleet exactness is stricter than E4: actions, scores and the forward must be byte-equal across repeats and
  across hosts. That is correct for identical 3990X hosts. E4's Torch tolerance is a Mac-versus-Linux allowance.

**C5.**
- Every other slot runs the frozen corpus loop.
- MHz is sampled at 1 Hz in both periods: T1 `supervise.py` writes `{utc, slots, physical_core_mhz}` over exactly
  `physical_cpus[:5*slots]`, and `compare_mhz` reads that schema.
- The per-state pooled median is used.
- "Every reporting host" and "excluded from reporting before the freeze" are **not** satisfiable as written once
  references move to END. See A1.

**C6 and E2.**
- The fleet runs `Session.exactness`, which covers native golden125 with 1/2/4-worker equality and zero-budget
  immutability, plus belief125 with deadline ON and OFF, before any timing.
- Pooling re-verifies those receipts for every host.
- **One gap:** the fleet accepts ARM64-NEAR-EXACT, ≤ 1e-12. That allowance exists only for Mac versus Linux. See A5.

**C7.** Not applicable to fleet mode, except as the model for mechanical failure classification (A6).

**Row contract and fair information: conforms.**
- The fields are the public or sampled set accepted in round 2.
- `opponent` is proved mechanically to be a public-posterior sample: `belief.sample` with `belief_rng_state` must
  reproduce it exactly, and the RNG state must then equal `root_rng_state`.
- `root_digest` is proved to be `resources.root(info, opponent, rng)`.
- No row field is unchecked and outcome-bearing.
- Type-level checks are missing (N1). This is not blocking, because the key allowlist plus those reconstructions
  already close the hidden-state path.

**Does the load really reproduce the reporting layout?**
- **Masks, nice, scheduler, slot count and per-arm width: yes,** exactly as in F2.
- **Residual differences**, all disclosed and none blocking:
  - The background is continuous no-deadline search. Reporting games include simulator and v1-opponent gaps and run
    at 200/160 ms deadlines, so the reference load is probably *heavier* than reporting, which lowers clocks. If
    anything, that makes the fleet walls slower and inflates r_T. The MHz gate is the agreed empirical check; this
    is why A3 matters.
  - The 03 perception-I/O exception, the idle services and the hub copy job are absent at END.
  - The reference occupies one fixed slot, whereas reporting spreads over all 11 slots (N3).

**Is the pooling math right? Yes.**
- The initial per-state wall is the p50 over **raw** host × repeat walls (`sum([w[key] …], [])`), not over per-host
  medians.
- Each host's ratio is the geometric mean over all 1,200 states (pooled over tiers, per §6.1) of (pooled wall ÷ host
  per-state median).
- Exclusion is one-pass at |r − 1| > 0.05. The remaining raw walls are re-pooled. A retained host still outside ±5%
  fails with no iteration, and if every host is excluded the pool fails.
- Deadline rates are Σ flags ÷ n over raw rows of the included hosts, with the counts and per-state distributions
  kept. The 0.8 cell is checked as exactly 0.16 s.
- I checked by hand three hosts at 1.00, 1.04 and 1.10:
  - the initial median is 1.04;
  - the ratios are 1.040, 1.000 and 0.945, so the third host is excluded;
  - the re-pooled median is 1.02;
  - the retained ratios are 1.020 and 0.981.
- `quantiles` interpolates linearly, which is fine for even n.

**Does exactness fail closed? Yes**, with A5 tightening the tolerance. Every one of these ends the run:
- golden or belief mismatch before timing;
- repeat-to-repeat `assert_exact`;
- D1, opponent, RNG or root-digest mismatch inside no-deadline work;
- a background worker's mismatch, which kills the worker, after which `background.check()` raises.

In pooling:
- every host's native and belief receipts are checked before pooling;
- the cross-host `result` and `forward` check iterates over **all** hosts, including excluded ones.

A failed run still seals its receipts, via `ReceiptStore`.

**Does anything read T1's sealed outcomes? No.**
- The reference reads only pinned bundle files:
  - `states.pkl`, from the corpus games on the excluded corpus range;
  - `corpora.json`, which must assert `outcomes_read: false`;
  - `plan.json`, `mhz.jsonl` and the END marker.
- The pool reads only E4 receipts.
- Neither touches `hub-blocks/`, game bytes or the barrier.
- **But** the END marker is a hand-written three-key file and is not bound to T1's committed completion (A1c).

## 3. Rulings on the amendment-pending items

### 3.1 END placement: **accept by coordinator-signed amendment, with A1**

**This departs from the frozen text.** §6.1 says references are "built on the fleet before the freeze" and that an
outlying host "is excluded from reporting before the freeze". §11 steps 3–4 say the same, and so does C5.

**It is acceptable because steering is unaffected.**
- References are timing-only, they are measured while outcomes are sealed, and they feed only the Mac r_T and gate 6.
- No one can see an outcome when they are produced.

**What breaks is the ±5% rule's meaning.**
- Before the freeze, excluding a host removed it from **both** reporting and the reference, so the reference
  described exactly the hosts whose games are counted.
- At END, every named host has already contributed counted blocks. B2 now spreads every cell across hosts, so those
  blocks are in every cell.
- `fleet_pool` would drop an outlier host from the reference **while its games stay in the outcome population**.
  The reference would then no longer describe the counted games. That is the opposite of the rule's purpose.

**A1 (blocking; coordinator plus a small code change).** The amendment must state all of the following.
- **a.** References run at END, after the last reporting and replacement round and before any outcome release.
  The Mac session therefore cannot precede the end of reporting, so the C15 preference is forfeited; disclose this.
- **b.** At END, the reference host set **equals the set of hosts with counted reporting or replacement blocks**.
  - A host outside ±5% is **not** excluded one-pass. The pool **fails closed for an outcome-blind amendment**, and
    `fleet_pool` needs an END-mode switch that raises instead of excluding.
  - The amendment may pre-list one alternative: excluding the outlier's counted blocks from reduction. That would
    need a reviewed T1 reducer change, because primary cells currently assert 48 seeds each. My recommendation is
    simply to fail closed.
  - A named host that cannot run its reference has the same consequence. Example: 08 vacated at the B window after
    contributing blocks. `plan.json` already says this needs a "reviewed reference amendment".
- **c.** The END marker is the **committed T1 reporting-completion receipt**, bound by SHA and commit:
  - the same object `barrier.outcome_release` checks (`reporting_complete`, `outcomes_sealed`, 2,400/600 counted
    blocks);
  - plus that host's `supervisor-exit.json` for every reporting and replacement round;
  - not a free-standing `{host, reporting_complete, outcomes_sealed}` file.
- **d.** **No outcome release by any route, including `fourteen_day_escape`, before `pool-complete.json` and the
  registration packet are committed.**
  - `barrier.outcome_release` currently checks only the completion receipt for the escape.
  - If references slipped past day 14, they could be measured with outcomes open. That is the one new steering
    path END placement creates.
  - Add the pool-complete commit and SHA to the escape receipt.

### 3.2 MHz gate: **accept as an added fail-closed validity gate, with A3**

- §6.1 and C5 only require MHz to be *recorded and reported*. A ≤ 5% mean-difference gate is stricter, so it is not
  a weakening.
- It is also the only mechanical check that the all-slot no-deadline background approximates the reporting clock
  state (§2).
- The two-sided ±5% matches the host rule.
- Within the band, a reference 5% slower than reporting would inflate r_T by up to about 5%. Disclose the signed
  ratio rather than tightening it.

**A3 (blocking, binding and validation).**
- **a.** The reporting rows must be that host's `mhz.jsonl` from the `reporting` and every `replacement-r*` phase.
  - Extract them mechanically, SHA-bound to the hub receipts.
  - Keep only rows at **full occupancy**: join with the same-`utc` `census.jsonl` row and require
    `inflight == slots`. The ramp-up and drain tails, where slots are idle, otherwise bias reporting MHz upward.
  - `compare_mhz` filters only on the configured `slots`.
- **b.** Carry the signed `reference_to_reporting_mean` per host into `pooling.json` and the registration packet.
  `tiers-summary` must disclose it next to r_T.
- **c.** A failed gate makes that host's reference a **technical failure**, with one fresh repeat (mechanically
  classified, A6). A second failure leads to the A1b amendment.
  - The pool descriptor must list **every** attempt for each host, and the pool uses the first passing attempt.
  - No hand selection of attempts.

### 3.3 Deadline-cleared posterior, committed copy, no suspended credit: **accept (ratify round 2)**

- Both the fleet and the Mac replay start from the committed public posterior with `_pending=None`, and both do the
  full update. Replay work is therefore ≥ live work, identically on both sides, so the r_T and gate-6 comparisons
  are like for like.
- **Round 2's conditions are met in code:**
  - per-row `belief_had_suspended_transaction`, plus `suspended_progress_replayed: false`, appear in every raw timing
    row;
  - `capture_health.suspended_transaction` is reported, and `selected_suspended_transaction_states` is checked
    against the rows;
  - `belief_resume` is rejected twice.
- Blindness of selection to the flag is T1's side (SHA-256 priority of tier/seed/tick), to be confirmed in the T1
  corpus review (K1/K2), which is out of scope here.
- The amendment text should say in one sentence that live multi-poll resumption is not represented, and in which
  direction (replay is conservative for speed on both sides).

## 4. Further conditions (blocking before the first reporting-host reference)

**A2: pool host-set and profile binding.**
- `fleet_pool.run` accepts any hand-written host list. Under C5, omitting a host is selection.
- Require `{hosts in descriptor}` to equal the A1b reporting-host set, derived from the pinned plan and the
  completion receipts.
- Add to the cross-host `binding`:
  - `load_profile.reference_slot`, which must be **one pre-registered index, the same on every host**;
  - `warmup_seconds` and `perception`;
  - per host, a `console_rule` and `slot_count` that equal that host's reporting `launch.json` `slots`;
  - `nice == plan.compute.nice`. The pool test currently passes with nice 12, and only the Mac checks 10.

**A4: reference validity census.**
- The monitor records `foreign_over_one_core_seconds` per process, but nothing fails on it.
- Apply reporting's stop rules mechanically to `capacity.jsonl` before `fleet-complete.json`:
  - foreign compute;
  - a console user above 1 core for more than 60 s, via `fleet-console-users`;
  - MemAvailable below 24 GiB. Eleven `TierBackend` instances each unpickle `states.pkl`.
- A violation is a technical failure under A6.

**A5: fleet exactness must be EXACT.**
- The fleet path builds `exactness_class="EXACT"`, but `score_exactness` and `belief_exactness` still pass ≤ 1e-12,
  and the pool accepts `max_relative_difference ≤ 1e-12`.
- Linux against Linux references must be bit-exact: require 0. ARM64-NEAR-EXACT is a Mac-only allowance under C6
  and E2.

**A6: end-to-end smoke and failure rule.**
- Round 2 asked for an end-to-end fleet-mode run, and there still is none. The new background test mocks
  `TierBackend`, `pinned_profile` and `validate_bundle`.
- Before the END run:
  - Execute fleet mode once for real on a non-reporting host. Use a smoke-labelled plan that names that host, with
    reduced slots allowed, and the reviewed corpus bundle.
  - The run must cover real spawn of every background slot, real `TierBackend`, the ≥ 300 s warmup, telemetry,
    `compare_mhz` against a synthetic reporting file, and sealing.
  - The output must be unpoolable: the plan SHA differs.
- Add a mechanical classifier for fleet-reference failures, modelled on §F, listing the repeatable technical causes:
  crash, host loss, A3c and A4. An exactness failure is never repeatable.

## 5. Non-blocking (recommended)

- **N1.** Type checks in `validate_row`:
  - `info` is a `fair_player.Information`;
  - `belief_before` is a `belief.Belief`;
  - `pending` elements are `Reservation`, or a dict with exactly `submitted, due, action, card, cost`;
  - after the timer, assert that `opponent_elixir` equals the D1-derived value.
- **N2.** `activate()` closes the other tiers' cores, and `anchor.close()` drops `_pool`. So the first K2/K4 state of
  every 50-state block creates the `ThreadPoolExecutor` **inside the timer**. Reporting creates it once per game.
  - This affects about 2% of states and is symmetric between fleet and Mac.
  - Pre-create the pool in `activate` (outside the timer), or disclose.
- **N3.** On Zen2 a CCX is 4 cores, so 5-core slots straddle CCX boundaries differently. For example, K2's 3 cores
  sit in one CCX in slot 0 but are split in slot 2.
  - Record the CCX split of the registered `reference_slot`.
  - Optionally, rotate the reference slot per repeat over three pre-registered slots.
- **N4.** `compare_mhz` indexes `cpu_clock_mhz` by list position. Key it by the `processor` field instead.
- **N5.** Disclose the load-shape difference in §2, and report each period's busy-core average from `/proc/stat`,
  next to MHz.
- **N6.** `README.md` still says "the receipt uses 127x05 … one background corpus CPU" for Linux smoke. That is
  correct for smoke, but say explicitly that fleet mode never uses that path.
