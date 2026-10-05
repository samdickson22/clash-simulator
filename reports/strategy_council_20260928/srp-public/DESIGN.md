# Public SRP design

Written before implementation or evaluation, 2026-10-04.

The planner accepts a public-v4 packet, tick, planning seat, its own card state,
and the opponent's complete public sequence of accepted card names and play ticks.
It receives no BattleState. The adapter accesses only the planning seat's player
record and the engine's explicitly public play history. Opponent elixir is absent
from public-v4. Estimate it from the known six-elixir start, public phase schedule,
and accepted card costs, with the engine's integer-frame regeneration and [0,10]
clamp. Never inspect opponent hand, deck, cycle, resources, or engine RNG.

The derived_public_state.py module retains all 8! initial deck orders for each
training-prior deck, with prior weights. Filter and advance them on every public
accepted play and deterministic refill. Agreement across all remaining states
establishes exact hand membership, queue positions, next card and any known UI
slots. This can resolve before all eight cards have been revealed. Once the hand
multiset and full queue are determined, use them directly without sampling those
quantities. Otherwise sample a complete remaining state; every derivable component
is identical across the posterior and therefore stays fixed. The private UI hand
slot permutation may remain unknown even when available cards are known; use a
consistent representative once the semantic hand and queue are resolved, and do
not claim the UI order is known. Impossible histories fail closed.

Elixir is exact integer-frame tracking from the public six-elixir start. The P16
scope has no Collector or other resource-generating card; no estimate fallback is
needed. Unknown resource-changing cards are unsupported, not silently estimated.
Full recorded-game replays audit elixir, determined hand membership, ordered queue,
next card and every determined position against truth in test code only. The
planner module has no BattleState reference and cannot read hidden truth.


Each search samples K independent hidden completions and fresh engine RNG seeds.
Board positions, identity, owner, HP, facing and permitted static features come
only from the projected packet. Create native entities from immutable card
templates. Combat clocks, targets, shield state and unobserved effect clocks
must be assigned model defaults or priors, never copied from the real board.
This is an approximate public state reconstruction, so loss relative to privileged
SRP includes board-state estimation error as well as opponent uncertainty.
Visible projectiles/effects are reconstructed from public identity and position;
their unobserved targets/timers require model assumptions documented in code.

Use the existing native SRP continuation and defense-v2 leaf, horizon 160,
interval 10, own balanced public script, opponent balanced StrategyBot, elixir
weight 1. The candidate list is shared across K roots: script choice, no-op,
script top four and 16 random public-legal plays. Average scores by candidate
across K, resolving ties in candidate order with the existing 1e-9 threshold.
The policy variant replaces the 16 random plays with eight highest-probability
public-legal actions from s2902 1M. Its recurrent state advances on every decision
using executed actions and zero public-v4 reward. Search every second decision.

Before evaluation, test hidden-state invariance in both seats and both variants,
including scores and candidates; poison forbidden reads; check history consistency,
RNG independence, public masks, purity, and native rollout parity. Benchmark K=1,
4,8 on non-evaluation public roots, including packet conversion and policy work.
Choose the largest K whose measured maximum whole-decision wall time is <=0.25s
for both variants on a single-threaded CPU, with a margin preferred. Freeze the
choice before evaluation. Report tails and overruns rather than claiming a hard
real-time guarantee from averages.

Preregister exact code/config content hashes, existing Git HEAD, checkpoint/data
hashes, protocol and analysis before any evaluation game. Git commits are forbidden;
an uncommitted content manifest is the actual code identity, not a fictitious commit.
Use the original 256 holdout and 64 Hog seeds/cells. Evaluate each player head to
head with the stochastic s2902 policy for 128 games, paired seats, holdout candidate
and training opponent decks. Copy OQ analysis and setup without changing its files.
No evaluation-driven tuning. Store compact per-game receipts below 1 GiB; at most
three nice-10 workers, launched only through the required detach wrapper.

## Initial cost choice, superseded by full-game timing

K=4 for both players. The final K=8 maximum was 0.2479 s but two prior
measurements exceeded 0.25 s; K=4 retains useful headroom. Hidden combat phases are
uniform within each public card's attack interval; shields use full spawn value only at full body HP and zero after visible HP loss,
status/route caches reset, and projectile destinations extrapolate visible facing.
Body aliases and projectile templates come from canonical immutable gamedata.
These approximations are fixed before scoring any evaluation game.

Before live decisions, warm one synthetic public policy input and discard its recurrent state. Lazy Torch initialization is startup work; the measured setup cost is reported separately. Every actual game starts a fresh recurrent state and its prescribed random seeds.

## Final cost choice

K=1 for both players. A full-game K=4 decision required 0.270865 core-s and
0.271016 wall-s, failing the strict 0.25 s gate. This latency-only change is
Amendment 4; every evaluation game restarts. The preceding K=4 run is retained
separately and excluded from final chosen-K results. Pre-game warmup is required.
