# Null's Royale native mechanics fixture plan

Phase 1 prepared offline, 2026-10-16 UTC. Exploration tier. No native connection,
emulator operation, capture, commit, or sealing was performed. Work lives in the
CARD LEAD worktree `/mpac/sdicks02/repos/clasher-cards`, exclusively under
`reports/cards/nulls/`; raw outputs belong in jobs directories.

**Requested first slot: 120 minutes**, exclusive, granted by LIVE LEAD through
CARD LEAD. Owner `live-nulls-generator-opus-r1` pauses its capture and controls
startup/shutdown. Until the window arrives, no SSH/probe/adb execution.

## Authority and what was learned

Every scenario and capture identifies **APK/client 15.535.13, content 15.535.86**.
These are native mechanics observations for this reference, not live-16.402 stat
values. Preserve actual attestation, config, observed opening state, and code/data
hashes with every attempt. Hashes provide provenance; nothing is frozen or sealed.

Sources read in this worktree:

- `m0/native-speed/live-validation-20260929/README.md`: a successful schedule or
  reconnect is weaker than proven action execution; mutation delivery must not be
  retried blindly. Old serials/ports in that report do not apply to this slot.
- `m0/readiness/execution-workflow.md` and
  `m0/readiness/paired-repetition-run-v6-report.md`: paused/ready preconditions,
  exact opening-state reconstruction, independent repeats, provenance limitations.
  Their long-match noise-floor/admission workflow is not this exploration task.
- `native-corpus/{study.py,FEASIBILITY.md,infer_order.py,levelled_order.py}`:
  empty config command/event streams, `replay-schedule-card`, hand/cycle shuffle,
  nominal level versus actual level, and injection-versus-execution distinction.
  Historical rich packets contain cumulative rings and can grow to MB per frame;
  compact-only misses body/status/target detail. No newer probe command is assumed.
- `m0/native-mechanics-20260928/nm_lib.py`: stock configure + fixed-range opening
  hand seed search, persistent `session-v1`, submission at tick T and native
  scheduling at T+1, world coordinates in 1,000 units/tile.
- `c56/data/{PROGRESS.md,FLEET-RESULTS.md}`: C56 data reconstruction/extraction and
  its provenance are separate from native truth. Its reported completion does not
  make newly generated simulation rows native fixtures.
- `bot/fidelity/{fixture.py,run.py,engines.py}`: accepted `exec_tick` events,
  observed initial hand/cycle/elixir, HP-bearing object trajectories; loader accepts
  only registered train/validation episodes. The historical 577 fixtures are a
  regression baseline, not evidence that a new card is already covered. OursEngine
  can force hands/top up elixir and `run.replay` can retry deployments; this runner
  rejects those interventions and never retries.
- `reports/cards/batchA/RESULTS.md` §4 and
  `reports/cards/fidelity/{scenarios.py,summarize.py,RESULTS.md}`: the exact five
  residual scripts, Witch's ordinal artifact, and the two reference table choices.

All abbreviated strategy paths above are below
`reports/strategy_council_20260928/`. No historical evidence was edited.

## Scenario contract

`scenarios.py` is the executable, name-only specification: **106 scenarios**,
covering 14 Batch A cards, 19 B1/B2 cards and one C56 control. It supplies the exact
two eight-card decks, ordered command list, absolute deploy coordinates and ticks,
version, question, priority and script identity for every scenario. Materialize it
only into a jobs directory:

```sh
mkdir -p /mpac/sdicks02/jobs/clasher/cards/nulls/plans
python3.12 -B reports/cards/nulls/scenarios.py > /mpac/sdicks02/jobs/clasher/cards/nulls/plans/scenarios.json
```

Each whole battle ends at tick **600 = 30 seconds**, including idle warmup.
Residuals submit at tick 100 and capture ticks 100..600 inclusive. Expensive
Three Musketeers scripts start at 220; cluster/support/enchantment scripts start
at 300 to refill naturally. Their shorter active windows still fit the same
30-second total. These are prefixes of the original 30-second combat / 75-second
building runs; they do not cover building lifetime or every late wave. Do not
report a missing late event as an incorrect native mechanic.

Decks contain unique scripted cards in first-use order, then unique members of
`Knight, Archer, Giant, Minions, Musketeer, BabyDragon, Balloon, Wizard, Zap,
Skeletons`, truncated to eight. This matches the existing paired harness's
declaration rule. Native initial hands are shuffled: choose the first seed in
1610150001..1610150200 whose initial hands contain every scripted card. Selection
uses opening hands only, never combat outcomes. Retain every seed attempt and
actual deck/hand/cycle. Replay both simulation arms from that observed order and
elixir. Never equate declared deck order with initial hand order.

