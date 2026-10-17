# PT1: prior tie-break at the K4L-R root. Pre-registration (cycle-model owner, for the BOT LEAD; exploration; written before any PT1 game)

Origin: SC1 add-on 2 (reports/bot/spell-hold/RESULTS.md). At 18 live missed spell windows: 9 scorer vetoes (median gap
0.0065), 6 pre-filter cuts, 0 proposer gaps. The BOT LEAD ordered the run on 2026-10-17, applied to ALL root keys.

**BASE = 68725711644388.** Drawn with os.urandom(6) at 2026-10-17T21:49:44Z, before any PT1 game; logged in job dir
bot-cycle/pt1/pt1-base.txt on 04 and 08.

## Term (main 68816487f, bot/search/priortb.py; token `pt<N>`, λ = N/1000, default OFF)

- **Formula:** every root key the search scores (plays, WAIT, timed waits) gets score(a) += λ · log max(π(a), 1e-4).
- **Prior source:** π comes from the LivePlayer's fast tier at the same poll: the f1a2 student, an R3-architecture
  SetPolicy, the fast tier the live stack runs.
- **Prior formula:**
  - π(play a) = P(play) · softmax over its legal plays of its joint card+tile log-probs;
  - π(WAIT) = π(timed wait) = 1 − P(play).
- **Mechanics:** the term composes into core.reserve (subtracted by reserve.apply) on top of `res`. If the fast tier did
  not poll at the decision tick, the term is 0 and the decision is counted as `missing`.
- **Rules:** no per-card or per-class rules. The fast tier's own decisions are unchanged: the forward is recomputed
  from its kept inputs.

## Design

