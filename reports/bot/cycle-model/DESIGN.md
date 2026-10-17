# Opponent cycle model: tolerant of unseen plays, soft about phantoms (exploration)

Status 2026-10-17T03:45Z: code on main, default OFF. The BOT LEAD's decision: no ship and no live A/B until the
max-level (L16) sizing shows the problem matters (RESULTS.md, PROGRESS.md).

Owner: cycle-model owner (BOT LEAD track). Started 2026-10-17T01:55Z. Code: `bot/cyclemodel/` (never bot/live).

## Problem

The search belief (frozen `derived_public_state.DerivedPublicState` → s1 `Belief` → `LiveBelief` / `FullPoolBelief`)
is a table of rows (deck × hand/queue order) with weights. A card play keeps only the rows that hold the card in hand.
A too-early repeat empties the table and raises, so the live translator's `_consistent` guard drops those plays before
they reach it: 435 drops in 80 battles, about 67.5% of them real. Births never sees opponent spells, so each unseen
spell leaves the cycle one short. The frozen D1 trackers (the it5s2/R3a pollers) are just as strict: they raise
`public play inconsistent with ordinary cycle`.

## Model (belief level, append-only)

Each row is still an exact hand/queue state. Two new mechanisms are added:

1. **Hidden plays.** One unseen play takes a hand card h to the back of the queue, and the queue head refills the hand.
   When an observed play of C is impossible in every row (C is only ever in the queue), the belief looks for the
   **minimal explanation**:
   - First, a forced pending refill (timing slack, k = 0). Failing that, C at queue index j needs k = j+1 hidden plays.
   - k\* = the minimum over rows that contain C. Only rows with k = k\* are kept. Each one branches over its hidden
     cards, and each branch is weighted by the product of λ(h) over its hidden cards. λ(h) = P(a play of h is unseen).
     It comes from data: λ = 1 for cards with no Troop/Building body in the runtime config (spells, which births can't
     see) and λ = ε (the measured births miss rate) for the rest. So rows with spells in hand absorb the gap, with no
     per-card rules.
   - **Elixir bound.** A branch is pruned if the hidden cards plus C cost more than the exact ledger plus a slack
     (ledger error from phantoms and misses). If every branch is pruned, the play is impossible.
   - Duplicate rows merge exactly: a row holds all 8 cards, so equal rows are the same state. A weight floor and a
     row cap bound the cost.
   - Hidden plays are derived state, not events, so a prior rebuild (an off-prior reveal) replays them deterministically.
2. **Soft plays.** A new event kind `PublicEvent(tick, 'card?', name, amount=p)` carries p = P(real). The row
   posterior becomes a mixture: the "real" branch (p mass; minimal hidden plays if needed) and the "phantom" branch
   (1−p mass, state unchanged). The translator's p is already conditioned on "this play conflicts", so the belief
   doesn't charge a separate ε^k (no double count). The ledger is charged p·cost(C) plus the expected hidden cost.
   - A soft play that is impossible under any explanation (C in no row, k\* over the elixir bound) counts as a phantom.
     A certain 9th distinct card is still rejected, as today.
   - Optional later evidence: `PublicEvent(tick, 'unseen', '', amount=p)` (e.g. tower damage with no visible source)
     = one hidden play with probability p, inserted at that tick.

**Perfect observation is the frozen code path.** If a batch has only certain events and no conflict, `update` runs
the frozen per-event operations in the same order (advance → filter → append), so states, weights and RNG use are
bit-identical. With perfect observation (sim), conflicts never occur.

**Deadline mode.**
- A clean batch uses s1 `Belief`'s chunked transaction as today.
- A conflict (ValueError inside the transaction, with `self` untouched), or a batch that holds `card?`/`unseen`
  events, runs the resolver unbounded, but only if the cutoff hasn't passed. It's rare (≈5 times per battle in live),
  and its cost is measured.

**P(real) (`bot/cyclemodel/preal.py`).**
- v0 (the in-code default): a smoothed stratum table from sample 1.
- **v1:** `reports/bot/cycle-model/preal-v1.json`, a logistic model on the translator owner's 200 labels (kind,
  near-spawner, plays_between, log ticks_since_same). Leave-one-out log loss 0.229 vs v0's 0.514, calibrated per cell.
  Select it with `BOT_CYCLE_PREAL=<path>`. The translator calls `p_real(self.drop_features(...))`.

**Implementation notes (after two Sol review rounds).**
- The elixir budget applies to every explanation (k\* = 0 too), with the tolerance in elixir units.
- Hidden cost is a weighted average.
- `card?` with p = 1 uses the soft operation.
- The heaviest row always survives pruning, and zero-weight rows are dropped.
- Only the output of `_hide` skips the merge.
- Stats reset on a fresh or rebuilt event list.
- Merge keys are uint64 when queue_len = 4.
- Cost: ~1 ms per conflict, except the first conflict of a battle while ~100k prior rows remain (≤ ~120 ms on loaded
  fleet hosts; ≤ 7 ms max_ms in the translator owner's Mac-env shadow).

## Wiring (default OFF, so today's bot is unchanged bit for bit)

`BOT_CYCLE_MODEL=soft[:eps=…,slack=…,cap=…]` wraps whatever belief class the planner installs, under the rebuild
layer:
- `FullPoolBelief`: the Mac's full-pool tree, `bot/fullpool/belief.py`;
- `LiveBelief`: the C56 fallback; this needs a one-line hook in bot/live/player.py, delivered as part of the diff.

## Translator hand-off (DIFF for the LIVE LEAD / translator owner; I never edit bot/live)

In `accept_events`, an opponent play that fails `_consistent` is no longer discarded. It is appended to the **belief
stream only** (`self.events`) as `card?` with p = `preal.p_real(features)`, counted as `cycle_conflict_soft:1`. The D1
stream (`public_events`, the mirrors, `plays`, `board_card_ok`) stays guarded, so the frozen pollers can't break.
D1's queue still misses those plays; fixing that is a separate follow-up.

## Validation

- **(c) Determinism.**
  - Belief level: recorded event streams give identical rows, weights and samples with the model ON and OFF.
  - Players: command-hash parity ON vs OFF on ≥20 LIVE-AB1 cases each for the deterministic twins of the live player,
    `K4L-R-gs-mk1a1` and the lopp_fast path `K4L-R-gs-rw-fc-t2-mk1a1` (the w200 players aren't hash-reproducible).
- **(a) Sim A/B.** The live player under live-like opponent history (live-diag's injector: births-only/unseen spells,
  ~3.7 real drops and ~1.8 phantoms per battle). Arms: hard rule vs soft model vs clean history. Battle Log decks, pin
  live16402b-r3, vs LIVE-K4CW-r16 and R3a, ≥100 paired cases, fresh bank.
- **(b) Live replay gate (the translator owner runs it).** The 80 battles: how many of the 435 are kept, and the
  phantom acceptance rate, with a Sol video check.