Coordinates are shared arena coordinates: owner 0 defends low y; 18 x 32 tiles.
Both sides receive the exact stated coordinates; do not mirror owner 1 again.
`command_tick=T` means the pre-step boundary; schedule at native `executeTick=T+1`.
An accepted event stores `exec_tick=T+1`, with hand-change/spending witness on that
one tick. Native visual deployment/birth can occur later. Replay issues it at
`exec_tick-1` (`issue_offset=-1`). Never align each card independently to erase a
timing disagreement. Validate this global convention against the initial direct
deployment and Wizard control before making a one-tick mechanics claim.

Cards and kings nominal level 11, Princess towers, base forms only. Copy the
owner's exercised native template and exact native attestation to the jobs area;
keep all non-deck/rules fields from that template. `capture.py` writes empty
`cmd`/`evt`, base deck entries and explicit level/tower settings. The historical
template and native ruleset paths are not present in this Linux checkout: they
are slot inputs from the owner's existing Mac cache, not files to reconstruct
from memory. Card IDs come from the supplied local gamedata; no data tables enter
git. Body-name lookup, if supplied, maps rich `dataGlobalId` to native body names;
keep it in jobs too. Unmapped names remain `data:<id>` and are missing semantic
coverage, not guessed names or passes.

## First work: five disagreements plus control

All commands below submit at **100**, execute-schedule at **101**, end at **600**.
Each is repeated three times with the same selected seed/config/opening state.
Independently reconfirm opening hands on each run; retain every attempt.

| Scenario ID | Owner 0 tile | Owner 1 card/tile | Focused native observables and decision |
|---|---|---|---|
| `GoblinCage.giant` | Cage (7.5,12.5) | Giant (3.5,17.5) | Cage death D, Brawler birth B, deploy-ready R, target/reach at R, launch L and first nonlethal impact H. Report B-D, R-B, L-R and H-R separately. RS claim: H-R=16; ours=17 after readiness at relative 171. Native must witness an already-in-reach Giant; older HP may move D/R, so absolute H alone cannot settle it. |
| `Tombstone.hog` | Tombstone (7.5,12.5) | HogRider (3.5,17.5) | Combat death D and death Skeleton birth B, count, child positions at B and B+1, parent/death anchor, target/reach and phase events. RS claims four children take a 0.15-tile step on B toward the in-reach Hog; ours hold. Distinguish periodic Skeletons from the death wave by parent/root and birth. |
| `Barbarians.minions` | Barbarians (3.5,14.5) | Minions (3.5,17.5) | Trace early shared prefix, first Barbarian death, Minion launch/impact and Princess acquire/launch/impact. Identify the first local phase divergence; later total damage/deaths are HP-confounded. |
| `BattleRam.minions` | BattleRam (3.5,14.5) | Minions (3.5,17.5) | Ram death/release and child deploy clocks, then same Minion/Princess chain. Existing tower-hit relative 313/315 is a locator, not a native expectation. |
| `Witch.alone` | Witch (3.5,14.5) | No play | Match entire Skeleton-wave records as multisets of birth/position/ready/death/HP. Preserve native enumeration separately. A swapped pair of equal semantic records is an ordinal artifact; do not assign identity by reusable entity-array slot. |
| `Wizard.minions.control` | Wizard (3.5,14.5) | Minions (3.5,17.5) | Existing pure-C56 control with Minion/Princess timing drift. It separates shared combat behavior from new-card release logic; same one-tick convention as every other script. |

If the exact script fails the focused precondition on the older stats (e.g. Giant
not in reach when the Brawler becomes ready), record **PRECONDITION_NOT_MET**.
Do not select a favorable seed or silently retime the command. The lead can add
a separately named fixed-script control after inspecting that trace. No global
1-tick tolerance: it would hide the Cage dispute. Combat events must be complete
at the relevant boundary before claiming intra-tick phase order; truncated or
overwritten rings mean that observable is unavailable.

## Remaining coverage

Every ID is `<internal card name>.<variant>`. Reuse P0 captures for their matching
coverage entry rather than duplicating them. `scenarios.py:script` gives each
variant's exact commands; the generated manifest expands every ID and deck.

