# X4S-4: do on-policy cutoff-state labels make a better student? (exploration, NEVER ADOPTABLE). PLAN r3; nothing launched

- **r1:** f9f528b9. **r2:** a72b3213, which adopted every condition C1–C9 of the Opus design review r1
  (`/mpac/sdicks02/jobs/clasher/x4s4-review/OPUS-DESIGN-REVIEW-r1.md`, SHA-256 969e47ec…, verdict
  APPROVE_WITH_CONDITIONS) under COORDINATOR ea7cf79f.
- **r3 (this revision):** makes all 11 consolidated edits of the Opus re-check r2
  (`OPUS-DESIGN-RECHECK-r2.md`, SHA-256 665c73d2…) as ruled in COORDINATOR 7b989359. They are tagged **[E1]–[E11]**
  in the text. R2-9 and R2-11 are built into the scripts for the Sol review.
- **Process:** the coordinator verifies r3 textually; then one Sol review of the full script set; then the coordinator
  GO. **No host run happens before the GO.**
- **Status: exploration only, NEVER ADOPTABLE.**
  - No student enters a frozen manifest; SD1 stays R3a.
  - Results are never cited in K4S, TIERS or T1 reporting.
  - No sealed K4S, T1 or TIERS outcome is read.
  - No held-out deck or split is used.
  - No 03/04/Mac contact; 08 is not used.

## 1. Hypothesis, students, contrasts and rules

**Why.** X4S-3 found that 46% more *off-policy* W roots did not help: R4-D − R3a = +0.7 pp [−1.5, +2.8]. The
student decides actions at search cutoffs and fallbacks, and those states are reached by the deployed student-tier
agent, not by W. That is DAgger's covariate-shift argument. X4S-3's null was underpowered (MDE ≈ 3 pp), so it does not
show that data levers are exhausted. X4S-4 states its power and has an explicit "inconclusive" outcome (C2).

**Hypothesis.** Refitting R3a's recipe on r1 plus about 0.40 M W-labelled states that the *current* student-tier
agent (R3a in K4S-120 and S-200) reaches in its own play, chiefly at cutoffs, lowers loss vs v1 in those same two
deployment configurations, *beyond fit-seed variance*.

**Students.** All are fitted with the X4S-3/R3a recipe: init v1 d77005d5, width 192, root-only, T = 0.003, play weight
1, value weight 0, AdamW 3e-4, warmup 2000 then cosine, batch 8192, final EMA, the frozen R3 trainer, loader6, 2,500
steps.

| ID | Teacher roots | Train seed | Role |
|---|---|---|---|
| R3a | existing 37509a43 (r1 + 212,542 G-04) | — | control |
| R3a-rep | existing X4S-3 checkpoint 8d537a78 (r1 only), threshold 0.49952925741672516 | — | control replicate |
| **R5** | r1 + on-policy set **O**, packed batches listed ×4 | 2026101301 | treatment |
| **R5-rep** | same as R5 | 2026101302 | treatment replicate, **mandatory** (C1) |
| **R5W** | r1 + matched off-policy set **O_W**, listed ×4 | 2026101303 | matched-data control (C3) |

- **Disclosed: R3a-rep differs from R3a** in its G-04 rows as well as its fit seed. So "mean of the controls" averages
  two closely related, but not seed-only, replicates (C1).
- **×4 up-weighting.** The trainer samples rows uniformly across the listed shards, so listing each set's packed
  batches four times gives about a 21% share. Each O state is seen about 10.8 times, against about 2.7 times for r1
  states. Memorization is monitored by the O-holdout diagnostic (§6). The ×4 is pre-declared and is not tuned.
