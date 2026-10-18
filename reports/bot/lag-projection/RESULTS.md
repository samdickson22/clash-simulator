# LP1 — reconstruction audit; outcome evaluation pending

The 20-state audit found material root errors before any outcome games. Goblin
Barrel's carrier survives the full-public simulator rebuild, but its destination
becomes `(0,0)`. Live perception omits that carrier entirely. Freeze status,
production phases and building decay remainders also fail to survive rebuilding.
The native diagnostic scorer selected a different action on 8/20 rebuilt roots.
This is a reconstruction finding, not evidence that projection improves wins.

**Disposition, BOT LEAD:** the full-pool owner (Opus) will implement root fidelity
first, then the LP1 projected-root adapter. This worker has stopped treatment
implementation and will run no outcome games before receiving the adapter
commit. No files in `bot/live` or the read-only `clasher` checkout were changed;
the Mac was not accessed.

## Registration and scope

Preregistration landed on main at **fa07883e4**, before any simulation, with
fresh `os.urandom(6)` BASE **202492701121077**. The initial command failed because
`python` was unavailable and produced empty commit c9f5fb2b9; the registration
was then written using `python3` and committed before starting the audit.

Five controlled level-11 Python-engine scenarios were sampled at ticks
5, 15, 30 and 60: Goblin Barrel, Archers/Knight combat, Tombstone/Hog Rider,
Musketeer/Knight under Freeze, and Archer Queen/Electro Wizard. The Queen's
ability was successfully activated at tick 21. These are 20 constructed states,
not 20 independent matches or a frequency estimate for live errors.

For each state, the audit compared a native export of the physical Python
engine state with `Resources.root` and with a body-only observation passed
through the same root builder. Body-only removes spell, shot and effect rows;
it isolates the documented live carrier omission but is not a complete replay
of live perception. Opponent HUD state was held identical offline to remove
belief/deck error. The player under test never received the physical snapshot.
`LevelRoot` at all levels 11 reproduced `Resources.root` byte-for-byte on all
20 states.

The scoring diagnostic used WAIT plus one public-legal tile per hand slot,
selected nearest `(8,10)`: five actions per state, 100 action scores. Each score
is the mean of three native 160-tick scripted rollouts, with both command delays
27 ticks and the same elixir weight. These are **not** the learned K4L reduction's
scores. Root reconstruction also resets the RNG; the score differences include
that sampling/defaulting behavior and are not isolated causal ablations of
individual fields. No confidence interval or win-rate interpretation is claimed.

## What the rebuild loses or approximates

- **Goblin Barrel:** all three airborne states retained the `SpawnProjectile`
  in full-public roots, but its aim changed from `[3.5,6.5]` to `[0,0]` and
  `effect_age` reset to zero. The root repairs aim only for literal
  `class == 'Projectile'`; `SpawnProjectile` retains prototype aim. The maximum
  absolute rollout-score difference in this scenario was **0.049743** and the
  diagnostic argmax changed on **3/4** states. Body-only roots dropped the
  carrier in **3/3** airborne states. Thus retaining the public entity alone
  does not preserve its landing behavior.
- **Other in-flight objects:** a physical Archer shot at tick 30 survived the
  full-public rebuild but had prototype radius/range/sight differences and an
  inferred destination rather than its actual target. Body-only removed it.
  The combat scenario's maximum absolute score difference was **0.024719**,
  with **0/4** argmax changes. Across the bank, body-only removed eight non-body
  entity occurrences: three barrels, one Archer shot and four Freeze areas.
- **Production and decay:** Tombstone at tick 30 had production
  `elapsed=50, waves=1`, rebuilt as `elapsed=0, waves=0`; its decay work changed
  from `80` to `0`. Production and decay fields differed in both post-deploy
  spawner states. Building HP and its static lifetime remained present, so
  future decay continues from a reset fractional phase. The scenario's maximum
  absolute score difference was **0.039384**, with **3/4** argmax changes.
- **Spawn identity/value approximation:** the two Tombstone Skeletons at ticks
  30 and 60 were represented as `SkeletonArmy` prototype bodies. They were
  present, not dropped: HP stayed 81, but `payload_key`, name and
  `leaf_elixir_share` differed (`0` versus `0.2`). The name-based comparator
  lists these four aliases as missing/extra pairs; they must not be reported
  as four lost troops. Immediate root values differed by about -0.00432 and
  -0.00447 in those two states.
- **Statuses and clocks:** Musketeer's Freeze stun reset to zero in **4/4**
  Freeze states; its first sampled physical stun was 3.3 seconds. Slow/effect
  fields also differed. The immediate value bias was **+0.006781** in each
  Freeze state; maximum rollout-score difference was **0.006113**, with no
  argmax change. Across all scenarios, deploy fields differed in **11/20**
  states, ordinary attack-clock fields in **5/20**, cooldown fields in
  **20/20**, and forced age in **20/20**. Targets, routes, attack/deploy phases
  and other non-public state use deterministic prototypes/defaults.
- **Champions versus evolved/hero forms:** the base Archer Queen identity and
  own active ability survived rebuilding; ability timestamp/state details did
  not match exactly. This scenario's maximum absolute score difference was
  **0.036438**, with **2/4** argmax changes. This does not validate evolved or
  hero forms. The runtime had no evolution/hero-named config entries or
  templates, the balance-overlay traversal explicitly excludes
  `evolvedSpellsData`/`heroData`, and the v5 descriptor traversal excludes them
  too. Distinct unsupported identities have no form-aware reconstruction;
  an identity mapped upstream to a base token receives the base template.
  These base-card simulations cannot quantify the cost of actual evolved/hero
  units, and the absence of such units in this bank is a coverage gap.
