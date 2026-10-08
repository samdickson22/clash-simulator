# Independent pre-registration review: gates (b) and (c), v1

Reviewer: Opus review sub-agent (DESIGN §7). Read-only on 127x05, 2026-10-08 ~21:14Z. No games or heavy jobs
were run, and no gate (a) heldout output was opened. This file is the only one written.

## Reviewed content

| File | SHA256 at review |
|---|---|
| `imitation/gate-b/PREREG.md` | `fb92c3ddd9de195e48cd803969a713d2a1d0bb85e10d460ea5e9bde8665304e0` |
| `imitation/gate-c/PREREG.md` | `872e4de5a8f2b58dbdf845d353e9cbe7b3a2ebc0ecd62e943f932095afd5586d` |

Both files changed during the review. At the start they hashed to `73f3820aa032daf28cecd841c42ae48ec73943e5b6d9d1fdd12092550ad24513` (b) and `9c5eefb41dd88a548d2ab9753d16884bd85b383c5b94474fe97a12cb3742c779` (c).
I re-read both; the only change was the closing "Prospective analysis-contract tests" paragraph. The verdict
applies to the hashes in the table. The seed-inventory section was out of scope, as instructed.

Implementation read to test the text against: `imitation/evaluation/{register,run_gate,smoke,search,candidates,
run_p16,p16_adapter,standalone}.py`, `imitation/gates-bc/operations/{analyze_gates,run_host,pilot.sh,
seed_inventory}.py`, `imitation/model/inference.py:load_policy`, P16 `run_eval.py` and `compare.py`, Stage 5b
`deadline_player.py`. Hashes of the files I relied on, at review time (full SHA256):

| File | SHA256 |
|---|---|
| `imitation/gates-bc/operations/analyze_gates.py` | `ad6db06705cde576385bc1244e2cb097a2eb6b584f16fe71dd2445b336847500` |
| `imitation/evaluation/run_gate.py` | `687964778417e5d32d4b8d154c820bfc746f5406930e51403760194a23f89fba` |
| `imitation/evaluation/smoke.py` | `ebbac105fd96e2f8c4999057956eb23b747f2be21b949a01c9e57841eb7edefc` |
| `imitation/evaluation/search.py` | `f0e8f638429f1ff5b7587b54afd346ee95a43d8997847db2f9b1162dc9dba973` |
| `imitation/evaluation/candidates.py` | `aedccfb5c38d0d1269c80a5999613ae61f0adf1dcd6299ec4bf1a5016cf4ce9c` |
| `imitation/evaluation/register.py` | `863e0629fdb32899bf5f1c186b9a31bff4e049282ef9cd77194ee30486a8a32a` |
| `imitation/gates-bc/operations/run_host.py` | `35e1a929662bc4a5ed9f826f883b39095ae661b43a900aeb27427d01e8b1ff1a` |
| `imitation/gate-b/v1/schedule.json` | `7a96ca9004a045f17f30b7534da609f5536fada0894b620216d90a8766e756d2` |
| `imitation/gate-b/v1/proposed-seeds.json` | `299f81c8e1917f01d0768ce976749c0019d03eb36951b36ca59b53b1f0234615` |
| `imitation/gate-c/v1/schedule.json` | `f6cf74d08b7d42f32d8f230c6bc77a9112f15275acbcf4ca9f37d115c7c12bee` |
| `imitation/gate-c/v1/proposed-seeds.json` | `a78f7e9b92eb635600144963489543daaeec8a7e768cdb216f4ff3825baf10c3` |

Provenance verified: the seal, release and selection files hash to `8a8929326dc2d1313fcd10e4422cb770e9bc246eccd28d7ed2e5b746fbbae681`, `c8a44c8dcb04e07f582570bdf994e9c8c576c256f201a7f7b53de4b44412d3c5` and
`1cbb2bf54c98dc570eb1715950f9ec21e9f4459560727bb4ac26c0d63789fc69`, matching both drafts. The selection names `main-2026100802`, step 22552, checkpoint
`d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`, dev joint NLL 0.34537 (best of four). The seal is dated 20:21:29Z with
`heldout_inference_started: false`. `load_policy(..., ema=True)` loads `payload["ema"]`. `run_gate.py`,
`smoke.py` and `p16_adapter.py` refuse temperatures ≠ [1, 1, 1]. This matches the coordinator's EMA, T=1 decision.

## Verdict: **APPROVE WITH REQUIRED CHANGES**

The design is faithful to DESIGN §5.2/§5.3. The arms, matched counts, game counts, protocols, seat swaps, tests and
bars all match, and the one count-convention deviation is justified and asserted. The statistics are sound and
fixed in advance. The power claim holds up roughly as stated. Nothing found requires a REJECT.

The drafts do leave several outcome-relevant behaviours unspecified or misdescribed:
- exception handling (R1);
- what happens to late decisions, and how exposed the zero-overrun bar is to host noise (R2);
- a schedule claim that is false: eval_ood (R3);
- a discordance definition that is inverted in code (R4);
- resume units that don't match the code (R6);
- missing pins, notably the analysis script itself (R8).

