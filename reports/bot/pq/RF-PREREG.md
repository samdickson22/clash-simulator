# RF1: root fidelity A/B. Pre-registration (play-quality owner, exploration)

Registered before any RF1 game. Bank drawn on 127x04 at 2026-10-18T03:12:07Z with
`int.from_bytes(os.urandom(6),'big')<<4`: **BASE 1481988713230448** (check_bank: disjoint from HEADLINE and every
bot/fullpool/banks.py eval bank).

## Change under test

Token `RF` (bot/search/rootfid.py, default off). The search root is LevelRoot's payload (byte-identical to R.root
when no public extra matches) with the public timing/target facts the v5 packet drops, read from
`info.extras` (bot/players/royalesim_translate.py PublicInformation):
- in-flight carriers keep their actual destination: Goblin Barrel (rebuilt aiming at (0,0) today), Fireball/Arrows
  and other spell projectiles (rebuilt aiming one tile ahead), unit/tower shots; Goblin Barrel keeps its flight age;
- deploying bodies keep their remaining deploy time; stunned bodies their stun;
- body age from first sight; spawner buildings get the production phase that age implies.
Dev check on 04 (RoyaleSim truth vs root, native forward): barrel lands at tick 54 (truth 54, R.root 73 at (0.25,0.25));
an in-flight Fireball hits the tower (R.root: no hit); a deploying Knight first moves at tick 19 (truth 19, R.root 1).

## Design

- Driver bot.livediag.l16_cadence (this commit; `--own-deck`), runner bot/pq/l16.sh, runtime live16402b-r3,
  RoyaleSim 16.402, noise clean, 27-tick command lag both seats.
- Own deck (live): HogRider, Archers, Cannon, Skeletons, Fireball, Zap, ElectroSpirit, Valkyrie.
- Opponent decks: Battle Log pool v3.2 (`/mpac/sdicks02/jobs/clasher/bot-cycle/lvg2/battlelog-pool-v3.2.jsonl`,
  sha256 01732d23…), the 53 King-9 rows with logged levels (LVG2 strata `all=92,108,…,170`, no Goblin Hut);
  vocab vocab-full.json (sha256 f588168f…).
- Opponents: LIVE-K4CW-r16-fp (strong, primary) and R3a; 200 paired cases each, seat alternating.
- Rows: **L16** (every card and tower 16 both sides) and **account** (ours Skeletons 7, Archers 8, Valkyrie 7,
  Cannon 9, Fireball 7, Zap 9, ElectroSpirit 8, HogRider 8, King 7; opponents their logged levels, King 9).
- Arms (serial twins, paired on every case): `res-lb-wintp` (live player) and `res-lb-RF-wintp`. 1600 games.
- Hosts 127x04 and 127x08 via bot/exit/cpu_job.sh + bot/detach.sh, nice 15, 4 shards per row.

## Prediction and ship rule

Prediction: RF − plain > 0 vs LIVE-K4CW-r16-fp.
Ship: vs LIVE-K4CW-r16-fp pooled over both rows (400 pairs), the paired 95% CI lower bound ≥ 0, neither row's point
estimate below −0.02, and the play-quality metrics not worse. Otherwise no ship; the readout says which part failed.

## Readout

bot.fullpool.hz_report (score, paired Δ with 4000-draw case bootstrap, Random(0), per opponent and pooled, per row),
plus the standing play-quality metrics per arm: idle (no enemy within 6 tiles) share, wrong-lane defensive share,
elixir at the enemy's crossing (all incursions, and enemy Hog crossings: mean/median, share with Cannon+3 available),
wincon spend share, spell use (plays/game per spell card; Fireball/Zap hits), Goblin Barrel responses (a spell or
troop answer reaching the landing point within 1.5 s), reaction p50/p90, CPU-ms per decision. Duplicate rows must be
identical and count once. No early stopping; results reported as they land.
