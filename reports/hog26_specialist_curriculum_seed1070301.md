# Hog 2.6 specialist curriculum

The learner deck is fixed to Cannon, Fireball, Hog Rider, Ice Golem, Ice Spirit,
Musketeer, Skeletons, and The Log. Opponent decks continue to come from the full
card-balanced training curriculum. This is a curriculum restriction, not a card-name
branch in the policy, simulator, action space, or reward.

The first bounded run resumes the selected parent-heavy update 28 checkpoint for 12
updates (49,152 transitions). Its league contains random, six public-information
strategy workers selected through PFSP, and several historical policy checkpoints.
The causal human rehearsal remains active at coefficient 0.125 to limit forgetting.

Promotion is not implied by training completion. Candidate checkpoints must be
evaluated with the candidate-only Hog pool and diverse opponent pool in both seats.
The gate requires broad random/strategy/policy strength, defense non-regression,
playable no-op below 95%, Hog use in both seats, and conversion of at least 25% of
legal affordable Hog windows. Fresh quarantine decks stay sealed until a development
checkpoint clears those conditions.
