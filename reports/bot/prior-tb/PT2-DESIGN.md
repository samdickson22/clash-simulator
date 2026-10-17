# PT2: human-prior tie-break. Design (proposal; NOT run; cycle-model owner, for the BOT LEAD; 2026-10-17)

PT1 (PREREG.md) uses f1a2, a search-distilled self-prior. PT2 asks the human question: does a tie-break toward the
human **v1** imitation policy (main02: trained on c56-store-v1 human replays) pull our commitment timing toward human
banking (Giant behind the King at ~9 elixir, more elixir held at enemy pushes)?

## Feasibility (counted 2026-10-17 on 04; bot/fullpool/cards.py C56, pool v3.1, WINT-ACC1's 43 King-9 rows)

**Our side:**
- Sam's deck is fully C56. Valkyrie, Archers, **Bats**, Cannon, Fireball, **Zap**, MiniPekka and Giant are all in C56.
- So π is over our own actions, which v1 learned from humans.

**Opponent side:**
- **7 of the 43 rows are fully C56, which is 5 distinct decks of 31.** That is below the ~15-deck bar for a C56-only
  subset.
- All v3.1 King-9 rows with levels, Goblin Hut included: 9 of 51.
- **Non-C56 opponent cards by number of rows:** Pekka 20, Barbarians 18, Witch 17, BattleRam 10, SkeletonDragons 9,
  Guards 8, Bomber 8, Tombstone 5, SpearGoblins 4, MegaMinion 2.
- 29.4 % of opponent deck slots are non-C56.
- Rows by number of non-C56 cards: 0: 7, 1: 6, 2: 8, 3: 12, 4: 7, 5: 3.

## Fallback

The least-bad fallback is **v1-fp** (ext/main02-fp.pt, the bundle's extended v1) as π on every row.
- v1-fp is the human v1 network with 90 card-embedding rows added for non-C56 tokens. Each added row is copied from a
  C56 look-alike (bot/fullpool/extend.py receipt, e.g. Bandit ← Knight).
- On C56 inputs it is bit-identical to v1 (bundle parity PASS, 0/600 roots differ).
- So the prior's *output* (our actions, all C56) is human-trained.
- Only the *encoding* of non-C56 opponent units and cards uses proxy embeddings: 29.4 % of opponent deck slots, in
  36 of 43 rows.

Rejected alternatives:
- **A per-decision v1/f1a2 mix:** f1a2 would decide every decision after a non-C56 reveal. That is most decisions in
  84 % of games, so the test would mostly re-run PT1.
- **A C56-only subset:** 5 decks is too narrow.

## Pre-registration draft (fixed when the BOT LEAD says run)

- **Term:** as PT1 (bot/search/priortb.py), with π from v1-fp instead of the fast tier.
  - New token `hp<N>`, λ = N/1000.
  - Inputs: the same kept (model packet, D1) as the fast tier at that poll. v1 has the R3 architecture, so the same
    single_features feed it.
  - π(play) = P_v1(play) · softmax of its card+tile log-probs over legal plays; π(wait) = 1 − P_v1(play).
- **Arms:** res-lb-wint (live name, the driver's wintp) vs **+hp2 (λ 0.002)** vs **+hp5 (λ 0.005)**. These are the
  same λ as PT1, so the two priors compare directly.
- **Rows:** account (V6 A8 B7 C9 F6 Z8 MP7 G7 King 7 vs logged levels) and L16.
- **Opponents and decks:** vs LIVE-K4CW-r16-fp + R3a; WINT-ACC1's 43 rows.
- **Bank:** fresh os.urandom BASE logged first; 200 paired per opponent per row. Default-off parity before any game.
- **Co-primary readouts:**
  - (1) Δ score with a paired normal 95 % CI, L16 and account, pooled and per opponent;
  - (2) the behaviour diagnostics per arm, with stated predictions: Giant behind-King share up from ~3–5 % toward 19 %;
    elixir at the Giant play up toward ~9; elixir at enemy bridge pushes up from ~2.6–3.9; swarm response and lethal
    missed windows not worse.
  - Plus reaction, undefended share, elixir at the cross.
- **Secondary:**
  - the same readouts on the 7 fully-C56 rows (pure v1), stated as small-n;
  - the gate share of the term: v1's per-poll P(play) is human-paced and low, so λ·log P(play) is a near-constant play
    penalty. Its mean size goes in the smoke report before launch, and the readout splits gate vs within-play shape.
- **Compute:** 2,400 games, the same as PT1.

## Update 2026-10-17 (BOT LEAD, from HP1 reports/bot/hp1/DESIGN.md, main 1a6983396): use v2 as π

**π = v2:** the full-pool human policy `main-2026100822`, best-dev step 46459, sha256 87794378….
- Copies: 04 ~/repos/clasher-checkpoints/v2/main-2026100822/87794378…/best-dev-step-00046459.pt, and the same file on 01.
- Trained 10-08 on the v2 store: 121 own cards, 8.36 M supervised plays, 29.2 % of them non-C56.
- Its config and weight shapes are identical to v1 / v1-fp (SetPolicy, vocab 360), so it loads through
  bot/exit/student.load_policy unchanged. It has never played a game.

**Why v2 replaces v1-fp:**
- No proxy embeddings: v2 learned every human card from real data.
- v1 saw only ~1 % of the store's Zap plays and 12 % of its Bats plays. Sam's current Hog deck carries both.
- The C56-coverage problem above disappears. The design runs on the full deck set: WINT-ACC1's 43 rows, or the
  v3.2 53-row set used by LVG2, with Sam's current deck.
- The fully-C56 secondary readout is dropped.

**Token:** `hp<N>` = bot/search/priortb.py's term with π from v2. It reads the fast tier's kept (model packet, D1) at
the same poll and runs a v2 forward lazily at root decisions only. Before any game:
- a parity check that v2's decisions on recorded roots match the feature path (HP1 §2: DerivedD1 on live16402b-r3);
- the usual default-off parity.

**Cautions carried into the pre-registration:**
1. **Command lag.** Human labels assume an instant effect, but our loop has ~1.35 s (27 ticks) of command lag, so
   v2's play timing may lean early or late. It is noted as a known skew. The behaviour diagnostics (Giant timing,
   elixir at pushes) are where it would show.
2. **WAIT dominates human decisions** (96.3 % of v2's training decisions). So P_v2(play) per poll is small, and
   λ·log P(play) acts as a near-constant play penalty. Planned handling:
   - the smoke reports the mean gate term per decision (wait vs best play), before launch;
   - the readout splits the term into gate and within-play shape;
   - if the gate part dominates (e.g. > 2× the shape part at λ = 0.005), add a shape-only arm (`hps<N>`: same
     within-play log-softmax, gate term 0) instead of one of the two λ arms. That decision is fixed after the smoke,
     before any claim game.
- The arms, rows, bank, parity and co-primary readouts are otherwise as drafted above.
