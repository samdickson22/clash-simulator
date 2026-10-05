# Fresh F3 causal decision-rehearsal screen — seed 1067901

The update-20 random-outcome candidate is rejected despite improving gameplay:
it went 16-8 versus random, 17-7 versus its parent, and 10-26 across the six
strategy bots, but deterministically predicted play on 100% of 17,928 held-out
human replay decisions. The natural and square-root-balanced BC initializers had
the opposite all-wait collapse. Neither checkpoint is continued.

The failure identifies a missing training contract rather than a reason to tune
another reward coefficient: outcome PPO could not consume the verified causal
human corpus. The legacy rehearsal path uses simulator-exact confidence and
does not understand untrusted visual labels or the hierarchical mode gate.

This screen restarts twice from the untouched random F3 control and adds only a
new causal decision rehearsal loss:

- public-v2 confidence tensors and label-independent mask contract v2;
- complete recurrent chunks and zero privileged previous reward;
- trusted play/wait/ability labels only;
- no card, tile, value, expert-action legalization, or masked-label loss;
- coefficients 0.01 and 0.025, chosen from a measured raw rehearsal gradient
  norm of 4.068 versus recent PPO norms near 0.17;
- identical seed, random opponents, decks, optimizer, and 40,960-transition
  budget per arm.

The fixed screen uses 12 random games, 12 balanced-strategy games, and 64
held-out human replay episodes per arm. An arm is rejected if training is
unstable, random wins improve by fewer than two over the untouched control,
balanced wins regress, deterministic human play rate is at most 0.5% or at
least 50%, or human play average precision regresses. A passing arm authorizes
only a fresh mixed-league pilot; held-out promotion remains forbidden.
