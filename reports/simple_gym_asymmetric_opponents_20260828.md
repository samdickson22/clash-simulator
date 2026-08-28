# Simple Gym asymmetric opponent collector certification

## Accepted source

- Isolated branch: `codex/simple-pytorch-asymmetric-opponent`
- Source/test tip: `37c70b03cb426e4e7532e4a5c649d54e11b9c931`
- Source archive SHA-256:
  `748688c8d6ff546bb0caf5d430410ed0d4845153731b41e85f5a6731b7af9f3e`
- The protected Desktop checkout remained at `20cc861b`; none of its dirty files
  or retained champion checkpoints were modified.

## Implemented contract

The Simple/PyTorch route now supports learner-only rollout collection against
noop, device-resident uniform-legal, device-resident public strategy, and frozen
V2 checkpoint opponents. Learner ownership alternates by environment row. Only
learner observations, actions, recurrent inputs, rewards, values, and policy
storage enter PPO. Frozen opponent recurrence and actions remain on the actor
device and are not exported into the PPO batch.

Checkpoint metadata persists the rollout ownership profile, alternating-seat
profile, opponent contract and digest, learner/opponent deck-pool hashes, exact
row deck-assignment digest, public-mask-v2 semantics, typed vocabulary, entity
projection profile, execution mode, and entity/effect capacities. The diverse
default is 56/64. Capacity 48 remains available only as an explicitly selected
specialist configuration.

## Python comparison gates

Two fixed hashes must pass before training:

- Three-decision learner/opponent ownership against an independent Python
  stationary row loop:
  `7c29456d6bdcdc3d489c4712d78d480efb8dcbfd96523e8c17b6cdd5cc80b8ba`
- Direct-token Python stationary actor and privileged-critic boundary against
  Simple for both alternating learner seats:
  `bde5a61ba47169737182a32bb75b383ea0fcf50f7143caabe409b15758c24e36`

The latter canonicalizes the sign of floating zero before hashing. Every named
array is still checked first for exact shape, dtype, and numerical equality.
Public-mask-v2 remains the actor legality authority; it is not replaced by the
older private Python simulator mask.

## CPU and MPS

- Full local Simple and focused RL surface: 440 passed, 259 accelerator-only
  skipped.
- Stationary noop route passed on CPU and Apple MPS; CUDA was the only skipped
  parameter locally.
- Fresh CPU one-update smokes passed for both noop and frozen checkpoint
  opponents. The frozen smoke used the diverse 56/64 capacity.

MPS remains an eager functional route. CUDA Graph is the production route.

## CUDA certification

Environment: Python 3.12.14, Torch 2.10.0+cu128, CUDA 12.8, NVIDIA RTX A6000.

- Focused asymmetric/backend/opponent/projection/public-mask/Graph/reset suite:
  55 passed, 6 non-CUDA skips.
- This includes exact eager-vs-CUDA-Graph equality for a real recurrent learner
  against a frozen recurrent checkpoint opponent at capacity 56/64.
- Hog learner versus all 33 supported opponent decks, alternating learner seat,
  public strategy opponent, batch 33 x 8 decisions:
  264 learner transitions, all admitted, all committed, zero fallback, exact
  native interval 8.
- Strategy trace digest:
  `65bfdd984aa6949ada9c2c48149066cac74e88e151b533ff9ad9567a3d9753ec`
- Row deck-assignment digest:
  `449d85425ceaeab5f2b29dc5b9cf5751ae33ce6aa02225b326f6ce83fd40dd77`
- Real CUDA frozen-checkpoint PPO smoke: one update, 8 learner transitions,
  checkpoint SHA-256
  `a9ac3908f4b3c1d1fd247c099f64e4163c2b394e5d2b18f4fc622a70524afab9`.
  Reloaded metadata asserted CUDA Graph, learner-only ownership, alternating
  seats, frozen checkpoint digest, public-mask-v2, typed vocabulary, and 56/64.

## Production collector profile

Batch 64, eight decisions, interval eight, capacity 56/64, balanced public
strategy opponent, real recurrent policy and coalesced host handoff:

- Trial learner decisions/s: 175.010, 174.748, 174.853
- Median learner decisions/s: 174.853
- Median native row-ticks/s: 1,398.824
- Peak allocated CUDA memory: 220,589,568 bytes
- Peak reserved CUDA memory: 819,986,432 bytes

An A/B probe disabling Python-canonical entity sorting recovered less than one
percent, so the exact typed projection was retained. These numbers certify the
new asymmetric path; they do not supersede the earlier capacity-specific PPO
throughput study because model, opponent, and measurement windows differ.

## Boundaries

- This does not claim global capacity 48; the supplied exhaustive deck-pair
  audit observed 49 entities.
- This does not claim human-level play or promote a new champion.
- No mirror-self-play training was launched.
- Strategy opponents use a persisted public-only tensor strategy profile; they
  are not claimed bit-identical to the scalar Python `StrategyBot` internals.
- The CUDA deck sweep is a collector/admission gate, not a replacement for the
  supplied 1,089-pair full capacity audit.
- Both paid pods were terminated; `prime pods list` returned zero active pods.

Raw checksummed evidence is in `reports/asymmetric_cuda_20260828/`. The three
temporary checkpoint binaries are excluded from Git; their hashes remain in
the remote manifest and the complete tar archive is retained at
`/private/tmp/asymmetric_cuda_20260828.tar.gz` for this handoff session.
