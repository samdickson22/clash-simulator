# X4S-4: do on-policy cutoff-state labels make a better student? (exploration, NEVER ADOPTABLE). Design only; nothing launched

Drafted 2026-10-12 by the X4S-3 owner (Opus), as requested by the coordinator after COORDINATOR 3466cefe (X4S-3:
"data helps" = NO; G-style generation stops). This is a plan for design review and Sol script review. **No host run
happens before both reviews and a coordinator GO.**

**Status: exploration only, NEVER ADOPTABLE.** No student enters a frozen manifest (SD1 stays R3a). Results are
never cited in K4S, TIERS or T1 reporting. No sealed K4S, T1 or TIERS outcome is read. No held-out deck or split is
used. No 03/04/Mac contact.

## 1. Hypothesis, contrasts and rules

**Why.** X4S-3 found that 46% more *off-policy* W roots (G, generated on W's own trajectories) did not help:
pooled R4-D − R3a = +0.7 pp [−1.5, +2.8]. The student matters most where it actually decides: at search
cutoffs and fallbacks. Those states are reached by the deployed student-tier agent, not by W. W-generated data
covers them only incidentally. This is the classic DAgger covariate-shift argument.

**Hypothesis.** Suppose R3a's recipe is refitted on r1 plus about 0.4 M W-labelled states that the *current*
student-tier agent (R3a in K4S-120 and S-200) reaches in its own play, chiefly at cutoffs. Then the refitted student
(R5) loses less to v1 in those same two deployment configurations, by more than the fit-seed noise.

**Students.** All use the X4S-3/R3a recipe: init v1 d77005d5, width 192, root-only, T = 0.003, play weight 1, value
weight 0, AdamW 3e-4, warmup 2000 + cosine, batch 8192, final EMA, frozen R3 trainer, loader6.

| ID | Teacher roots | Steps | Train seed | Role |
|---|---|---|---|---|
| R3a | existing 37509a43 | — | — | control |
| R3a-rep | existing X4S-3 checkpoint 8d537a78 (r1 only) | — | — | fit-seed noise reference (no refit) |
| **R5** | r1 (6,009,681) + on-policy set O, listed **×4** | 2500 | 2026101301 | **primary: on-policy labels** |
| R5-rep | same as R5 | 2500 | 2026101302 | treatment replicate (gated; see stop rules) |

- **Why ×4.** The trainer samples rows uniformly across shards and has no per-shard weight, so listing O's packed
  shards four times gives about 21% on-policy share for about 0.4 M states. That's a DAgger-style aggregate with the
  reviewed trainer unchanged. The factor is pre-declared and won't be tuned.
- **Why r1 and not r1 + G.** X4S-3 showed G adds nothing, so R5 differs from R3a-rep's data only by O. R5 −
  R3a-rep therefore isolates the on-policy addition.

**Deployment arms**, exactly as X4S-3: K4S-120 and S-200, opponent the exact v1 policy, d = 27, capacity 1, honest
lateness, the five X decks, alternating seats, 50 cells.

**Pre-declared readout** (paired bootstrap, 5,000 reps, seed 2026101301, percentile 95% CI; the X4S-3 reducer
semantics):
- **Primary contrast:** loss(R5) − loss(R3a), paired by seed and pooled over both arms with equal arm weight. Each
  arm is also reported separately.
- **Noise reference:** R3a-rep − R3a on the new seeds (X4S-3 found +1.4 pp pooled).
- **"On-policy helps"** means both:
  - upper 95% CI of pooled (R5 − R3a) < 0;
  - point estimate of pooled (R5 − R3a-rep) < 0.
- **Secondary:** R5-rep − R3a, if run (replication of the sign), and R5 − R5-rep (treatment fit-seed spread).
- **Also reported per student and arm:** cutoff %, student-default %, play %, wall p50/p99, overrun %.

**Stop rules.**
- Fixed N: a student's contrasts are reduced only after all its games are terminal.
- **Skip R5-rep** (its fit if not yet started, and its games in any case) if the pooled R5 − R3a point estimate is
  ≥ 0, using the X4S-3 gate logic.
- The fit is killed on a NaN, a divergence, or more than 2× its expected wall time.
- **Interrupted games:** excluded; their seeds are retired for every student and never re-run.
- **Memory:** no dispatch while MemAvailable < 24 GiB or memory PSI avg10 > 10%. Kill only on MemAvailable < 24 GiB
  or owned PSS > 50 GiB.
- **Fits never overlap S-200 phases** (the X4S-3 thrash lesson).
- **Yield on a console user:** stop, then ≤16 game processes.

**What the result changes** (descriptive, exploration only):

| Result | Next |
|---|---|
| On-policy helps | Iterate DAgger (collect with R5, label, refit) and scale O. A separate SD2 PREREG for the slow-Mac/1-core tiers only after the K4S/TIERS release. |
| Null | Both data levers are exhausted at this scale. The next lever is student capacity or architecture (width/heads) or value targets. Mac tiers stay on SD1. |
| R5 worse (lower 95% CI of R5 − R3a > 0) | The on-policy labels or the up-weighting hurt. Audit label quality (teacher at cutoff states versus the frozen references) before any rerun. |
| \|R3a-rep − R3a\| ≥ 4 pp, or R5 and R5-rep differ in sign | Fit-seed noise dominates; future student studies need replicates or ensembles. |

## 2. State collection

- **Behavior policy.** The deployed student-tier agent with the **current student R3a** (SD1, threshold
  0.5005528330802917), playing exactly the X4S-3 deployment configs K4S-120 and S-200 on 127x01. Opponent, decks,
  cadence, lateness and timing class are all identical. So the states are on-policy for the tier being improved,
  under the same host timing that produces its cutoffs.
- **Mechanism.** `collect.py` imports the **unchanged** X4S-3 `run.py` and wraps two module attributes, so the game
  path is byte-identical:
  - `run.apply_lateness`: called after the decision timer closes and lateness is computed. The capture therefore
    costs the game no decision time.
  - `run.run_game`: writes one capture file per game.

  At a captured decision it records, for the student seat:
  - the gate-c training row: `observation(build_public(b, seat), mask, d1)`, using the student's own
    `player.last_d1` and policy mask;
  - `info` (deep copy);
  - one opponent hidden state, sampled from the agent's current belief with a **separate** capture RNG seeded by
    (seed, tick), so the agent's own RNG is untouched;
  - the root RNG state and the candidate RNG state;
  - the root digest;
  - `deadline_stats`: hit, fallback, student_default, completed and candidates.
- **Which states.** Every student-seat search decision with **deadline hit = true**, excluding preparation cutoffs
  (the belief is mid-transaction; these are counted and disclosed). Also a seeded **25% sample of non-hit** search
  decisions, as nearby anchors, so the labelled distribution is cutoff-heavy without being cutoff-only. The strata
  stored are hit, student_default, fallback and arm.
- **How many.**

  | Arm | Games | Hit states/game (X4S-3) | Non-hit sample/game | ≈ states |
  |---|---:|---:|---:|---:|
  | K4S-120 | 2,000 | ≈78 (122.5 × 64%) | ≈11 | ≈178 k |
  | S-200 | 1,500 | ≈136 (182 × 75%) | ≈11 | ≈220 k |

  Total **O ≈ 0.40 M** states, about 6.5% of r1 before up-weighting. **Cap: 0.45 M**; collection stops at
  whichever comes first, the game count or the cap.
- **Deduplication.** Exact duplicates are dropped by the SHA-256 of the row's feature bytes (the
  `feature_bytes` set) together with the root digest. The lowest (seed, tick) is kept. A dedup ledger is
  committed as counts only.