Each could make a PASS or FAIL contestable after the fact. All are cheap to fix before freeze.

## 1. Fidelity to DESIGN (checked)

| Item | DESIGN | Draft / code | Status |
|---|---|---|---|
| (b) arm A | Stage 5b: script choice, no-op, script top-4, ability, 16 sampled; 200 ms, 2 threads | same; `MatchedDeadlinePlayer` (deadline .2, threads 2) | OK |
| (b) arm B | imitation top-8 dedup vs scripts + random fill to 16; count same; inference inside deadline | `replacement_candidates`: base + ≤8 legal proposals + A's own draws, truncated to **A's post-dedup count**; asserted per searched root; timer starts before `observe()` | OK. The count convention is a documented, justified deviation that preserves the matched-count intent. |
| (b) primary | 320 worlds × 2 swaps = 640 | schedule 320 head-to-head pairs; decks fixed, controllers swap | OK |
| (b) secondary | A and B each 256 vs scripts, identical seeds | 128 pairs × 2 seats × 2 arms; same `ep`, same seat-relative seeds | OK |
| (b) bars | ≥.53 & LB>.50; drop ≤.03; 0 >250 ms & p99 ≤ A+15 | identical | OK |
| (c) P16 | 6 cells × 2 fresh blocks = 384 per policy, 3 policies, identical seeds | 2 × 6 × 16 worlds × 2 seats; analysis asserts identical seed, seat, decks, levels across policies | OK |
| (c) H2H | 128 worlds × 2 = 256 vs s2902, P16 Python engine, mask asymmetry recorded | 64 holdout + 64 hog26; fixed physical decks; v5/v4 recorded | OK |
| (c) C56 | 384, 3 styles × 128, eval-role decks, descriptive | 192 pairs, 64 per style | OK |
| (c) total | 1,792 | 1,152 + 256 + 384 | OK |
| (c) tests | exact McNemar p<.05; Newcombe for s2902; H2H LB>.50 | `compare.mcnemar` (exact two-sided) plus direction; `compare.newcombe`; percentile bootstrap | OK |
| Policies | v1 at T=1, gate hazard per 250 ms | `StandalonePlayer` enforces a 5-tick cadence and stochastic sampling; EMA weights; T=1 guard | OK |

## 2. Statistics: my own arithmetic

**Gate (b) primary.** Let q be the fraction of decisive pairs, where the same controller wins both seats (pair
mean 0 or 1). Then Var(pair mean) = q/4 − (μ−.5)², and SE = sqrt(Var/320). The rule "point ≥ .53 AND percentile
LB > .50" has an effective threshold of max(.53, .5 + 1.96·SE).

| q | SE at μ=.55 | threshold | power μ=.54 | power μ=.55 | power μ=.57 | 80% MDE |
|---|---|---|---|---|---|---|
| .10 | .0084 | .530 | .88 | .99 | 1.00 | .537 |
| .30 | .0151 | .530 | .75 | .91 | 1.00 | .543 |
| .40 | .0175 | .534 | .63 | .82 | .98 | .549 |
| .50 | .0196 | .538 | .53 | .72 | .95 | .555 |

DESIGN's "SE .015–.020, ~70–90% power at .55" is correct. The false-pass probability at μ=.50 is ≤ .025. That makes
the test one-sided at 2.5%: conservative, and matching DESIGN's "95% … LB > .50". Given the prior evidence (ExIt
0.4805 [0.426, 0.531]; srp-pub vs srp-pub-pol 0.809 vs 0.797), the realistic effect may be under +.04. A FAIL
would then be weak evidence against such small effects, so the report must not call it "no effect" (R5).

**Gate (c) P16 McNemar.** Simulated at 384 pairs: 30% discordant with a 10 pp gap gives power .94; 40% gives .87;
a 7 pp gap gives .68; a 5 pp gap gives .41. DESIGN's "~90%" holds for a ≥10 pp gap only.

**Gate (c) H2H.** The bar is LB > .50 at 128 worlds. Power is .37–.56 at μ=.55 and .92–.99 at μ=.60. "s2902 stays"
is therefore the expected outcome unless v1 is clearly stronger, so the report should not present it as
equivalence (O9).

Clustering is by world everywhere, as DESIGN specifies. There are no multiplicity loopholes:
- each bar is a single prespecified comparison;
- per-cell, per-family and per-style results are descriptive;
- there is no variant selection;
- the gate (c) decisions are separate decisions, not a "pass any of" construction. R10 still asks the draft to
  state what each one does.

## 3. Required changes

**R1 — both PREREGs, "technical interruptions" paragraph (gate b "Analysis and pass bars", last paragraph; gate c
"Analysis, bars and decisions", last paragraph): define the term narrowly and say what an in-game exception does.**

