# Expert iteration on P16

Written before implementation and evaluation, 2026-10-04.

Start from v7r4h s2902 policy_decisions_001000000.pt. Run at most three
iterations and stop after the first rejection. All new artifacts live here.
Use canonical workspace gamedata and the admitted native search backend.
The live game and standard policy evaluation retain their existing Python engine.
Copy the public planner, derived-state module and setup helpers without changing
their decisions. No engine, source experiment, frozen runtime or pilot edits.

## Collection

Collect 150 complete games per iteration, 75 seat pairs, using the current
policy's top eight proposals in the ACTING srp-pub-pol player. K=1, search every
second decision, horizon 160, rollout interval 10, original script candidates,
no-op and public-only reconstruction. Opponent styles are sampled uniformly per
pair. Every third pair uses Hog26 for the planning seat, exactly 50 games;
remaining planning decks and all opponent decks use roles_v2 training.
Save every public observation and mask, executed previous action, zero public
reward and episode start, including unsearched context. At searched rows save
all unique candidate IDs, scores and the executed choice. No hidden legal mask
or hidden opponent truth enters the planner or targets.

## Fitting

Hold out 20% of complete game pairs, keeping both games of each pair together.
Use training rows only to choose a global score temperature by bisection so the
median softmax target entropy is 1 nat. Report unattainable entropy if score ties
prevent that target. Weight every searched row by max(score)-mean(score), divided
by the training mean of this gap. No margin filter or clipping. Exact ties have
zero weight. Report score, entropy, raw-gap and normalized-weight quantiles,
zero-weight fraction and effective sample size, separately for Hog26.

Optimize mean(weight * candidate-conditioned soft CE) plus
1.0 * mean(KL(student || previous iteration policy)) over searched training rows.
The KL uses the full legal action distribution and a frozen full-episode anchor.
Use LR 5e-6, AdamW, gradient norm cap 0.5, one epoch, four 64-step chunks per
batch. Reconstruct each chunk's recurrent state from the complete executed
prefix under current weights. Do not use stored-state TBPTT. Report full-prefix
held-out CE and KL before and after fitting. Keep one final checkpoint per
iteration, no aggregate corpus duplication or stored full-logit disk cache.
Shuffle games and then chunks within each game, loading only one complete game
and its frozen anchor logits at a time to bound RAM on this 24 GiB host.

## Evaluation and acceptance

The historical 88/192 is background. Re-evaluate the initial policy and student
on identical fresh seeds using human-prior-p16/scripts/run_eval.py's six cells,
32 games each, public scripts, stochastic actions and standard horizon. Redirect
its outputs here and use the canonical workspace runtime. Names exit-itN-*.
Seed base is 770031 + N*100000000, retaining the standard cell offsets. This
avoids the previously used 770031 games; every iteration has fresh seeds.

For search players, evaluate BOTH current student and initial-policy proposal
players on the same 64 script games, 32 holdout and 32 Hog26, paired seats and
styles 12 balanced / 10 pressure / 10 defense per role. Then play 64 direct
head-to-head games, 32 holdout and 32 Hog26, swapping controller seats on each
identical ordered-deck pair. Both decks are sampled from that role so neither
controller gains a deck-pool advantage. Both head-to-head planners receive the
same publicly declared prior mixture of training, holdout and Hog26 decks,
never the actual opponent deck. Script-game planners retain the training prior.
Search evaluation seed offsets are +30000000 for scripts and +50000000 for
head-to-head, with disjoint role/style offsets.

Score wins 1, draws 0.5. Compare policy-alone scores using an exact one-sided
paired sign-flip test on seat-pair score differences, testing a drop. Accept
only if p_drop > 0.1 and the new search player's head-to-head score >= 0.5.
Report seat-pair bootstrap intervals and Hog26 separately. The script comparison
is diagnostic, not an extra acceptance gate. No outcome-based tuning.

## Ownership and recovery

Use at most three nice-10 heavy worker processes. Launch the driver through
pilot/detach.sh; it records owned child PIDs and commands in PROGRESS.md and
atomic completion/error receipts. Resume only missing games and completed
stages, checking content hashes. Stop on source/data drift or unexpected errors.
Keep exit/ below 2 GiB; guard budget before every game and fit. Never signal
foreign processes. No Git mutations. Write RESULTS.md after each evaluation.