- **Seeds.** Fresh banks, to be confirmed by the repo-wide `audit_seeds.py` scan before launch. The scan covers
  every seed-audit receipt, including X4S-1/2/3, K4S-confirm, TIERS and T1; it fails closed.
  - collection **C** = 4503606317370496 + [0, 4000): K4S-120 uses indices 0–1999, S-200 uses 2000–3499, and the
    rest is spare;
  - evaluation reporting **E** = 4503606307370496 + [0, 1200);
  - smoke = 4503606327370496 + [0, 8);
  - qualification = 4503606337370496 + [0, 8).

  A preliminary run of the unchanged X4S-3 `audit_seeds.py` against these four banks on an origin/main export
  (2026-10-12) found them clean: 156 sources, 291 prior ranges, 10,703 raw literals, none in the window, no
  intersections. The audit is rerun and committed as a receipt at staging.
- **Leakage rules.**
  - Training data comes only from bank C; no state from bank E is ever captured. The verifier checks that every
    packed row's `perspective_ids` lies in C.
  - Collection-game outcomes are never reduced or inspected. Labelled rows store `recorded_outcome = 0`, which is
    unused at value weight 0.
  - Calibration stays on the ExIt R1 held-out64 slice 0ecce0f0, label-free.
  - No K4S, T1 or TIERS output, deck or split is read.