| Card / internal name | Variants | Main mechanics observable |
|---|---|---|
| GoblinCage (+ GoblinBrawler) | alone, hog, giant | Death release, Brawler deploy and first load; alone only if Cage dies by the short horizon |
| SpearGoblins | alone, knight, minions | Formation/stagger, launch to impact; distinguish hit/load value changes |
| Bomber | alone, knight, minions | Ground-only acquisition and splash ordering |
| Tombstone | alone, hog, giant | First periodic wave, first step and combat death wave |
| Barbarians | alone, knight, minions | Formation/stagger and target cascade |
| BattleRam | alone, knight, minions | Charge/impact, death release and deploy |
| MegaMinion | alone, knight, minions | Air/ground acquisition and first attack control |
| BarbarianHut | alone, hog, giant | First/early periodic waves, death release if reached |
| Mortar | alone, hog, giant | Minimum-range rejection/retention/drop, projectile origin |
| FlyingMachine / DartBarrell | alone, knight, minions | Flying classification; ground Knight cannot attack it; projectile origin |
| Witch | alone, knight, minions | Simultaneous wave emission, first step, wave multiset |
| PEKKA / Pekka | alone, knight, minions | First attack and retarget ordering |
| Guards / SkeletonWarriors | alone, knight, minions, shield_break | Formation radius; shield breaks without excess damage spilling to HP |
| SkeletonDragons | alone, knight, minions | Formation, air/splash targeting and launch offset |
| RoyalRecruits | alone, knight, minions, shield_break | Six-body lane split/stagger and shields |
| ThreeMusketeers | alone, knight, minions | Three deployment clocks and independent shots |
| GiantSkeleton | alone, knight, minions | Death bomb creation/arming/explosion if combat kills parent |
| SkeletonBarrel / SkeletonBalloon | alone, knight, minions | Air parent -> death impact -> ground release/count/placement |
| Hunter | alone, knight, minions, hunter_far | Pellet spread/contact count; near/far range control |
| Zappies / MiniSparkys | alone, knight, minions | Deploy stagger, stun pending attack and reacquisition |
| RoyalGiant | alone, knight, minions | Building-only targeting and ranged launch ordering |
| BattleHealer | alone, knight, minions, wounded_support | Attack/passive heal trigger, wounded friendly target eligibility |
| GoblinGiant | alone, knight, minions | Passenger fire and post-death passenger release |
| RuneGiant / GiantBuffer | alone, knight, minions, enchant_support | Enchantment selection and third-hit trigger on actual allies |
| Freeze | tower, cluster, support | Impact/freeze entry/expiry/pause/reacquire |
| Snowball | tower, cluster, support | Impact, knockback/slow, movement order |
| Vines | tower, cluster, support | Target cap/selection, snare and DoT timing |
| Rage | tower, cluster, support | Friendly aura entry/refresh/exit and haste order |
| Void / DarkMagic | tower, cluster, support | Strike cadence and target-count damage tier selection |
| GoblinCurse | tower, cluster, support | DoT/amplification order and kill conversion geometry |
| Clone | tower, cluster, support | Clone placement/identity/shield/HP behavior; support is the positive case |
| Graveyard | tower, cluster, support | Birth/ready cadence and count; RNG geometry gets repeat/distribution treatment |
| Heal (= Heal Spirit) | alone, knight, minions, wounded_support | Jump/impact/heal order and wounded ally eligibility |

