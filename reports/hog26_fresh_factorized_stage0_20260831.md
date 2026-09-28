# Fresh factorized Hog 2.6 stage-0 decision

Date: 2026-08-31

Status: fresh actor plumbing and initializer accepted for bounded outcome-RL A/B;
no gameplay promotion or human-skill claim.

## Common architecture

Both upcoming RL arms use the same 1,628,884-parameter actor-critic initializer:

- current 494-token typed vocabulary;
- 128-wide, three actor attention layers, two critic layers;
- 64-channel structured recurrence;
- explicit play/wait/ability gate;
- shared slot-equivariant semantic+mechanics card pointer;
- exact card-conditioned 18-by-32 placement heatmap;
- canonical lane globals and public mask v2 Simple Gym.

The candidate adds the 67,140-parameter actor-visible action-value head behind an
exactly zero policy gate.  Same-seed initialization and initializer loading leave
all shared state entries bit-identical.

## Hierarchical behavior pretraining

The new batched pretrainer independently supervises trusted decision, card, and
tile components.  Privileged critic/value/opponent-prediction heads are excluded.
Simulator corpora without explicit confidence arrays receive exact confidence
only through an all-or-none typed conversion; partial confidence contracts fail.

Full corpus:

- train: 167,631 rows / 2,495 complete recurrent chunks;
- validation: 54,333 rows / 812 chunks;
- selected epoch: 4 of 5;
- selected checkpoint SHA-256:
  `b9c22445e5b30e12b6fd37183b13c5aa8329ee9b87c249ec9b0445207b1040de`.

Epoch 4 validation:

- decision accuracy 89.23%;
- play recall 78.84%;
- wait accuracy 90.32%;
- card accuracy 96.26%;
- tile accuracy 39.19%;
- exact action accuracy 83.69%.

Epoch 5 had lower loss but only 85.21% wait accuracy and 80.03% exact action, so
the gated selector correctly retained epoch 4.

## Free-playing evidence

Pure behavior pretraining did not transfer sufficiently:

- one epoch: 0-4; balanced placement 0%, random 11.33%;
- selected epoch 4: 0-4; balanced placement 0%, random 11.33%.

This rejected pure BC as the skill route and triggered executed-state
supervision rather than a loss-weight adjustment.

The executed six-strategy corpus fine-tune used 78,693 training and 25,470
validation rows.  Epoch 1 of 3 was selected:

- decision accuracy 92.80%;
- play recall 97.03%;
- wait accuracy 92.22%;
- card accuracy 96.65%;
- tile accuracy 28.74%;
- exact action accuracy 84.42%;
- checkpoint SHA-256
  `3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5`.

Its free-playing collapse screen remained 0-4, but the failure mode changed
materially: both balanced and random placement rates were healthy at about
11.1-11.3%, and every game survived to the 450-decision tiebreak.  This is an
active but weak initializer suitable for outcome learning, not promotion.

## Evaluation infrastructure correction

The old legacy evaluator could not load semantic-v3 checkpoints because it built
a semantic-v1 observation table.  Loading now uses the checkpoint's semantics
and canonical-lane contracts.

A new deterministic Simple Gym evaluator avoids legacy fallback.  Its first
implementation materialized all 760 observation steps and used MPS at batch 2,
reaching about 3.9 GiB RSS.  The accepted implementation uses 32-step chunks,
stops after every row's first terminal game, uses CPU for the tiny batch, and
held about 478 MiB RSS.  The aborted run published no result.

## Matched RL fork

The control and action-value candidate were created from the exact executed-state
initializer.  Their initial checkpoints have 169 shared state entries with zero
bit mismatches and 14 candidate-only action-value entries:

- control SHA-256
  `8d4bf30900498b12764ccd5e09b4eee499825d8cef1f962fce136d25367efbe2`;
- candidate SHA-256
  `b511e6e02cea1366931473164e3fc3e4b53078c10b57d1821969609b7bcdc183`.

The corrected one-update MPS smoke produced identical pre-update rollout,
entropy, value, auxiliary, KL, play/no-op, and episode metrics.  Candidate-only
action-value loss was finite (0.1876).

## Next gate

Run equal-budget short stratified league phases for control and candidate from
these exact initializers.  No arm proceeds unless it avoids passivity/overplay,
improves the 0-4 baseline, preserves every strategy bucket in the matched screen,
and retains at least 95% of control collector throughput.  Only then expand to
three seeds and the 72-game breadth matrix.
