# Plan: freed GPUs/CPUs, 2026-10-09 10:30Z → ~Oct 11 04:20Z

Planning analyst (Opus) for coordinator 0523ae6f. Read-only analysis; no jobs launched.

## 0. Bottom line

**CPU (search games) is the binding constraint, not GPU.** Every high-value item next is search-heavy (W-screen8 at
~177 ms CPU p50 per decision). The GPU demand worth having over the next 12 h is ~25–40 GPU-h, against ~90 available.
So:

1. **Make W-screen8 cheap enough for live play.** Distil the search teacher into a fast student (ExIt round 1), and run
   the two CPU checks that decide whether W's gain survives live conditions. This is the top priority.
2. **Finish T11 v2 and run its registered gate (a).** T11 is nearly done: by my count, 6 epochs is about 46.46k steps,
   seed 21's checkpoint step-46460 was verified at 10:17Z, and seed 22 is ~1 h from its end.
3. **Park the T5 GRU now.** Release 04's CPU to teacher generation.
4. **Treat the remaining leased GPU time as opportunistic.** Fill it with a preemptible capacity scan of the human
   prior. No DDP, and no extra T11 seeds.

Why distillation: W cut losses 50.8→19.3% (W-screen8 RESULTS), but its decisions miss the 200 ms live budget 68.8% of
the time (w-confirm: wall p95 491 ms for W; loaded p95 330 ms for screen8). Live play gets W's gain only if the
behaviour is available inside the deadline. A student that imitates W is both the fallback for overruns and a
proposer (gate (b): the proposer moved C56 score to 0.656).

## 1. Candidates

| # | Workload | EV toward ladder wins | GPU-h / CPU-h (24–40 h) | Depends on | Wasted-compute risk |
|---|---|---|---|---|---|
| **a** | W-screen8 teacher labels → student fine-tuned from v2 on teacher + human rows (ExIt r1; DAgger r2 later) | **High.** The only path that moves W's −31.5 pp into the deadline-bound live player. | 8–15 GPU-h; **1,500–2,500 CPU-thread-h** (~8–12M labelled decisions at ~0.2 s each; measure in the first 15 min) | v2 final (or v1), teacher-label emitter (B2), trainer adapter (B3) | **Medium.** In Aug, Hog play-gate students collapsed to all-wait and broke under free-running states. Mitigations: soft root-score targets, rare-play weighting, human-row anchor, game-based (not NLL) screen, DAgger r2. |
| **b** | More T11 seeds or longer runs | **Low.** v1's 4 seeds differed by only 0.0007 dev NLL; v2's schedule is ending. | ~50 GPU-h per extra seed | – | **High.** Selection noise, no strength gain. **Don't.** Finish both seeds → select → registered gate (a). |
| **c** | T5 GRU (234 rows/s; Stage A/B need 6–8 h of qualification) | **Very low.** Descriptive only, decoupled from the gates. v1 feed-forward has passed (b) and (c). Recurrence also conflicts with search calling the model on reconstructed states (DESIGN §0.5). | 120–200 GPU-h remaining on 1 GPU; DDP qualification another 8 | – | **Very high.** **Park it.** |
| **d** | Reserve/tempo search change (under-4 arrivals at 61%) | **Medium, but unproven.** The R leaf term was +2.0 pp worse; E was +1.5 [−0.3, 3.4]. The metric is mechanically confounded by delay (delay-fixes). | ~150 CPU-h per 600-seed arm | E1b below | **High** if run blind. **Gate it on E1b**: run it only if W loses to a human-like opponent through punished low-elixir defence. |
| **e** | Live perception and decision latency (vectorized decoder, W-screen8, GIL roots) | **High**, but the live path is the **Mac**, so ~0 fleet compute. | ~0 GPU-h | Sam's Mac authorization | **Low.** Prepare **one combined Mac E4 package** now so a single session measures everything. |
| **f** | DDP over 10 GbE | **None now.** No run left is >10 h: student arms are ~1–2 h and T11 is finishing. | 8 GPU-h just to qualify | – | **High. Don't.** |
| **g** (new) | **E1:** CPU checks of W under live conditions | **High per CPU-h.** They decide whether (a) and (d) matter. | ~100–150 CPU-h, about 1–1.5 h wall | B1 harness | **Low** |
| **h** (new) | Capacity scan of the human prior (v2 data, ~4× width), preemptible | **Low–medium.** A better proposer/fallback, if latency allows (≤15 ms p99 single core). | ≤40 GPU-h on otherwise idle leased GPUs | B5 adapter | **Medium.** Kill rule: dev-NLL gain <0.005 at matched rows by 25% of the schedule. |

**E1 arms.** S6 harness, 600 fresh paired seeds, symmetric d=27, 5 decks / 25 matchups:

- **E1a:** W-screen8 vs baseline under an **enforced 200 ms single-core deadline**, using best-so-far or v1 fallback.
  Does W's gain survive the deadline?
- **E1b:** W and baseline, each against the **v1 standalone policy**, as a human proxy. Does W beat human-like play,
  and is under-4 causal for its losses (loss-review)?

## 2. T5 GRU on 04: no, release it