Currently any crash looks like a "technical interruption" that is replayed from seed. Gate (b) games are not
bit-reproducible (wall-clock deadlines), so a replay can silently avoid a state that crashed B. Examples:
- `replacement_candidates` raises on an illegal imitation proposal;
- the matched-count `assert` in `smoke.play`;
- `StandalonePlayer` raises on an illegal sample or cadence violation;
- an engine or script exception.

Stage 5b r1 stopped on exactly such an exception (an unsupported held-out deck), so this is not hypothetical.

Insert in both:
> "A *technical interruption* is only an external stop of an otherwise healthy process: operator or supervisor
> SIGTERM/SIGKILL, lease cutoff or reclaim, host reboot or loss, OOM-kill by the kernel, or disk/filesystem
> failure. It is replayed per the resume rule. Any exception or assertion raised inside game, engine, script,
> search, model, candidate-matching, legality or D1 code is **not** technical. Record it with its traceback and
> world identity. No further games of that gate start. For gate (b), an exception attributable to arm B or its
> matching assertions is an integrity FAIL of gate (b). Any other in-game exception stops the gate pending a
> written, outcome-blind amendment reviewed before any further game. Exceptions are never resolved by replaying
> the same world."

**R2 — gate b, condition 3 and a new sentence after it: make the timing bar's scope, in-game effect and
interpretation explicit.**

Insert:
> "A decision that exceeds 200 ms is applied in the game unchanged. Simulated time is paused while a controller
> decides, so lateness has no in-game effect and counts only toward condition 3. Condition 3 covers every B
> decision in all 896 B games (640 primary + 256 secondary), about 6.7×10^5 decisions. A's pool is every A
> decision in the same 1,152 games (the primary opponent role plus the A secondary). Report A's >250 ms count
> under identical conditions as a host-noise control. Report the conditions 1–2 verdict and the condition 3
> verdict separately. A condition 3 failure is a gate (b) FAIL whatever its cause, with no rerun of these games;
> any timing remedy needs a new registration on fresh seeds."

Why this matters: the pilots on admitted configurations total 95,196 decisions with 0 overruns. That only bounds
the per-decision overrun rate below about 3.2×10^-5 (95%). P(zero overruns in 6.7×10^5 decisions) is .51 at a rate
of 10^-6. At the rate seen on 14 with 16 processes (1 in 12,142), it is about .002. See also escalation E1.

**R3 — gate b, "Schedule and fresh seeds", first paragraph, and "Analysis", first paragraph: the eval_ood claim is
false for the actual schedule.**

`schedule.json` has **320/320 primary and 128/128 secondary pairs with role `eval`, and 0 `eval_ood`** (none of
the eval_ood decks are supported by the train-only prior). Deck identities are also concentrated:
- 44 distinct own decks in the primary and 28 in the secondary;
- one deck fills all 46 Hog 2.6 worlds;
- 22 primary worlds are mirror identities.

Replace "Use Stage 5b role-held-out eval/eval_ood planning" with:
> "Use Stage 5b role-held-out planning. Under the train-prior support restriction, the frozen schedule contains
> only `eval`-role decks (0 eval_ood worlds) and 44 distinct own deck identities in the primary. Inference is
> conditional on this fixed deck schedule and makes no claim about eval_ood or deck-population generalization."

In "Analysis", delete "and eval/eval_ood descriptions". If kept, they must say eval_ood n=0.

**R4 — gate b, "Analysis": define "pair discordance" and fix the code to match.**

DESIGN's power model calls a pair discordant when the same controller wins both seats (pair mean 0 or 1).
`analyze_gates.py` line 44 counts `B,0 score != B,1 score`, which is the complement (seat-determined split pairs).
Insert:
> "A *decisive* pair has pair mean 0 or 1; a *split* pair has mean 0.5; draws give 0.25/0.75. Report counts of
> all five pair-mean values and the decisive fraction q used in the sample-size premise."

Rename or fix the code field before freeze.

**R5 — gate b, "Sample-size premise": state the effective threshold and the conditional nature of the claim.**

Replace with:
> "The joint rule has effective threshold max(.53, .5 + 1.96·SE). At 320 pairs, power at true .55 is about .91,
> .82 and .72 for decisive fractions .3, .4 and .5. The 80% MDE is about .543–.555, and the false-pass rate at .50
> is ≤ .025. These are design premises, not evidence about the effect. Given ExIt 0.4805 [0.426, 0.531], a FAIL
> does not exclude improvements smaller than about +.04."

**R6 — both, the amendment paragraph "P16 cell execution may be split…": make the resume unit and procedure match
the code, and ban partial analysis.**

The text describes per-world atomicity and fresh attempt directories. The code does something different:
- `run_gate.py` publishes one receipt per **game** (`games/pair-NNN-ARM-SEAT.json`), into the same `games/`
  directory, and skips existing receipts on resume.
- In-flight games leave no receipt.
- `run_p16.py` refuses to continue past a failed per-world adapter receipt.
- `analyze_gates` reads only the `--games-root` list and fails on duplicates.

