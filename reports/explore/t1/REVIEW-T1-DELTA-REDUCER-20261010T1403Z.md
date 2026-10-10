# Review round 2: T1 reducer, T1 corpus builder, E4-v3 fleet-reference mode

Independent verifier/reviewer for coordinator `0523ae6f`, 2026-10-10 ~14:03 UTC. I am a separate author from the T1
worker and from the E4-v3 worker, and I edited none of their files. Binding text: the frozen PREREG r3 and E4-v3
addendum r3 (`cc6410b2`), together with review conditions C4 and C5. Round 1 is
`REVIEW-T1-DELTA-REDUCER-20261010T1350Z.md` (`7dfd6086`).

## Verdict: **REJECT (round 2): not ready to freeze**

| Component | Verdict |
|---|---|
| T1 reducer `reduce.py` | **APPROVE_WITH_CONDITIONS** (R1–R4 blocking) |
| T1 corpus builder (`run.py` capture, `corpus.py`, `corpus_game.py`) | **REJECT** (K1–K2) |
| E4-v3 `measure_tiers.py --fleet-reference` and `FLEET-INPUT-SCHEMA.md` | **REJECT** (F1–F4) |
| Round-1 carry-overs | B2, B5 and B6 are open; B4 is partly fixed; B3 is mitigated (see §4) |

## Reviewed bytes (16-hex SHA-256 prefixes; all files were uncommitted and changing during the review)

- **T1:** `reduce 0c79ac98`, `replace 6a12b69f`, `corpus 3020339d`, `corpus_game f1c70c27`, `run b395a6b8`,
  `plan 176bcf36`, `supervise 48bdebc6`, `barrier ce41a98d`, `schedule 2c6dcf85`, `mirror bc0e4878`.
- **E4-v3:**
  - `fleet_reference d4287e13`, `tier_backend 4a67bde2`, `replay_load b7899bc3`, `measure_tiers 23912df8`,
    `receipts 003f6b18`, `telemetry d17c3891`, `FLEET-INPUT-SCHEMA 21f5f756`.
  - I also kept a snapshot outside the repo so later changes can be diffed.

## 1. T1 reducer (`reduce.py`)

**Verified:**
- The release is checked before any game byte is read.
- The reducer counts only blocks that are complete, hub-acked and not excluded by the ledger, and every game SHA is
  checked.
- Non-terminal games fail an assertion. The `loss` field is checked against `winner` and seat. Draws are non-losses.
- The 8 arms are paired, with identical decks and seat.
- Each replacement is mapped to its logical original, and its cell must equal the original index mod C. Logical IDs
  are unique and there are 2,400/600 of them, which implies exactly 48 per primary cell and 33 or 34 per guard cell.
- The bootstrap uses one `default_rng(2026101040)`, primary cells 0–49 and then guard cells 0–17, with
  `integers(0, n_c, (R, n_c))` over rows sorted by logical ID, shared across all contrasts.
- Gates: V1 ≤ −10, V2 ≤ 40, NI (97.5%) ≤ +5, G1 < 0 (strict), G2 ≤ +10. The validity window SUSPENDs selection.
- Selection: cheapest first; NI ∧ G2 against every costlier admissible tier; the costliest tier qualifies trivially;
  F0 if A = ∅. The output is labelled PROVISIONAL, and `program_kill` is computed.
- **Cross-check:** my verifier now uses T1's within-cell ordering, so a replacement occupies its lost block's slot.
  The new test `test_cross_check_against_t1_reduce_on_synthetic` runs T1's own `population_stats` read-only on
  synthetic data. Counts, points and every interval agree to 1e-9: the draws are bit-identical. No index export is
  needed.

**Blocking:**
- **R1 (= B5).** `ci9833` uses the literal 0.9833. V1 and V2 must use 1 − 0.05/3. My verifier flags any decision
  this changes (`LEVEL_ROUNDING_FLIP`, `T1_GATE_DECISION_DIFFERS`).
- **R2. Float bounds at inclusive thresholds.**
  - The bootstrap accumulates per-cell fractions in float, and the gates compare float bounds. The validity window
    also compares a float `loss_pct`.
  - A bound that is exactly on a threshold can land 1 ulp on the wrong side. Synthetic data already produced an
    exact +10 pp G2 bound at n = 600.
  - **Fix:** compute integer per-resample counts and make the threshold tests exact. Failing that, **pre-register
    now** (coordinator) that the exact integer computation governs any float/exact disagreement.
