# Mechanics-only timing-invariant policy adapter (2026-08-13)

## Decision

Prepare, but do not promote, a mechanics-only conditional hand-card adapter for
the compact 489K policy. The final 1,000-game public-state corpus must decide
whether any pretrained or human-adapted query is safe. The 120-game prefix did
not justify a checkpoint promotion.

The adapter is intentionally narrower than the rejected semantic adapter. It
scores each legal hand card from exactly the 16 normalized public mechanics
features used by the successful linear probe. It receives no learned card-ID
embedding. Its state input is the policy's existing `repair_features`, which is
the exact tensor captured by `fit_mechanics_slot_probe.py`.

## Architecture contract

- One bias-free `Linear(d_model + memory_size, 16)` query.
- Frozen `(token, 16)` public mechanics table.
- Dot-product score between state query and each hand card's mechanics.
- Optional additive or replacement mode selected in checkpoint configuration.
- Exact legal-slot log-mass renormalization shared with the existing safe slot
  adapter.
- Play versus wait/ability probability is invariant after training.
- Placement geometry is invariant because location logits are never modified.
- Additive mode initializes with a zero query and is bit-exact to the parent.
- No card-name condition, learned identity key, or architecture-specific weight
  padding is permitted.

The fitted v1 linear probes contain `state_query.weight` with shape `(16, 192)`.
That shape matches the compact public-policy parent (`d_model=64`,
`memory_size=128`). A deliberate integration attempt against the retired 6.54M
update-40 lineage failed closed because that policy requires `(16, 576)`. The
probe is therefore bound only to the architecture on which its state features
were extracted.

## Evidence

The combined adapter, checkpoint-upgrade, card-semantics, structured-policy,
cross-seed selector, materialized-candidate, gameplay finalizer, and pipeline
gate passes 123 tests. Ruff is clean; the changed policy/evaluator/finalizer
Python modules are individually mypy-clean; both orchestration scripts parse
under zsh; `git diff --check` is clean.

A real compact-checkpoint smoke upgraded
`checkpoints/reactive489k_public_v2_distill_gated_seed1055205/endpoint.pt` in
both zero and seed-1055410-probe modes. On a fixed exact-state forward pass:

- zero mode matched action-type logits, location logits, joint logits, values,
  and both recurrent-state tensors bit-for-bit;
- the pretrained query changed conditional hand-slot logits;
- wait/ability logits and location logits remained bit-for-bit unchanged;
- total legal placement probability matched within absolute tolerance `1e-6`;
- the adapter added 3,072 trainable parameters;
- a direct unit gate proves adapter scores are bit-exact to the standalone
  `MechanicsSlotScorer` for identical state, hand mechanics, and weights;
- a separate identity-isolation gate proves distinct card IDs with equal public
  mechanics receive equal adapter scores.

A two-game paired-seat full battle smoke against the balanced strategy bot also
matched the zero adapter's complete game-record JSON byte-for-byte. Every
non-wall-clock aggregate metric was identical (2-0, +2.0 crowns/game, 0.85973
playable no-op, seven resolved defense events); only elapsed time and checkpoint
path differed in the summary JSON.

The policy configuration additionally supports an exact normalized-logit blend:
setting base scale to `1 - alpha` and pretrained-query scale to `alpha`
reproduces the standalone sweep's conditional distribution after legal-slot
renormalization. This permits additive, convex-blend, and direct-replacement
arms without changing code or silently approximating the offline candidate.

## Final-corpus gate

After the 1,000-game corpus passes integrity and visual inspection:

1. Refit three fixed simulator-pretrained linear queries.
2. Evaluate zero-shot conditional card choice on replay-, deck-, archetype-,
   and chronology-disjoint public splits.
3. Run guarded human fine-tuning using the external replay/deck-disjoint
   validation split; do not select on the final human test partitions.
4. Screen additive query scales and direct replacement as distinct candidates,
   with predeclared simulator-disagreement limits.
5. Materialize a policy checkpoint only for a cross-seed-safe candidate.
6. Require Hog utilization, defensive behavior, diverse strategy-bot play,
   full-game crown outcomes, and exact parent no-regression gates before any
   promotion.

