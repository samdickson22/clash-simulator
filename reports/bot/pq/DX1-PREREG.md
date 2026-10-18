# DX1: where the v2 policy alone loses what the live search wins. Pre-registration (play-quality owner, diagnosis)

Registered before any DX1 game. BASE **2680308772461232**, drawn on 127x04 at 2026-10-18T10:23:54Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint).

## Why (Sam, binding 2026-10-18)
"The search is a bad idea; if our bot is worse without it, it's a problem with the bot." Goal: a policy-only bot that
beats the live search bot (HP1 RL owner). This study finds, with counts and examples, the decision types where the v2
policy loses what search wins, as concrete training targets for the RL owner (data, labels, reward, opponents).

## Arms (paired on every case)
- `res-lb-RF-sdiag-wintp`: the live search bot (with RF), plus the shadow recorder (bot/pq/shadow.py): at every poll the
  v2 policy's gate, top plays and decoded action on the same packet/D1, and at searched decisions the search's own scores
  for every key (refined set, coarse scan of every play, waits). Smoke: identical command hashes to `res-lb-RF-wintp` on
  2/2 cases (analysis only).
- `pv2`: the v2 human policy @ τ* 0.019753086419753086 ALONE in our seat (LivePlayer fast tier).

## Design
Live Hog deck; pool v3.2 53 King-9 rows, vocab-full; opponents LIVE-K4CW-r16-fp, R3a, HPv2; 150 paired cases each; rows
L16 and account (RF1's account levels). 1800 games, 04/08, after PTR1 (queued behind it).

## Readout (diagnosis; no ship rule)
1. Outcome gap pv2 − search per opponent and row (paired CI), and every play-quality metric for both arms (idle, wrong
   lane, wincon dumps, Hog-crossing elixir, barrel answers, spell plays/hits, Cannon placement, reaction).
2. Shadow table over the search arm's searched decisions: agreement rate, and disagreements by type: search holds/waits
   vs v2 plays (and the reverse); different card class (spell / building / troop / win condition); same card,
   different tile (distance; own/enemy half; lane); the search's score gap between its choice and v2's action where v2's
   action was scored (refined or coarse), as a regret proxy, per type and per game phase (single/double elixir) and
   context (enemy push on our half, enemy win condition on board, our elixir).
3. For the RL owner: the top regret types with counts, 5 examples each (tick, board, hand, elixir, both actions, scores),
   and proposed training targets (states to weight, labels = search actions, reward terms, opponents).