- **Arms (paired on every case; the live name, through lopp_fast.make_live_lopp `-wint`, i.e. the driver's `wintp`):**
  - `res-lb-wintp` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint (control);
  - `res-lb-pt2-wintp` = …-res-lb-pt2-wint (**λ = 0.002**);
  - `res-lb-pt5-wintp` = …-res-lb-pt5-wint (**λ = 0.005**).
  - All are serial twins with deadlines cleared, as in WINT-ACC1 (-lb is a no-op without a worker pool).
- **Rows** (the same cases in both):
  - **L16** (primary, per Sam's rule): both sides at L16.
  - **account:** ours Valkyrie 6, Archers 8, Bats 7, Cannon 9, Fireball 6, Zap 8, MiniPekka 7, Giant 7, King 7. The
    opponent plays at each row's logged card levels and logged King level.
- **Opponents:** LIVE-K4CW-r16-fp and R3a.
- **Decks:**
  - Ours: Sam's live deck.
  - Opponents: WINT-ACC1's pre-declared set, for comparability. That is pool v3.1 (battlelog-pool-v3.1.jsonl), the 43
    King-9 rows with full levels and no Goblin Hut (pools/wintacc1-rows.json; indices 92, 108-114, 116, 118, 119,
    122-131, 133-141, 143, 144, 146, 148, 149, 151, 152, 154-159), drawn uniformly by index.
- **Cases:** **200 per opponent per row**, seed = BASE + opponent_index · 301 + i (the driver's rule). That makes
  3 arms × 200 × 2 opponents × 2 rows = 2,400 games.
- **Code:**
  - Source tree: an archive of main 68816487f.
  - Driver: cadence-pt1, a copy of live-diag's cadence-pk1 (l16_cadence.py 174b70bb…). The copy adds `pt\d+` to the
    token whitelist and changes the run script's own path: l16_cadence.py ceb07587…, run-l16-cadence.sh 0ae16d05….
  - Vocab: vocabv3/vocab-full.json. Prior counts go to $BOT_PRIORTB_LOG.
- **Default-off parity BEFORE any game:** `res-lb-wintp` on 68816487f vs its parent e686e2a6a, 10 cases vs R3a, account
  row. All command_sha256 must be identical; any difference halts PT1.
- **Hosts:** 08 and 04 (04 ≤ 70 load, user-limited), below deckopt3 and WINT-ACC1, above HZ1. cpu_job, nice.

## Pre-registered readout

- **Primary:** for each pt arm, Δ = score(arm) − score(control), score = win 1 / draw .5. Paired over the same cases,
  normal 95 % CI, per row:
  - pooled over the two opponents (400 pairs);
  - per opponent (200 pairs).
  - **The L16 row is the primary row.**
- **Decision (report as measured; the BOT LEAD decides):** a λ is a candidate only if:
  - its L16 pooled Δ > 0 with CI lower bound > −0.03;
  - AND its account-row pooled Δ CI lower bound > −0.03.
  - A candidate still needs a fresh-bank replication before any live change.
- **Mechanism (no decision attached; it matters as much as win rate):** per arm and row, the behaviour diagnostics
  (bot/livediag/behaviour_diag.py, definitions as committed):
  - Giant behind-King vs bridge share, and elixir at the Giant play;
  - our elixir when an enemy push reaches our bridge;
  - swarm-response rate;
  - lethal missed windows;
  - tower-only casts;
  - plus l16_report's reaction p50/p90, undefended share and elixir at the cross.
- **Hypothesis stated in advance:** the prior pulls commitment timing toward human banking. Predictions: Giant behind
  the King share up from ~3–5 % toward the human 19 %; elixir at the Giant play up toward ~9.
- **Prior bookkeeping:** missing share, and the share of decisions whose scanned work set holds one of the prior's
  top-3 plays (the pre-filter question).
- No early stopping. All rows are read together once complete.

**Smoke (before parity and before any PT1 game; base 4242, account row, 2 cases vs R3a, 08; job dir pt1/smoke1):**
- 0 errors; the pt5 arm's command hashes differ from the control's.
- Prior available at 433/433 pt5 decisions.
- The prior's top-3 holds a scored play in 58 % of decisions.

**Amendment 1 (2026-10-17, before any PT1 game; labelling only, design unchanged).**
- The prior f1a2 is search-distilled, not human. Evidence is its checkpoint args:
  - init bot-fullpool/ext/rl5-v10-fp.pt;
  - data bot-fullpool/G1/packed-g1a-* (manifest schema clasher.exit-r1.teacher-v6.v1) + bot-exit-r1/packed-kc7a-*;
  - new_ratio 0.5, temperature 0.003, advantage_weight 0.
- So PT1 tests a **self-prior tie-break** (PUCT-style smoothing toward our own distilled search). The human-banking
  hypothesis above stays stated, but a self-prior is not expected to carry it.
- A human-prior run (PT2, v1 as π) is a separate proposal.

**Default-off parity (before any PT1 game; finished 2026-10-17T22:09:34Z): PASS.**
- `res-lb-wintp` on 68816487f vs its parent e686e2a6a, 10 cases vs R3a, account row, base 4246, 08.
- **10/10 identical command_sha256**, 0 errors (job dir pt1/par-new, pt1/par-old).

**Launch 2026-10-17T22:10Z** on 08 at LOW priority: two lanes × 4 workers (pt1/lane.sh), claiming 16 shard jobs
(rows l16/acct × shard k/8). Bank check: 400 cases (200 per opponent), first seed = BASE.

**Amendment 2 (2026-10-17 ~23:10Z, BOT LEAD: PT1 to NORMAL priority; new co-primary readouts from the s81 review).**

- **Priority:** after deckopt3's final, LVG2 and PF1; ahead of HZ1, LV2 and NS2/S0. Up to ~24 workers on 08 / 04 under
  their caps. The lanes resume as soon as LVG2's slots free.
- **Co-primary readouts added, per arm and row, each as Δ vs the live arm `res-lb-wintp`, paired over cases,
  bootstrap 95 % CI** (10,000 case resamples, seed 0, ratio of sums):
  1. **idle-play share:** our plays of Troop/Building cards with no enemy unit within 6 tiles of the deploy tile;
  2. **spend-down before a revealed win condition:** the share of opponent win-condition plays preceded, within 3 s,
     by a play of ours that left us at ≤ 1 elixir. Win condition = a card with a unit whose stats.only_buildings is
     set (a config data rule, cardtable `wincon`).
  3. **elixir at the enemy's cross:** l16_report elixir_cross_p50.
  - Definitions: bot/livediag/behaviour_diag.py (f)/(g) and cardtable.py `wincon` / `body_cards`, committed with
    this amendment and fixed now.
- **Disclosure:** written after 68 PT1 games were played (22:10–22:38Z, shards l16-s0 / acct-s0). They were then
  discarded whole and unread when PT1 paused for LVG2. Those shards rerun fresh, and no PT1 outcome has been looked at.
- **Context:** the s81 review found 4 cases where search overrode a better fast-tier proposal. That is PT1's
  hypothesis; its prior is that same fast tier, f1a2.
