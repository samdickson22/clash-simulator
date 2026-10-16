# B2 semantic snapshot comparison v1

Status: proposal authorized by CARD LEAD on 2026-10-16; independent review and affected
execution pending. This contract does not accept an engine change. Decision:
`/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/B2-semantic-comparison-decision.md`.

The original `probe_dash_full.py`, strict run PID3422841 and its raw FAILs remain unchanged.
`b2-semantic-snapshot-v1` produces a separate `*.semantic-pass.json` only when its validator
passes. Selected semantic equality is never described as complete serialized equality.
Digest agreement supplies an additional trajectory check, not an exemption for private state.

## Compared state and evidence

The collector exports Python state using the existing `differential.snapshot` and canonicalizes
it through native serde construction/serialization **without stepping the expected state**.
It advances the actual Python/native pair once per tick and compares both directions. Entity
IDs, players, next ID, clocks, position, stats, targets, hit multiplicity, strike/chain state,
buffs, scopes and every unlisted field remain strict under the original six-decimal numeric
normalization. Hit-ID ordering is immaterial, but contents and duplicate counts must match.
The original baseline compares alive entities and omits immutable config; v1 retains that
scope and hashes config inputs, exporters and the native libraries independently.

Each run records every applicability item with full field path, entity class, raw Python/native
values, reason and disposition. Identical records may share a list of observed ticks; distinct
raw values remain separate records. `raw_first` and `raw_differences` preserve the first raw
cache discrepancy before semantic applicability. All distinct semantic differences are kept
while the public trajectories agree. A digest divergence ends continuation and fails the run.
There is no limit that silently truncates or accepts extra differences. The original immutable
raw comparator/run remains the reference for the uncorrected exporter and earlier strict FAIL.

## Applicability matrix

| Field/path | Class and exact scope | Rule and recorded evidence |
| --- | --- | --- |
| `public_speed_base` | Troop | Independently call the actual Python entity's `_unslowed_movement_speed()`. Compare against the actual non-null native cache, including zero. Only native `None` selects `stats.charge_speed` at charge>=10000, otherwise `stats.speed`, exactly as `leaf.rs:128`. Record raw cache values as `effective-value-compared`. Never substitute a current-charge estimate for a non-null historical cache. Any unexplained phase/history mismatch fails. |
| `public_speed_base` | Building, including towers | Inapplicable only for this field on this exact class. `leaf.rs:127` gates the sole cache read to Troop. Building shots become Projectile; fresh spawn/death/Clone templates supply any later Troops. Record raw values and source reason. |
| `public_speed_base` | Projectile | Flight uses `stats.speed`. `combat_one` can copy actor history into the shot; `projectile_children` can copy it onward but retains Projectile class. Materialized Troops use fresh templates. No exemption for travel speed, aim, target/homing/delay or hits. Record raw history rather than reconstructing it from the current shooter. |
| `public_speed_base` | SpawnProjectile | `delivery_tick` clones `card.spawns` Troop templates, not the live delivery object. Dynamic source-sentinel/child-continuation witness required, both seats. |
| `public_speed_base` | RollingProjectile | `rolling_tick` clones `card.spawns`; `rolling_character_tick` never retypes the object into Troop. Dynamic BarbLog source-sentinel/child-continuation witness required, both seats. |
| `public_speed_base` | TimedExplosive | `bomb_tick` supplies `config.bomb_children` to `spawn_death_templates`; `clone_payload` transfers clone/HP/shield status without the cache. Fresh actual-template check plus source inspection bounds this exemption. |
| `public_speed_base` | Any other/new class | Strict raw comparison. An unknown class receives no exemption. Class disagreement cannot acquire an exemption from either side. |
| `aim` | Projectile and SpawnProjectile | **Compared**, projected from actual Python `target_position`, the last committed endpoint. Use the same projection at initial native construction and each expected comparison. Do not export the target's newer position before homing commits it. `shot_target`, homing, launch delay and damage remain strict. |
| `birth` | Only entities with no Python `_native_object_birth_tick` | Existing strict-r2 baseline exclusion for synthesized birth; raw values/reason recorded. Recorded birth remains strict. |
| `cooldown`, `route_occupied` | Troop only | Existing strict-r2 baseline projection/occupancy representation exclusions; clock and force_due stay strict. Raw values/reasons recorded. |
| `age`, `attacked_current`, `lane`, `last_target`, `started`; `stats.max_hp`, `stats.sight` | Projectile with stats.name exactly `Tower` only | Existing strict-r2 actor-clone representation exclusions. No expansion to other shots or fields. Raw values/reasons recorded. |
| `finish_tick`, `landed_tick`, `push_tick` | Only when both sides encode unset as -1 or 0 | Existing strict-r2 equivalent representation. Different raw values/reason recorded; every set value remains strict. |
| Every other field | All compared classes | Strict; no additions on a failing case. Meaningful metadata failure remains FAIL even with equal digests. |

