# Level-aware search pilot: design (exploration)

2026-10-16, owner: level-aware search pilot for the BOT LEAD, resumed under Sol high. Scope: [SCOPE.md](SCOPE.md) (copy of 127x05
`/mpac/sdicks02/jobs/clasher/bot-levels/SCOPE.md`).
Log: [PROGRESS.md](PROGRESS.md). Results: [RESULTS.md](RESULTS.md). Code: `bot/levels/`.

**Status (2026-10-16 12:28 UTC): mandatory gates pass at reviewed R26 source:9 cold isolated regressions,216 integration tests,254 native checks,145 catalogue classifications/1024 binary commands, and8 clean complete-game all11 rows with4/4A-B hashes/positive B roots/zero rejections.** Exact original support bytes restored under review; all seven cache files unchanged through validation. Earlier failures remain preserved. BOT LEAD's explicit100-case serial A/B/B0 authority is active; fresh BASE/rule registration and bank creation are next. No primary bank or outcomes yet.


## Question

The live bot (LIVE-K4L-R-gs-rw-fc-w200-t4-p4) plans as if every card and tower were level 11. On the ladder our cards
are level 4–7 and the opponents' about 4–6, with level-6 towers. Does search with the true physics (our exact
levels, a fair estimate of the opponent's) win more, with everything else frozen?

## True game

RoyaleSim 0.1.34 with the 16.402 rules (`client='16.402'`), with per-card and per-tower levels passed to `reset`
(`bot/players/royalesim_match.py`, new optional `levels`/`tower_levels`; omitted = the unchanged level-11 call).
Checked on 127x01 (`rsim-probe-01.txt`): level-6 towers give king 3312 and princess 2030 HP, exactly what the live
client shows; Musketeer HP is 375/496/721 at levels 4/7/11.

**One fixed true-level profile per case** (`bot/levels/profile.py`), identical for every arm:

| | levels |
|---|---|
| our deck (live, Cannon version) | Valkyrie 5, Archers 7, Minions 5, Cannon 6, Fireball 5, Giant 6, MiniPekka 5, Musketeer 4; towers 6 |
| opponent cards | each card independently: a common level drawn from the battle-log prior at 750–840 trophies (shown levels: L4 4, L5 49, L6 25), minus one for rares/epics/legendaries, never below the rarity floor (3/6/9) |
| opponent towers | 6 (princess HP at match start was level 6 in 48/49 live battles s18–s27) |

The rare offset is a scenario assumption (rares are never shown in the battle log; our own rares are one level below
our commons). The opponent levels are a population scenario, never per-match hidden state given to a planner.

**Opponent decks:** the battle-log decks at ≥600 trophies, each projected onto the C56 belief catalog by maximum card
overlap (the frozen K4L belief only holds catalog decks; the deck search did the same). Opponent controllers: R3a and
v1 (pinned), alternating by case pair; our seat alternates by case. Non-C56 cards (Tombstone, BattleRam,
GoblinCage, ...) are therefore replaced by catalog decks: a limitation.

**Fixed supported-card belief scope (accepted before bank/outcomes):** all experimental arms share the same
ordered catalog with decks containing Clone, Earthquake or Tornado removed. This retains 2,500/2,925 decks and
54,009/69,380 frequency weight; omitted mass is 15,371/69,380 = 22.15479965%. None of the 54 selected true-deck
projections changes. `scope.install(rt)` preserves an immutable original catalog for projection/rollback, applies
the restriction before any player starts, rejects external belief-prior overrides, and records both digests. The primary bank explicitly reads the frozen population receipt
`receipts/opponent-decks-snapshot.jsonl` (SHA256 b00ae7df0caa96358cbe0b6fdd9ed0dfb0becd7b270e80de96cca40c2cfd7440),
matching the original DEV input; later live-log changes cannot alter its population.
The original catalog still determines true-deck projection, with equality to the restricted projection asserted
for every eligible row. This is a **conditional-population physics pilot**, not literal current-live-prior
equivalence or evidence for immediate live promotion. Standard A outside this pilot is unchanged. No
outcome-dependent exclusions or silent level-11 fallback are allowed.

## Arms (same K4L player object, frozen weights/features and common candidate eligibility)