Insert:
> "Gate (b) and gate (c) C56 publish one receipt per game. On resume, completed games are kept, and missing games
> replay unchanged, on an admitted host at its frozen concurrency. Before any resume, append each interrupted
> in-flight game or world (world, arm, seat, host, worker log path, reason) to an interruption ledger. For P16 and
> H2H, a failed world is replayed in a fresh attempt root named in the ledger. The analysis roots are exactly the
> primary `games/` root plus the ledger's replay roots, and failed-attempt roots are excluded by the ledger only.
> No outcome analysis is performed on an incomplete set at any time. If a gate cannot be completed, it is
> reported as *not completed, no verdict*, with no outcome summary."

**R7 — gate b, new subsection "Hosts, concurrency and load envelope" (currently only "fixed host concurrency are
pending").**

Insert:
> "Game hosts and worker counts:
> - 127x03, 127x04, 127x13 and 127x15 run 16 workers each; 127x14 runs 8.
> - Each worker is pinned to its own 3-CPU taskset, at nice ≥ 10, with 2 Rust threads and 1 Torch/BLAS thread.
> - Workers use a single global `--workers` N with a static `pair % N` partition.
>
> These are frozen for the whole run.
> - No change of concurrency, host set or affinity in response to observed timing.
> - During the run, operators may inspect liveness, exit and resource receipts only, not timing or outcome
>   receipts.
> - Other own CPU workloads on a gate (b) host must not exceed those present during that host's qualifying pilot
>   (for example, the 03 v4 threshold grid). Otherwise that host stops starting gate games.
> - If a console user appears, the host stops starting new games, and in-flight games finish.
> - On leased hosts, no game starts after 04:30Z and all are killed at 05:00Z. Killed games are technical
>   interruptions (R1/R6)."

Also record that every timing pilot so far ran **B vs scripts** (`pilot.sh` → `smoke.py`, no `head_to_head`). The
primary runs two searching controllers per process, roughly twice the search duty cycle. Before freeze, either run
one B-vs-A pilot per admitted host at frozen concurrency (disjoint plumbing seeds, outcomes not computed), or have
the coordinator record an explicit waiver in this section.

**R8 — both, the freeze block: list every pin and mark the open ones.** Add a "Pins" table to both drafts:

| Pin | Current value | State |
|---|---|---|
| Released checkpoint | `d77005d5…72ed` | done |
| Selection, release, pre-heldout seal | `1cbb2bf5…`, `c8a44c8d…`, `8a892932…` | done |
| Snapshot tree | candidate `506eb289379861ce…` | **TBD**. It is not the qualified `e3c60ef3…`, so name the full hash and cite the timing, skew and parity receipts produced **on it**. `pilot.sh` defaults to `e3c60ef3`, so say which pilot used which snapshot. |
| Runtime root and manifest | `runtime-bc-v1`, `c3dbc5d3…0213` | **TBD**. Name it as the authoritative `ROOT` and confirm that `register.py`'s `ROOT/runtime-inputs.json` is this root on every host. |
| Analysis script `gates-bc/operations/analyze_gates.py` | `ad6db067…6847500` (in flux) | **TBD**. It is **absent from `register.py`'s file list**; add it, and add `test_analysis.py`. |
| `run_host.py`, `run_gate.py`, `smoke.py` | listed via `imitation/evaluation/*.py` except `run_host.py` | add `run_host.py` |
| P16 `compare.py` (imported at analysis time) | n/a | **TBD**. It is not in gate (c)'s list (only `run_eval.py` is); add it. |
| Comparators s2902 1M and human-bc-natural | in gate (c) list | write their SHA256s into the gate (c) text |
| Stage 5 prior `human_deck_catalog.json` / staged `prior.json` | n/a | write its SHA256 into the gate (b) text |
| ExactFastPrior parity receipt `receipts-t6t8/prior-parity-r1.json` and D1 skew receipts | exist | cite hashes |
| Schedules and proposed seeds | b `7a96ca90…`, `299f81c8…`; c `f6cf74d0…`, `a78f7e9b…` | pin, or re-pin after any shift |
| Merged seed audit across 10 hosts (01/02/03/04/05/07/08/13/14/15) | inventories `complete_inventory: false` | **TBD**, in progress |
| Host, concurrency and per-host pilot receipts | see R7 | **TBD** |
| Review receipt (`passed`, `prereg_sha256`, `snapshot_tree_sha256`) | n/a | after these changes |

**R9 — both, after "D1 is deck-free…" (b) and "D1 is shared with search…" (c): state the fair-information rule and
its evidence.**

Insert:
> "Neither arm nor v1 reads the opponent's unrevealed hand or cards, deck order or engine RNG. Opponent elixir and
> revealed hand/cycle facts are derived only from public events (fair per project rule). Search roots use opponent
> states sampled from the train-only public prior with the player's own planner/belief seeds. Evidence: the T1
> §2.4.1/§2.4.2 audits and the §2.4.3 skew receipts (hashes in Pins). Legacy comparators and scripts keep their
> unchanged public v4 observations."

**R10 — gate c, "Analysis, bars and decisions": say what each decision does.**

The P16 bar has no stated consequence. Insert:
> "Gate (c) has two independent decisions and one descriptive protocol.
> 1. The P16 bar certifies (PASS) or does not certify (FAIL) 'v1 standalone beats the P16 BC'. It changes no
>    default player and does not affect gate (b) or decision 2.
> 2. H2H: LB > .50 means v1 replaces s2902 as the P16 reference policy; otherwise s2902 stays.
> 3. C56 is descriptive.
>
> No combined 'gate (c) PASS' is reported."

If the coordinator wants a different consequence for (1), it must be written in before freeze.

**R11 — both, new sentence in the protocol sections: define truncation and draws.**

Insert in (c):
> "P16/H2H use `max_ticks` 6001, which resolves the tiebreak after 300 s. A game recorded with `terminated=false`
> is not excluded: it is scored as `eval.py` recorded it (a draw is a non-win for McNemar and 0.5 for score), and
> the truncated count is reported."

Change `analyze_gates.py`'s `assert r['terminated']` to count and report rather than abort, or state that it
aborts and what happens next.

Insert in (b) and (c) C56:
> "C56 games run to engine `game_over` (regulation, overtime, tiebreak). No winner means a draw, scored 0.5."

**R12 — gate b, "Analysis" (and gate c): define the DESIGN §7 spot-replay check.**

Gate (b) games are not bit-reproducible: the number of completed rollouts depends on wall clock. Insert:
> "Coordinator spot-replays (4 gate (b) games) must reproduce decks, initial state, seeds, and the candidate set at
> every searched root up to the first root whose search was deadline-truncated. Outcome equality is not expected.
> Gate (c) P16/H2H/C56 spot replays are expected to reproduce the exact action stream; any mismatch is reported."

**R13 — both, "seed plan": verify seeds above 2^31.**

Every qualification seed so far was below 2^31 (68–69 M). All gate seeds are 2.82–3.22 ×10^9, above the int32
range. A silent int32 or modular reduction in any seed consumer (Python, NumPy, Torch, the Rust engine, native
search) would create collisions the integer-equality audit cannot see. Insert:
> "Before freeze, a recorded plumbing check confirms that every seed consumer accepts values in [2^31, 2^32)
> without truncation: one game per route at a disjoint plumbing seed above 2^31, outcomes not computed, plus a
> static review. After any namespace shift, every seed must remain below 2^32 (`np.random.seed`)."

**R14 — both: remove stale or contradictory text.**
- Gate (b): delete "Freeze after T5 selects its checkpoint" and "Re-snapshot and requalify if T5's model code
  differs". Change "T5 hash" in the launch prerequisite to the pinned hash.
- Gate (b): define "20 full smoke games" as "20 real-checkpoint games on the final snapshot and runtime, zero
  candidate illegal or rejected actions".
- Gate (c): delete "if model code changes during T4/T5".
- Both: merge the host lists. The body says 01/02/03/04/05/07/08; the amendment adds 13/14/15; `register.py`
  requires all ten. List all ten once.

## 4. Optional suggestions

- **O1.** The p99 condition is close to vacuous. Both arms' p99 is deadline-dominated (pilots: 200.2–200.4 ms).
  Also report, descriptively, searched-only p99, the overshoot distribution max(0, t−200), B's `proposal_ms`
  p50/p99, and the truncation and fallback fractions per arm.
- **O2.** Add a descriptive deck-identity-clustered bootstrap for the gate (b) primary as a sensitivity check (44
  identities; 46 worlds on one Hog 2.6 deck). It is not a bar.
- **O3.** McNemar treats the two seats of a world as independent pairs, and `compare.newcombe` is the unpaired
  interval. Keep both as registered, label them that way, and add a descriptive world-clustered resampling of b−c.
- **O4.** If belief seed = planner + 1 as the draft states, then seat 0's belief seed (w+100001) equals seat 1's
  planner seed. It's harmless and symmetric under the swap, but verify it and say so, or spread the per-seat seeds
  (e.g. +100000 + 10·seat) **before** the audit runs.
- **O5.** Historical P16 rates (s2902 88/192, BC 40/192) came from `pilot-runtime-v4`; this gate uses the checkout
  engine. Show this gate's s2902 and BC script rates next to the historical ones as an engine-drift check, and make
  no v1-vs-historical comparisons.
- **O6.** Report whether the P16 "holdout" deck identities appear in C56 train-role perspectives, since v1 may have
  imitated humans on them.
- **O7.** State that the real-checkpoint pilot and qualification games (no winners recorded) stay unscored at least
  until both gates publish, and never enter either analysis.
- **O8.** Within a tick, the seat-0 controller decides first. This alternates under the swap and is balanced; a
  sentence saying so preempts a reader's question.
- **O9.** In the gate (c) text, state the H2H power: about .4–.55 at μ=.55, so "s2902 stays" is not evidence of parity.

## 5. Escalation to the coordinator (not a condition of this approval)

**E1. Zero-tolerance timing over about 6.7×10^5 decisions.**

DESIGN's "0 decisions > 250 ms" was written with no exposure estimate. The current evidence is 95k decisions
without an overrun on admitted configurations and 1 in 12k on 14 at 16 processes. Against that, the chance of
passing condition 3 is driven mainly by host noise rather than by B. Neither outcome is very informative: a FAIL
may be a host artefact, and a PASS depends on luck at rates around 10^-6.

The registration is still valid as DESIGN wrote it, provided R2 is adopted. If the coordinator wants condition 3 to
measure B rather than the hosts, decide it **before freeze**, as a written, outcome-blind DESIGN amendment. One
option is to keep zero > 250 ms and add the A-arm control as a co-reported diagnostic. Another is to bound B's
overrun count relative to A's. I am not requiring this.

## 6. Items checked and found acceptable

- **Gate (a) independence.** Both drafts declare it. `seed_inventory.py` DENY patterns exclude gate4 heldout
  statistics, reports and RESULTS before files are opened.
- **No interim analysis or optional stopping.** Game counts are fixed. The lease cutoffs in
  `run_gate.may_start` and `run_host` are clock-based and outcome-blind.
- **Matched compute.** B's inference and double candidate construction count against B's own 200 ms, as DESIGN
  requires. Under truncation, B scores imitation slots before random slots; that is proposal priority, not extra
  compute.
- **Script rejections.** Candidate and opponent rejections and illegal actions are counted separately in all
  routes.
- **Role and deck audit.** Run before analysis: eval-role candidate, train-role opponent, train-prior support
  for (b).
- **Primary score.** B's score is taken from B's seat in each primary game; the mean of the 640 equals the mean
  of the 320 pair means.
- **Cross-gate namespaces.** Disjoint now (1,794 and 2,562 seeds, 0 overlap), and still disjoint after a single
  +10^8 shift of either gate.
- **Analysis is fail-closed.** It requires exact counts (1,152 / 1,792), unique keys, manifest hash agreement and
  the pinned checkpoint SHA, so it cannot run on a partial set.

---
**Verdict: APPROVE WITH REQUIRED CHANGES** (R1–R14; E1 optional for the coordinator)
Review file: `imitation/reviews/GATES-BC-PREREG-REVIEW-20261008.md`

---

# Addendum A (2026-10-08 ~21:20Z): post-T5 source pin and the home-host move

The coordinator sent two decisions as context:
1. The gates use the exact post-T5 model source that gate (a) scoring used, with a dev-only forward-equality check
   and a frozen tree hash. The e3 pilots are historical.
2. Gates run on home CPU hosts 03/02/07, with 04/01 as spares. Gate (b) is requalified on 02 and 07.

**State of the drafts.** At 21:18Z both PREREGs still hashed to `fb92c3dd…` and `872e4de5…`, the versions reviewed
above. **Neither yet contains the source pin or the host change**, so this addendum states what the updated text
must contain and assesses the evidence that exists now. R7 and R8 above are amended by R15–R21.

## What I verified

- **The scoring source is pinned by a manifest.** `gate4-scoring-launch.json` (`6a4f6339…f46053`) ran
  `gate4_decoupled.py score` with `--source /mpac/sdicks02/tmp/t5-main02-hostloss-20261008/source` (127x01) and
  `--freeze …/gate-a/resource-r2/executable-manifest.json`. That manifest hashes to
  `2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13`. It is the same `manifest_sha256` recorded
  for all four runs in `gate4-selection.json` and in the calibration entries of the seal and release. It pins 52
  files, including the 20 `imitation/model/*` files and `imitation/t5/{score,variants,…}.py`. Adapter freeze:
  `d77419e3…1816`.
- **The model source matches that manifest.** `gates-bc/receipts/t5-all-model-source-parity.json`
  (`5339ab5e…7524`): all 20 `imitation/model/*` files in the evaluation source match the manifest byte for byte.
  It includes `inference.py` `d5d05d7c…`, `network.py` `f9319603…` and `features.py` `4a1d2f79…`.
- **The receipt can't be tied to a snapshot.** It doesn't record which snapshot tree, host or time the "actual"
  hashes came from, or the expected manifest's hash. The narrower `t5-model-source-parity.json` does record
  `training_manifest_sha256` = `2854ce1f…`. See R15.
- **The D1 serving dependencies are the training-time ones.** In the snapshot, `runtime_dependencies/
  {derived_d1,own_cycle,sidecar_observer}.py` hash to `92b72418…`, `18cf0aaa…` and `cdb2d830…`. Those equal the
  `source_sha256` recorded in the T2 sidecar receipt `data/receipts/t2-complete-127x01.json`. The 6,326-row D1
  skew equality in the post-T5 pilots therefore compares serving against the true training-time extractor, not
  a drifted copy. That is sound.
- **Same weights and class, different execution path.** Serving uses
  `inference.load_policy` → `SetPolicy(...)`, loads `payload["ema"]` and calls `single_features` (unpadded, batch
  1, CPU fp32). The scorer uses `t5/score.load_model` → `create_policy('main', …)`, which is also `SetPolicy`,
  loads `ckpt['ema']`, checks checkpoint provenance pins, and runs collated, bucket-padded batches of 1,024 on
  CUDA under **bf16 autocast**. Byte-identical source therefore does not establish forward equality. The
  coordinator's dev-only check is necessary, and its tolerance has to be defined (R16).
- **The pilot snapshot keeps changing.** The sequence is e3 → ed42 → 1fed → 506e → d992 → `0f290ed17363df25`.
  `snapshot-delta.json` documents e3 → d992. The latest 02/07/01/04 r8 pilots run on `0f29`, described as d992
  plus manifest runtime-root metadata. The 03 final-source pilot r7 ran on d992 (32 games, 23,834 decisions, p99
  200.240 ms, max 202.445 ms, 0 >250 ms, 6,326 exact D1 rows). The 02/07/01/04 r8 pilots were still running at
  review time; I did not wait for them or inspect their receipts.

## Assessment

**Source pin.** The chain "evaluation snapshot model files = resource-r2 manifest `2854ce1f…` = what gate4
`score` verified at launch" is the right pin. It is adequate once R15 and R16 are done. The e3 pilots, the
leased 13/14/15 pilots and the 04 r3 pilot (snapshot not identified) are historical, not admission evidence.

**Requalification evidence.** Adequate in kind, not yet complete. Each admitted gate (b) host needs one
real-checkpoint pilot on the **final** snapshot and runtime at its frozen worker count. That pilot must show:
- 0 decisions >250 ms;
- 0 model illegal or rejected commands;
- exact D1 skew rows;
- exact candidate-count equality.

As things stand, 03 is on d992, not the latest snapshot; 02, 07, 01 and 04 are running on `0f29`. One 32-game,
~24k-decision pilot per host only detects gross problems: per-decision overrun rates above about 1.25×10^-4 (95%).
It cannot certify the zero-overrun bar (E1 still applies, and the move to GPU-co-tenant hosts makes it more
pressing). Also, all pilots are still B vs scripts only (R7).

**Timing fairness between arms after the host move.** Not threatened in structure. Each primary game runs A and B
sequentially in the same process, on the same host, at the same moment, with the seat swap balancing within-tick
decision order. Each secondary pair's four games run back to back in the same worker (the static
`pair % N` partition), so both arms see the same host. Host heterogeneity mostly adds noise, not bias.