## Cache propagation proof for the frozen source

`rg -n public_speed_base engine-cards/src/*.rs` finds one read (`leaf.rs:128`), the field
declaration and explicit writes/resets. The read is under `class == "Troop"`. `rg -n 'class = '
engine-cards/src/*.rs` finds only live retyping to Projectile (`lib.rs:2383`) and
RollingProjectile (`lib.rs:2422`), never Troop. A live non-Troop cache cannot become applicable
through a class change in this source. All currently reachable Troop constructors are bounded:

| Source/constructor | Cache provenance at materialization |
| --- | --- |
| `lib.rs:2380 combat_one` | Actor clone becomes Projectile; historical cache may persist but class stays non-Troop. |
| `projectiles.rs:148 projectile_children` | Clones a Projectile; does not change class to Troop. Child travel stats and hit IDs remain compared. |
| `lib.rs:1160 rolling_tick`, `c56.rs:592 delivery_tick` | Clone fresh `config.cards[...].spawns` templates. Never copy parent cache. |
| `c56.rs:170 bomb_tick`, `lib.rs:3507 spawn_death_templates` | Consume fresh configured bomb/death child templates. `clone_payload` changes clone/HP/shield fields only. |
| `clone.rs:5 clone_spell`, `clone.rs:88 clone_payload` | Clone an immutable Troop clone_template; no cache transfer from live donor. |
| `scope.rs scope_child`, Graveyard scope tick, curse child creation | Configured fresh child/spawn templates, not live parent clones. |
| `spawn.rs` production/wave children, `souls.rs` skeleton creation | Configured fresh prototypes, not live parent clones. |
| `lib.rs death_effects` | Configured death-area/object/child templates; any Troop is fresh. |

At each initial native state, `fresh_troop_templates` traverses the actual native config and
all live clone_template subtrees. Every encountered Troop template must have a null cache and
at least one must exist. The resulting actual paths are recorded, not inferred from a Python
configuration default. A non-null template is a hard collector error.

Dynamic witnesses seed only the actual native BarbLog/RoyalDelivery non-Troop source cache
with sentinel137, leaving Python unchanged. Both seats must materialize child Troops and
continue them for20 ticks. Every child's actual native cache/fallback must match actual Python
base speed and must not carry137. Poisoning that now-Troop cache with137 must be detected.
Other semantic or digest drift still fails the witness; it cannot pass solely on the speed
assertion. Its applicability records and first raw differences are preserved too. Source
inspection proves the other constructors; this is not claimed as dynamic coverage of every
death/production route. The proof is restricted to the source hashes in the review/identity.

## Export gap and negative controls

The shared production `live_snapshot` exporter is **unchanged**: it can project a tracking
projectile's current target position instead of its last committed `target_position`.
The probe-only projection addresses expected-state observation; it does not repair that
production exporter or establish correct runtime root construction. The earlier arrow failure
receipt did not retain enough delay/birth detail to attribute that particular instance to
launch delay. The independent diagnostic remains in `evidence/snapshot-cache-diagnostic-20261016.md`.

Local stdlib controls use the actual source Python unslowed/debuff methods. They reject wrong
native cache, wrong Python original speed/slow recovery, a cache/fallback change across a
charge threshold, wrong committed aim, target ID, strike/chain target, launch delay, hit
contents/multiplicity, buffs and projectile travel speed. Unknown-class cache mismatch and
poisoned nested Troop templates also fail. The semantic validator has rejection controls for
missing raw/applicability evidence, missing offsets, truncated comparisons, errors, wrong
mutant class/field/seat and a mutant intended hit difference whose **own** digest disagrees.
Dynamic guard deletion A (ranked Lightning) and B (rolling Log) must expose intended hit-set
differences in both seats; B's intended difference must occur with digest equality.

## One affected execution, after review and the old run ends

