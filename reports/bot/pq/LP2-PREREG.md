# LP2: lag-projected candidates on top of the shipped root fidelity. Pre-registration (play-quality owner, exploration)

Registered before any LP2 game. BASE **927358666375088**, drawn on 127x04 at 2026-10-18T04:59:41Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint).

## Why
RF shipped (RF1: +0.085 [+0.030, +0.140] vs K4CW-fp). The Cannon/barrel diagnosis (clasher-bot-cannon-sol
CANNON-PULL.md §2) found that with a corrected barrel aim, the exact landing Zap is absent from the candidate list in 8/8
constructed roots, and adding it flips the choice. LP26 appends the proposers' picks on the board projected 26 ticks by
the planner root; with RF that projection lands the barrel and its goblins where they really land, so landing-point
spells, and Cannon/troop placements against where a Hog will be, become candidates. LP1 (running) tests LP on the
old root, where an in-flight barrel is projected to (0,0); LP2 is the live-relevant test.

## Design
As RF1 (reports/bot/pq/RF-PREREG.md): live Hog deck, pool v3.2 53 King-9 rows, vocab-full, LIVE-K4CW-r16-fp (primary)
and R3a, 200 paired cases each, rows L16 and account (same account levels). Tree: origin/main 656771761 (RF and LP code
as reviewed). Arms `res-lb-RF-wintp` (new baseline) and `res-lb-RF-LP26-wintp`. 1600 games, 04/08.

## Prediction and ship rule
Prediction: RF-LP26 − RF > 0 vs K4CW-fp. Ship: vs K4CW-fp pooled over both rows, lower 95% bound ≥ 0; neither row's point
below −0.02; the standing and Sam-complaint metrics (barrel answers, Hog-crossing elixir, spell hits, idle, wrong lane)
not worse beyond ~2 SE, with the targeted metrics (barrel answer share, Zap/Fireball hit share) reported first. CPU-ms
per decision reported (LP adds candidates; the live wall is 200 ms).
