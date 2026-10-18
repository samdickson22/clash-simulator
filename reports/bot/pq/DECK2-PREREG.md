# DECK2: IceSpirit 6 vs boosted ElectroSpirit, at real levels (supersedes DECK1). Pre-registration (play-quality owner)

Registered before any DECK2 game. BASE **1710938605083664**, drawn on 127x04 at 2026-10-18T12:36:15Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint). DECK1 (older player, IceSpirit 1) was ended unscored.

Request (LIVE account manager, collection /mpac/sdicks02/repos/clasher-live/reports/live/account/collection-20261018T1234Z.json):
IceSpirit upgraded to 6; King 8; wild cards 0. Live player LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-pt5-wint, so every
deck here plays the serial twin `res-lb-RF-pt5-wintp`. Rule: switch if paired lower 95% CI > 0, or a step toward Hog 2.6
with point >= −2 pp and the CI including 0. No in-game edits.

Decks (levels: HogRider 8, Archers 8, Cannon 9, Skeletons 7, Fireball 7, Zap 9, Valkyrie 7, ElectroSpirit 8 as displayed,
IceSpirit 6, Bats 8, Musketeer 5; King 8 vs logged opponents):
- P0 current: HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie.
- P1 (requested; a step toward 2.6): IceSpirit replaces ElectroSpirit.
- A1: Bats replaces ElectroSpirit.
- A2 closest-owned Hog 2.6: HogRider, Musketeer, Valkyrie (for IceGolem), IceSpirit, Skeletons, Cannon, Fireball, Zap (for TheLog).
Opponent LIVE-K4CW-r16-fp (strong), 200 cases per deck, the same cases for every deck (pool v3.2 53 King-9 rows, logged
levels; vocab-full; l16_cadence --levels account). 800 games on 04/08 in the room the RL actors leave.
Readout: paired Δ vs P0 with 95% CI (4000-draw case bootstrap, Random(0)); rule per deck; one result line.

## Amendment 1 → DECK3 (2026-10-18, before any DECK3 game; supersedes all DECK2 rows for switch decisions)
Collection /mpac/sdicks02/repos/clasher-live/reports/live/account/collection-20261018T1354Z.json: HogRider 8 → 9; ElectroSpirit
base verified 2 and upgraded to an actual 8 (no longer boost-dependent); King 8, IceSpirit 6, others unchanged. DECK3 = the
same four decks (P0, P1 IceSpirit, A1 Bats, A2 closest-owned Hog 2.6), same bank and player (res-lb-RF-pt5-wintp), with
HogRider 9. Launcher /mpac/sdicks02/jobs/clasher/bot-pq/deck3.sh (one 6-worker group per deck, cpu_job admission).
DECK2/DECK2b partial rows (HogRider 8) are not used for any switch decision.

## Amendment 2 → DECK4 (2026-10-18T15:15Z, before any DECK4 game; supersedes DECK3)
Collection /mpac/sdicks02/repos/clasher-live/reports/live/account/collection-20261018T1513Z.json: King 9 and Princess 9 (the sim's
single tower level 9 now matches), HogRider 9, Fireball 8, Valkyrie 8, ElectroSpirit effective 9 (base 8, King-boosted),
IceSpirit 6, BabyDragon 8 and Arrows 8 owned. Same bank and player. Started now (levels stable): P0, A1 (Bats for ElectroSpirit)
and a new A3 (BabyDragon 8 for Archers). Held until the IceSpirit 7 batch is confirmed: P1 (IceSpirit for ElectroSpirit) and A2
(closest-owned Hog 2.6), launched later on the same bank and paired with P0 by case index. Launcher deck4.sh.

## Amendment 3 (2026-10-18T15:4xZ): held arms launched at IceSpirit 8
Collection collection-20261018T1539Z.json: IceSpirit 6 → 8 (no further upgrade available); all other levels unchanged from
Amendment 2. P1 (IceSpirit 8 for ElectroSpirit 9) and A2 (closest-owned Hog 2.6: Musketeer 5, IceSpirit 8; IceGolem and TheLog
unowned) launched into deck4/ on the same bank by deck4i.sh (= deck4.sh with IceSpirit=8). P0/A1/A3 rows are retained.
