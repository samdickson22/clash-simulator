# Batch C1: attack, targeting and dash fixes (12 cards + 4 native≠Python bugs) — results

Exploration tier. Spec: `reports/cards/specs/C1-SPECS.md` (Sol researcher), checked against the code before each
change; where the spec and the code or RoyaleSim disagreed, the deviation is listed per card. Ours = engine-cards
Python engine plus its native mirror; reference = RoyaleSim (MIT) 16.402 through the fidelity harness (`--table
160402`, harness copy `batchA/tools/scenarios.py`). Branch `cards/c1` (from b16716481). Host evidence: 127x08
`/mpac/sdicks02/jobs/clasher/cards/c1/` (fidelity, builds, negative control) and 127x04 (native verification, gate).

Value rule: native mechanics are authoritative; RoyaleSim 16.402 is authoritative on stats. **Pure stat-value
corrections are not in git** (§3, for the live16402 overlay; fidelity "with stats" runs use a scratch gamedata on
08 built by `batchA/tools/apply_stats.py`). Omitted metadata that the compact export drops (no value in our data at
all, or a mechanic switch) is restored declaratively in `balance.py`, as Batch A did.

Shared Troop follow-up is active under the ordered B2→C1 contract: see
[triage and witness ledger](SHARED-TROOP.md). Zap's forced-state mismatch is
established; heading coincidence, exact Spirit mode history and ordinary gameplay
reachability still need B2's reviewed captures. No new fix/parity/acceptance claim.
Read-only capture preparation independently **APPROVED** at32eb85cd1
([scoped review](shared-troop/REVIEW-preparation-r3.md)); this supplies no engine,
host-execution or actual-witness approval.

Exact B2 captures are now verified:36 legacy root hashes plus retained normal
fixture evidence; [captured diagnosis](shared-troop/CAPTURE-DIAGNOSIS.md) distinguishes
forced Zap/heading reproduction from ordinary gameplay claims and records the
normal-fixture IceSpirit mode transition. A scoped native candidate is written,
with32-case prospective clone/reload/continuation coverage. **After-fix native
verification is pending:** no build or simulation ran; frozen B2-first source,
independent source/probe review and actual parity/C56 gates remain required.

Launcher repair is complete: fresh independent r5 **APPROVE** at tools commit
`97171f531a31f9663f74ff95093d58053125860d` ([full review](reviews/FINAL-TOOLS-r5.md),
[exact receipt/rollback](reviews/REPAIR-RECEIPT.json)). All six launcher findings plus expiry wording and later
startup/interruption findings are repaired.19 submitted +13 independent local groups PASS. Engine/native,
approved comparator and followup are unchanged; no host launcher/build/gate ran. B2→C1 integration,
exact-source affected checks, owner-authenticated inventories, duplicate audit and fresh C56 remain required.

## Verdicts (3 scenarios per card: alone / knight / minions)

| Card | Before | Mechanics | Mechanics + stats overlay | Remaining |
|---|---|---|---|---|
| Bowler | 2/3 | **3/3** | **3/3** | — |
| Assassin (Bandit) | 1/3 | **3/3** | **3/3** | — |
| ZapMachine (Sparky) | 1/3 | **3/3** | **3/3** | — |
| ElectroWizard | 1/3 | 2/3 | 2/3 | knight: C56 Knight's hit cycle under the stun-on-hit (§4) |
| IceWizard | 1/3 | **3/3** | **3/3** | — |
| InfernoDragon | 2/3 | **3/3** | **3/3** | — |
| MegaKnight | 0/3 | **3/3** | **3/3** | — |
| Fisherman | 2/3 | **3/3** | **3/3** | — |
| AxeMan (Executioner) | 0/3 | **3/3** | **3/3** | — |
| ElectroDragon | 2/3 | **3/3** | **3/3** | — |
| BossBandit | 0/3 | **3/3** | **3/3** | — |
| Ronin | 0/3 | 0/3 | **3/3** | needs the §3 overlay rows (hit/load) |

**C1 scenarios PASS: 12/36 before → 32/36 mechanics → 35/36 with the overlay.** Rest of the 66-card pool (54 cards,
162 scenarios), same runs: **no verdict and no difference-count change** (pool total 54 → 74 → 77 of 196). Runs: 08
`c1/fid/final-{base,mech,stats}.jsonl` (base = engine-cards at b16716481 on native de11f124).

## 1. Causes and fixes, per card (Python reference + native mirror; all in `engine-cards/`)

Ported logic carries `Ported from RoyaleSim (MIT), <file>` comments. New serialized native fields are
`serde(default)` and `skip_serializing_if` at their inert default; the new exporter keys are emitted only when set.