- At 234 rows/s it needs ~8 days. At the unmeasured 400 rows/s it still needs ~120 GPU-h, and only gives a descriptive
  addendum.
- Stop it at its next checkpoint with an exact-state backup (one is already verified off-host at step 1850). Retain
  all artifacts. No Stage A/B qualification, no DDP.
- Revisit only if a later v2-scale study needs recurrence.

## 3. Allocation, next ~12 h (10:30–22:30Z)

| Host | GPU | CPU | GPU-h |
|---|---|---|---|
| **01** (home) | T11 s22 to completion (~11:15–11:30Z). Then v2 selection and registered gate (a) scoring. Then student arm S-mix (~17–19Z). | ≤24 SCHED_IDLE while T11 runs; then ≤64 teacher-gen | ~6 |
| **16** (leased) | s21 final backup and state audit, then v2 gate (a) share. Then **h** arm 1, preemptible. | ≤16 procs (lease) | ~8 |
| **04** (home) | GRU parked ~10:45Z. Student arm S-teacher (~17–19Z). | **E1 (~12:30–14:00Z), then teacher-gen**, ≤96 procs | ~3 |
| **03** (CPU) | – | **E1 + teacher-gen**, ≤96 procs. Keep cache services (hard stop Oct 11 04:00Z) and the archive copier. | 0 |
| **08** (home) | **Idle, reserved for B** (critical path). | Teacher-gen ≤96 at nice 19 with a stop file. **Fully vacate and verify** before the B call; in-flight games are expendable. | 0 |
| **09** (leased) | A17 qualifications. Then student control arm S-human (v2 continued on human rows only, same steps). | ≤16 | ~2 |
| **13/14/15** (leased) | R16-1 recaptures. Then **h** arms 2–3 plus student round-2 reserve. GPU only, no sims (lease). | ≤16 each | ≤30 |
| **05** | – | Light only | 0 |

Total: ~50 GPU-h (about half opportunistic) and ~1,800 CPU-thread-h. The GPUs left idle are a deliberate choice:
nothing else on the table earns its compute.

## 4. What to build first (in parallel, starting now)

| ID | Build | Owner | Due | Acceptance |
|---|---|---|---|---|
| B0 | Park the GRU (exact checkpoint, backup, exit receipt) | T5 owner | 10:45Z | SHA-verified off-host |
| B1 | E1 harness: reuse the w-screen8 harness plus the gate (c) v1 adapter; add a wall-deadline mode with fallback | Sol | ~12:30Z | OFF arm reproduces frozen baseline parity (250/250); deadline mode deterministic under an injected clock |
| B2 | Teacher-label emitter: S6 sims (5 train decks plus the L2 decks) → v6 store rows. Records the chosen action (a timed WAIT expands into per-poll waits), the root score vector and the final outcome. Opponents: a mix of W, v1, baseline and scripts. | Sol (Astra if equality fails) | ~15:00Z | Obs rows byte-equal to the gate (c) adapter on the same states; action replay reproduces the game; rate measured against target in 15 min |
| B3 | Student trainer adapter: new path; frozen T11 trainer untouched. Mixed sampler (teacher:human), soft-target CE on root scores, optional value head. | Sol | ~15:00Z | Equality test: ratio 0 reproduces T11 loss exactly |
| B4 | Freeze the exploration plans for E1 and the student screen (fresh seeds, tuning seeds separate) | Opus | 12:00Z / 16:00Z | Frozen plan SHA before the first game |
| B5 | Capacity-scan config adapter plus a single-core latency probe | Sol | ~13:00Z | Proposer p99 recorded per width |
| B6 | Combined Mac E4 package: vectorized decoder, W-screen8 ON/OFF, 1/4 GIL roots, fallback policy | Sol, Opus review | before Sam's OK | Pinned binary and config hashes |

**Student screen (exploration lane), ~19–22Z:**

- Arms: S-mix, S-teacher, and the S-human control, each ~1 h on one GPU (~40M rows at 12k rows/s).
- Tests:
  - 256 head-to-head games against v2;
  - as the **fallback** inside deadline-enforced W search vs the v1/v2 fallback (600 paired seeds);
  - play rate and wait collapse checked against the teacher.
- **Kill rule:** play recall <50% of the teacher's, or the fallback arm not better than the v2 fallback.
- If an arm survives, DAgger round 2 runs overnight: the teacher labels student-rollout states, using ~1,000 CPU-thread-h.

## 5. Gates and rigor

- **Exploration lane** (frozen plan, fresh seeds, no tuning on reporting seeds, no PREREG): E1, the student screen, the
  capacity scan, and any reserve follow-up.
- **Confirmatory, full PREREG and independent review:**
  - v2 gate (a): already registered in `imitation/gate-a-v2/PREREG.md`.
  - The v2-vs-v1 adoption gate: re-scope T12 now that (b) has passed with v1.
  - Any student replacing v1/v2 as the live fallback or proposer. This also needs an L2-v4 amendment, because
    L2-v4 pins the player.
- **Perception (A1 → A2 → B on 08)** keeps priority over all of the above. Nothing in this plan touches 08's GPU or the
  frozen perception trees.