## 3. Labeling budget

- **Teacher.** W-screen8 at no deadline, using the **K4 anchor kernel**. X4S qualification showed this kernel
  reproduces the frozen screen8 reference actions, candidates and scores on all 125 states, and again here on 01,
  matching X4S's receipt. That is the same equality `x4s/qualify.py` asserts. The labeler rebuilds the root from
  (info, opponent, root RNG state), checks the stored digest, regenerates candidates from the stored candidate RNG
  state, and scores them.
- **Rows.** The labeler writes `teacher_root = 1`, `teacher_wait_kind = 0`, `root_actions/scores/valid` from
  `core.last`, `expert_actions` (W's choice, with timed WAIT folded to 2304, as in the G emitter) and
  `teacher_search_action`. Each game is sealed as a v6 shard with the unchanged `exit_r3.rows.seal`. Shards are then
  packed with the **unchanged** `imitation/exit_r1/pack.py`. The trainer's `RootTeacherStore` reads only root rows,
  so pollWAIT rows aren't needed.
- **Cost.** G-01 receipts (1,229 games) give **0.28 core-s per W root** with script opponents (0.41 with v1, which
  includes v1 polls).
  - 0.40 M roots × 0.28 s ≈ **31 core-hours**, about **40 min on 01's 50 game cores** (one single-thread labeler per
    core).
  - Capture overhead per state (one belief sample, one root build, pickling) is about 10 ms. That's outside the
    timer, and adds about 1–2 s per game.
- **Storage.** Captures are about 30 KB per state, so about 12 GB. Labelled shards are about 2 GB. The ≤100 GB
  prefix cap holds.

## 4. Hosts

**127x01 only.** Collection games, labeling, fits and evaluation games all run on 01. That keeps the deployment
timing class identical to X4S-3 and adds no cross-host transfer.
- **Cores.** Games and labeling use physical cores 0–49 (labeling and games are never concurrent). The fit runs on
  56–61, with loaders on 120–125. Cores 50–55 and 62–63 stay free.
- **Limits.** nice 10, ≤70 processes, GPU ≤40 GB, disk ≤100 GB under `/mpac/sdicks02/jobs/clasher/x4s4-onpolicy-<date>/`.
- **Never touched:** `t1-*`, `end-*`, release roots, the paused hub mirror, or any other job's tree.

**08 is not used.** Labeling is about 40 min on 01, and using 08 would need two new host-touching transfer scripts,
each requiring review. 08 is also pre-emptible for perception B. If the coordinator later wants 08 for labeling, that
is a separate amendment: a reviewed transfer script and a determinism check of 08 labels against 01 labels. It is not
part of this plan.

## 5. Scripts

Everything not listed here is reused **byte-identical** from X4S-3 or the frozen sources:
- `x4s3/run.py`, `runtime.sh`, `detach.sh`, `calibrate.py`;
- `x4s/sdefault.py` and the S1 kernels;
- `exit-r3/source` (the trainer), `fit_runtime.py`, `loader_prefetch.py`, `proposals.py`;
- `exit_r1/rows.py` and `pack.py`.

The game metadata's `study` string therefore reads "X4S-3"; the reducer accepts it and identifies X4S-4 by seed
bank E.

| # | File (`reports/explore/x4s4/`) | New/modified | Purpose | Touches another host? |
|---|---|---|---|---|
| 1 | `collect.py` | **new** | Imports unchanged `x4s3/run.py`; wraps `apply_lateness` (post-timer capture) and `run_game` (per-game capture file and receipt); same CLI as run.py plus `--captures` | no (01 only) |
| 2 | `label.py` | **new** | Offline W-screen8 labeling of captures: rebuild the root, check its digest, regenerate candidates, score with no deadline, build v6 rows, `seal` per game. Self-guarded (STOP, MemAvailable, ≤50 workers) | no |
| 3 | `qualify4.py` | **new** | Pre-run qualification (§6) | no |
| 4 | `verify_onpolicy.py` | **new** | After packing: the X4S-3 `verify_g` checks (SHA, link-free inventory, non-blocking reads, sealing) plus a provenance check that every row's seed is in bank C; dedup counts; writes the O gate | no |
| 5 | `supervise.py` | **modified** (from x4s3) | One added option, `--script` (default `x4s3/run.py`; allowed `x4s4/collect.py`), plus pass-through of `--captures`. Guards unchanged | no |
| 6 | `run_fit.sh` | **modified** | IDs R5/R5-rep, seeds, shard list r1 + O×4, job path. Recipe unchanged | no |
| 7 | `driver.py` | **modified** | Constants: job path, `STOP_AT`, `FITS` = R5/R5-rep, students R3a/R3a-rep/R5/R5-rep, the R5-rep gate rule, fits-never-beside-S-200 for all fits. Fix the gate-event `utc` TypeError | no |
| 8 | `reduce.py` | **modified** | Students/pairs/readout keys for X4S-4; seed-bank check E; study-string acceptance | no |
| 9 | `write_report.py` | **modified** | Labels only | no |
| 10 | `audit_seeds.py` | **modified** | Own-echo label X4S-4 (as X4S-3 did) | no |
| 11 | `plan.json`, `plan-collect.json`, `plan-qual-*.json` | config | Arms, banks C/E/smoke/qualification, students | — |