| Card | Cause (vs RoyaleSim) | Fix (Python / native) |
|---|---|---|
| **Bowler** | The boulder's finite range started at the muzzle (endpoint 1000 too far), took a terminal 1800 area sample, and flew on its creation tick; spurious tower hits 74..374. | Straight shot: endpoint = body centre + trunc(v·range/n); creation-tick test at the muzzle, no step; then `advance_client` steps of 170 (trunc0, nothing carried), expiring on the reaching step without a test; circle contact ProjectileRadius + victim radius, once per victim; radial push from the sample (no combat interrupt). `entities.py:RollingProjectile._update_straight/_deal_straight_damage`, `_create_projectile`; native `projectiles.rs:rolling_character_tick/_hits`, `lib.rs` shot creation. Bowler is the only character with a rolling shot; Log/BarbLog (rolling spells) untouched. |
| **Assassin, BossBandit** | Charge started from the previous tick's target and counted a full 800 ms from the next frame; one 500 step a tick to an exact endpoint, hit only on arrival; tail 100 ms (Boss: no dash metadata). Assassin died at 81 before travel. | `cards/bandit.py` rewritten as RoyaleSim's movement-phase dash: first sight of the current target (blocked for that sight inside DashMinRange+both radii), stand DashCooldown/50−1 = 15 ticks (combat runs normally; a stand ends on target change/death or an attack starting), still entry, goal = 500-cell centre `dash_goal_native`, two JumpSpeed/2 half-steps a tick (`dash_half_step`), range test Range+both radii after each against the target's current point, blow, ground repair (`recover_native_ground_position`), tail 150 ms. Python's non-interrupting Freeze contract is kept: a stand neither counts down nor cancels while stunned. `balance.py`: Assassin tail 150, BossBandit dashCooldown 800 + tail 150 (omitted). Native `dash.rs` (new State: phase/wait/target/blocked/goal), `dash_snapshot.py`. |
| **ZapMachine** | LoadFirstHit and AttackPushBack omitted (and the ZapMachine body had no mechanics: the `Sparky` registry entry is dead). First shot 42 instead of 101; period 80 not 79. | Restored `loadFirstHit`, `attackPushback 750`, `projectileStartRadius 1200`, `ignorePushback` (omitted). The ordinary progress clock now covers LoadFirstHit: load leaves the deploy at LoadTime (`first_hit_time` = HitSpeed), a leave/target loss before the fire refunds load = max(LoadTime − progress, 0) and installs no finish work (`attack_clock.py refund_on_leave`, LOAD_FIRST_HIT_LEAVE), and an armed launch recoil releases the swing (progress 0) (`firecracker.py AttackRecoil`, RoyaleSim `attack_recoil`). Native `clock.rs` (`refund`), `projectiles.rs:recoil`, exporter clock seed. Firecracker (C56) keeps its recoil and clock. |
| **ElectroWizard, IceWizard** | The spellAsDeploy area (ElectroWizardZap 192 + 500 ms stun / IceWizardCold 84 + slow) was cast at deploy end on everything then in range; RoyaleSim casts it on the character's creation tick and adds one tick to its deploy. | `gamedata_normalization.py` marks the card area `spawnAreaAtCreation`; `SpawnAreaEffect.cast_at_creation` runs from `battle.deploy_card` (hand plays and Mirror; never Clone copies or direct spawns), deploy +50 ms, no ready-time recast. Native: no code change; the card template now carries the area as a second unit (`differential.py`, AreaEffect takes the character's deploy snap). |
| **InfernoDragon** | LoadTime 1200 > HitSpeed 400 was reduced to an 800 ms retarget delay; every retarget fired 10 ticks early. | RoyaleSim progress cycle for this body only (`overloadedProgressClock` in `balance.py`): a load timer runs 50 a combat update (finish hold included), each beam sets it to LoadTime, and a fresh cycle on a new target stands until load ≤ HitSpeed, then starts from progress 0; the stand is not ramp lock time. `entities.py:_update_active_combat` / native `combat_one` (`overload_clock`, `ovl_load`, `ovl_target`). Inferno Tower / Mighty Miner (C56) keep the legacy clock. |
| **MegaKnight** | A 300 ms landing hold after the blow (RoyaleSim ends the dash 4 ticks after it), plus the same prior-tick charge and interpolated flight as the Bandit. | `cards/mega_knight.py` rewritten as RoyaleSim's timed dash: first-sight stand 17 ticks, entry moves, JumpSpeed (250) a tick to the 500-cell goal holding where the arrival step ends, blow at entry+16 (motion stops, ground repaired), end at blow+4 (`DASH_BLOW_TO_END_TICKS`; raw dashLandingTime 300 kept as `landing_raw_ms`). Native `leap.rs`, `leap_snapshot.py`. |
| **Fisherman** | The idle hook scanned every far enemy; after the self-drag to the princess he hooked the king and never swung. | The hook considers only the current target (RoyaleSim `special_step`). `cards/fisherman.py:_find_hook_target`, native `hook.rs:hook_candidate`. |
| **AxeMan** | The axe was a one-way piercing shot; the thrower kept firing every 18 ticks and walking. | `PingpongProjectile` (`entities.py`): 30-update sine out-and-back from the body centre to ProjectileRange (integer `sin_pi_frac`, RoyaleSim `fixed.rs`), each update testing the previous point, hit set cleared once on the turn; the thrower holds (live target kept, no new target, progress stands, load runs, no walking) until the axe is removed at T+31, so throws are 49 ticks apart. `balance.py`: AxeMan projectileStartRadius 600, AxeManProjectile projectileRadius 1000 (omitted). Native `projectiles.rs:pingpong_tick`, `lib.rs` (throw, `pingpong_waiting` in combat and movement). |
| **ElectroDragon** | The chain hopped with no wait, several hops per update. | Dragon-only chain mode: the next target is taken at release by (centre distance², creation order); each hop waits 3 updates (`CHAIN_HOP_WAIT_TICKS`), then flies at 2000 a tick, one hop per update; a hop whose target died lands on its last aim, counts, and releases on. `entities.py:ChainLightning._release/_update_waited`, `cards/electro_dragon.py`; native `c56.rs:chain_release/chain_waited_tick`. Electro Spirit's chain unchanged. |
| **Ronin** | No counter (the compact export keeps only the action names); hit/load are stat rows. | `cards/ronin.py:RoninCounter` from restored metadata (cooldown 3500, scalar 200 %, stop 500 ms, reflect after 300 ms): a ready Ronin countering a normal direct hit by a ground troop without an attack projectile takes 0, restarts its attack progress, slows the attacker (movement 0, hit speed 5 %, spawn 0) and reflects 2× the hit 6 ticks later. Interception at `entities.py:_resolve_attack_damage` (primary target), delivery at the Ronin's combat component; native `attacks.rs:try_counter`, `lib.rs` melee loop and `combat_one`. Flyers, buildings, projectiles, spells and dash blows are not countered. |

