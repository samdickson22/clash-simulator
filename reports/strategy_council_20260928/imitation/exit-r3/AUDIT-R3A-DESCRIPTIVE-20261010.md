# Independent audit: R3a descriptive r1(b) result (−28.67 pp vs K0)

Auditor: Opus (independent, read-only), 2026-10-10, for coordinator thread 0523ae6f.
Scope: `round2/K0-FALLBACK-ADDENDUM.md`, freeze a0beb995, `round2/eval-ops/*`, frozen runner
`imitation/exit_r1/screen.py` (17d1b408), E1 planner, and all 1,200 raw case files plus 600 block files
copied read-only from `127x01:/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2/k0-descriptive/`.
No running job was touched, and no file was changed except this document and
`audit-r3a-20261010-artifacts/`.

## Verdict: **CONFIRMED_WITH_CAVEATS**

**Confirmed:** in the frozen r1(b) harness, R3a + W beats the v1 + W mirror by about 29 pp.
- Every student inference runs inside the decision timer.
- The same rules, opponent, native build, core and seeds apply to both arms.
- Pairing and the CI reproduce exactly from the raw files.

**Caveats:**
1. The proposer-latency gap is a labelling artifact. The student's proposer is a cache read, and its real inference cost is charged to the fallback call.
2. One small real asymmetry favours the student: v1 runs two forward passes per search call, the student runs one.
3. The gain works through a near-threshold "cliff" in a control that is heavily starved for time.
4. **The claim "1-core plus student matches 2-thread search" is not supported by this data.** The opponents and the kernel differ from K2/K4.

## 1. Proposer latency: 0.08 ms vs 9.45 ms

**Where the student's inference runs.** `game.py:TimedPolicy.sample` runs the student's **single** forward pass. It computes the gate probability and ranks every legal play, then caches `(d1, order, mask)`. `TimedPolicy.propose` only slices `cache[:8]`. It asserts that the cache is for the same `d1` object and an identical mask, so the cache is never stale or reused across decisions. The 0.084 ms is therefore building an 8-element list, not inference.

**Is that cost on the clock?** Yes. In `screen.py:133` `begin=time.monotonic()` is taken *before* `observe` and before `adapters[actor].decide`, which calls `sample`. The cutoff is `begin+0.192`. The student's forward pass is therefore fully charged to the same timer.

**Nothing precomputed, cached across decisions, batched or skipped.**
- Each game runs as one process on one core, with Torch using 1 thread and `single_features` building a batch of 1.
- I checked every raw game (`artifacts/hook_counts.json`, 0 mismatches):
  - `student_fallback_calls == student-seat polls`, 465,804 in total.
  - `student_proposer_calls == student-seat search calls`, 89,094.
  - All hook calls are inside `run_case` after `begin`, with a maximum minimum offset of 3.9 ms.

**Is v1's 9.45 ms the same kind of measurement?** No. `Policy.propose` for v1 is a full second forward pass, through `single_features` and `log_policy`. It runs on top of the forward pass v1 already did in `sample` for the fallback.

**The asymmetry that follows.** Per search call, v1 pays about 2 × 9.5 ms and the student about 1 forward pass plus 0.08 ms. The two networks are architecturally identical: `exit_r3/network.py` differs from `imitation/model/network.py` only by the advantage head, which is off.

A regression on non-search wall time estimates the student's `sample` at about **+2.35 ms [2.10, 2.61] per poll** compared with v1's (`artifacts/poll_cost.json`). The likely sources are lexsort ranking and differences in game state. So the net saving is about **7 ms per search call, roughly 3.6% of the 192 ms window.**

This is a legitimate deployment optimisation, since v1 could cache too. But it is an uncontrolled asymmetry in K0's disfavour. Given the cliff described in §4, it may account for a non-trivial share of the effect, and this study cannot apportion it.

## 2. Same rules for both arms