The frozen native libraries remain out4 `7738f9d2...`, mutantA `ff74a2fc...`, mutantB
`2964dec3...`; staging checks full hashes and matches every tracked engine file against the
already-built frozen tree. No source substitution, rebuild, shared engine/export edit or
runtime/pin change is part of this proposal.

`stage_semantic_v1.py` requires a review receipt matching this document and every new affected
tool. It refuses a live old3422841 process/group, a remaining old CPU lease, unexpected old
PASS, missing phase1 terminal receipts, or any prior FU/Clone/scenario JSON. It preserves
old inputs/logs/FAIL receipts and hashes them into the new identity. A fresh isolated tag/dir
is exclusive: rerunning the tag fails rather than replacing files. It queues ONE normal
`nice -n15 cpu_job.sh4` launcher on08, writes PID/PGID/args/library/source identities, and
does not kill/requeue an existing job. Lost acknowledgment requires inspection, never retry.

The old third shard stopped on `config(('Executioner', ...))`: canonical gamedata has `AxeMan`
and no Executioner alias. The new fixture retains case label `executioner` but explicitly
uses `AxeMan`; an AST/data preflight checks all31 fixture names against frozen data/aliases.
Original shard3 remains a failed collection and the strict run remains FAIL. Because its
runner stops after any failed phase, original FU/Clone/scenario phases were not entered;
the scheduler verifies that fact before running those unchanged fixtures once here.

The reviewed runner uses at most four processes: four semantic shards; then mutantA,
mutantB, descendants and first-update; then sequential Clone pair plus three parity scenario
workers. It waits each exact PID, records each exit, stops on a nonzero phase, and validates
JSON counts/content before an atomic versioned semantic receipt. The62 case/seat rows each
require40 accepted actions and all45 compared ticks for an unmutated PASS. Seven critical
source families require observed Python source-specific guard queries during dash travel in
both seats. All other actual query counts, including zeros, are reported as coverage limits.
No claim that every nominal selector was dynamically exercised is permitted.

Separate unchanged parity evidence requires42 first-update case/seat rows (exact action
counts; six setup-only names), six Clone bounds cases, two exact combined water/building
recovery cases,28 B2 root scenarios,28 scratch-stat scenarios and42 BatchA scenarios.
All original meaningful action/exception gates remain. Source, Python exporters, native
libraries, fid helpers/pool, both gamedata arms, es_common and preserved strict evidence are
hashed at admission and checked again before any semantic receipt.

Rollback: retain and use the original strict comparator/raw FAIL; revert this reporting/probe
contract if invalidated. A queued affected launcher may only be stopped by its exact verified
owned PGID under existing authority; no automatic requeue of any frozen arm. C56 parity,
fresh independent final engine review and B2→C1 integration are still outstanding acceptance
gates. No main merge or live pin change is authorized here.

Communication remains Sam strict silence: no progress/result/queue/commit acknowledgments;
only blocking parent action, urgent live failure, explicit request or essential owner handoff
may be messaged, max2 sentences+one path. One automatic final result after the whole assignment.
All future child briefs must carry this rule; questions go direct parent, never input tools.

## Frozen source proof hashes

These hashes bind the applicability proof; staging refuses local/frozen source drift.

- `engine-cards/src/leaf.rs`: `274c5956c7c3f6f961c7d0e983c0681390618b28d13eb3dd338fb7e3ac19ec55`
- `engine-cards/src/lib.rs`: `b222283043d2cceb56335eef667194bb832d154768d32dc5259e5d1d6aea1a7d`
- `engine-cards/src/projectiles.rs`: `c1c75debb35723f7aa292658be382596dba39f5282f45d0fe116fa624be63b32`
- `engine-cards/src/c56.rs`: `a6279dd8044a5ae90280d07798708e6557eadb07aebaff3b85c382a15c3f5b7e`
- `engine-cards/src/clone.rs`: `c940249d5789b7de59465aa62e5bad33bb8a72266dd2cf98ab788319b97dc004`
- `engine-cards/src/scope.rs`: `1c17032bf59ee198e5bd6b393fd644e3a10fc1b9eaa150cb593adba1cdf1f374`
- `engine-cards/src/spawn.rs`: `c6cf27771140d7fe514fde3ea47b82500b462264bfc42033407a3f8ba826ec83`
- `engine-cards/src/souls.rs`: `aa7f97f7d5a163f3deb94a846278f9aa6a657da4a5000bb40d45d5041226e0db`