Three residual risks need prespecification, not redesign:
1. **Drift within a secondary world.** A's two games run after B's two, separated by minutes. On a GPU host
   (01/04/07, and 02 during the GRU DDP qualification), training-job phases can change load between them.
2. **Overrun exposure.** It is higher on GPU-co-tenant hosts, which mainly hurts B's absolute zero-overrun bar.
   A has no such bar, so the asymmetry is in the bar, not in the play.
3. **Different interpreters.** Each home host runs its own `/mpac/.../.venv/bin/python` (`pilot.sh` line 10), and
   `/mpac` is per-host and unsynced. Different torch/numpy builds would change model numerics across hosts. For
   gate (c) this breaks cross-host reproducibility. For gate (b) it changes B's proposals only, but undetectably.

## Additional required changes

**R15 — both, "Pins" table (amends R8): pin the post-T5 source chain.**

Replace the snapshot row with:
> "Model source: the exact post-T5 source used by gate (a) scoring, pinned by resource-r2 executable manifest
> SHA256 `2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13` (gate4 scoring launch receipt
> `6a4f6339…`, adapter freeze `d77419e3…`). The final evaluation snapshot tree is `<full SHA>`. Its
> `imitation/model/*` files equal the manifest byte for byte (receipt `<path, SHA>`), and its D1 runtime
> dependencies equal the T2 sidecar source hashes `92b72418…`/`18cf0aaa…`/`cdb2d830…`. The original T6/T8
> snapshot `e3c60ef3…` and every pilot run on it are historical plumbing evidence only."