Variant rules (absolute start is in each scenario's script):

- `alone`: owner 0 at (3.5,14.5); buildings at (7.5,10.5).
- `knight/minions/hog/giant`: owner 0 at (3.5,14.5), or building at
  (7.5,12.5); owner 1 named opponent at (3.5,17.5), same command tick.
- `tower`: owner 0 spell at (3.5,25.5). Friendly-only spells are intentional
  eligibility/no-effect controls, not evidence their friendly effect works.
- `cluster`: owner 1 Knight (3.5,18.5) at S, SkeletonArmy (5.5,18.5) at S+1,
  Minions (3.5,20.5) at S+2; owner 0 spell (3.5,18.5) at S+30.
- `support`: owner 0 Giant (3.5,14.5) and owner 1 Knight (3.5,17.5) at S;
  owner 0 spell (3.5,14.5) at S+35.
- `wounded_support`: Giant/Knight as above, healer/spirit (4.5,13.5) at S+80.
  Require a wounded ally actually in the heal area; otherwise mark missing trigger.
- `enchant_support`: owner 0 Rune Giant (3.5,12.5) at S, Archer (3.5,13.5)
  at S+1, Skeletons (4.5,13.5) at S+2; enemy Giant (3.5,17.5) at S.
- `hunter_far`: owner 0 Hunter (3.5,12.5), enemy Giant (3.5,17.5), both at S.
- `shield_break`: owner 1 Guards/Recruits (14.5,21.5) and owner 0 Fireball
  (14.5,21.0), both at S; require an observed break, no fabricated stationary unit.

All support scripts use ordinary legal plays. No edited HP, frozen units, forced
hands, custom native unit injection, champion actions, evos or hero forms.
Death bombs, passenger releases, healing, enchantments and conversions are
**trigger coverage**, not automatically PASS because a scenario completed.
Older stats can prevent these triggers before tick 600. Keep that denominator.

## Slot procedure and resource budget

Authorized instance only: AVD `clasher_reference_api35`, Mac probe
`127.0.0.1:26795`, serial `emulator-5596`, adb server port **5049**. The collector
uses the existing probe forward and makes **zero adb calls**. Never touch
`emulator-5554`, start/stop emulators, repair forwards, restart adb, or alter the
owner's process. No roader, hosts 09–18, tailscale, crontab or runtime worktree.

1. The lead supplies window/grant reference, baseline Mac swap bytes, current
   attestation and exercised template paths; owner makes the instance paused and
   ready and runs the live-latency watchdog. Stop immediately on owner/watchdog
   request. `capture.py` enforces window/instance, >=8 GiB disk and <=1.5 GiB swap
   growth. It checks the window before every session command (five-second handoff
   reserve), resources every ten captured ticks and before every seed configure.
   It reads a lead-specified stop file if present. No automatic reconnect/retry.
2. Copy only these worker scripts into the Mac jobs area
   `/Users/sam/.cache/clasher-native-reference/cards/nulls/tools/` using explicit
   paths, with owner-provided inputs in its `inputs/`. Do not sync a worktree.
3. First capture `Wizard.minions.control` and `GoblinCage.giant` once. Measure
   time, compressed bytes, peak rich packet size, available disk, swap growth and
   watchdog latency. Do not infer throughput from old host measurements.
4. Finish the five residuals plus control three times each (18 runs total), using
   the same selected seed/config for each exact repeated script. The deterministic
   seed search repeats from its fixed start; do not change seed if outcomes drift.
5. Run remaining Batch A coverage once each, then B1/B2 once each. Add independent
   identical repeats for any boundary claim and Graveyard if time permits. Focused
   trigger/phase extraction happens after raw data is safely copied; do not spend
   the exclusive slot running Linux comparisons.
6. Stop at the window/watchdog/resource boundary; do not overrun to finish the list.
   Leave paused state and report it to CARD LEAD; owner resumes capture or stops
   the emulator. The worker makes no lifecycle changes. Retain failed output dirs.

Owner-created slot JSON example (values are placeholders, not a grant):

```json
{
  "grant_reference": "LIVE LEAD -> CARD LEAD message/window identifier",
  "start": "<granted UTC timestamp>",
  "end": "<granted UTC timestamp, at most 2 hours later>",
  "serial": "emulator-5596",
  "probe_port": 26795,
  "adb_server_port": 5049,
  "native_version": {"client": "15.535.13", "content": "15.535.86"},
  "baseline_swap_bytes": 0,
  "stop_file": "/Users/sam/.cache/clasher-native-reference/cards/nulls/STOP"
}
```

`baseline_swap_bytes` must be the actual measured value at slot start, not the
example zero. The slot file does not authorize emulator or live-bot operations.

Example capture command, only inside the granted window, using actual paths:

```sh
python3.12 -B reports/cards/nulls/mac_exec.py -- \
  nice -n 10 python3 -B /Users/sam/.cache/clasher-native-reference/cards/nulls/tools/capture.py \
  --scenario GoblinCage.giant \
  --slot /Users/sam/.cache/clasher-native-reference/cards/nulls/inputs/slot.json \
  --template /Users/sam/.cache/clasher-native-reference/cards/nulls/inputs/template.json \
  --gamedata /Users/sam/.cache/clasher-native-reference/cards/nulls/inputs/gamedata.json \
  --attestation /Users/sam/.cache/clasher-native-reference/cards/nulls/inputs/attestation.json \
  --body-names /Users/sam/.cache/clasher-native-reference/cards/nulls/inputs/body-names.json \
  --output /Users/sam/.cache/clasher-native-reference/cards/nulls/raw/slot01/GoblinCage.giant.r1
```

`mac_exec.py` shell-quotes the argument vector and requires one unambiguous
`__RC=<integer>` token. **SSH's exit 0 alone is never success.** Use that wrapper
for slot commands; tests exercise missing/duplicate/nonzero tokens. Mac Python
must be >=3.10 (historical tooling uses the same requirement); use the owner's
existing interpreter, no package installation during the slot.

Initial scheduling estimate: historical native-corpus rich requests cost about
69 ms each, so 500 active ticks suggest ~35 s plus setup/compression per short
run. This is only a planning anchor. The full 106-script slate plus 12 additional
P0 repeats is 118 runs; reserve up to 120 minutes including startup handoff,
measurements, failures, transfers and trigger checks. Reduce the tail if observed
cost or latency is worse. Each run streams compressed data; it never retains all
rich frames in RAM. Do not compress/copy concurrently if the watchdog objects.

Copy recordings to **127x05**
`/mpac/sdicks02/jobs/clasher/cards/nulls/raw/<slot>/` using explicitly named
directories. Verify relative filenames, sizes and SHA-256s on both ends before
claiming a copy complete. No deletion is required. Keep configs, native body maps,
attestations, ID maps, complete raw rich observations and trajectories out of git.
Only plans, code, and small derived per-scenario numbers may go to the lead.

## Fixture format and replay

Each attempted output directory is new and cannot overwrite an older attempt:

- `metadata.json`: version, scenario/script identity, slot, input/code hashes,
  observed status, and complete/failed state; `failure.json` on failure.
- `config.json`, `seed-attempts.jsonl`, `ids.json`, `attestation.json`: raw provenance.
- `setup.json`: `entry.decks`, `entry.start_tick`, `entry.split=train`, plus version.
- `evaluation-only.jsonl.gz`: full ordinary observation, including actual opening
  hand order, cycle order, deck slots and elixir; first row is the replay root.
- `events.jsonl`: only a succeeded schedule plus same-tick hand change and cost
  spending earns `accepted=true` and a non-null `exec_tick`; failed events persist.
- `objects.jsonl.gz`: each tick's `native_id, owner, card_id, body_name, x, y, hp`
  plus max HP/raw body metadata. Coordinates are native integer millitiles.
- `rich.jsonl.gz`: unmodified rich frames for targets, status, projectiles, phase
  clocks and diagnostic rings. HP-only loader does not discard this separate stream.
- `split.json`: local loader compatibility registration, explicitly development
  exploration. It does not add data to historical splits or authorize training.
- `complete.json` only after the full planned horizon and final attestation checks.

The real `bot.fidelity.fixture.load_fixture` loads these without source edits.
`replay.py` reconstructs both existing adapters from the *same captured fixture*,
issues plays at `exec_tick-1`, refuses hand/elixir intervention and does not retry.
Every arm binds actual opening order/elixir, horizon and accepted commands into a
`replay_sha256`, in addition to the name-only scenario `script_sha256`. It records
the actual engine data hash or RoyaleSim table/provenance. Use the CARD LEAD's
reviewed engine source checkout; the runtime worktree is explicitly refused.

On 127x05, with the appropriate existing Python/RoyaleSim environment:

```sh
python -B reports/cards/nulls/replay.py --fixture "$FIXTURE" --source-root "$CARDS_SOURCE" \
  --arm native --ruleset-label nulls-15.535.86 --output "$JOB/native"
python -B reports/cards/nulls/replay.py --fixture "$FIXTURE" --source-root "$CARDS_SOURCE" \
  --arm ours --ruleset-label batchA-base-no-stat-overlay --output "$JOB/ours"
python -B reports/cards/nulls/replay.py --fixture "$FIXTURE" --source-root "$CARDS_SOURCE" \
  --arm rsim --rsim-client 16.402 --rsim-table adapter \
  --ruleset-label rsim16402-adapter-cards15535 --output "$JOB/rsim"
python -B reports/cards/nulls/adjudicate.py --native "$JOB/native/measurements.json" \
  --ours "$JOB/ours/measurements.json" --rsim "$JOB/rsim/measurements.json" \
  --output "$JOB/adjudication.json"
```

The adapter table is the Batch A §4 dispute reference. Separately run
`--rsim-table 160402` to reproduce the wider fidelity report's full table, and
`--rsim-client 15.535.29 --rsim-table adapter` as the nearest older-stat control.
That older adapter label is not the exact native APK/content version. Each is a
distinct arm/run; never combine table identities. Neither the `--ruleset-label`
nor native version metadata applies a stat overlay. Applying a scratch overlay
requires its actual reviewed data checkout; replay records the data hash.

## Per-observable adjudication

`adjudicate.py` compares native/ours/RS for each explicitly evidenced observable.
Zero tick tolerance by default. Missing values/unsupported fields, different
script or opening-state hashes, and mismatched measurement contracts do not pass.

The automatic common trace derivation emits max-HP sets, birth tick multisets,
whole-life multisets and capped/unattributed HP-loss events. It deliberately calls
combat-derived lifetimes/births/movement **dependent**, because stat skew can move
their causal boundary. It is a baseline, not automatic extraction of every native
phase field. Focused P0 measurements require reading the rich trace and adding the
same named observable and evidence/tick window to each arm's measurements file.
Do not invent a native deploy-ready field name before inspecting the installed
probe's schema; mark unavailable fields honestly. Preserve baseline measurements
and put focused revisions in new job files.

See `OBSERVABLES.md` for the measurement record and required controls. Verdicts:

- `AGREE`: this observable agrees under its declared contract.
- `STAT_DIFFERENCE_EXPECTED`: a direct configured/max stat value differs; older
  native content is not a live stat authority. Review ours/RS stat differences too.
- `STAT_CONFOUNDED_REQUIRES_CONTROL`: HP, lethal damage, speed, range or duration
  could shift the downstream event; does not adjudicate the mechanic.
- `RNG_DISTRIBUTION_REQUIRES_REPEATS`: different PRNG algorithms must not become a
  placement bug. Graveyard cadence and spawn-ready ordering remain testable.
- `MECHANICS_SUPPORTS_OURS`, `MECHANICS_SUPPORTS_ROYALESIM`, or
  `MECHANICS_NEITHER_MATCHES_NATIVE`: focused control established mechanics
  comparability; exact native timing/selection/ordering decides that observable.
- `ORDERING_DIFFERENCE`: enumeration differs under an order-sensitive contract.
  Witch semantic waves use `multiset=true`; multiplicity remains significant.
- `MISSING_EVIDENCE` / `OBSERVABLE_CONTRACT_MISMATCH`: no adjudication.

Direct stat fields include HP/shield capacity, configured damage/speed,
hitSpeed/loadTime, lifetime, radius and duration. An observed attack interval,
movement distance, death tick, tower outcome or target set is not automatically
stat-only. Level and capped lethal damage must be accounted for. Promote a
dependent observable to mechanics only after a documented nonlethal, reach/phase
matched comparison or a controlled same-stat arm. Never fix live stat overlays
from this old client.

Per-scenario handoff: version and IDs; actual seed/decks/opening state; all
commands and acceptance receipts; repeat identities; observable value in each arm;
classification and cause/control; first divergence and confidence/coverage;
raw evidence paths and hashes. No raw packets or full official tables in git.

## Offline checks and remaining slot work

- **21 synthetic tests pass**, with all real socket creation forbidden: manifest
  coverage/horizon, residual geometry, tick basis, actual fixture-loader roundtrip,
  fake-server full collector path, strict spend witness, script/version/opening
  mismatch rejection, one-tick residual detection, stat/dependent separation,
  missing evidence, Witch multiset multiplicity, resource/serial stops and SSH RC.
- **106/106 Python engine scripts pass** full-horizon deployment checks, using
  current CARD LEAD checkout, six initial elixir and the declared deterministic
  planning hand. No adapter hand forcing/elixir top-up, rejected play, stalled tick
  or early engine terminal. This is deployability, not native/RS fidelity. Evidence:
  `/mpac/sdicks02/jobs/clasher/cards/nulls/offline-checks/engine-r1/checks.json`.
- Reproduce: `python3.12 -B reports/cards/nulls/test_offline.py`; the real-engine
  check is `validate_engine.py --source-root <reviewed checkout> --output <new job>`.
- No native fixture exists yet. The installed native schema, global tick basis,
  exact version attestation, old-client trigger coverage, actual throughput and
  live latency all remain slot checks. The current Linux venv lacks RoyaleSim;
  its replay path is prepared, not claimed executed. Use an existing qualified
  RS environment after capture; no broad dependency changes here.

READY FOR SLOT: 120
