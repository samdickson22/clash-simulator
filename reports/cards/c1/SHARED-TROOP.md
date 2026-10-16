# Shared Troop triage and witness ledger

2026-10-16 UTC. This is new work after launcher repair acceptance, under CARD LEAD's
`/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/B2-C1-integration-contract.md`.
No engine change, new build, sweep, gate or selector copying has occurred here.

## Evidence levels

| Family | Established evidence | Not yet established |
| --- | --- | --- |
| Zap route history | Frozen B2 summary: blue10/40 failed, lead1 first relative0, facingY750/1250, later route/direction differ with equal digests. Source control independently executes the unmodified reference route functions and reproduces750,250,-250,-750 and the single pop/new direction254,-28. Python finishes frozen-route work after special movement; native dash returns before it. This is a forced-state continuation mismatch. | Exact constructor stun/frozen/nav/target values were not retained. Residual Zap stun is an inference. Ordinary gameplay reachability and complete post-fix continuation are unproved. A route alone does not invalidate a fixture. |
| ElectroDragon heading | B2 blue30/40 failed, lead6 relative14 Troop8 facingY-1000/0. Python `Entity.face_towards` preserves heading when the displacement quantizes to zero; native combat writes zero unconditionally. Source control executes that reference routine with exact-zero, quantized-zero and nonzero displacement controls. | Actual first-bad attacker/target positions, IDs, prior heading and component phase were not captured. Coincidence remains a candidate cause, not dynamic confirmation. |
| IceSpirit mode stats | B2 blue36/40 failed, lead0 relative23 Troop8 ordinaryfalse/true and projectile_slow_multiplier1/0. Source controls execute actual `supported` and exporter multiplier expression: kind0→2 changes ordinarytrue→false, and projectile buff0 becomes carrier slow1 (or0.7 under a retained slow). | Exact live kind/launch phase, actual config/modifiers, full state and descendant continuations have not been captured. No inert-field claim, exporter correction or normalization is authorized. |

`shared-troop/source-witness-v2.json` retains the exact old difference lists and their
source file hashes, without claiming to possess the missing full roots. Its
`source-receipt-v2.json` binds the command, source bytes and deliberately limited
local AST test. That test imports no engine/native, performs no battle simulation
and supplies no native parity, gameplay reachability or acceptance result.
V2 also calls the real reference finalizer on explicit post-transport states and
its dash dispatch on explicit standing/travel states. It preserves facing with
no stun, no frozen_moving or no route, verifies facing before external movement
and route advancement after it, and demonstrates the stopped-standing versus
forced-stunned-travel guard difference. These remain source controls. Original
v1 output/receipt remain intact; the inspection tool was expanded for v2.

Preparation review r1 at b66b8f538 **REJECTED** the JSON inspector's outcome
projection and constructor timeline checks, not the underlying source triage.
Full independent verdict/commands retained in shared-troop/REVIEW-preparation-r1.md
and its receipt. Corrections now preserve all owner outcome/error fields, complete
later legacy/natural differences and missing-versus-null result keys; imported
template/full-root blocks remain explicitly in the hash-bound raw capture. Typed
integer frames are anchored to constructor+relative index, with the frozen45-frame
window and recorded-count bounds. New tests reproduce both rejected sequences and
the collector's CAPTURE_COMPLETE wrapper with explicit FAILs. Fresh independent
exact-commit review remains required before treating the inspection tool as ready.

Fresh preparation r2 **APPROVE** binds exact
2105c29595ddd2d684446b80f6446435f1039c25; full verdict and exact independent
commands/hashes are in `shared-troop/REVIEW-preparation-r2.md` and its receipt.
Both preparation findings closed; current source/cleanup AST witnesses were
reproduced byte-for-byte and strict JSON controls passed. This approval covers
preparation only. Actual captures, dynamic causes, ordinary reachability, engine
fixes/parity, fixture classification, host execution and actual coverage remain
unapproved and open. Original631ac/tool approvals are unchanged.

## Read paths and scope constraints

- Zap: `Entity.finish_movement_tick` (`entities.py:389`) runs from the movement
  `finally` (`battle.py:871`), including after the Bandit special movement return.
  It faces the retained waypoint and advances at most one route node when
  stunned + frozen_moving + route, even with no remaining external vector.
  Native `dash_movement` (`src/dash.rs:111`) applies travel/external movement and
  returns through `movement_one` before its frozen-route branch. The existing
  pushback branch already performs equivalent frozen finalization. A candidate
  correction must preserve its post-transport timing, zero-displacement heading
  rule and one-node projection threshold; it must not erase navigation or stun.
  Normal `BanditDash.on_movement_tick` checks stun before standing/launch, while
  direct `_launch_dash` does not. Capture both paths; do not generalize a synthetic
  mismatch into a gameplay bug.