Until all six steps pass, the adapter is development plumbing rather than a
stronger policy.

## Final selector negative control

The final selector is implemented before the 1,000-game corpus completes. It
uses only the replay/deck-disjoint human validation split for model choice,
requires all three human-fine-tune seeds to promote, and chooses the median
validation seed rather than the best seed. Human archetype and chronology
splits are loaded only after the candidate and alpha are frozen. A materialized
candidate evaluator independently proves its logits reproduce the selected
standalone blend before reporting those post-selection splits.

An end-to-end negative control used the existing 120-game disjoint split, all
three original probes, and all three guarded human-fine-tuned probes. Both the
zero-shot and human-fine-tuned arms returned `no_cross_seed_safe_alpha`; the
formal decision was `rejected`, with no candidate checkpoint. This reproduces
the prior scientific conclusion through the exact final selector rather than a
hand-written interpretation.

The production runner also requires an accepted visual-audit record bound to
the SHA-256 of all eight final contact sheets before it can train. A successful
offline selection creates only a development candidate for later full-game,
Hog, defense, strategy, PFSP, and human-level gates; it cannot promote itself.

## Complete-game RL-initializer gate

The development candidate now has a separate fail-closed gameplay runner. It
first requires the exact offline handoff marker and refuses any existing output
root. Its evidence comprises 24 direct candidate-versus-parent games on
validation and held-out decks plus 72 matched parent/candidate games against
random, balanced, reactive-defense, bridge-pressure, slow-push, spell-control,
split-lane, and Hog-specific workloads. It requires strict per-workload outcome
no-regression, nonnegative aggregate crowns, defense-success/outcome and
playable-no-op tolerances, absolute and relative Hog-use gates, and nonnegative
human archetype/chronology gains.

The finalizer does not trust filenames. It independently binds the materialized
evaluation to SHA-256 digests of the parent, candidate, and selected probe;
checks the frozen alpha and median-seed probe against `selection.json`; verifies
the declared selection versus post-selection split roles; and verifies every
gameplay metric's checkpoint, opponent checkpoint, deck pool, seed, mirror
setting, opponent type, strategy, reward profile, and exact game count. Each
paired comparison must identify the exact generated parent/candidate game
records. Only after all gates pass is
`mechanics_rl_initializer_ready_v1` written via an atomic rename. That marker
authorizes only diversified PFSP league initialization, never champion
promotion or a human-skill claim.

## Bounded diversified PFSP pilot

The first online phase is predeclared rather than designed after seeing a
candidate. It consumes exactly four updates/16,384 decisions over the strict
1,720-deck card-balanced pool. Eight of twelve actor slots are allocated by a
six-opponent PFSP benchmark on a separate 308-deck tuning pool; the other four
are random, two frozen copies of the approved initializer, and the retained
update-40 comparison policy. Neither the training nor PFSP-tuning pool overlaps
the frozen v2 validation or whole-archetype held-out signatures.

Only `action_type_head`, the mechanics-slot state query, the critic encoder,
and value head may change. Placement geometry and the remaining perception,
attention, memory, and confidence paths stay frozen. Forward KL on rollout
states plus recurrent joint-distribution rehearsal on diverse simulator states
constrain forgetting. Stability requires all four contiguous updates, 16,384
new transitions, finite tensors/metrics, no KL early stop, and an exact
state-dict scope audit.

The endpoint must then win a 24-game direct parent screen, preserve all 72
matched random/strategy/Hog records and aggregate crowns, improve weighted
defense-event success by at least two points without worsening defensive
outcome, preserve playable no-op and exact Hog utilization, and avoid mean or
worst-strategy regression. Finally, parent and candidate are compared on the
replay-disjoint human validation, whole held-out-archetype, and chronology
corpora; action-type and exact improvements must each be at least their paired
regressions on every split. Only an atomic
`mechanics_pfsp_development_candidate_ready_v1` marker can survive. This is
still a development candidate, not champion or human-skill evidence.

Every initializer and pilot input/output is SHA-bound, including checkpoint,
game record, decision trace, utilization, strategy, stability, deck-pool, and
human-corpus evidence. This prevents later gates from consuming a file changed
after its producing summary passed.