No script touches a host other than 01. Per review-before-host-scripts, **all of 1–10 (and the configs) get a Sol
review before any run on 01**, including qualification.

## 6. Qualification (on 01, before any collection or reporting game)

1. **Unit tests** (as X4S-3), plus `label.py` unit tests on synthetic captures.
2. **Capture non-perturbation.** No-deadline K4S-none and S-none games give identical command hashes with
   `collect.py` and with the unchanged `x4s3/run.py`, on the 8 qualification seeds. This proves the capture leaves
   behavior untouched (agent RNG, belief, channels).
3. **Labeler equals the frozen teacher.** On the 125-state frozen corpus, `label.py`'s scoring path reproduces the
   screen8 reference actions, candidates and scores exactly, matching the X4S `qualify.py` equality.
4. **Capture → label round trip.** On smoke captures: the rebuilt root digest equals the stored one for 100% of
   states. Relabelling the same 200 states twice gives byte-identical scores. The row `feature_bytes` equal the
   student's actual model-input features at that decision.
5. **Trainer compatibility.** A packed smoke shard loads in `RootTeacherStore`, and a 2-step fit runs
   (`EXIT_QUALIFICATION_STOP_AFTER`, as in R3); its output is discarded.
6. **Smoke:** 8 seeds × 2 arms of collection, plus 8 + 8 R3a evaluation games and a live STOP test. All excluded.

## 7. Timeline and hard stop

T = first launch after the reviews and a coordinator GO.

| Window | 01 CPU (cores 0–49) | 01 GPU |
|---|---|---|
| T+0–0.7 h | staging, seed audit, qualification, smoke | — |
| T+0.7–2.8 h | collection: K4S-120, 2,000 games (≈960/h, 10 slots) | — |
| T+2.8–3.3 h | collection: S-200, 1,500 games (≈2,960/h, 50 lanes) | — |
| T+3.3–4.0 h | labeling, ≈0.40 M roots (50 single-thread labelers) | — |
| T+4.0–4.3 h | dedup, pack, `verify_onpolicy`, O gate | — |
| T+4.3–7.5 h | evaluation: R3a, then R3a-rep (K4S-120 1,200 games ≈1.25 h + S-200 ≈0.45 h each) | R5 fit (≈1.4 h, beside K4S phases only), then R5 calibration; R5-rep fit |
| T+7.5–9.1 h | evaluation: R5 | — |
| T+9.1–10.7 h | evaluation: R5-rep (only if the gate passes) | — |
| T+10.8 h | reduction, RESULTS | — |

- **Expected compute:** about 11 h, about 420 core-hours and about 3 GPU-hours.
- **Hard stop: T+24 h**, and never later; the supervisor and driver enforce it.
- **If time runs short:** R5-rep is dropped first, then evaluation N is cut to whatever is complete for all reduced
  students. That cut is disclosed and paired, and no extra seeds are added.

## 8. Risks and validity limits

- **One round, one behavior policy.** This is DAgger iteration 1 only. A null result doesn't rule out multi-round
  gains.
- **Label semantics.** The teacher scores one sampled hidden state per root, as the G/r1 teacher did. Labels come
  from the X4S-qualified anchor kernel. The r1/G emitter path is a different wrapper of the same screen8 scorer;
  their equivalence rests on the 125-state frozen-reference equality and is disclosed.
- **Up-weighting.** ×4 is a single pre-declared choice. Its sensitivity isn't explored, to avoid a forking path.
- **Same limits as X4S-3.** One opponent and five decks; budget equivalence, not a real slow Mac; calibration slice
  reuse; about 4 unadjusted contrasts. The deployment-timing class and the seed and deck schedule are those of X4S-3.