Spec deviations (decided, documented): Bowler's boulder tests its muzzle on the creation tick (RoyaleSim `fire`
creation test) instead of the spec's "no hit" creation tick. The Bandit stand is a countdown paused while stunned
(Python's Freeze contract) rather than an absolute mark. Fisherman takes only the current-target fix; the spec's
450/510 drag speeds, margin release and primed hit were not needed for any scenario and are left as listed
residuals. Ronin counters only the primary target of a direct hit (splash/secondary bolts on a Ronin are not
countered) and the attacker buff lands at once, not next tick.

## 2. Native≠Python bugs (Python is the oracle)

| Bug | Fix (native only; Python unchanged) | Replay (native-diff plan, full length) |
|---|---|---|
| §13 BossBandit × MightyMiner/Monk: movement spent toward a target that entered dash travel | `lib.rs:movement_one` committed-target check adds the combat helper's channel predicate (ramp owner and target in dash travel) | games 22, 245, 274, 323: **match** (base arm: first mismatch 1909, 2027, 749, 844) |
| §14 ElectroDragon chain hook for an invalid primary | the source-hit hook runs only for a primary in this impact's recipient set (alive, enemy, not kind 2/3, plane or ground jumper), taken before the damage; the whole-phase `projectile_alive` set is gone | games 16, 86, 336, 460: **match** (base: 696, 745, 3139, 3160) |
| §15 MegaKnight long-distance splash discard | exported `discard_exempt` = Python `should_cancel_committed_hit` exemptions (dashCooldown > 0, or direct area damage while the global is off) | games 189, 415: **match** (base: 171, 709) |
| §16 IceSpirit × BossBandit non-interrupting freeze | `c56.rs:stun_target_mode` cancels a dash stand only when `interrupt` | game 548 **match**; it no longer diverges on the base arm either (the Batch A Python changes its action history), so the focused cases `bandit_freeze_stand`, `bandit_icespirit_{50,56}`, `bandit_zap_stand` carry the check (§4) |

All eleven games were replayed with C1 Python + native `2ac024c7` (04 `c1/verify/nd.json`) and, as control, base
Python + native de11f124 (08 `c1/nd/base.json`).

## 3. Stat-value corrections for the `live16402` overlay (not applied in engine-cards)

| Card | Body (nested object) | Field | Ours (gamedata, base) | RoyaleSim 16.402 | Effect |
|---|---|---|---|---|---|
| Bowler | BowlerProjectile | projectileRange | 7500 | 7000 | not needed for PASS (mechanics alone pass 3/3) |
| AxeMan | AxeManProjectile | projectileRange | 7500 | 7000 | not needed for PASS |
| Ronin | Ronin | hitSpeed | 1400 | 1300 | period 28 → 26 ticks; required for 3/3 |
| Ronin | Ronin | loadTime | 1100 | 900 | first hit +2 ticks; required for 3/3 |

The scratch overlay on 08 (`c1/stats/gamedata.json`) applies exactly these four rows.

Omitted metadata restored in `balance.py` (not stat rebalances: absent from the compact export, or a mechanic
switch): Assassin `dashImmuneToDamageTime` 100 → 150; BossBandit `dashCooldown` 800, `dashImmuneToDamageTime` 150;
ZapMachine `loadFirstHit`, `attackPushback` 750, `projectileStartRadius` 1200, `ignorePushback`; AxeMan
`projectileStartRadius` 600; AxeManProjectile `projectileRadius` 1000; InfernoDragon `overloadedProgressClock`;
Ronin counter metadata. MegaKnight's recovery is a mechanic constant (4 ticks), its raw 300 is kept.

## 4. Native == Python

Native `2ac024c79f473d8ac3e29b83f494401f1021dcca148c8c66dbe9f8ae7bae83cd` (built on 127x04 from this tree; evidence
04 `c1/verify/`; the first round on 6741bb91 is in `c1/verify-r1/`).

| Check | Result |
|---|---|
| `batchA/tools/probe_native_scen.py`, the 36 C1 fidelity scenarios, digest every tick | **36/36** equal (no overlay) and **36/36** (with overlay) |
| Focused C1 cases (`c1/tools/probe_c1_cases.py`, 36 scripts × both seats; 12 scripts fixed after both engines rejected a deploy): Freeze/Zap/IceSpirit/Log during a Bandit stand, Zap during travel, Fisherman hook vs Bandit and MegaKnight, target death mid-dash, dash ending over water, Bandit vs Inferno Tower / Mighty Miner, MegaKnight vs Zap/Giant, Bowler vs Barbarians and off-axis, Sparky zapped / target killed pre-fire, Inferno Dragon vs Skeleton Army and Zap, Electro Dragon vs Skeleton Army / Goblins, Electro/Ice Wizard close at birth, Clone, Mirror, Fisherman vs Giant and two targets, axe vs Skeleton Army and owner killed mid-throw, Ronin vs Barbarians / Minions / Prince / Electro Wizard | **72/72** equal (count corrected by raw receipt audit) |
| Batch A first-update path audit (`probe_first_update_paths.py`, 21 paths × 2 seats) | **42/42** equal |
| Batch A review cases (frozen Tombstone death, Witch corner, both seats) | **4/4** |
| native-diff named games (§2) | **11/11** full-length match |
| Mixed-deck sample: 96 native-diff plan games with ≥ 2 C1 cards (not the named 11), full length (`c1/tools/nd_sample.sh`) | **82 match**; 14 first divergences, all known causes: IceGolemite alias harness artefact 10, Poison × Bandit dash (75, B2 scope), Mirror × Skeleton Barrel level (133), C56 X-Bow load clock in a mixed context (173: the X-Bow fires a tick early, load 300 vs 50 — the known native-diff X-Bow cause, reached here because the C1 game trajectory changed; the base arm never gets there), game 72 (diverges identically on the base arm at its game-over tick). Round 1 found one C1 bug (game 4, below), fixed. |
| Negative control: C1 Python with the unpatched native de11f124 | diverges on Bowler (147/29/147), ZapMachine (209/177), InfernoDragon minions (72), Fisherman alone (121); Assassin/BossBandit/MegaKnight state no longer loads; ElectroWizard/IceWizard equal (that fix is config-only) |

Bug found by the mixed sample (round 1, native 6741bb91, game 4 at tick 676): Python's area-damage eligibility
(`can_receive_area_damage`) skips a unit in Bandit dash travel or stealth **without marking it hit**; the native
boulder and axe filters lacked both terms, so a boulder that crossed a dashing Boss Bandit could never hit it after
it landed. Both native filters now skip such units (`projectiles.rs:rolling_character_hits`, `pingpong_tick`). Older
piercing shots (C56) keep their filter unchanged.

The digest does not cover every private timer; the new private states (stand/travel, overload load, axe t,
chain wait, counter queue, clock refund) are exported in snapshots, but no mid-flight snapshot-continuation probe
was run for them.

## 5. Residuals and not implemented

- **ElectroWizard × Knight** (6 differences): the C56 Knight's swing cycle under the Wizard's 500 ms stun-on-hit is
  34 ticks here, 33 in RoyaleSim (Knight hits on the Wizard 54/88/122/156 vs 53/86/119/152). C56 clock; blocked by
  C56 parity.
- Spec items left out (no scenario needs them; candidates for a follow-up): Fisherman drag speeds 450/510, margin
  release and primed first hit; Bandit route clear at entry; Ronin counters on splash/secondary hits and next-tick
  buff installation; Sparky "target unlocked" after recoil; MegaKnight non-collidable after the blow; the Electro
  Dragon dead-hop visibility rules beyond `_can_chain_to`; ElectroWizard spawn crown-tower damage (UNCERTAIN row).
- No Mirror-level/evolution/hero forms were touched.

## 6. C56 parity

C56 config export (`differential.config`, all 56 cards, `batchA/tools/cfg_dump.py`): base and C1 **byte-identical**
(sha256 `e52e8a960aed71f69624ccdb297cd890dcdd8b60506ea662a48d3353fac6d9db` both).

**Run 1 PASS — native 2ac024c7, engine source commit e0ade18d3 on `cards/c1` (handoff bc8eba7c2).**
The Batch A gate copy (`c1/tools/gate.sh`, using `gate-tools/parity_fixtures.py`, `parity_roots.py`, `compare.py`)
ran on 127x04 on 2026-10-16, 08:04:25Z–08:45:16Z. Fixtures finished at 08:44:10Z, then roots at 08:45:16Z.
The inherited `cpu_job.sh 8 bash /mpac/sdicks02/jobs/clasher/cards/c1/tools/gate.sh`, PID = PGID 2082511,
completed normally. The shepherd waited with `while kill -0 2082511`, polling every three minutes; no relaunch.

Pinned = runtime r1 Python + native-total-r1 `681b5f2c`; patched = C1 Python in the r1 mirror + native `2ac024c7`,
without the stat overlay. Evidence: `127x04:/mpac/sdicks02/jobs/clasher/cards/c1/gate/compare.json`, all fixture/root
JSONLs in that directory, and `c1/gate.log`.

| Run | Patched native | Fixtures byte-identical | Rust-only chains equal | Full roots identical | Cut roots identical | Verdict |
|---|---|---|---|---|---|---|
| 1 | `2ac024c7` | **577/577** | **577/577** | **300/300** | **300/300** | **PASS** |

Independent audit confirmed exact fixture-file bytes, Rust-only trajectory records, and exact root shard bodies
(excluding native metadata headers); no missing or duplicate fixture/root IDs, the same 300 IDs in both variants,
and agreement with `compare.json`. All eight root headers and both binaries identify the expected native hashes.

| Coverage | Result |
|---|---|
| Fixture records | 577 pinned, 577 patched; no differing IDs |
| Rust-only chains | 577 equal; 1,010,680 ticks; zero errors in either arm |
| Python↔Rust full-length parity | 429/577 in each arm, unchanged; this gate measures regression parity |
| Root records | 600/600 equal (300 full + 300 cut); no differing IDs |
| Root sample | 300 of 1,043 roots, 12 games, ticks 140–5,570 |
| Root operations | 9,336 rollout_e1 values, 1,800 select_action calls, 478 apply_discrete, 1,800 step checks; all equal |

SHA256 receipts:

- Pinned native: `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`.
- Patched native: `2ac024c79f473d8ac3e29b83f494401f1021dcca148c8c66dbe9f8ae7bae83cd`.
- Fixture files (both): `f5a2665b2e7a14e4bf5cb2691a63ddc5cb7df150efd7f3b4ca7fd42fb5b5c670`.
- Combined root shard bodies (both, headers excluded): `a710536268e111f1c200dea5c916302a258199dc3859e817e35236fb6094ea92`.
- `gate/compare.json`: `0b0237acf79f51b49f36c68f789e107fbfa79229c894ef8dc2ad9b2d331315d0`.

No differences: no diagnostic bisect, fix spec, or owner wake-up needed. Measurement only; no engine edits or sealing.

## 7. Coordination: dash-travel target exclusion (owned by B2)

Per the lead (2026-10-16), target-selection dash-travel guards belong to the B2 audit. C1 keeps only the
dashing unit's own movement/target revalidation (§2 §13) and the non-interrupting Freeze (§2 §16). C1 contains
exactly **two** target-exclusion guards, both in hit filters that exist only in C1 form, both required for
native==Python parity (mixed game 4) and both in the gated build 2ac024c7. They are listed here for routing; C1
adds no other guard and does not touch the older C56 `piercing_hits`, the spell `rolling_tick`, scope, Lightning
or grouped-spell selectors.

| Native function (`engine-cards/src/projectiles.rs`) | C1 status | Guard added | Python rule mirrored |
|---|---|---|---|
| `rolling_character_hits` (Bowler boulder; body rewritten by C1, used by no C56 card) | rewritten | skip `dash_travel()` and stealthed (`stealth_until > now && !area_while_invisible`) units without adding them to `hit_ids` | `RollingProjectile._deal_straight_damage` → `can_receive_area_damage` |
| `pingpong_tick` (Executioner axe; new in C1) | new | same two terms | `PingpongProjectile.update` → `can_receive_area_damage` |

Merge note for B2: `probe_dash_paths.py` launches the dash through the old `BanditDash._launch_dash` with no
seen target. Under C1's dash the travel target is `_bandit_seen_target` (native `dash.target`); a forced launch
must set it (and `_bandit_goal` comes from `_launch_dash`), otherwise the forced dash ends on its next movement
update. The older C56 `piercing_hits` has neither guard, while Python's piercing path does go through
`can_receive_area_damage`: a candidate for B2's "piercing remembered hits" row.

## 8. Review r1 corrections (focused independent r2 APPROVE)

Review r1 rejected `e0ade18d3` for the boulder snapshot endpoint and Ronin finish reset, and requested
death-surviving reflected damage. The following candidate is separate from the historical §6 gate artifacts.
Native build: **631ac18d27cb15d4eba7011113a9f69a4b85740ef68a27a87cabb0d68320ad86**, 04 `c1/out-r2/`.

- Boulder: `live_snapshot.py` now exports `straight_endpoint` into `aim`. Mid-flight Python snapshot import
  therefore retains the fixed flight goal. The existing Bandit WIP also aligns the still entry frame's
  `consumed` flag with native; its travel state owns that movement frame.
- Ronin: countering resets only the ordinary clock timeline. Python and native both retain load, target,
  and finish recovery; the generic movement stop helper is no longer used for a counter.
- Ronin death: living defenders retain their existing combat-slot delivery. Work on a dead defender is moved
  to battle `orphan_counter_pending` before eligibility (if already dead) or at cleanup; an eligible defender
  killed earlier in the combat phase still delivers its due work in its slot. The battle queue is exported
  only when nonempty, `serde(default, skip_serializing_if = "Vec::is_empty")`, cloned independently, and serviced
  at the combat boundary. Events retain their absolute due tick, attacker ID, and amount; missing/dead attackers
  are dropped, and reflection uses damage directly without re-entering the counter hook. Idle fast-forward
  cannot skip pending work. This is a narrow persistence fix, not a generalized scheduler change.

`c1/tools/probe_review_r2.py` **PASS: 21 distinct focused cases** (19 in `review2.json` + 3 extra executions,
including one repeated idle/clone case, in `extras.json`), 04 `c1/verify-r2/`. Four finish-recovery cases cover
both seats and both creation orders; fourteen reflect cases cover live/dead defender, dead attacker, both dead,
multiple events, dead at eligibility, and killed earlier in the same combat phase; two boulder cases resume
mid-flight; one idle/clone case proves empty queue omission, fast-forward refusal, and clone independence.
Each applicable case compares the selected semantic fields from full snapshots (explicit baseline exclusions
in `probe_snapshots.py`), digest, clocks, and both pending queues after every tick. Python-export continuation
and native serialize/reload continuation match, including after defender cleanup. Missing-endpoint,
missing-finish, and missing-queue controls all detect the deliberately dropped state.

The same finish probe against old native `2ac024c7` **fails at tick 22 as intended**: target/windup differ,
Python finish=51/timeline=0/load remaining=350 versus old native finish=0/timeline=800/load remaining=1100.
Evidence `negative-old-native.log`. An initial synthetic deploy fixture retained stale native movement telemetry;
clearing that setup flag fixed the probe, with failed attempt retained as `review.log` (no engine workaround).

Existing 08 launcher PID/PGID **1042473** is preserved and still running its original pre-Ronin-fix source/native
`2ac024c7`; completed first Bowler/Assassin cases are equal. That long run is evidence for the boulder/Bandit WIP,
not verification of the new Ronin native. No completion receipt yet. Its code/binary were not replaced.

The final internal queue is excluded from the Python constructor (`init=False`); the affected idle/clone and
combat-death controls were repeated in `extras-final.json`, **3/3 PASS**, native unchanged.

Fresh independent r2 review **APPROVE** is recorded below; B2→C1 integration coverage and the final exact-native
C56 gate remain prerequisites to overall acceptance. No new full C56 gate or pin/runtime/model change has occurred.
Sam's updated direction retires the blanket Opus/design/
promotion hold: confident reversible work can proceed within ownership when its gates pass. Broader counter
selection/buff-phase work remains outside this focused correction, not blocked merely waiting for Opus.
Rollback: revert the focused candidate commit to recover `2e8005054`'s engine and use native `2ac024c7`;
existing gated artifacts are preserved and no live pin/runtime needs restoration.

## 9. Independent r2 approval and final preparation

Independent Sol-high review **APPROVE**, focused code `f68e5f80f` / native `631ac18d`, documentation through
`933178477`. Full verdict: `/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/C1-r2.md`, SHA256
`5e609d02ec033f86959af8278c470f053eaaf4a7b69fd96834f6fc9891d39a2a`.
No actionable new C1 finding. Reviewer extra checks passed recovery/cold-deploy, staggered/lethal/orphan
reflection, clone/reload, real Knight countering and boulder continuation through expiry. This is focused
continuation approval, **not complete snapshot byte equivalence**. Existing secondary/chain selector findings
in `src/attacks.rs:22`, `src/c56.rs:309` and Log/Bandit remembered hits remain B2-owned.

09:28:36Z inherited jobs: 08 PID/PGID **1042473**, 04 PID/PGID **4131290** and child **4132214** all active;
neither `verify/snap.done` exists. Artifacts/source/native remain unchanged; the 08 native is still `2ac024c7`.
The inherited broad comparator reports additional digest-equal fields. Exact partial examples and provenance
are in [SNAPSHOT-DIAGNOSTICS.md](SNAPSHOT-DIAGNOSTICS.md); no broad PASS is claimed.

Preparation only: [FINAL-GATE-PLAN.md](FINAL-GATE-PLAN.md), new `tools/final_gate.sh` submitted for independent
host-script review **before execution**. The launcher is unexecuted; only shell syntax/embedded-Python AST
checks are permitted at this stage. B2 acceptance/integration precedes C1 merge/rebase and final full gate.
The frozen combined source/native must pass affected C1/B2 probes and fresh 577-fixture + 300×2 root coverage.
The plan provides isolated output paths, exact commands, input/approval hash bindings, duplicate prevention,
PID/PGID/UTC receipts and raw-byte/ID/header audits. No active live pin switch or runtime edits.

The authorized small follow-up is **2/2 PASS** on unchanged `631ac18d`, proof plus post-comparator checks;
exact predicates/read sites, negative controls, provenance and receipt hashes are in `SNAPSHOT-DIAGNOSTICS.md`.
Only Pingpong's proved representation and childless Arrows' unreachable origin are normalized. Nonzero phase,
changed hit membership/multiplicity/endpoints and child-capable/unproven origin remain detected. No engine or
native change/rebuild, generalized snapshot rewrite, duplicate ongoing sweep, or whole-byte equivalence claim.
Lead review of this comparator diff/proof remains a prerequisite to broader coverage acceptance.

04 older diagnostics completed **09:44:07Z**, 21/36/36/72 JSON rows, zero errors/digest mismatches, with the
previously recorded semantic field classes; artifacts are preserved. 08 PID/PGID **1042473** remains active
at **09:46:12Z**, no completion receipt. Raw earlier digest-case receipt has 72/72 entries, correcting the
old 35-script/70-case prose arithmetic; no raw evidence or historical gate result was modified.

## Launcher rejection repair (preparation, no new engine verdict)

CARD LEAD `reports/cards/reviews/C1-final-tools-r1.md` rejected the schema1 launcher at476a747f for six
safety/provenance defects; its scoped comparator normalization approval is unchanged. The new schema2 driver
and contract fix per-child exits, complete source/dependency/typed evidence binding, output confinement,
original-control freezing, inherited pin/environment leakage, and expected fixture/root/schema validation.
`FINAL-GATE-PLAN.md` specifies admission, exact commands, failure receipts and rollback. Helpers preserve
historical fixture pools/root sample/budgets while adding audit metadata and relocating inputs to private copies.
No final gate/host launcher/native build ran; local synthetic verifier checks do not establish integrated parity.
Fresh candidate-bound independent launcher review is required before execution. B2 acceptance/integration,
affected combined-source checks and fresh C56 remain mandatory; no live pin/runtime change.

The origin continuation was **through expiry (10 updates to expiry)**, not10 post-expiry updates. Corrected
prose without extending evidence. Prior failed review/artifacts are preserved; review's final followup raw-file
authenticity caveat remains. Exact local commands/results/hashes and repair rollback are in PROGRESS/reviews.

Fresh launcher review r2 rejected c45854f for dropping USER before CPU accounting and an empty full-tree Git
pathspec. Both repaired; an additional local flag check corrected workers ignoring hashseed0 under-I.
The13-group revised local suite passes with no engine/native/host launcher execution. Original r2 rejection
and artifacts remain; see FINAL-TOOLS-r3-response.md for full repair/review bindings. Fresh r3 required.

Fresh r3 rejected4bfae6b for losing prior exit receipts during a later interrupted wait. Persistent per-label
statuses, partial/final phase receipts and protected spawn/cleanup boundaries now preserve that provenance;
16 local synthetic groups pass. Failed r3 artifacts remain intact and source-bound. A fresh r4 review must
approve revised code before host execution. Engine/native/comparator and B2→C1 gate prerequisites unchanged.

Fresh r4 rejectedc7de06e for a second-stop window before cleanup masking. The raising-handler/mask design is
retired: handlers now only latch cancellation, with controlled spawn/wait/publication checkpoints and
uninterruptible mandatory cleanup. Nineteen local synthetic groups pass, including repeated cleanup-entry
and post-link stops. Full r4 failure evidence remains source-bound. Fresh exact-commit r5 review required;
engine/native/comparator and B2→C1 prerequisites remain unchanged.

Final tools approval is scoped to preparation at97171f5; the later receipt-only commit changes no reviewed
code/test/plan. Source/receipt/code hashes, faithful typed launcher-review translation, preserved failures,
exact commands and concrete rollback are indexed in reviews/REPAIR-RECEIPT.json and PROGRESS. The final
origin claim remains through expiry (10 updates to expiry), with no added simulation or byte-equivalence claim.

Shared Troop work remains open: exact B2 captures establish scoped Zap/Dragon
forced-state causes and IceSpirit's two mode failures. Candidate65fca is unbuilt.
Independent source/probe r1 rejected two probe gaps; the response and local
repairs are in `shared-troop/CANDIDATE-r1-response.md`. Fresh independent r2
**APPROVE — SOURCE/PROBE_PROPOSAL only** binds exact4635a3f45; full review and
receipt are `shared-troop/REVIEW-candidate-r2.md` and
`review-candidate-r2-receipt.json`. Both findings resolved, with no further
proposal blocker. No actual continuation/build/native acceptance follows from local mock
checks. Lead's reviewed frozen B2-first base, affected exact-native evidence and
ordered fresh C56 still precede acceptance; old7738 is not that base.

## B2-first diagnostic execution (2026-10-16, isolated integration only)

Supplied frozen9fa is now the preserved first-parent base of the separate
cards/b2-c1-integration-20261016 branch; original cards/c1 stays11ff unchanged.
Full postmerge/probe/procedure independent reviews and actual execution are
indexed in integration/DIAGNOSTIC.md. R1 rejected757 (duplicate recovery method,
failed-probe identity evidence, causal controls); repairs18d passed R2 source
review but actual prebuild failed inherited2700 output/cleanup. R3 approvedc077
and exact one-job closure; old FAIL/source/log/modes remain preserved.

Fresh c077 build passed, nativef42a84b3a8f7c61ca037ba9ee185a73206de5db481ec1b375ac5f8ac2ec07dce,
CPU4/nice15/Cargo-j4. Actual shared32 completed all witnesses, reporting22PASS/
10ZapFAIL rows; source identity independently failed on two generated Numba cache
files. Worker retained after-import failures, child statuses and all raw roots.
Overall DIAGNOSTIC_FAIL, seven other phases NOT_RUN; no coverage accepted.

First-bad Zap rows are a cold-clock landing projection mismatch after successful
route/external finalization witnesses: same pose/HP/digest, Python remaining600/
no seed vs native remaining0/seed1000, clock uninitialized on both. This is a
confirmed constructed-state difference; natural gameplay reachability and any
damage/timing change remain unproved. Bounded Astra reasoning supports a narrow
successful ordinary Dash-hit projection repair preserving cold initialization,
finish/refund and existing loaded-clock behavior. Leap/Hook audit finds distinct
unproved candidates, not grounds for speculative changes or broad equality.

Next candidate changes only dash.rs in engine, routes Numba cache to a fresh
private directory outside authenticated source without an ignore, and adds12
cold/loaded/hit/miss/missing-target continuations. Five local stdlib/AST/mock
suites pass; new native/probe execution requires fresh exact independent review.
Required nine bounded phases32/12/21/8/2/42/6/2/4 remain open. Exact FAIL/source/
artifact/provenance/rollback bindings are in integration/diagnostic-r2-execution-evidence.json,
small witness extracts and DIAGNOSTIC-r3-execution-response.md. No stats tables,
new comparator exemption, main/pin/runtime acceptance or final fullC1C56 run.
Later reconciled B1/current-main freeze and ordered full C56 remain mandatory.

Independent diagnostic R4 REJECTED8d's new probe: it lacked fresh Python cloning
at every current pre-step and lost failed clone post-step roots. Both are now
repaired locally with exact run_case/main mocked controls and persisted failed
case read-back; no engine bytes changed from8d and no host run occurred. Five
local suites pass, but the actual source-bound build/nine phases still require
fresh independent exact review. Response: integration/DIAGNOSTIC-r4-response.md.

R5 confirmed the Dash repairs but rejected9466's selector failed-root retention.
Selector and the new first-update catch now preserve available post-error arms
through saved cases; expanded exact AST/main mocks pass. Engine bytes remain8d,
no new host/native execution. Fresh complete exact R6 review and actual bounded
diagnostic still required; see integration/DIAGNOSTIC-r5-response.md.

## 2026-10-16T17:06Z — exact R6 approval and single approved execution

R6 independent review APPROVED exact5fc9c5121b4d0a995500eecb2bce21c0f7833625,
526 inputs. Report SHA2a1d0e90aca1da588756cc5e15570c7e9441bedcf77ed59e70217c11c219b891;
typed approval SHA1756302570c8493eb998bd1dec4d203d9a8ce973ce252dca2f9a33d4bd5252c9.
Local stdlib-only Python3.12 nice15 rehashed all526 and verified clean tracked
HEAD. Read-only08 17:05:35Z ps for3502954/3503110/539594/540091/608754 found
none; old wrapper leases absent and both original FAIL cleanup terminals read.
Approved stage independently also rejects any live prior family/lease or missing
terminal. No old artifact changed and no recovery rerun.

Executed once, unchanged reviewed tool, on local05 (staging only):
`nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B reports/cards/c1/tools/diagnostic_job.py stage reports/cards/c1/integration/diagnostic-review-r6.json c1diag-20261016T170550Z-r3`.
Source-bound08 launch17:05:50.926040Z PID/PGID1054216; CPU4 nice15,
admission2326e269528bf3e6c38882ceeaa0ba2bf0c942852904713f5ed2107087c6ffb4,
manifest7977982fb6747340c670d1d94b28112990c4f59ae0fac85b7ae5235a78a88182,
platformac7483bccdd813ada044866e6e7ef70cd3f3f59018f210afb8999c6ddfaa06e9.
17:06:03Z exact wrapper live nice15, lease `4 1054216`; job/output/numba-cache
all exactly0700. Build started; actual nine phases remain pending. Source/cache/
all prior failures preserved; no borrowed native, engine import or compute05.
Launch receipt is integration/c1diag-20261016T170550Z-r3-launch.json. Rollback
is isolated integration commits only, no active deployment/pin changed.
Assignment OPEN through actual phases/failure resolution/final evidence review;
final reconciled-main full C56 and live pins WITHHELD. Strictsilence/direct-owner
coordination and one automatic final delivery remain in force.

## Owner 2: native==Python closure, Spirit C56 fix, merge onto main (2026-10-16 17:45–19:20Z)

New owner (the previous thread could not continue). Exploration tier: correctness gates only.
Branch **`cards/c1-main`** = origin/main (A + B1 + B2, engine-cards == f71fe8d20) merged with
`cards/b2-c1-integration-20261016`. Merge commit `d0a60de59`; gated engine commit **`5c41d4a8a`**, native
**`9f66228815bbb6c3349feeee256aa2d9d546171e4a8cc8e9731699c359869bd1`** (reproduced on 04 and 08).

### Root causes fixed

| Class | Symptom | Cause | Fix |
|---|---|---|---|
| Combat stun gate | shared `zap/external` (both seats): Python reacquires the target on the stun's last tick, native one tick later; then `clock_initialized` | `Troop._update_active_combat` returns early only on the freeze pause and observes targets before its stun return, without `get_clock()`. Native also returned early on `stun > 0` for ordinary troops and initialized the clock before targeting | `lib.rs combat_one`: the early gate keeps the pause (plus the king/Tower stun terms); a stunned ordinary troop skips `consume_clock_reseed`. Every ordinary stun sets the pause (`stun_target_mode`), so reachable states are unchanged; forced stun-without-pause states now follow Python |
| Spirit launch stats (C56) | first C56 gate on the integration (g1): 142/577 fixture chains and 11 roots differ, final snapshots equal; every sampled first divergence is a launched Electro/Fire/Ice Spirit's `stats.ordinary` / `stats.projectile_slow_multiplier` | The shared-Troop candidate rewrote the carrier's stats at native launch to match Python's export. They are unread in flight, but the rewrite changes snapshot bytes | `troop.rs launch_spirit` keeps the pinned template; `finish_started` chooses clock vs `started` by the `spirit` flag (Python `on_combat_target_removed`); `differential.entity` exports a launched carrier's mode stats as the character's. Shared probe 32/32 |
| Spell-shot origin | `Snowball/*`: `projectile_origin` Python `[9,3]`, native `[0,0]` | Native set the origin only on character shots and children | `apply_action` and `projectile_volley` set it for child-capable spell shots, the only reader being `projectile_children`. No C56 or pool spell shot is child-capable (only Firecracker's character shot), so C56 bytes are unchanged |
| Merge with B1 (class closure) | — | B1 replaced stagger-only filters with `absent()` (stagger or mounted rider). Python's `RiderOnMount` blocks effects and secondary targeting | The C1 axe filter (`pingpong_tick`) uses `absent()`. Both chain selectors (`chain_release`, older `chain_tick`) skip a mounted rider (`_can_chain_to`). C56-inert: no C56 entity has a mount |

Merge conflicts (B1 vs C1) were unions: differential helpers and stats keys; creation areas (B1 Battle Healer
`create_areas` first; C1's wizard creation-cast areas stay card-template units); projectile creation order
(boulder birth tick, B1 Hunter fan, C1 axe); detector (C1 `spawnAreaAtCreation` + B1 on-hit area); `lib.rs`
modules and pre-combat blocks (B1 mount facings, then C1 orphan counters); boulder filter = B1 `absent()` + C1 stealth.

### Full-snapshot comparator (`tools/probe_snapshots.py`)

Every rule below is backed by a source reader audit, and each keeps any nonzero or semantically different value
detectable (local negative controls):
- **Pending reseed** (`clock_reseed`) is resolved on both sides exactly as `consume_clock_reseed` before `force_due`
  and the clock are compared (BattleRam's charge-ready tick: Python defers the write, native applies it at once).
- **`hit_ids`** is compared as a multiset: Python sets; native only `contains`/push/extend, never iterated or digested.
- **A key omitted at its serde default** equals that default (native skips `chain_wait` 0).
- **Nested scope templates** (Rage child/impact) are compared with zero-default keys stripped.
- **`aim` on spell rolls** (Log), which `rolling_tick` never reads. The character boulder stays strict.
- **`projectile_origin`** only where neither side can spawn children. This replaces the Arrows-only exemption.
- **A shot's cloned `production`**, which only the character/building object branch ticks.

### Evidence

- Previous owner's diagnostic (08 PID 1054216, source 5fc9c51, native `ed4b7ebd`) is terminal. Build, dash-clock,
  review (21), selectors (8), followup (2), first-update, clone-bounds, clone-recovery and terrain all pass. Shared
  was 30/32: only `zap/external` failed, which is fixed above.
- Integration natives (08 `c1/o2/`):
  - `400ad335`: shared 32/32.
  - `39968cc0` (`116620b30`): shared 32/32. The partial full-snapshot suite s3 was clean on every row it reached (C1
    36/36, cases 40/72, B2 22/28, Batch A 28/42, plus dash-clock, selectors and Batch A cases) before it was stopped
    for the main merge.
- C56 g1 (04 `c1/o2g/g1`, native `400ad335`) **FAILED** with the Spirit stats cause above. g2 (`39968cc0`) was
  stopped unfinished, superseded by the main gate.
- Fidelity on the B2+C1 integration source (08 `c1/o2/fid/f1-*`): **C1 32/36 mechanics, 35/36 with the overlay**,
  identical verdicts to the original C1. Pool 77/193 mechanics, 80/193 with stats (C1 alone: 74/77). The residual
  is ElectroWizard × Knight (C56 Knight clock, §5).
- First main run (`d0a60de59`): the suite showed every Spirit export raising `UnboundLocalError`. Main's
  `differential.entity` had a later function-local `SimpleNamespace` import, which shadowed the module import
  used by the launched-carrier line. Fixed in `5c41d4a8a`, Python-only, native unchanged. That gate (PID 3515215)
  and suite were stopped; the aborted dir is `c1-main-gate-d0a60de59-aborted`.
### Final on main: engine `5c41d4a8a`, native `9f662288` (both jobs finished 2026-10-16 19:53Z / 20:32Z)

**C56 gate PASS**: 04 `/mpac/sdicks02/jobs/clasher/cards/c1-main-gate/`, Batch A gate script unchanged; pinned = r1
Python + `681b5f2c`, total = C1-on-main tree + `9f662288`. Fixtures ran 19:27:52Z–19:52:38Z and roots finished at
19:53:14Z. `gate/compare.json` SHA256 `aee02318327586ac49bd7ab91876d8bd53bf4a6a864008ec61b97389605d9018`.

| Check | Result |
|---|---|
| Fixture records identical | **577/577** |
| Rust-only chains equal | **577/577** (1,010,680 ticks, 0 errors either arm) |
| Python↔Rust full parity | 429/577 in both arms (unchanged) |
| Root records identical | **600/600** (300 full + 300 cut; 300 of 1,043 roots, 12 games, ticks 140–5,570) |
| Root operations | 9,336 rollout_e1, 1,800 select_action, 478 apply_discrete, 1,800 step checks; all equal |

**native == Python**, 08 `c1/o3/m2/` (frozen source `5c41d4a8a`, native `9f662288`): every phase exited 0.

| Coverage | Result |
|---|---|
| Full-snapshot field compare, every tick: C1 36, focused cases 72, Batch A 42, B2 28, B1 30 | all digest-equal; no field difference except two representation classes, both since covered by comparator rules (`5c341d698`) and the affected rows re-run clean: Rage ×3 (export-only `public_identity`/`public_static` sensor keys inside the nested scope templates) and `inferno_dragon_zap` ×2 (`move_target` on the stun tick: native clears it, Python keeps it until both reset it at the next combat start) |
| Shared Troop 32, dash-clock 12, selectors 8, review 21, followup 2, clone bounds/recovery, terrain 4 | all PASS |
| First-update diagnostic (21 paths × 2 seats) and Batch A `probe_first_update_paths` (42) | all complete / matching |
| Batch A review cases (4); B1 review regressions (16) | 4/4; 16/16 ok |
| Named native-diff bug games (§13–§16, 11 games, full length) | 11/11 match |

**Fidelity vs RoyaleSim on main** (08 `c1/o3/fid/fm-*`, `--table 160402`): C1 **32/36 mechanics, 35/36 with
the overlay**, the same verdicts as the original C1. The residual is ElectroWizard × Knight (C56 Knight clock, §5).
Pool **83/193** mechanics, **86/193** with stats (original C1 74/77; the difference is B1 + B2). The four stats
rows remain overlay-only (§3).

Lesson: a rebuild copied over a native that running probes had mmap'd segfaulted the first suite (s1, discarded).
Builds now go to `native-<sha>/` with an atomic symlink, and each suite pins its native and a frozen source copy.
