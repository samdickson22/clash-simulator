# Accepted-6M LSTM mechanistic-interpretability probe (2026-08-14)

## Scope

The probed checkpoint is the accepted legacy parent:

`checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt`

- SHA-256: `cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305`
- parameters: 6,194,196
- recurrent core: one 384-unit `LSTMCell`
- actor domain: exact simulator observations (this is not the newer causal-vision
  actor)

The workflow follows mechanistic-interpretability practice: cache activations,
compare linear decodability against the current recurrent input, inspect gates
and state geometry, and intervene causally instead of inferring function from
correlation alone. TransformerLens itself is not used because this is a custom
PyTorch LSTM rather than a supported language transformer.

## Corpora

Two deterministic live-policy corpora were collected against all six strategy
bots with both candidate seats:

| Corpus | Decisions | Purpose |
| --- | ---: | --- |
| general sampled decks | 4,113 | broad state/gate geometry and frozen PCA basis |
| fixed Hog deck pool | 5,119 | designated-card and slot-sensitive behavior |

The linear probes report both a deterministic one-in-five within-trajectory
holdout and a stricter complete-game holdout containing one seat/deck trajectory
from every strategy. Negative complete-game R-squared values are retained rather
than hidden: they show that many linear readouts do not transfer cleanly across
decks/trajectories.

## State geometry and gates

The 384-dimensional hidden state is extremely low-dimensional in observed play:

- general corpus: 3 principal components explain 95.24% of hidden variance;
- Hog corpus: 4 components explain 90% and 6 explain 95%;
- general hidden participation ratio: 2.44 effective dimensions;
- general cell participation ratio: 2.75 effective dimensions.

This does not mean only three units are nonzero. It means the population moves
mostly along a few highly correlated directions.

Average input, forget, and output gate values are 0.330, 0.333, and 0.316.
Fewer than 0.2% of forget-gate values are below 0.1 and fewer than 0.14% are
above 0.9. The LSTM therefore does not look like a collection of mostly hard
on/off memory bits; it continuously mixes state through a low-dimensional
trajectory.

## What is linearly present

The clearest cross-game memory signal is whether the opponent has played a
card yet. On general held-out games its ROC AUC rises from 0.812 in the current
recurrent input to 0.999 in hidden/cell state. In the fixed-Hog corpus it rises
from 0.738 to 0.940 hidden / 0.965 cell. Recent opponent play is weaker but still
above chance.

The cell also improves readout of several action-relevant quantities:

- general within-trajectory own-elixir R-squared: 0.454 current input to 0.585
  cell;
- Hog within-trajectory own-elixir R-squared: 0.545 to 0.677;
- general held-out policy-play AUC: 0.610 to 0.637;
- Hog held-out policy-play AUC: 0.680 to 0.746;
- Hog held-out policy-will-play-Hog AUC: 0.732 to 0.833.

The current recurrent input remains better than the LSTM state for many directly
visible quantities such as time, tower HP, danger, and board value. The LSTM is
compressing those rather than preserving a universally linearly readable copy.

Linear decodability is evidence of information, not proof that the policy uses
it. The causal tests below are the controlling evidence.

## Causal prior-state ablation

At sampled live decisions, the same current observation was rerun after zeroing
the prior hidden state, prior cell state, or both:

| Corpus | Intervention | Deterministic action changes | Mean distribution TV |
| --- | --- | ---: | ---: |
| general (198 samples) | zero hidden only | 0.00% | 0.00121 |
| general | zero cell only | 0.51% | 0.00579 |
| general | zero both | 1.01% | 0.00545 |
| Hog (503 samples) | zero hidden only | 0.00% | 0.00179 |
| Hog | zero cell only | 0.20% | 0.00820 |
| Hog | zero both | 0.20% | 0.00813 |

Thus the recurrent state contains history, but the accepted deterministic policy
usually chooses the same immediate action from the current observation alone.
The cell matters more than the carried hidden state. Full-game effects can still
compound after a rare changed action, so this is not permission to remove memory
without a matched gameplay evaluation.

## Top-three activation patch

The intervention basis is frozen from the separate general corpus:

`reports/lstm_mech_interp_accepted6m_seed1062501/hidden_top3_pca_basis.npz`

- SHA-256: `24f29f6a512efbafcbd3071296deeb9e3dd7df37b95d1f8d0732f7ce12f920a4`
- source decisions: 4,113
- cumulative hidden variance removed: 95.2378097%

After every LSTM step, the activation-patched arm applies:

`h <- h - ((h - mean) @ components.T) @ components`

The patched hidden output drives the action heads and is carried to the next
step; the cell state, weights, inputs, legal mask, deck, and simulator RNG remain
unchanged. Six matched baseline/patched pairs against all strategy bots are being
rendered in the dedicated viewer worktree. Because this removes dominant current
context as well as historical context from the LSTM output, it is deliberately a
strong circuit intervention, not an estimate of the value of history alone.

## Artifacts

- general report: `reports/lstm_mech_interp_accepted6m_seed1062501/report.json`
- general activations: `reports/lstm_mech_interp_accepted6m_seed1062501/activations.npz`
- Hog report: `reports/lstm_mech_interp_accepted6m_hog_seed1062502/report.json`
- Hog activations: `reports/lstm_mech_interp_accepted6m_hog_seed1062502/activations.npz`
- reproducible collector/prober:
  `scripts/probe_lstm_mechanistic_interpretability.py`
- PCA freezer: `scripts/build_lstm_pca_basis.py`