Base player: `K4L-R-gs-rw-fc`, the deterministic twin of the live variant (same decisions whenever the live search
completes). One process per game (fork after the runtime is built).

- **A:** standard K4L with the common experimental prior restriction. Roots, rollouts and native metadata all level 11.
- **B0 (diagnostic, root-only):** the existing `bot/live/levels.py` LevelRoot installed on the actual K4L search
  object (`root_fn`, a new one-line hook in `bot/search/players.py`; the live installer currently loses it because
  `make_live_lopp` replaces the search object). Scales root bodies by the card ladder and towers by the card ladder
  (known wrong for towers); cards played in rollouts spawn at level 11. A null here does not reject level-aware search. Own bodies use the producing-card level map
  (unmatched own bodies default11); every opponent body uses fixed5 without B's rarity adjustment. Tower inputs
  are6 but the legacy scaler applies the card ladder, not the exact crown curve; native metadata remains11.
- **B (level-aware):** `bot/levels/root.py` + `configs.py`:
  1. root bodies: the exact level-L fields (export of the producing card at L vs at 11; no rescaling of truncated
     values), hp = observed fraction × level max HP; projectiles in flight take the level's damage; spell carriers name
     the level's spell;
  2. towers: the tower curve (7%/8%, 10% after level 9, integer-truncated; = `tower_scaling.py` below level 10),
     level 6 = 3312/2030 HP and 72 damage per princess hit (not the card ladder);
  3. rollouts: a per-seat level config. The native already looks every secondary payload (death/production children,
     spawn/death areas, chains, ability bombs) up by `stats.payload_key` = `level<L>:<name>` and spells by the
     carrier's `spell_name` (Mirror's level-12 mechanism), so `cards[c].units[seat]` ← the level-L formation and the
     level-L card and side tables under qualified keys reproduce the level-L game **without a Rust rebuild**;
     fc cuts keep the qualified keys (`CutConfig`: config_need + mirror_need + SideCut + qualified-reference closure);
  4. leaf: NativeScripts with the crown-tower maxima of the tower level (leaf.rs normalises tower HP by
     `meta.bodies[Tower/KingTower].hp`; at level 6 a full tower would otherwise read 0.665).
  - **Metadata audit (source only):** changing the two crown maxima also changes scripted spell lethal checks and
    Lightning target ordering, not only leaf normalization. Identical-state learned features remain unchanged.
    Pool workers currently start before the substitution and retain old metadata; fork/spawn recovery can diverge.
    This joint leaf/controller-state adjustment is part of the accepted serial B semantics; see
    [bounded diagnostic](receipts/leaf-diagnostic-astra-r1.md). The serial pilot makes no pooled LIVE claim.
  - **Planner knowledge (fair):** our levels; our tower level; the opponent's tower level (shown at match start);
    the opponent's card levels = fixed prior median (common 5, rare 4, epic 6, legendary 9). Never true per-match
    opponent levels, hidden deck/order or future observations.
  - **Not changed:** R3a proposer, it5s2/learned-opponent weights and their level-11 static columns; NativeScripts
    scripted-opponent metadata other than the two tower maxima; direct-cast spells (no carrier units) are one level for
    both seats; Mirror stays at 12.

## Gates (before any pilot game)

1. All-11 parity: B forced through its own path (no bypass) with every level 11 ≡ A, command hashes equal.
2. Same card, different sides: a level-4 and a level-7 Musketeer deployed by the two seats in one rollout config have
   the exported HP/damage; native snapshot equals the Python engine's deployment.
3. Spell impact damage: Fireball cast by each seat at different levels hits for the level's damage (and crown damage
   on a tower).
4. Tower stats: curve = tower_scaling.tower_stat at 10–12, = RoyaleSim 16.402 HP at 4–8.
5. Snapshot / fc-cut / pool-cache preservation: every rollout value on cut roots and snapshot-rebuilt roots equals the
   uncut root (lopp_fast_check-style).
6. Fair information: B's decisions are invariant to the opponent's TRUE card levels (two profiles differing only in
   opponent true levels give identical B roots/config at the same public state).

## Pilot and decision rule (pre-registered in PROGRESS.md before any game)