- Heading: Python combat calls `face_towards(current_target.position)` before its
  stun return (`entities.py:3912`). Native engaged combat's assignment is at
  `src/lib.rs:2295`; natural `move_one` already has a nonzero guard at1776.
  Facing feeds avoidance (`lib.rs:1941`, Python entities.py3318), spawning angles
  (`spawn.rs:93`, death spawn lib.rs3646) and persisted snapshots. It is meaningful
  continuation state even when the current digest agrees. A global guard may
  affect C56; no identity waiver or comparison exemption is available.
- IceSpirit: `IceSpiritFreeze.on_attack_start` changes the carrier to
  entity_kind2/self_projectile; `ordinary_combat_clock.supported` explicitly stops
  supporting that mode. `differential.entity` derives ordinary and the multiplier
  from the live entity kind, whereas native launch (`lib.rs:2420`) only changes
  spirit/entity_kind/launch/shot_target/aim and retains initialized Stats.
  Native spirit object flight uses spirit_speed/radius/stun and damage
  (`spirit_tick`, lib.rs1028); its normal combat/movement/status passes skip
  spirit. This does NOT prove all ordinary readers unreachable: end-of-frame
  target-death cleanup at3407 still branches on stats.ordinary for living
  entities, and a reloaded snapshot preserves these mode stats.
  Generic projectile status reads projectile_slow_multiplier in projectiles.rs127,
  but Spirit flight follows its separate branch; exact config/read-path proof is
  still required, including optional `config.spirit_areas` and ElectroSpirit chain
  descendants. Spawn/Clone use fresh configured prototypes, not permission to
  drop mode-stat comparisons. IceSpirit belongs to C56, so any mode-stat fix must
  preserve the required exact C56 results.

## Captures and ordered integration

Bounded Astra source diagnostic completed; full result in
`shared-troop/ICE-MODE-DIAGNOSTIC.md`. It supports conditional on-launch runtime
mode synchronization, not an exporter workaround. The retained slow-only minimum
must exclude movement_mode/haste and percentage rounding (so `slow_percent(false)`
is unsuitable). More subtly, Python target-removal cleanup still consults an
existing ordinary clock after kind2; changing native ordinary alone changes which
cleanup predicate is used. Preserve the retained clock and test started/timeline
disagreement, target death/launch and midflight clone/reload before accepting any
two-field fix. Captured roots still required. These are new design constraints,
not proof that the retained dynamic mismatch has this cause.

B2 owns fixture validity and collection. Direct owner requests sent11:31–11:41Z
ask for immutable constructor and paired pre/post-first-bad roots for all three
old cases, with source/native/tool bindings, plus normal acquisition. B2's
`evidence/B2-C1-CAPTURE-INDEX.md` confirms current frozen collector contains only
summaries; it cannot recover roots from them. Its11:36:39Z observation has existing
08PID/PGID3586969 active, lease4 and24/62 rows. Do not duplicate/poll/restart that
owner's job. B2 prepares one reviewed bounded capture after it becomes terminal.

Frozen B2 source receipt: reporting commit203beac3a plus six engine WIP paths in
`semv1-admitted-identity.json`; reporting head697d0a24d is not an engine commit.
Native7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff
is not C1 native631ac or an integrated build. Preserve strict3422841 failures,
semantic3586969 failures, every offset/seat/denominator and all C56 artifacts.

Current source e6b017ff6 and engine tree64ed8e5bb66bff6cbe0e746ec59fbd0dd36b48f7
remain the original focused f68e5f80f/native631ac source. Existing launcher97171f5
approval and original focused approval remain scoped to those exact artifacts;
new fixes cannot inherit them. No changes to approved comparator/followup/tools.

After exact roots: demonstrate each supported cause, develop narrowly scoped
source changes and strict full-state continuation/clone/reload/negative controls,
then obtain genuinely independent commit-bound review. No B2 selector copying.
CARD LEAD must supply a frozen isolated B2-first integration prerequisite before
combined builds/coverage/final C1 C56. B2 exact-source C56 precedes combined C1
C56. All applicable retained failures require a fix or separately reviewed,
evidence-backed fixture classification; no filtered PASS or new applicability
exclusion. No main publication/runtime/live pin action is authorized here.

Rollback: discard/revert only new scoped source/probe commits, keeping all old
failures, original source/native/tool approvals and raw receipts intact. No runtime
rollback is needed. Host-touching scripts require independent review before use;
new bounded diagnostics use normalCPU<=4/nice15/thread limits on04/08 only.

Sam authority: make confident reversible decisions within ownership; uncertainty
labels alone do not defer routine work. Missing information goes directly to the
existing owner/parent via t3_thread_send(auto), never user-input tools. Strict
silence permits only actual action-needed blockers, urgent live failures, explicit
requests or essential owner handoffs; max2sentences+1receipt path. No routine
results/status/ack DMs. One automatic final delivery when this whole assignment is
done. Future delegated briefs carry these rules; no tiny-step delegates.
