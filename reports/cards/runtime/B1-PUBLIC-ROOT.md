# B1 compatible public Resources and graph reconstruction

CURRENT: speed-corrected sourcef89b8acd5 has fresh independent Sol-high reviewr4
APPROVE; admitted combined-source acceptance remains pending. Historicale0
approval was superseded by the owner-found speed defect before execution and
does not accept these bytes. Baseebab18cc, engine aliasc13249919. Authority:
`reports/cards/reviews/B1-public-identity-root-policy.md` on cards/lead. No
published r3 root/evidence, model, vocabulary, active pin or consumer deployment
is changed by this branch. B1 owns final integration/testing sequence; lead owns
main integration and consumer owners own deployment.

## Template selection

The sensor and exporter use B1's explicit existing ThreeMusketeers aliases for
all three generated mechanical bodies and actual shots. The fixed360-token
vocabulary (existing token326) and model shapes/rows remain unchanged. Public
kind distinguishes body and projectile. `Resources` deliberately selects
`ThreeMusketeer_Rework_Character_1` from the static formation, asserts its700ms
load and rework selector, and registers an actual isolated shot created with
that member's engine projectile factory. It requires both actual sensor tokens
to agree with the declared existing alias. This replaces only those two exact
template keys. Normal Musketeer and all C56 entries keep their existing priority.
The actual shot template normalizes native movement speed with
`round(shot.travel_speed*50)`, exactly the conversion in `live_snapshot.live_entity`.
Raw `differential.entity` exports zero `stats.speed` for ordinary Projectile
objects, despite their positive `projectile_speed`. The scoped installer rejects
zero/mismatched movement speed. Actual native motion controls require1000logic
units/50ms and about one tile of positive displacement, independently of native
restart equality; deliberately zeroed controls must remain stationary.

The public model deliberately uses700ms for every rank; it loses rank2's650ms
load. Engine names, loads700/650/700, formations, stagger, selectors, source
names and clone mechanics remain intact. Config traversal/list ordering or the
first sampled demo cannot select a different rank or ordinary Musketeer shot.
Unknown combat phase, attack choice, target and clone status still use the
existing deterministic template defaults. These are approximate roots, never
exact reconstruction of the live engine state.

## Goblin Giant public graph

Isolated configuration/demonstration `mount` references are not live IDs. A
single helper in `engine-cards/public_root.py` is called after row reconstruction
in BOTH `Resources.root` and `ExactLevelRoot.payload`, after level deltas. It
clears stale top-level mount/rank references on GG/rider bodies and their shot
prototypes. It does not reinterpret unrelated graph mechanisms or C56 rows.

Only observed Troop/GoblinGiant parents and Troop/SpearGoblinGiant riders
participate. Parents expose the static two-rider geometry already serialized
in their templates. Each observed parent provides two rank slots. Candidates
must have equal public owner and remain within1.15tiles of the parent. Interior
points must also lie within0.25tiles of the static900unit radius. Character
creation clamps to[.25,extent-.25]; later carry can leave the arena and public
coordinates clip to[0,extent]. Points on these known clamp edges (float32
tolerance1e-4tiles) may have compressed radii. Arbitrary compressed interior
points stay unsupported. Preferred slot distance compares the raw static offset
and both known clamp projections using the engine's integer trigonometry.
Deterministic
augmenting matching fills distinct slots up to capacity. Source IDs, demo links,
private targets, rank state and prior frames never enter the matching.

Observed heading is end-of-tick, while rider positions used start-of-tick
heading: radial admission permits turns and slot assignment is a deterministic
approximation. Multiple compatible/coincident parents count as ambiguous;
public geometry and then new row IDs break ties. A new row ID breaks only
indistinguishable public ties, never claims to recover an engine ID. Reordering
distinguishable public rows preserves geometric relations; indistinguishable
coincident graphs have no identifiable true pairing under v5. Clone rows are
paired with the same policy without inferring hidden clone status from HP.

No absent row is filled. Missing rider rows leave slots empty. Orphan, remote,
wrong-owner and over-capacity riders raise `PublicGraphError` with unsupported
row counts/IDs, rather than leaving stale references or fabricating parents.
Released ordinary SpearGoblin children and Projectile rows are never attached.
Live GG template clone prototypes remain closed immutable static graphs: native
Clone remaps those prototype-local IDs itself. They are future spawn capability
templates, not an observation-to-hidden-ID lookup.

## Level consumer

