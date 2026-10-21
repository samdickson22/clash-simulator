# pretrain-v1: engineering decisions

Implementation of `/mpac/sdicks02/scratch/new-pretrain-20261020/{DESIGN,PREREG-DRAFT,INVENTORY,FIDELITY}.md`
(coordinator-approved build, 2026-10-21). This file records choices made **within** that design. Each entry gives the
choice, the reason, and what it costs. Code: `bot/pretrain_v1/`.

## Contract and producers

1. **Pinned memory package.** The record contract is the deployed A3 memory tree (Mac `~/clasher-live/mem`,
   MEM-MANIFEST at 2026-10-21: `state.py` 9085e337, `rfextras.py` 513088f2, `cards-122.json` 289d240f,
   `card-aliases.json` 3b2533b9). `state.py` and the card data are vendored byte-identical under
   `bot/pretrain_v1/vendor/livemem/`, and the builder refuses to run if the hash differs. Live mem is not on
   `origin/main`; the vendored copy is the dataset's projection code, not a fork for serving.
2. **One featurizer.** `featurize.observe(record, extras, history)` is numpy-only and imported unchanged by the
   dataset builder, `policy.Session` (the sim/live entry point) and the audits. The output is **integer arrays**
   (positions 1/100 tile, HP 1/1000, elixir 1/1000), so parity between producers is byte equality, and storage is
   exact. `feature_hash()` (featurize.py + catalog.json) is pinned in every shard and checkpoint, and loaders refuse
   a mismatch.
3. **Inputs.** Only `RECORD_KEYS` with their unit/tower/event/hand allow-lists. `poll` is the one logging key that
   gets stripped. Extras are exactly `first_seen` (aligned with `units`, which is FrameBuilder.unit_first_seen) and
   `spells` (FrameBuilder.spells filtered to `rfextras.SPELL_CARRIERS`). That is the same public information
   `rfextras.MemoryTranslator` turns into `live`/`deploy` and `aim`/`flown`. Deploy-remaining is a deterministic
   function of (body, age), so the network gets the age and the body and is not given a second derived copy.
   Misaligned or absent extras become explicit missing bits, which matches the live translator returning `{}`.
4. **No ids.** Reader ids never enter the featurizer. Motion is a finite difference against the previous poll's
   record: the nearest unit with the same owner and body within 2 tiles, matched greedily by distance. It is a public
   position difference, not an identity claim, and is identical for every producer, including logged live records,
   which carry no ids.
5. **Opponent history** is detected inside the featurizer from public records only. A play is counted when the
   number of the card's *primary* body (first listed body; any body when none is listed) rises. This means
   descendants such as Witch Skeletons, Golemites and hut spawns are not plays. A play is also counted for a new
   in-flight carrier (key: card + aim; play tick = tick − flown), for the first bodies of a spell card (Graveyard,
   landed Barrel), and for record events (empty live: `spell_events=False`). Cooldown is 20 ticks per card, 80 for
   spells, so a carrier and its landing count once. After Sol R1, the rules are more conservative:
   - carriers form a multiset, and each new instance is a cast;
   - spell-card bodies count one cast per episode (100 ticks without bodies, 240-tick cooldown) and mark the count
     uncertain;
   - bodies already present at the first poll reveal the card without counting a cast.

   The last 64 observed plays feed 16 revealed-card summary rows (count, ticks since last use, other plays since
   last use, first-reveal age, uncertainty bit), and 32 recent public play events (own and opponent, 60 s window) are
   tokens. Unrevealed cards are never inferred. Zap, Log and other carrier-less
   spells are invisible in this contract, the same as live.
6. **Own channel: one record-derived rule (after Sol R2).** `History.submit` is called only when the channel accepts
   a command. The rest is computed by `observe` from the record alone, identically for every producer (re-drive
   builder, RoyaleSim, probe replay, future engine or live producers):
   - **confirmed** when its card leaves the observed hand (the live memory route confirms the same way,
     `confirm_polls=1`);
   - **rejected** when the card is still in the hand `REJECT_AFTER` = 45 ticks after submission (27-tick lag plus
     grace; live taps land after about 22 ticks);
   - **expired** after 90 ticks as a backstop.

   Producers never report rejections. One command can be outstanding; a busy channel masks every slot (forced
   no-op). **Mirror** costs the last confirmed ordinary own card's cost + 1 and uses that card's placement. With no
   predecessor it is illegal, as in engine-cards `battle.resolve_card_play`.
7. **Entity cap 256** bodies plus carriers. Above it, `observe` raises `FeatureError`, which is a refusal and never a
   truncation. Live maxima are about 60.