Regenerate the parity receipt so it records:
- the snapshot tree SHA it read;
- the expected manifest path and SHA;
- the host and UTC time;
- the D1 dependency comparison.

Freeze only a tree for which that receipt exists.

**R16 — both, new paragraph "Serving-path forward equality (dev only)".**
> "Before freeze, on dev-role rows only (never eval/eval_ood or any gate (a) heldout artifact), using a fixed
> seeded sample of at least 4,096 dev rows (seed and row IDs recorded), compare at T=1 (temperature buffers 1):
>
> (a) the scorer forward (`t5/score.load_model`, `main` variant, collated and bucket-padded batch) **on CPU
> fp32**, against
>
> (b) the serving forward (`inference.load_policy` EMA, `single_features`, batch 1, CPU fp32, 1 thread),
>
> both on the released checkpoint `d77005d5…`.
>
> Pass requires all of:
> - max |Δ log-prob| ≤ 1e-4 over gate, card and tile heads on legal entries;
> - identical legal masks;
> - for every row, an identical top-8 joint action list, except swaps between entries whose joint log-probs
>   differ by < 1e-5 (counted and reported).
>
> Also report the mean dev joint NLL of (b) on the sample, and the bf16-GPU-vs-CPU-fp32 difference descriptively.
> Rows near the entity cap (>100 entities) must be over-represented, or all included. On failure, no gate game
> starts; the result is reported and the cause fixed by a reviewed amendment."

