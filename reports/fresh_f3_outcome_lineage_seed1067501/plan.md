# Fresh F3 outcome lineage — seed 1067501

The retained F1 short-PPO route is rejected after two matched seeds produced a
combined strategy-win change of -1. This fresh lineage does not resume any F1
actor weights.

## Architecture

- current-client 494-token vocabulary and card semantics v3;
- causal-frame actor domain with canonical lane globals;
- 128-wide, three-layer packed global attention actor;
- 64-channel typed structured memory, not LSTM/GRU;
- one learned play/wait/ability gate;
- permutation-equivariant shared semantic+mechanics card pointer;
- unchanged card-conditioned 18x32 categorical placement head;
- separate privileged critic.

## Stages

1. One epoch of causal simulator-native hierarchical BC on the current-client
   152,637-row replay+oracle corpus, with label-independent public masks, exact
   hand permutations, left/right augmentation, and complete recurrent episodes.
2. Evaluate without fitting on the latest reviewed YouTube causal corpus. Reject
   collapse, illegal-mask dependence, slot asymmetry, or worse-than-control card
   learning.
3. Run a fresh-seed strategy/random screen. This is an initialization screen,
   not promotion evidence.
4. If structurally sound, run short diversified outcome PPO. Human frame-level
   wait/play labels are never optimized; video supplies observation realism and
   card/action diagnostics only.
5. Only a broadly improved outcome policy may reach held-out decks/archetypes.

No F1 blending, per-opponent repair, dense residual patch, or search is allowed
in this lineage.

## BC closure

The natural-frequency hierarchical arm reached 85.67% simulator decision and
62.15% conditional card accuracy, but deterministically played on 0/64 untouched
camera episodes. One predeclared square-root play/wait-balanced arm also produced
0% deterministic camera play. Both BC checkpoints are rejected before gameplay.

The next and final use of this architecture family is outcome learning from the
untouched random control. A bounded random-opponent PPO pilot will test whether
game consequences can teach a noncollapsed gate. No supervised timing weights or
gate biases will be tuned again.