- **HP, shields and pending casts:** perfect public HP fractions were preserved
  to at most **0.0000216 HP** error among matched bodies. This is an optimistic
  sensor assumption: `LiveTranslator` defaults an unread unit's HP to full.
  Shield state is private in v5; roots use prototype shield and set it to zero
  when body HP is below full. This bank did not exercise shields. All 20
  physical samples had zero pending direct casts, so the unconditional
  `pending_casts=[]` loss is a source finding, not a measured frequency here.
  **Correction to the first notification:** Goblin Barrel is a carrier, not
  the pending-direct-cast mechanism.

For the full-public rebuild, mean absolute rollout-score difference was
**0.010395**, median **0.006003**, maximum **0.049743**. Best-action disagreement
was **8/20**; the true diagnostic scorer's mean regret for the rebuilt choice
was **0.005138**, maximum **0.023174**. Body-only mean absolute difference was
**0.011576**, maximum **0.057454**, with **7/20** disagreements. These small,
correlated constructed scenarios do not establish that one observation model
is stronger than the other.

## Earlier projection, lag verification and implementation boundary

The read-only earlier implementation is
`clasher/src/clasher/analysis/loss_review/delay_fixes.py`: `planner_class` defines
`forward_state` at lines 141–145; `hypothetical_packet` starts at 171;
`imitation_candidates(..., forward=True)` projects imitation proposals at
226–267. The experiment arm is **IF**, versus **I0**; its internal option is
`forward_prior`. In `delay_simulate.py:113–123`, candidate scoring still uses
the original root. Its reported +0.00 pp result is therefore not a test of a
projected live-search decision pipeline.

Our lag is actually modeled: `bot/players/royalesim_match.py:183–206` defaults
to `delay=27`, passes it to both players' `MatchContext`, and constructs a
`CommandQueue(delay, capacity)` for **each** seat, including ours. The L16 driver
uses that default. This is a physical command delay in addition to simulator
card deployment/travel behavior. Both LP1 arms must retain the same physical
delay; the planned projection is 26 ticks.

There is no existing live-search projection token to wire. Required Opus work,
already sent to BOT LEAD and the live-diag owner:

1. `fair_player.py:171–204` and `bot/live/levels.py:89–128` contain the resets;
   the aim repair is specifically `fair_player.py:181–183` and
   `levels.py:101–104`. Root fidelity needs a public-information design for
   carrier target/age, production and decay phases, and statuses. The audit's
   private truth labels are not permitted as player input.
2. `bot/live/player.py:125–158` constructs proposals/candidates before calling
   `root_fn`. An isolated search adapter must handle the projected packet and
   proposal path, preserve current affordability and hand-slot identity, and
   prevent sampled hidden opponent state from leaking into policy input.
   A root wrapper alone does not cover that path; this worker may not edit
   `bot/live`.
3. `bot/search/lopp_fast.py:525,541` and `bot/search/lopp.py:170–190` schedule
   actions using `core.command_delay`. Projecting 26 ticks and then applying
   another full 27 would double-count lag. Opus must settle initial residual
   delay, subsequent command delay, pending reservations, opponent forecast,
   cadence phase and horizon semantics consistently across native/learned
   scorers. The existing forward helpers are primitives, not this adapter.
4. The owner can expose the adapter from a separate module and add a small hook
   to their `bot/livediag/l16_cadence.py`. At source 11fca5cd4, the helper's
   default `DECKS['sam']` is a Giant deck, not the requested Hog deck; the
   explicit own-deck override must also be wired/pinned before LP1.

## Outcome bank and handoff

The contingent preregistered bank remains unrun: 150 paired cases for each of
LIVE-K4CW-r16-fp and R3a, in L16 and the specified account-level row, 1200
games across two arms. Exact source, pool-v3.2 King-9/no-Goblin-Hut rows, vocab
and adapter pins must be recorded in an amendment on main before those games.
No source/pool substitution or fidelity fix should be silently folded into
the projection contrast. A separate root-fidelity A/B will be scored if the
owner requests it.

**Win rate, reaction, idle-play share, elixir at enemy cross and CPU-ms per
decision: not measured.** No outcome games were launched, and diagnostic
scoring time is not substituted for decision CPU time.

## Receipts and reproducibility

- Audit source checkout: tracked `bot` and `reports/explore/x4s` from
  **11fca5cd4**, mirrored to 04 job storage; frozen deployed runtime
  `live16402b-r3`, native SHA-256
  `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1`.
  Its actual imported `fair_player.py` SHA-256 is
  `89f0c28b4aab1dba42a56c3a2d0e23949d3e0d22bd5aceee03347e2ed6fecc46`;
  current-source line references above describe the same relevant resets.
- Evaluation-only script and complete raw snapshots stay outside git on 04:
  `/mpac/sdicks02/jobs/clasher/bot-lp1/audit.py` and `audit-r1/`.
  Script SHA-256:
  `77b309c16996c762fb558cbeed4c0039137f153be4bfb114b61ae871db8dd11c`.
- Summary receipt copied to 05:
  `/mpac/sdicks02/jobs/clasher/bot-lp1/audit-r1.json`, SHA-256
  `cd08d472af555a674a62e0ee9d4ecb2058d03405f8280135b15c6886f60bfcf7`.
  All 20 states and 100 action scores completed; no retries or state exclusions.
- Execution: 04, `cpu_job.sh 3 nice -n 15`, one evaluation process,
  `PYTHONHASHSEED=0`, `NUMPY_MADVISE_HUGEPAGE=0`, OMP/BLAS/Rayon threads 1,
  CUDA disabled. No lab user was logged in; observed load stayed below 110.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