(If the worker prefers exact equality as the bar, that is fine. The tolerance just has to be fixed before the
check runs.)

**R17 — gate b, "Hosts, concurrency and load envelope" (replaces R7's host list).**
> "Game hosts and worker counts:
> - 127x03, 127x02 and 127x07 run 16 workers each.
> - Spares 127x04 and 127x01 run 8 each, and are admitted only with their own passing final-snapshot pilot.
> - No leased host runs gate games.
> - The global worker count N and the worker → host map are frozen in the manifest.
>
> A spare may take over a failed host's workers only for a technical reason (R1), recorded in the interruption
> ledger before its first game. A spare is never activated for timing reasons.
>
> Gate (b) and gate (c) never run on the same host at the same time.
>
> Each admitted host's qualifying pilot records its co-tenant processes: GPU jobs, dataloader/DDP workers, and
> their CPU affinity and thread counts. During gate (b), co-tenant CPU load must not exceed that envelope.
> Otherwise the host stops starting new games, with in-flight games finishing, and the event is recorded.
> Gate workers' 3-CPU sets must not overlap co-tenant affinity, and their SMT siblings must not be counted as free
> (check `lscpu -e`)."

Keep the rest of R7: no concurrency changes in response to timing, console-user rule, inspection limits, and the
B-vs-A pilot-or-waiver.

**R18 — both: identical interpreter and numerics stack on every game host.**
> "The manifest records, for each game host: interpreter path, Python version, `torch.__version__` and
> `torch.__config__.show()` hash, numpy version, and a `pip freeze` SHA256. They must be identical across all game
> hosts, or the host is not admitted. The native engine `.so` and runtime tree are verified against runtime
> manifest `<SHA>` on each host before every worker start (`run_gate.verify` already does this per game)."

Gate (c) addition:
> "Before freeze, one P16 world and one C56 world are replayed on two different game hosts (plumbing seeds, outcomes
> not computed) and must give identical action streams."