8. **Placement mask** comes from public tower state only, using the engine-cards arena rules at 1831241d2:
   - fence tiles;
   - own zone rows 1–14 plus the six behind-king tiles, with a pocket and bridge when an enemy princess is down;
   - not on a live tower;
   - Miner and GoblinDrill may go anywhere off towers;
   - Log, BarbLog and RoyalDelivery are territory spells;
   - other spells may go anywhere off fences.

   Building overlap and payload occupancy (MASK-V2) are **not** modelled because they need non-record entity
   geometry. A rare tap the client then rejects is logged as an operational failure.

## Dataset (re-drive → records → rows)

9. **Projection.** Each raw native frame becomes the reader's PRIVATE frame for one seat (own p row only) and passes
   through `parse_line` and `FrameBuilder.frame`. This is the re-drive's `project.py` logic, unchanged. The
   FrameBuilder sees every frame from tick 0, but **policy polls start at tick 90**, as LiveSession and the sim
   harness do. These events end the perspective:
   - a schema failure (champion-cycle hand hole) skips only that frame;
   - a FrameBuilder error ends the perspective, because live refuses the rest of the battle;
   - the deciding record (`decided()`) is not a poll, because memloop deauthorises before stepping;
   - a stale tower ends the polls, because live disarms the gate.
10. **Declared cadence adaptation.** Live feeds about 1 frame per tick; the re-drive has 1 frame per 5 ticks. Native
    frames drop a dead tower's row. With the file's `GONE_FRAMES=20`, the re-drive would keep a fallen tower
    "alive" for 100 ticks, where live takes about 20. The builder therefore sets the vendored module's constants to
    `GONE_FRAMES, STALE_FRAMES = 4, 8` (same wall-clock rule). The file stays byte-identical. A residual skew
    remains: re-drive first-seen ages run about 2 ticks low on average, against about 0.5 tick live, because
    first sight lands on the next 5-tick frame.
11. **Lag-aligned labels** follow DESIGN. Decision d* is the latest poll ≤ E − 27. The builder emulates the human's
    **submission** at d* only from facts observable at d*: card in hand, channel free, affordable, and a mask-legal
    tile centre within 0.75 tile, which is asserted. A non-executed submission is rejected by the shared record rule
    (item 6). The **actor label** is admitted only if, in addition:
    - the play executed;
    - every ordinary-cycle opening assignment compatible with the seat's play sequence agrees on the own hand set
      and next card (PREREG §4; in practice from the 4th own play on);

    Future-dependent criteria never touch History, which the stronger suffix-mutation audit verifies.

    The tile label is the nearest legal centre; replay coordinates are unchanged. A rejected play is **never a
    WAIT**: polls d*..E get no actor loss, and the play still enters own history. Own ability events and source plays
    the client did not execute also blank d*..E. The unshifted audit (card in hand and affordable at the latest poll
    ≤ E) is counted in every shard's stats.
12. **Strict affordability costs data.** Measured on 300 matches (19,394 plays): at E−27 the card is in hand 99.0%
    of the time, but affordable only 88.3%. The deficit is a median of 0.28 elixir, so these are mostly
    "play at cost" decisions. The design's strict mask drops those labels, which biases the policy against exact
    play-at-cost timing: it waits for affordability and lands about 27 ticks later than the human. Projected
    affordability (elixir + regen × 27 ≥ cost) would recover them. It needs a live channel that accepts taps
    landing on time, so it is left as a possible registered amendment and not used.
13. **Thinning.** WAIT and forced/busy rows are retained with probability 0.1 using a blake2b hash of
    (match, seat, tick), at weight 10. Plays are all kept. DEV metrics use the same inverse-probability weights
    (natural frequency).
14. **Value** labels are W/D/L for tiers `exact` and `outcome` only (no early end; winner and crowns agree). A draw is
    the source `winner=None`. Other tiers keep imitation labels only, and are truncated at the client's end tick.
    Each match's meta carries `unc_tick`, so a strict ablation can drop all of an affected match's value targets.
    This is the coordinator's data rule for this build ("exact/outcome tiers whole … other tiers truncated at the
    client's end tick"). **Recorded disagreement (Sol R1 #2):** PREREG §4's qualified-prefix reading would cut actor
    and value supervision at the first unverified ability or non-executed source event. Every row at or after that
    point (either seat) is flagged `unc=1`, so the stricter rule is an ablation, not a rebuild. Coordinator to
    decide.
15. **Domain weight.** The actor weight is 0.25 when the own deck has any evo or hero form (modern-form transfer),
    and 1.0 for vanilla. In practice almost every HF deck is modern, so vanilla perspectives get 4× weight.
16. **Split** uses a seat-swap-normalised fingerprint of both decks (card, form, level), towers and the ordered
    command timeline. sha256 mod 10 gives train 0–7, dev 8, final 9. Duplicate physical games and both seats
    therefore share a split.
17. **Hog flag.** Base-composition Hog 2.6 means {Hog, Musketeer, Cannon, IceGolem, Skeletons, IceSpirit,
    Fireball} plus Log or Zap. `hog26_zap` marks the exact-Zap variant. BC samples Hog and general perspectives
    50/50.