- **O_W (C3):** W-screen8 at no deadline vs the exact v1 policy, on the five X decks, with the X4S index mapping
  (own = i % 5, opponent = (i // 5) % 5, seat = i % 2), from a fresh bank C′.
  - These are W's own roots, already labelled by construction.
  - **Matching unit [E5]:** scored `teacher_root` rows, the emitter's `root_decisions`, i.e. rows the trainer's
    `RootTeacherStore` uses; not emitted rows. The emitter also writes pollWAIT/timed-WAIT rows every 5 ticks, which
    the trainer ignores. The O_W root count is matched to |O| after dedup: the smallest prefix of games, in index
    order, whose cumulative root count is ≥ |O|. The overshoot is at most one game, about 123 roots. O_W is not
    deduped: every emitted root is kept, as in r1/G.
  - **What O_W matches and how it differs [E5].** O_W matches O in opponent (exact v1), decks (five X), seat and cell
    schedule, size (roots) and weight (×4). It differs in **behavior policy**: W's own decisions versus the
    student-tier agent's, **including the student-tier agent's cutoff-heavy state selection**. O takes every
    deadline hit plus a 25% sample of non-hit decisions, only decisions with > 1 candidate, and excludes
    preparation cutoffs and suspended transactions; O_W takes every W search decision, including single-candidate
    roots. There are two further disclosed differences:
    - the label wrapper (O uses the anchor kernel, O_W the emitter);
    - the belief class (`Belief` vs `ExactFastPrior`).

    O_W's single-candidate root share is reported. The cutoff-heavy selection is part of the DAgger treatment, so
    R5 − R5W measures the intended contrast.

**Deployment arms**, exactly as X4S-3:
- K4S-120 and S-200;
- the exact v1 opponent, d = 27, capacity 1, honest lateness;
- the five X decks, alternating seats, 50 cells.

**Pre-declared readout** (paired-seed bootstrap, 5,000 reps, seed 2026101301, percentile 95% CI; the X4S-3 reducer
semantics):
- **Primary (C1):** Δ = mean(R5, R5-rep) − mean(R3a, R3a-rep), paired by seed, pooled over both arms with equal arm
  weight. Each arm is also reported separately.
- **Power (C2) and fit-seed error [E2].**
  - With N = 1,200 the pooled SE of Δ is about 0.76 pp, so **MDE ≈ 2.1 pp** at 80% power (one-sided 2.5%).
  - **That figure and every bootstrap CI here cover game sampling only.** Fit-seed variance is not in the CI, and
    replication does not restore the error rate: in the 2v2 contrast the nominal-to-true SE ratio stays as for a
    single fit.
  - By the re-check's Monte Carlo, the true one-sided error of "helps" is about **6.5% at σ_fit ≈ 0.65 pp** (X4S-3's
    one-pair estimate) and about **10–12% at σ_fit = 1 pp**.
  - Including σ_fit = 0.65, the effective MDE80 is about **2.8 pp**, so the MDE range is 2.1–2.8 pp.
  - Plausible one-round effects are 0.5–2 pp. **N stays at 1,200**; there is no extension.
- **Three-way outcome on the primary (C2):**
  - **Helps:** the upper 95% CI of Δ < 0, **and** both **pooled** single-fit points (R5 − R3a)[pooled] < 0 and
    (R5-rep − R3a)[pooled] < 0 [E2].
  - **No material effect:** not "helps", and the lower 95% CI of Δ > −2.0 pp, so a gain of ≥ 2 pp is excluded.
  - **Inconclusive:** otherwise.
  - **Sub-label "harmful" [E9]**, descriptive: the lower 95% CI of Δ > 0. The row is still selected by the primary
    outcome above; see the decision table.
  - **Fit-inflated interval [E3]**, pre-declared and descriptive: Δ ± 1.96 · √(SE_boot² + 0.65²), where SE_boot is
    the bootstrap SD of Δ and σ_fit is **fixed at 0.65 pp now**, from X4S-3 (not the in-study estimate). It is
    reported next to the primary. If "helps" holds on the bootstrap CI but this interval's upper end is ≥ 0, RESULTS
    labels the outcome "helps (game-sampling CI only; not robust to σ_fit = 0.65)".
- **Declared secondaries** (descriptive; about 6 unadjusted contrasts; **only the primary drives the decision table**):
  - R5 − R5W and mean(R5, R5-rep) − R5W: on-policy beyond matched data (C3). The attribution sub-label [E4] uses the
    latter's bootstrap CI (see the decision table);
  - the single-fit contrasts R5 − R3a, R5-rep − R3a, R5 − R3a-rep, R3a-rep − R3a;
  - **σ_fit**, estimated from the two within-group differences R5 − R5-rep and R3a-rep − R3a, labelled 2-df and
    descriptive.
- **Also reported:** a timing-parity table (§4) and the contention-sensitivity version of the primary (§4); per
  student and arm, cutoff %, student-default %, play %, wall p50/p99 and overrun %; the O-holdout diagnostic (§6);
  and the O composition and duplicate report (§2).

**Stop rules.**
- **Fixed N for all five students [E1]:** every student's games always run. There is **no futility stop**: the r2
  R5-rep futility stop is deleted. **No reduction of any kind happens before the C5 contention receipt is
  SHA-frozen**, and no contrast, gate or point estimate is computed mid-block.
- **Fit kills:** NaN, divergence, or more than 2× the expected wall time.
- **Interrupted games** are excluded, and their seeds are retired for every student and never re-run.
- **Memory:** no dispatch while MemAvailable < 24 GiB or memory PSI avg10 > 10%. Kill only when MemAvailable < 24
  GiB or owned PSS > 50 GiB.
- **Console user:** yield, then run ≤16 game processes.
- **No reporting game runs beside any fit (C4).**
- **Hard stop:** T+24 h.

**What the result changes** (descriptive, exploration only; **the primary outcome alone selects the row**):

| Primary outcome | Next |
|---|---|
| **Helps** | The next step follows the descriptive **attribution sub-label [E4]**, from the bootstrap CI of mean(R5, R5-rep) − R5W:<br>• upper CI < 0: "on-policy beyond matched data". Iterate DAgger (collect with R5, label, refit, with replicates) and scale O. A separate SD2 PREREG for the slow-Mac/1-core tiers only after the K4S/TIERS release.<br>• lower CI > 0: "matched data does at least as well". Matched W generation (W vs v1 on deployment decks).<br>• otherwise (**the default**): "**on-policy or deployment-matched data helps; attribution unresolved**". Matched W generation first, since it is cheaper (no capture or labeling pipeline), then disambiguate before DAgger iteration 2.<br>In every case, check for overfitting to v1/X decks before any live use. |
| **No material effect** | One round of on-policy cutoff labels at this scale doesn't move deployment by ≥ 2 pp. The next lever is capacity/value targets (a separate X4S-5 with a latency-charged arm). Mac tiers stay on SD1. **If also "harmful" [E9]:** first audit the O labels (anchor kernel vs frozen references at cutoff states) and use the O-holdout diagnostic for ×4 memorization, before any rerun. |
| **Inconclusive** | The lever is untested at this power, **not** exhausted. Only a larger, replicated design (N and fits) can settle it. No program decision. |

The O-holdout diagnostic gives the mechanism context. If R3a is as accurate on its own cutoff states as on r1 states,
a null is mechanistically expected.

## 2. State collection (O, the O-holdout and O_W)

**Behavior for O.** The deployed student-tier agent with the **current student R3a** (SD1, threshold
0.5005528330802917), playing the X4S-3 deployment configs K4S-120 and S-200 on 127x01. Opponent, decks, cadence,
lateness and timing class are identical to X4S-3.

**Mechanism (C7c).** `run_collect.py` is a **byte copy of the reviewed `x4s3/run.py` plus one explicit hook call**
right after `apply_lateness`, which runs after the decision timer has closed:
- the call is `CAPTURE(seed, pair, arm, spec, b, actor, info, reserved, policy, p, ch, stats, action,
  preparation_hit, candidates, opponent_events)`;
- `CAPTURE` defaults to `None`, so the module is otherwise identical;
- evaluation games use the **unchanged** `x4s3/run.py`;
- `collect.py` installs the hook and writes one capture pickle per game;
- there is no frame introspection.

**Captured per decision** (student seat):
- the gate-c training row: the observation of the student's own **reserved packet**, policy mask and D1;
- a parity flag against `build_public(b, seat)`;
- deep copies of `info` and `reserved_packet` (C8);
- `opponent_elixir` (C8);
- `pending`, **asserted empty** (C8; capacity 1 with a free channel). A non-empty `pending` skips the capture and is
  counted;
- one opponent hidden state, sampled from a **deep copy** of the agent's belief (C7a), so the live belief is never
  touched;
- the root RNG state and root digest, and a candidate RNG state;
- `deadline_stats`.

**Capture RNGs (C9).** These are domain-separated: SHA-256("x4s4-capture|label|seed|tick") seeds a dedicated NumPy
generator for each use. No agent or battle stream is involved.

**Fair-information enforcement (C9).**
- The capture pickler's `persistent_id` hook **raises** if any object in a capture graph is a `BattleState` or
  `PlayerState` (the true hands, cycle and battle RNG live there).
- Qualification §5.4 adds the permutation-invariance test.

**Which states (C8).**
- Student-seat search decisions **with more than one candidate**.
- Excluded, and counted: preparation cutoffs, suspended belief transactions, and non-empty `pending`.
- Every decision with deadline hit = true is captured.
- Non-hit decisions are sampled at 25%, with a domain-separated (seed, tick) draw.
- Strata are recorded (hit, student_default, fallback, non-hit sample), and their shares are disclosed.

**Banks.** These are confirmed fail-closed by the repo-wide `audit_seeds.py` at staging. A preliminary offline run
on an origin/main export (all five banks, 2026-10-12) was clean: 156 sources, 291 prior ranges, 10,703 raw literals,
none in the window, no intersections.

| Bank | Base + range | Use |
|---|---|---|
| E | 4503606307370496 + [0, 1200) | evaluation |
| C | 4503606317370496 + [0, 4000) | collection: K4S-120 indices 0–1999 and S-200 indices 2000–3499 → **O**; **O-holdout**, never trained on (C6): K4S-120 indices 3500–3749 and S-200 indices 3750–3999 |
| C′ | 4503606347370496 + [0, 6000) | **O_W** |
| smoke | 4503606327370496 + [0, 8) | smoke |
| qualification | 4503606337370496 + [0, 8) | qualification |

**Sizes and caps (C6).**
- **Expected:** about 178 k (K4S-120) + 220 k (S-200) states from 2,000 + 1,500 games.
- **Per-arm caps, after dedup:** K4S-120 ≤ 0.20 M, S-200 ≤ 0.25 M. Each is truncated in index then tick order,
  replacing the global cap.
- **O gate:** O between 0.30 and 0.45 M.

**Dedup (C8).**
- The training key is SHA-256(row bytes + root digest). This intentionally keeps multiple determinizations (different
  sampled hidden states) of the same public state.
- Also reported: the **feature-only duplicate rate by 600-tick bucket**, which measures opening determinism and so how
  much of O recurs verbatim in bank E games.

**Collection interruptions (C6).** Capture files of games without a block proof (non-terminal or interrupted) are
dropped.

**Belief class (C8).** O samples hidden states from the deployed `Belief` (the S1 exact resumable prior). r1, G and
O_W used the emitter's `ExactFastPrior`. Both are exact-prior beliefs; the difference is disclosed.

**Leakage.**
- Training data comes only from banks C and C′; the verifiers require every packed row's seed to be in its bank, and
  none in E.
- The O-holdout indices are never packed into O.
- Collection-game outcomes are never reduced. O rows store `recorded_outcome = 0`. O_W rows carry the emitter's
  outcome field, which is unused at value weight 0 and never reduced.
- Calibration stays on the R1 held-out64 slice 0ecce0f0, label-free.
- No K4S, T1 or TIERS output, deck or split is read.

## 3. Labeling and the matched control

**Teacher for O.** W-screen8 at no deadline, using the **K4 anchor kernel**, built exactly as in
`reports/explore/x4s/qualify.py` with `reserve_floor = False` asserted (C8). This is the kernel X4S qualification
showed reproduces the frozen screen8 reference scores on 125/125 states.
- The labeler rebuilds the root and requires the captured digest, regenerates candidates from the captured RNG state,
  and scores.
- **Digest mismatch (C6):** the state is dropped; more than 0.1% mismatches aborts the run (no O gate).
- Rows get the G emitter's teacher fields. Each game is sealed with the unchanged `exit_r1.rows.seal`, then packed by
  the unchanged `exit_r1/pack.py`.

**O_W.** Generated by the **unchanged** reviewed `imitation/exit_r1/emitter.py`, with opponent = v1 and W-screen8 as
the teacher seat. A thin wrapper, `collect_w.py`, supplies the X deck pair and seat through the emitter's own `decks()`
and `index` parameters per game. The emitter's file is not edited. The realized (own, opponent, seat) schedule over C′
must equal the X4S 50-cell schedule, and the emitter's v1 checkpoint must be the evaluation opponent d77005d5. Both
are asserted (Sol item).

**O_W gate thresholds [E11].** All of these must hold, or there is no O_W gate and no R5W fit:
- 100% of packed rows' seeds lie in C′, and none in C or E;
- every selected game is sealed and verifies against its seal; the emitter's acceptance replay passes on the
  qualification smoke;
- interrupted or truncated games are dropped (the emitter raises on truncation and never seals an in-flight game),
  and only the contiguous selected index prefix is packed;
- the root count (scored `teacher_root` rows) lies in [|O|, |O| + roots of the last selected game];
- no dedup (stated);
- the single-candidate root share is reported.

**Cost** (G-01 receipts, 1,229 games):
- W ≈ 0.28 core-s per root (script opponents) and ≈ 0.41 core-s per root including v1 polls.
- **O labeling:** about 0.40 M + about 50 k holdout roots × 0.28 s ≈ 35 core-h, about 45 min on 50 cores.
- **O_W:** about 0.40 M roots at about 123 roots per v1 game ≈ 3,300 games × about 51 core-s ≈ 47 core-h, about 1 h on
  50 cores.

## 4. Hosts, host symmetry and contention (C4, C5)

**127x01 only.** 08 isn't used, so no transfer amendment is needed.
- Games and CPU work run on physical cores 0–49. The fit runs on 56–61, with loaders on 120–125. Cores 50–55 and
  62–63 stay free.
- nice 10, ≤70 processes, GPU ≤ 40 GB, disk ≤ 100 GB under `/mpac/sdicks02/jobs/clasher/x4s4-onpolicy/`.
- **Never touched:** `t1-*`, `end-*`, release roots, the paused hub mirror, or any other tree.

**Symmetric host conditions (C4).**
- No reporting game of **any** student runs beside **any** fit. All 5 × 2 reporting phases run in one contiguous
  fit-free block after the last fit, in the **ABBA order R3a, R5, R5-rep, R3a-rep, R5W [E6]**. Control and treatment
  positions have equal mean (2.5), so linear host drift cancels in Δ. R5W stays last.
- Fit windows overlap only non-reporting CPU work: O_W collection and offline diagnostics.

**Timing-parity check (C4), non-outcome metrics.**
- **Across students, per arm:** cutoff %, student-default % and wall p99, in a parity table. A cross-student cutoff or
  student-default gap > 2 pp is **disclosed in RESULTS next to the C5 sensitivity; it triggers no exclusion [E10]**.
  Such a gap can be a genuine treatment effect, through different trajectories. Wall p99 is descriptive only.
- **Collection vs X4S-3 (C7b), deadline-mode parity:** O collection's per-arm cutoff %, student-default % and
  overrun % must lie within ±2 pp of X4S-3's R3a. The X4S-3 values are K4S-120 64.2 / 22.3 / 0.16 and S-200
  75.3 / 0.0 / 0.14. Outside that band, collection is paused and the coordinator decides whether to continue or
  disclose.

**Contention sensitivity (C5), pre-declared now.**
- A reporting game is flagged if its interval intersects any supervisor census sample where any of these held:
  - memory PSI avg10 > 10%;
  - **foreign CPU > 2 cores, host-wide**;
  - a **yield / reduced-concurrency window [E7]**: a console user present, so the phase ran (or was relaunched)
    with fewer than its full worker count.

  The game interval is [mtime(game JSON) − wall_seconds, mtime].
- **Foreign CPU** (R2-9; definition for the Sol review) is the census-interval Δ(utime + stime) of every process outside
  the X4S-4 process tree, host-wide. That covers the SMT siblings 64–113 of game cores 0–49 and processes on any
  core. The X4S-4 tree is the supervisor, its child group, the driver and fits.
- The **union** of flagged seeds is excluded for **all** students.
- The primary Δ and its three-way classification are also reported on the kept seeds. The headline stays the
  all-seed primary.
- The exclusion receipt is built from timing fields only and **SHA-frozen and committed before any reduction**.

## 5. Scripts (exact list; all need a Sol review before any run on 01)

Everything else is reused **byte-identical**:
- `x4s3/run.py` (evaluation), `runtime.sh`, `detach.sh`, `calibrate.py`;
- the X4S/S1 kernels;
- the frozen R3 trainer, `fit_runtime.py`, `loader_prefetch.py`, `proposals.py`;
- `imitation/exit_r1/{rows,pack,emitter}.py`.

Evaluation-game metadata therefore reads `study` = "X4S-3". The reducer accepts that, and identifies X4S-4 by bank E.

| # | File (`reports/explore/x4s4/`) | New/modified | Purpose |
|---|---|---|---|
| 1 | `run_collect.py` | **new: byte copy of x4s3/run.py + the hook** | Explicit post-timer capture hook (C7c) |
| 2 | `collect.py` | **new** | Capture: deep-copied belief, C8 fields, domain-separated RNG, a `persistent_id` guard against Battle/Player objects (C9), per-game durable capture files, and qualification modes (belief-hash check, fair-information permutation) |
| 3 | `label.py` | **new** | Dedup/caps plan (per arm, plus the feature-only duplicate report) and offline W labeling; drop/abort on digest mismatch; holdout kept separate |
| 4 | `collect_w.py` | **new** | O_W generation by calling the unchanged emitter (v1 opponent, X decks via `decks()`/`index`, schedule and checkpoint asserted), guarded, PSI-gated dispatch, root-count matching |
| 5 | `verify_onpolicy.py` | **new** | The verify_g r3 safety primitives + provenance (C / C′ / not E) + the C6 O-gate and E11 O_W-gate thresholds; modes O, O-holdout and O_W; writes the gates |
| 6 | `diagnose.py` | **new** | O-holdout diagnostic (descriptive): top-1 agreement, gate accuracy and listwise CE vs W for every student, on O-holdout and on the R1 held-out64 slice |
| 7 | `contention.py` | **new** | C5/E7 exclusion receipt from census and timing fields only (PSI, host-wide foreign CPU, yield windows); SHA-frozen before reduction |
| 8 | `qualify4.py` | **new** | §6 qualification checks |
| 9 | `supervise.py` | **modified** | `--script` choice, plus census fields for C5/E7: host-wide foreign CPU outside the X4S-4 tree, and reduced-concurrency (yield) state |
| 10 | `run_fit.sh` | **modified** | R5, R5-rep and R5W: seeds and shard lists (O or O_W ×4) |
| 11 | `driver.py` | **modified** | Fits, then one fit-free reporting block (C4) in ABBA order; five students, all games always run (no futility stop, no mid-block reduction); the PSI dispatch gate; yield-window logging; gate-log fix |
| 12 | `reduce.py` | **modified** | Students, pairs, primary Δ, three-way outcome, σ_fit, contention-sensitivity view, parity table, bank-E check |
| 13 | `write_report.py` | **modified** | The C6 readout template |
| 14 | `audit_seeds.py` | **modified** | Own-echo label |
| 15 | `plan*.json` | config | Banks, students, capture and readout |

No script touches a host other than 01.

## 6. Qualification and the offline diagnostic (on 01, before any collection or reporting game)

1. **Unit tests** (as X4S-3), plus synthetic tests of capture, label, verify and driver logic.
2. **Capture non-perturbation:**
   - **No-deadline-equivalent:** with 1,000 s budgets (so there are no cutoffs), `run_collect.py` + capture-all gives
     command hashes identical to the unchanged `x4s3/run.py` on the 8 qualification seeds, for both arms.
   - **Belief:** the live belief's pickle hash is unchanged by every capture (C7a).
   - **Deadline mode:** the C7b parity band, checked on the collection smoke and on the running collection.
3. **Labeler equals the frozen teacher:** 125/125 screen8 references reproduced, at the labeler's thread count.
4. **Round trip and fair information:**
   - on smoke captures, a 100% digest rebuild and repeat-label byte identity;
   - `reserved_packet`, `opponent_elixir` and empty `pending` are present in every capture;
   - `features_equal_student_input` and `row_equals_build_public` both hold;
   - **fair-information invariance (C9):** at each captured decision of a qualification game, the battle is
     deep-copied, the opponent's **unrevealed** hand and cycle are permuted, and the battle RNG is reseeded. The
     capture payload built from the altered battle must be byte-identical. The no-Battle-reference guard must also
     hold.
5. **Trainer compatibility:** a packed smoke batch loads in `RootTeacherStore`, and the teacher targets are valid.
6. **Emitter wrapper:** 2 O_W smoke games through `collect_w.py` with the emitter's own acceptance replay
   (`--acceptance` path), sealed and verified.
7. **Smoke:** 8 seeds × 2 arms of collection, 8 + 8 R3a evaluation games, and a live STOP test. All are excluded.

**Offline diagnostic (C6), descriptive only and never a gate.** For R3a, R3a-rep, R5, R5-rep and R5W, on the
**O-holdout** and on the R1 held-out64 slice:
- top-1 agreement with W's best candidate;
- gate accuracy (play/WAIT vs W) at the student's calibrated threshold;
- listwise CE vs W's T = 0.003 targets.

It runs on the GPU only in fit-free gaps or after the last fit, never beside a reporting phase.

## 7. Timeline and hard stop

T = first launch after the reviews and the coordinator GO.

| Window | 01 CPU (cores 0–49) | 01 GPU |
|---|---|---|
| T+0–0.8 h | staging, seed audit, qualification §6, smoke | — |
| T+0.8–3.1 h | collection O: K4S-120 2,000 + 250 holdout games (≈2.3 h) | — |
| T+3.1–3.7 h | collection O: S-200 1,500 + 250 holdout games (≈0.6 h) | — |
| T+3.7–4.5 h | O labeling plan and labeling (≈0.45 M roots) | — |
| T+4.5–4.8 h | pack, `verify_onpolicy` (O, O-holdout), O gate | — |
| T+4.8–6.0 h | O_W collection (≈3,300 games), pack, verify, O_W gate | R5 fit (≈1.4 h) |
| T+6.2–9.0 h | — (no reporting beside fits) | R5-rep, then R5W fits; calibrations |
| T+9.0–9.3 h | offline diagnostic (GPU) | diagnostic |
| T+9.3–17.8 h | **reporting block** (ABBA): R3a, R5, R5-rep, R3a-rep, R5W (each ≈1.7 h: K4S-120 then S-200); all always run | — |
| T+18 h | contention receipt frozen (SHA committed); then, and only then, reduction; RESULTS | — |

- **Expected compute:** about 18 h, about 640 core-hours and about 5 GPU-hours.
- **Hard stop: T+24 h**, enforced by the supervisor and driver.
- **Truncation [E8].** If the block can't finish before T+24 h:
  - (a) R5W's completeness **never** cuts the primary's N. R5W secondaries use R5W's own complete prefix under the
    same rule.
  - (b) Any cut is to the **largest seed-index prefix** complete, in both arms, for every student in the contrast;
    never to the "terminal set", which is duration-selected. Retired seeds are skipped inside the prefix.
  - (c) Every pause counts against the T+24 h clock, including the C7b collection pause the coordinator decides.
    Truncation then follows (a) and (b).

  Any cut is disclosed. **N never exceeds 1,200.**
- **R5 fit beside O_W generation (R2-11).** The fit keeps its 2× wall budget, and O_W dispatch is gated: no new O_W
  game starts while memory PSI avg10 > 10%. A fit stretched past 2× is stopped and resumed from its last checkpoint
  once O_W is done.

## 8. Risks and validity limits
- **One DAgger round with one behavior policy.** "No material effect" applies only to this round and scale.
- **Labels score one sampled hidden state per root**, as r1, G and O_W do. O's labeler path (the anchor kernel) and
  O_W's emitter path are different wrappers of the screen8 scorer. Their equivalence rests on the 125-state frozen
  equality, which is disclosed.
- **×4 is a single pre-declared choice; O is seen about 10.8× per state.** Memorization is visible only in the
  descriptive diagnostic.
- **Opening determinism:** with 25 fixed matchups and a v1 opponent, early-game states recur across C and E. This is
  reported through the feature-only duplicate rate. A gain could be concentrated in memorized openings.
- **Calibration** uses the off-policy held-out64 slice, while R5's training shifts toward cutoff states. Deployment
  play % is a diagnostic.
- **Same limits as X4S-3:** one opponent and five decks; budget equivalence, not a real slow Mac; about 6 unadjusted
  contrasts, with only the primary driving decisions.
