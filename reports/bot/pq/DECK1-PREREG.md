# DECK1: deck screen at real levels (LIVE account manager request). Pre-registration (play-quality owner)

Registered before any DECK1 game. BASE **650753795946352**, drawn on 127x04 at 2026-10-18T10:29:25Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint).

## Request
LIVE Sol account manager, collection /mpac/sdicks02/repos/clasher-live/reports/live/account/collection-20261018T1026Z.json:
King 8; HogRider 8, Archers 8, Cannon 9, Skeletons 7, Fireball 7, Zap 9, Valkyrie 7, ElectroSpirit displayed 8 BOOSTED
(base unverified; the 20-gold upgrade cost is consistent with base 2), IceSpirit owned L1, Musketeer 5, Bats 8,
SkeletonArmy 6; IceGolem and TheLog not owned. Compare the current deck vs the best alternatives and the closest-to-Hog-2.6
deck at REAL levels vs strong opponents, paired. Rule: lower 95% CI > 0 vs current, or a step toward 2.6 with point
>= −2 pp and CI including 0. No in-game edits recommended here; the parent coordinates the bundle.

## Decks (all with the live player res-lb-RF-wintp; levels as above, King 8 vs logged opponents)
- D0 current: HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit (8, as displayed), Valkyrie.
- D0b current with ElectroSpirit at 2 (sensitivity: the boost ends; base not verified).
- D1 ElectroSpirit -> Bats 8 (no boost dependence).
- D2 Skeletons -> SkeletonArmy 6 (deck search final2's top alternative, here at its real level).
- D3 one step toward 2.6: Archers -> Musketeer 5.
- D4 closest-to-2.6 with owned cards: HogRider, Musketeer 5, Valkyrie (for IceGolem), IceSpirit 1, Skeletons, Cannon,
  Fireball, Zap (for TheLog).
Same bank, so every deck meets the same opponent deck, seed and seat per case (deck-independent case draws).

## Design
Driver l16_cadence `--levels account`, pool v3.2 53 King-9 rows with logged levels, vocab-full. Opponents LIVE-K4CW-r16-fp
(primary, 200 cases), R3a (100), HPv2 (100). 2400 games, 04/08, after/beside DX1.

## Readout
Paired Δ vs D0 with 95% CI (4000-draw case bootstrap, Random(0)) per opponent, primary vs K4CW-fp; D0b vs D0 reported
as the boost-expiry risk. Apply the request's rule per deck; one result line to the account manager.
