# PF1: policy-first, the fast policy alone vs the live search, on Sam's current deck at account levels. Pre-registration (bot live-diag; before any game)

Ordered by the BOT LEAD 2026-10-17, evidence for the coordinator's live POLICY-FIRST A/B: the fast policy decides alone, with
the search as rollback. **No ship rule is pre-registered** (the live A/B is already decided); this shapes its rollback threshold.

**BASE = 222822440760931.** Drawn with os.urandom(6) at 2026-10-17T23:44:12Z, before any PF1 game.

## Design
- **Our deck: sam5 with Valkyrie.** Live swaps Bats → Valkyrie 7, and this bank had not been drawn yet.
  - HogRider 8, Archers 8, Cannon 9, Skeletons 7, Fireball 7, Zap 9, ElectroSpirit 8, Valkyrie 7; King 7. Account levels.
- **Opponents:** each pool row's logged card levels and logged King level.
  - Rows: pool v3.2 (battlelog-pool-v3.2.jsonl sha256 01732d23…) restricted to complete logged levels, King 9, and no Goblin Hut.
  - Result: 53 rows (34 distinct decks; 24 of the rows have a P.E.K.K.A). Indices are in pools/pf1-rows.json (sha256 ecf79fc2…), drawn uniformly, so duplicates keep their observed frequency.
- **Opponent policies:** LIVE-K4CW-r16-fp and R3a.
- **Arms, paired on every case:**
  - (a) `res-lb-wintp` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint (the live search; serial twin, deadlines cleared);
  - (b) `fast-rl5v10fp` = LivePlayer(tier='fast', fast_spec=student:/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/rl5-v10-fp.pt@0.5375), sha256 a6565cab…. This is live's `LIVE-fast-rl5v10fp` decode;
  - (c) `fast-f1a2` = LivePlayer(tier='fast', fast_spec=student:/mpac/sdicks02/jobs/clasher/bot-fullpool/fits/f1a2/step-001200.pt), sha256 0c03f79f…. This is the bundle FAST alone.
- **Cases:** 150 per opponent.
  - seed = BASE + opponent_index * 151 + i;
  - the deck is drawn from the 53 rows; seat alternates.
  - Total 3 arms x 150 x 2 opponents = 900 games.
- **Code:**
  - driver cadence-pf1/l16_cadence.py sha256 cda77034… (read-only). It adds `--own-deck` and `fast-<label>` players, which build LivePlayer tier='fast' and skip the search-tier deadline configure;
  - source tree: main 7df775763 archive (k4cw_fp a8dac0a6);
  - vocab: vocabv3/vocab-full.json (f588168f…).
- **Precondition: met.** A smoke of all 3 arms x both opponents gave 6/6 clean games. Our levels and deck were confirmed; the fast arms played 22-40 cards per game.
- **Hosts:** --shard K/3. 127x08 runs shards 0 and 1 at 10 workers each; 127x04 runs shard 2 at 10 workers, behind cpu_job admission.
  - If 04 stays saturated, shard 2's cases are re-run on 08 with --only and the same seeds; the rows are deterministic.
  - Caps: <= 40 workers total, 04 <= 70 load while a lab user is on.

## Reported (bootstrap 95 % CI over cases, 10,000 resamples, seed 0)
- Per opponent: (b) - (a) and (c) - (a), paired by case.
- Per opponent x arm:
  - score with CI;
  - plays per minute (accepted plays / game minutes; catches WAIT-lock);
  - reaction p50 / p90;
  - undefended share;
  - our elixir at the enemy's river cross (l16_report);
  - **idle-play share** = our accepted troop plays with no enemy body within 6 tiles of the play's target tile. Measured on the bot's own decision packet at the submitting decision (entity features, enemy flag, troop and building bodies, towers excluded). Spells are excluded.
- All rows are read together once complete. No early stopping.