**R19 — gate b: admission evidence per host.** Replace "timing evidence" in the launch prerequisite with:
> "For each admitted host: a real-checkpoint pilot on the final snapshot `<SHA>` and runtime `<SHA>`, at the frozen
> worker count, with ≥ 20 terminal games, 0 decisions >250 ms, 0 model illegal/rejected commands, ≥ 8 exact
> D1-skew games and exact candidate-count equality. List each receipt's label, snapshot and SHA. Pilots on earlier
> snapshots (e3, ed42, 1fed, 506e, d992), on leased hosts, or with an unidentified snapshot are historical. Any
> executed-code change after a host's pilot requires a new pilot on that host. A metadata-only change requires a
> per-file delta receipt showing that no imported module changed."

This applies to 03's d992 pilot relative to the final snapshot.

**R20 — gate b secondary: remove the within-world ordering drift (code, outside the timer).**

In `run_gate.py`, iterate `for seat in (0, 1): for arm in ('B', 'A')` for scripts pairs, interleaving B and A per
seat, instead of all B then all A. Pin the order in the text:
> "Secondary games of a world run in the order B0, A0, B1, A1 in one worker."

This is an outcome-blind ordering change with no effect on play; re-run the analysis-contract test only. If the
worker prefers not to touch code, state the current order in the text and report per-arm timing by host as a
descriptive check.

**R21 — both: host 01 holds gate (a) material.** Add:
> "Gate processes on 127x01 read only the snapshot, runtime, checkpoint, prior and their own output roots. No gate
> process or operator reads `t5-gate4-*` statistics, reports or predictions."

The run roots already satisfy this; the sentence makes it auditable.

## Verdict after Addendum A

Unchanged: **APPROVE WITH REQUIRED CHANGES**. Now R1–R21, with R7 and R8 amended by R15 and R17. The coordinator's
source-pin decision is correct, and with R15/R16 it is adequately specified. The host move does not threaten
fairness between arms in structure. R17, R18 and R20 close the residual co-tenancy, numerics and ordering risks.
R19 defines when requalification is complete; as of 21:18Z it is not yet complete for any host on the final
snapshot. Freeze must wait for the updated PREREG text, the R16 check, the R19 pilots and the seed audit.

**Verdict: APPROVE WITH REQUIRED CHANGES** — `imitation/reviews/GATES-BC-PREREG-REVIEW-20261008.md`