- **R3. `--mac-summary` is unbound.** Assert that its SHA-256 equals the release receipt's `mac_summary_sha256`.
  Also apply §6.4's gates 1–3 for the K0c cell; at present only r, p10 and gate 6 are checked.
- **R4 (= B6).** `outcome_release` still accepts `explicit_coordinator_release` with no checks. Replace it with a
  checked `fourteen_day_escape`, as in round 1.

**Non-blocking:**
- `replace.py` takes a hand-supplied loss list. It should be generated mechanically from supervisor `exits/`
  (`complete=False`) and stop-reason receipts.
- The reducer's output schema differs from round-1 §4.8. That's fine: my verifier now reads the `reduce.py` schema
  directly and re-derives every gate decision from T1's own reported bounds.

## 2. T1 corpus builder

**Verified:**
- The capture is taken outside the honest timer: the pre-state is snapshotted before `WINDOW`, and the row is
  assembled after.
- The corpus is the tier's own game at 200 ms on the corpus seed range, with decks and seat following the primary
  mapping.
- Priority is SHA-256 of tier/seed/tick (outcome-independent). Strata are elixir and legal-play count, with
  proportional quotas and at least one per occupied stratum.
- There are 300 per tier with unique IDs, and the seed range is asserted.
- The committed-belief snapshot leaves the live collector untouched.

**Blocking:**
- **K1. Row contract mismatch.** The rows lack `d1_before`, `d1_events` and `strata` (elixir and legal-play count
  are top-level keys).
  - `fleet_reference.validate_row` rejects them, so the fleet reference cannot run on this corpus.
  - On the Mac path, `TierBackend.policy_input` would fall back to the `"d1" in row` shortcut, which **drops the D1
    update from the timed work**. That violates C4 ("complete decision").
  - **Fix:** capture `d1_before` (tracker `__dict__` without `builder`, before `poll`), `d1_events` (the recorder's
    public event list passed to `poll`) and `strata={elixir, legal_play_count, bins}`.
- **K2. Eligibility is filtered by deadline outcome.** A row is kept only if the corpus game reached
  `R.root(...)`, so every decision where belief preparation or sampling timed out at 200 ms is excluded. That biases
  each corpus toward cheap states. That is exactly the slow tail C4's `min(median, Σ, p90)` and p10 ≥ 0.70 gates
  are meant to see.
  - **Fix:** capture every search opportunity with more than one candidate. For the row's `opponent`, `root` and
    `root_digest`, compute them **after the timer** from a copy: a no-deadline update of the committed belief, then
    a sample with the captured `belief_rng_state`. The game must be unaffected.
  - Record the fraction of rows that were cut in the corpus game.

## 3. E4-v3 fleet-reference mode (scope extension)

**Conforms:**
- The fleet reference uses the same `TierBackend.work` as the Mac. The work unit covers the full decision:
  - D1/mask;
  - the forward and fallback sample;
  - the belief update;
  - proposals;
  - candidates;
  - sample;
  - root;
  - scoring and reduction.
- **The decision order matches the frozen S1 `run_game`.** I compared step by step. The S path's `DeviceStudent`
  ranking is identical to `rank_actions` (−score, then action ID) with the same threshold.
- The belief deepcopy now happens outside the timer (`prepare_work`), and work runs inside the frozen GC `WINDOW`.
- There are 3 repeats, with tier order rotated per repeat and 50-state blocks interleaved.
- Deadline references are taken at 200 and 160 ms with an 8 ms reserve and an honest timer from packet entry.
- Warmup must be at least 300 s. At least 300 unique own-tier IDs are enforced, and each row's tier must equal its
  corpus tier.
- Fleet mode requires nice 10, five physical non-SMT search CPUs, golden125 exactness on the host, and repeat-to-repeat
  exactness of action and scores.
- `/proc/cpuinfo` MHz is sampled at 1 Hz.

**Blocking:**
- **F1. Fleet mode cannot start.** `replay_load.corpus_load_worker` raises unless the host is 127x03/127x05 **and**
  nice is 19. Fleet mode requires 01/03/08 at nice 10, and spawned children inherit nice 10. On every reporting host
  the background load therefore dies, and `LinuxBackground` aborts. There is no end-to-end test of fleet mode; one
  would have caught this.