These are identical in both arms, verified in code and in every raw record:
- the frozen runner and E1 native (f387b2d2);
- the 200 ms deadline with an 8 ms reserve;
- 1 thread, horizon 160, no reserve floor (the hook asserts this for both W players);
- the opponent: released v1 as fallback and proposer, plus W;
- the opponent's RNG seeds, `belief.update`, root construction, the candidate generator, d27/capacity1 and abilities off.

Deployed hashes on 01 equal the repo's for `game.py`, `proposals.py`, `protocol.py`, `block.py`, `reduce_games.py`, `screen.py`, `inference.py`, `planner.py` and `network.py`. All 1,200 case SHAs match the sealed block proofs.

Other asymmetries and caveats:
- **Lateness is not charged in r1(b).** `screen.py` records `wall_overrun` but submits at the observation tick. K-v2/K2 instead charge ceil(overrun × 20) ticks. Overruns are similar for the two seats (539 vs 573; >250 ms: 203 vs 280), so this is roughly symmetric, but it differs from the K-series rules.
- The R3 guard replaces r1's `SCHED_IDLE` with nice10/`SCHED_OTHER` for both arms. This is symmetric, but it is a difference from r1's −7.5 pp run.
- The fallback gates differ by design. R3a uses a deterministic calibrated gate with a ranked argmax, while v1 uses a stochastic T=1 sampler.

## 3. Pairing, reduction and the meaning of "K0"

All 600 pairs passed every check:
- same seed, seat (index % 2), own and opponent deck, and physical core;
- complete rotated blocks with no abandoned or partial blocks.

I recomputed from the raw files:
- paired Δ **−28.667 pp, CI [−33.667, −23.333]**, matching exactly (percentile bootstrap, 5,000 resamples, seed 80991013);
- discordant pairs 230 (K0 lost, R3a won) vs 58 the other way; exact McNemar p ≈ 2e-25;
- the order effect is nil: −28.67 pp both when K0 runs first and when R3a runs first;
- R3a improves on every own deck: 57→22, 51→25, 33→12, 48→8 and 74→54 % loss.

**K0 here is the r1(b) "init-W" mirror:** v1 + W against v1 + W, the same reference as `reference=records('fallback','init')` in r1. Its expected loss is therefore **50%**, and the observed 52.83% (317/600; seats 51.0% / 54.7%) is within noise.

The 45–48% elsewhere (K-v2 47.67%, K2 45.67%) is a **different K0**:
- a different kernel and native (44874fd6), anytime W rather than coarse-first;
- played against a plain **v1 policy with no search** (`k2/plan.json: "opponent": "v1-policy"`);
- with lateness charged.

So "K0" is not the same quantity across studies, and R3a's 24.2% is **not on the same scale** as K2's 25% or K4's 16.5–18%.

## 4. Mechanism: why completed roots rise and fallbacks fall

"Completed roots" is a misnomer: it is `len(scores)`, the number of fully scored candidates. Each call has one root. All figures below are for the student seat (`artifacts/analysis.json`, `mechanism.json`).

| | K0 | R3a |
|---|---:|---:|
| Search calls | 134,238 | 89,094 |
| Deadline-hit rate | 81.9% | 55.7% |
| Fallback rate (coarse scan unfinished, or no candidate completed) | 55.0% | 15.2% |
| Trivial calls (only WAIT + 3 timed waits, nothing affordable) | 13.6% | 32.7% |
| Completed per non-trivial call | 2.27 | 5.73 |
| Fallback rate, non-trivial calls | 63.7% | 22.6% |
| Mode of unpruned candidates when falling back | 32 | 28 |
| Timed-wait polls | 141,769 | 214,805 |
| Plays submitted | 22,865 | 26,667 |

The mechanism is plausible and not an accounting artifact.
- **The control is starved.** At 1 core and 192 ms, the coarse-first W scan over about 30 play candidates sits near its time limit. K0 abandons search on 64% of non-trivial calls and falls back to v1's T=1 sample, which waits on about 98% of polls. Elixir builds up, which means more legal plays, more candidates, more cut-offs and more WAITs.
- **The student breaks the loop in three compounding ways:**
  1. Its top-8 overlaps the script, ranked and sampled candidates. The candidate generator dedupes, giving about 4 fewer unique candidates (mode 28 vs 32).
  2. It saves about 7 ms of inference per call.
  3. It spends elixir: 17% more plays, and 2.4× as many calls with nothing affordable.

  Together these push the scan under the cliff, so W actually completes and chooses (including more timed waits). When W is still cut off, the fallback is a distilled W-like action rather than WAIT.