100 cases (pairs) on a fresh bank: BASE = `int.from_bytes(os.urandom(6),'big') << 4`, drawn and recorded with this rule
before any game. Arms A, B (primary) and B0 (diagnostic) on every case. Score: win 1, draw 0.5, loss 0.

- Primary: paired Δ = B − A, 95% bootstrap CI over cases.
- **Promising** iff Δ ≥ +0.03. Then size a confirmation (fresh bank, preregistered) from the pilot's paired SD for 80%
  power at Δ = 0.05 (two-sided α = 0.05), within 650–1,300 pairs, and check the live 200 ms variant's default
  share and latency before proposing a bundle.
- Δ < +0.03: report; no confirmation run on this design without a new reason. B0 is reported, never decides.
- Secondary: tower damage dealt/taken, crowns, decision-change share, CPU per decision.

## Reversible execution decision and rollback

The serial experiment uses no learned process pool; its one process per game receives the B native object
consistently for coarse and learned rollouts. The separate raw-fc transport gate explicitly constructs a worker
with matching metadata and tests only that transport contract. Existing pooled LIVE startup/recovery behavior
is outside this pilot and cannot be inferred from it. No frozen runtime, pin, checkpoint or model file is modified.

Rollback: stop only a verified owned process group, preserve its outputs, and select standard A outside the
experimental factory, or remove the experimental root/native/prior hooks. Original catalogs and all failed
receipts remain available. Resume must reject changes in code, runtime, models, prior, environment or cache.

## Common simulator eligibility amendment (before primary bank)

The first all11 DEV run matched4/4 A/B full command hashes but failed acceptance on shared Cannon territory/water rejections. The installed RoyaleSim ordinary-building own-half rule differs from the existing planning mask's troop pocket/bridge expansion. The rule is labelled low confidence for the real client; this amendment matches the shipped experimental simulator and establishes no LIVE placement law.

All experimental A/B/B0 actors and both opponent controllers receive the same per-instance public mask intersection, version **rsim-static-water-intersection-v3**:

- Ordinary buildings retain existing own-frame rows0–14 and lose rows15–31. Legal boundary taps may relocate their3×3 box inward in RoyaleSim; no footprint erosion or command movement is added.
- Troops, including air/champions, tunnels, rolling/spawn spells intersect the existing mask with static not-WATER geometry from pinned public arena/card metadata. A tile centre touching any surrounding half-cell WATER is removed. Unrestricted spells retain their full base mask; tunnels retain enemy-side land.
- Spell deployment precedence uses both SpellAsDeploy and enemy-side permission. Uniform static variant forms resolve recursively; missing/mixed/cyclic identities fail closed. Public own accepted history resolves Mirror. No Battle, state/check_deploy legality oracle or hidden opponent input enters a player.
- Actual scripted/candidate/random/ranked/proposal and policy/fallback mask instances are wrapped and checked. No tile is enabled, tap moved/refunded, or deployment converted into an unlogged wait. WAIT, affordability, occupancy and base territory remain. Unknown identities fail closed.

Weights, learned feature definitions and static columns remain fixed. Native rollout geometry stays unchanged and remains a model mismatch. Standard factories outside this experiment are unchanged. This explicitly amends shared command eligibility before the fresh primary bank; it is part of the conditional simulator experiment, not a LIVE bundle proposal.

The reviewed v3 binary probe passed145/145 catalogue classifications and all1024 commands:64 Cannon fixtures and960 river/card/seat/public-tower fixtures, including the original18 nonbuilding observations. All16 Cannon boundary controls actually settled at own y13.5 with a fitting3×3 box. The complete matrix independently expects380 accepted commands,512 WATER refusals and132 territory refusals. [Raw receipt](receipts/placement-micro-r21.json), [owner audit](receipts/placement-micro-r21-owner-audit.json). Native flying flags are recorded, not asserted equal to root metadata.

The earlier failed v2 probe is preserved: it stopped before taps on two metadata classifications, repaired generically through spell precedence and uniform variant resolution; it contributes no physics result. The new raw token-data and serving-source provenance repair passed source review. Full controller/hidden-information integration, native transport gates and the same complete four-case all11 bank at final bytes remain mandatory before primary registration. Zero rejection/failure and completeness gates are unchanged. Rollback removes the experimental wrappers/selects standard A, with original catalogues and all failed receipts retained.