The wrapper shares the same canonical templates and graph helper. Explicit
700ms remains700ms at every exported level; "ExactLevelRoot" names level stat
selection, not exact hidden rank/phase recovery. Level exports now include
BattleHealer `create_areas` and `hit_areas`; their distinct public spell names
disambiguate shared-empty-name HealPulse bodies and select the correct producing
card and level payload. Direct spells retain their existing qualified names.
Level-specific clone capability prototypes follow their producing bodies for
the scoped GoblinGiant/ThreeMusketeers/BattleHealer producers only. Existing C56
prototype defaults remain unchanged; this does not broaden into unrelated Clone
or level-policy changes.
projectiles never inherit body clone capabilities or HP. Dynamic mount/rank
are excluded from level deltas and reconstructed only after deltas.

The level cache namespace includes the full static config digest, since new
Python templates can retain identical native/data pins. This avoids accepting
pre-B1 level exports with missing pulses or changed rework shapes. Existing
direct-spell per-seat approximation, unsupported exports, private phase/target
defaults and opponent level estimates remain documented consumer limitations.
Mirror and ordinary casts can emit the same public carrier identity. The plain
root retains its level11 template default; the level wrapper uses its existing
producing-card level rule and public deck/estimate, not hidden cast provenance.
Neither claims to recover a mirrored carrier's true level from a shared token.
The exact exported pulse/body fields are checked conditional on that level
selection. Public rework rank and combat phase remain equally unobserved.

## Validation interface and rollback

`python3 -B reports/cards/runtime/tools/test_b1_public_root.py` runs only stdlib
fixtures/source-extracted level methods on05 (21cases at corrected checkpoint;
16cases at superseded first checkpoint,19at superseded second checkpoint).
The actual admitted phase imports `probe_b1_public_root.py` and calls
`run(R, fair_player_module, fresh_output_json)`, reusing B1's ONE widened cached
Resources build. Its scope must include Clone in addition to B1's declared
public cards (Cannon is already C56). Sixteen actual public-row cases cover both seats, multiple and
coincident GGs, actual Clone rows, reorder/truncated parents, plain roots,
forced level11/9 consumers, distinct healer payloads,700ms rework defaults,
future native Clone graphs, leveled Cannon shot damage/unit HP, and full native
reload/continuation.32boundary fixtures cover eight walls/corners for both seats
at actual creation/carry hooks, through plain and forced-level consumers.
Native snapshots omit zero rider_rank: probes use its documented default0,
while always requiring valid mount ownership/type/ID. Two byte-equal
controls isolate the graph helper on C56 boards; they do not replace B1's full
old-vs-new source acceptance gate.
Eight positive native rework-shot movement witnesses (plain/level, levels11/9,
both seats), each with a zero-speed control, are included in the existing16
groups. No extra Resources build or competing phase is introduced.

B1 `public_emitted.run` separately owns all3 actual members/shots, GG shots and
released children, healer spawn/hit pulses and both TimedExplosive carriers.
Only fresh exact combined source/consumer paths may accept this change. The
older run02 mirror stage5 file resolves to old r1 fair_player: staging must bind
the repaired fair_player AND new engine-rs/public_root.py, and preload the owned
bot package before hardcoded shared-bot gate imports. Host staging/launch review
is separate from correctness/fair-information review and must precede execution.

Rollback: revert only new alias/root commits from the isolated candidate. Keep
the fixed pre-alias B1 ref/native, original source5c8 gate1634216 and all failed
artifacts immutable. No old acceptance is transferred to new Python source;
no deployment, opt-in root release, pin/model change or sealing is implied.

Implementation review history: native independent `/root/b1_public_root_review`, Solhigh,
roundr3 APPROVE at exacte0e9f634e28f6cbc8bdd10631a6b3437d69dfef2, subsequently
invalidated for acceptance by the pre-execution projectile-speed finding. Preserved r1/r2
REQUEST_CHANGES and r3 approval receipts record every finding/response/hash.
Root patch commits8aab1b2b5→fa3622618→e0e9f634e then a separate speed correction
atop aliasc13249919; no unrelated
shared edits.21stdlib tests PASS; native/public/gate acceptance remains pending
B1's one separately host-reviewed, exact-source admitted sequence.

The consumer inventory also found LIVE LevelRoot's copied scaled path. That
protected source remains read-only; a separate guarded same-helper patch and
source-extracted fixture evidence are in B1-LIVE-LEVEL-PATCH.md. LIVE owner owns
integration/native acceptance. The two owned consumers are the actual scoped16
gate paths; do not silently count proposed LIVE patch as deployed/tested native.
Fresh reviewr4 at exacte f89b8acd5f8b1927fef8f56ad4729269dff4fdc6 APPROVES full
combined corrected implementation/scoped probe and separately the proposed LIVE
patch. Receipt `receipts/b1-public-root-review-r4.md` binds hashes and real gate
conditions; active source packet-r4 supersedes preserved historical packet.