- **F2. The load profile is not reporting-equivalent** (PREREG §6.1, C5: "every other slot on that host runs the
  same frozen corpus loop").
  - The schema and code allow exactly **one** 5-CPU background group, running **K4 only** on `rows[:32]`, plus a
    replay-perception process. Reporting runs **11 slots (8 under the console rule)** of 5 cores. Rotated arm-cells
    use 1, 1, 1, 1, 3, 3, 5 and 5 cores, so roughly 2.5 cores per slot are busy on average, with no perception.
  - With one busy slot the CPU boosts higher than under reporting load. Fleet walls come out too short, so the
    reference is not the reporting clock state.
  - **Fix:** background = all other reporting slots of that host (10 or 7), one process per slot, each running the
    **rotated four-tier corpus loop** at nice 10. Either drop the fleet perception process or justify it in the
    load-profile review. Then compare reference-period MHz against reporting-period MHz; T1 must sample reporting
    MHz too.
- **F3. Pooling and the ±5% host rule are not implemented.** "The coordinator pools" needs a frozen, reviewed
  script that:
  - computes the per-state median over **all hosts × repeats** from `speed-reference-raw.jsonl`, not a median of
    the per-host p50 values that `speed-reference.json` stores;
  - excludes any host whose geometric mean of per-state ratios to the pooled median is outside ±5%;
  - pools deadline rates by counts.
- **F4. Corpus contract enforcement.**
  - Outside `--linux-dry-run`, remove the `elif "d1" in row` shortcut and require `d1_before`/`d1_events` in Mac
    `validate_counts` as well (see K1).
  - Make `validate_row` an **allowlist**: reject unknown keys, so no hidden-state field can enter by accident.
  - Reject `belief_resume` until a reviewed contract exists (the path is still live in `history_before`).

**Non-blocking (required):**
- **F5.** In-timer replay setup: `configure()` deepcopies `info` and `pending`, and `policy_input` checks the D1
  reconstruction with `array_equal` against `row["d1"]`. Move the check after the timer, and report the setup cost.
- **F6.** S/CPU uses the re-implemented `DeviceStudent`, which builds a Python dict of legal-action ranks, instead
  of the frozen `CachedPolicy(student, threshold)`. Its output is equivalent, but it adds overhead the frozen tier
  doesn't have. Use `CachedPolicy` for CPU, or measure the difference.

**Fair-information rule.** As captured, the rows hold only public or sampled state:
- `info` comes from `observe()`;
- `reserved_packet` is the agent's own channel;
- D1 is the public tracker;
- the belief is the public posterior;
- `opponent` is the `belief.sample` hypothesis;
- `root` is built from `info` plus that hypothesis;
- `pending` is the agent's own reservations;
- `opponent_elixir` is derived from D1.

`seed` is a label; the policy generator is overwritten from `policy_rng_state`. **Conforms**, subject to F4's
allowlist.

**Deadline-replay amendment (the schema asks for review):** **accepted, as disclosed.**
- With `_pending=None`, replay does a full public-history update from the committed posterior and gives no
  partial-preparation credit. That is exactly the §6.1 work unit for the no-deadline reference.
- For gate 6 it is identical on fleet and Mac, so the +2 pp comparison is like for like, if conservative relative
  to live.
- **Conditions:**
  - report per tier the count and fraction of rows with `belief_had_suspended_transaction`;
  - keep row selection blind to that flag;
  - keep `belief_resume` disabled (F4).

## 4. Round-1 carry-overs

- **B2 (static round-robin dispatch): still open.** The guard and descriptive cells are still confined to one host
  each (seat ≡ host on 2 hosts). `replace.py` also assigns round-robin. There is still no rule for never-started
  blocks on a lost host.
- **B3: mitigated.** The supervisor can still mark a cleanly completed block as failed. But the reducer excludes
  every ledger-lost block, so no double count is possible, provided the losses list comes mechanically from the
  exits. This is now non-blocking.
- **B4: partly fixed.** `mirror.py` copies all three phases with a hub-ack, but the supervisor's 30-minute check
  still globs `reporting/` only.
- **B5 = R1, B6 = R4: open.**
- **N1: fixed** (08 is now named). **N2 and N3: open.** `plan.ordering.blocks` is stale, and `ticks` is still
  printed per game.

## 5. Verifier status

Commit `b3759c25`, plus this round's update:
- within-cell ordering by logical original;
- an adapter for the `reduce.py` schema;
- re-evaluation of every T1 gate decision against the exact bound;
- rounded-level intervals for every population.

21/21 tests pass, all on synthetic data. No real outcome has been read.