18. **Storage.** Each sealed re-drive batch becomes one shard, written to a temporary directory and renamed into
    place. The store is keyed by featurizer and builder hash. `MANIFEST.jsonl` is append-only, and re-running picks
    up newly acked batches. Fixed arrays are `.npy`; entities, events and revealed rows are ragged with offsets.

## Model and training

19. **Architecture.** d=192, 4 pre-norm blocks, 6 heads, FFN 576: **2,102,597 parameters** (2,102,213 before
    the uncertainty column and spell-body source code were added). Tokens are
    CLS + 4 scalar/own-command + 6 towers + 5 hand + ≤256 entities + ≤32 events + ≤16 revealed + 4 lag
    summaries. There is no positional encoding over entities; coordinates use Fourier features.
    - Gate/slot head: a no-op logit from CLS plus four pointer logits from the hand tokens.
    - Tile head: an MLP over (CLS, chosen hand token) giving 576 logits.
    - Value head: W/D/L from CLS.
20. **Sampling at decision time** always samples the gate, slot and tile at T=1. An irregular gap uses survival
    scaling p_wait^(dt/5), with dt clipped to [1, 10]. A gap over 10 ticks or input older than 350 ms is declined as
    stale.
21. **Missing-extras augmentation.** 5% of training rows have unit ages masked, so evaluation on logged live
    records (which lack ids and therefore ages) is in distribution. Opponent-history timing from first-seen is not
    re-derived for those rows.
22. **Gate calibration.** One scalar is added to the no-op logit, fitted by golden-section search on natural-DEV
    weighted Bernoulli NLL, and stored in the checkpoint (`gate_bias` buffer). It is frozen after BC.
23. **Value-loss importance correction.** The value loss weights each row by natural/sampled probability, which
    undoes the Hog 50/50 draw. In the v0 shakedown, DEV Hog value NLL reached 3.05 after one pass because a few
    hundred Hog games' outcomes were memorised.
24. **RoyaleSim producer** (`sim_rsim.py`). Per poll, RoyaleSim state becomes the reader PRIVATE frame in the acting
    seat's own frame (seat 1 rotated, matching `action_to_command`), then the same vendored FrameBuilder, then
    `Session`.
    - Entity card = the creating `card_id`; body = `unit_type`.
    - Enemy underground/invisible units are dropped.
    - FLIGHT carriers become `<Card>Spell` rows with their aim.
    - Nothing from the opponent's player record is read.
    - A rejected command is detected (channel free, card still in hand) and passed to `Session.rejected`.
25. **Game-balanced BC sampling (Sol R3 #3).** Each pass draws rows whose marginal balances **physical games**: every
    (match, seat) perspective gets equal mass within its group (Hog-cycle / general, 50/50), and its rows share that
    mass equally, so long games do not dominate. The duplicate-donor exposure cap is ≤ 5 expected draws per retained
    row per pass. If the Hog group is too small to take 50% under the cap, its share is lowered and the realised
    share is reported in `run.json` (`sampler`). The value-loss importance weights use this actual sampler.
26. **G1 admission** (`admit_bc.py`) runs on the full DEV split at natural frequency:
    - model vs frequency-baseline joint NLL, with a 10,000-draw PCG64 (seed 2026102020) physical-game cluster
      bootstrap, broad and Hog-cycle;
    - gate ECE, gate Brier vs baseline Brier, and plays ratio;
    - per-target-card DEV coverage, top-1 and tile-within-one.

    The hazard-inversion-across-intervals check needs varied cadence, and the re-drive store is single-cadence, so it
    is reported as not applicable. Per-epoch training logs use a capped DEV sample and are labelled as such.
27. **Eval (a) accounting (Sol R3 #2, #5).** No assigned case is dropped. A nonterminal game, a projection/contract
    failure (FrameBuilder error, FeatureError, shadow mismatch) or an error is a **failure**, never a draw. The
    report gives:
    - the complete-pair estimate;
    - conservative ITT bounds (candidate failures as losses / control failures as wins, and the reverse);
    - a 20,000-draw PCG64 case bootstrap stratified by opponent controller with equal fixed controller weights, at
      95% and 97.5%. It is DEV evidence only.

    A run manifest (checkpoint, bank, feature hash, code hashes) is frozen in the output directory, and retained rows
    from another checkpoint/bank/case abort the run. RoyaleSim carrier reader ids include the launch tick, so repeat
    casts at one aim (Fireball, then Mirror-Fireball) stay distinct.
28. **Probe roots (Sol R3 #6, #7)** report the distribution `Session` would sample: survival-scaled gate per logged
    poll gap, and stale (> 10 ticks) or all-masked polls declined. Carrier flight ages come from per-lifetime tracking
    of the projectile log: a lifetime ends when the id is absent or reused for another card/owner.