- **Part of the higher completed count is trivial calls,** which complete 4 candidates each: 116k of R3a's 460k vs 73k of K0's 337k. Even excluding them, completion per call is 2.5× higher.
- The v1 opponent also completes slightly more in R3a games (fallback rate 55.0% → 49.9%). This is consistent with a state-distribution effect.

Implication: the effect size is tied to where the cliff falls on this hardware and budget. On a faster or slower core (the Mac), or under the anytime kernel, the gap could shrink or grow substantially. K-v2 already shows a steep loss cliff between 160 and 120 ms.

## 5. Fairness rule

The student gets exactly v1's inputs:
- `single_features(model_packet(public packet, public mask), d1, costs)`;
- the D1 tracker built from the public recorder events;
- the own HUD and own cycle;
- `opp_elixir` derived from public play.

These are all opponent-derivable under the fair-information rule. There is no access to the opponent's hidden hand, the battle state or the RNG, and the cache holds only the current decision's own outputs. Search roots use the frozen fair public belief path, unchanged. Training and evaluation seeds are disjoint (round-2 seed audit passed with no intersections). The student trained on the same five archetype decks it is evaluated on, so generalisation to other decks is untested. **No fairness violation found.**

## Other comparisons

- **r1 S-teacher, −7.5 pp, same harness and same mirror reference.** r1 students used the generic `Policy`: two forward passes, stochastic T=1 gate, `SCHED_IDLE`. R3a's larger gain therefore mixes three things: a better student, a deterministic calibrated fallback, and single-pass caching.
- **X's r2 1-core *anytime* default, 99% loss.** This is a different kernel and role. I did not audit X, and it doesn't contradict this result.

## What a confirmatory pre-registered study should fix

1. **Equalise inference.** Give K0 the same single-forward cache: v1 `sample` and `propose` from one pass, the same deterministic calibrated gate option. Alternatively, run both arms uncached. Report fallback-path and proposer latency separately, and rename "completed roots" to completed candidates.
2. **Factorial ablation on the same seeds:** student proposer + v1 fallback, v1 proposer + student fallback, and both. This isolates proposal quality, dedup/time savings and fallback quality.
3. **Common scale with K2/K4.** Evaluate R3a+W (1 core), K0, K2 and K4 against the **same opponent**: the sealed plain v1 policy and v1+W. Use the **same kernel and native** (the K-v2/K2 anytime collector) and charge lateness as ceil(overrun × 20) ticks. Only that supports a "matches 2-thread" claim, via a pre-registered retention or non-inferiority margin.
4. **Budget and speed sweep** (e.g. 120/160/200/240 ms, or a Mac-measured per-core speed) to locate the cliff and test robustness; and a loaded-Mac timing qualification.
5. **Wider evaluation:** decks beyond the five training archetypes, a fresh student fit (a new seed rather than a killed arm), a fixed adoption gate and a multiplicity plan.
6. **Log per-decision traces:** unpruned candidate counts on every call, own elixir, and the action actually taken on fallback. These would let the elixir-leak mechanism be tested directly instead of inferred.

## Artifacts

`audit-r3a-20261010-artifacts/`:
- scripts: `analyze.py`, `poll_cost.py`, `mechanism.py`, `hook_counts.py`, run with `uv --with numpy`, `python -I`;
- outputs: `analysis.json`, `poll_cost.json`, `mechanism.json`, `hook_counts.json`;
- `raw-copy-manifest.sha256`: 2,400 files, byte-identical to 01.

The 113 MB raw copy is kept outside the repo at `/mpac/sdicks02/jobs/clasher/audit-r3a-20261010-raw/raw01/`. Nothing is committed.
