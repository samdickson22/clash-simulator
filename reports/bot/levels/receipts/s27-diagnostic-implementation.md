# s27-m02 offline diagnostic implementation receipt

Updated 2026-10-16T11:03:35Z (UTC), source host127x05.

Status: SOURCE COMPLETE, awaiting fresh independent review. No project imports,
Python execution, tests, sync, jobs, commits, GPU/emulator/account actions or
runtime writes occurred. Only the six new files under
`/mpac/sdicks02/repos/clasher-bot-levels/bot/levels/diagnostics/` and this receipt
were written. Existing completed harness and the active R14 paths were preserved.
No running processes were started for this assignment.

## Files for review (SHA256)

| File under bot/levels/diagnostics/ | SHA256 |
| --- | --- |
| README.md | cbc6397ed3003a9325531556c6c23bae1799c9b2c43eeac02ddad928cdc8954e |
| __init__.py | 552d25e037116d369e8ccf5bff3a7339d3bddb170c8c8064193eead0efb89179 |
| live.py | 1b4c5f2ed254fd9a1ae292601bdeb66433f963f2b466b58fbd40fa7e521b428f |
| protocol.py | dcdab0b6e413af4c638d2dd8a8c9555ffceeeb332b326f158a3396ca96daff29 |
| replay.py | 05bf92c80867d91246ab3ef2f58753f1bd0e60191e7bdfcfd42462fd7ace5b83 |
| test_replay.py | 03d4cc3de65d2556d59fbc30b446d8cba87eaa330332bede647a4e23ca07bc80 |

The README describes protocol, scope, normalization, provenance, offline-only
rollback and the proposed bounded01 CPU-wrapper/nice commands. This new package
is below the primary runner's immediate source glob and is not imported by any
primary pilot path. It reads primary/runtime/live sources for provenance only.

## Decisions and input evidence

- Verified copied perception hash
  `0238b560389741ad4d84240af6bf4d9d786d57c858a4abafa94567ab17a764c2`
  and session-config hash
  `dc77804fbe52b541341dd974157f4e72b0b6849a315dbf436dbd7bf6a285457e`.
  All seven public-input hashes are pinned in protocol.py.
- Data-only inspection:343 perceptions, frames175–517;164 decision polls90–905;
  23 original search opportunities; five acknowledged taps26–30. These are
  input counts, not executed replay results or claimed action agreement.
- Live source already normalizes crown `hp_read` by actual inferred maximum.
  Translator consumes `hp_frac` unchanged. The suspicious template division is
  for unit `hp_abs`, not these crown rows. Both arms therefore keep identical
  recorded fractions; no joint normalization bridge is needed. King59 at
  frames500–509 is fraction0.0178, giving58.9536/3312 in a correct B root.
  One early enemy king maximum-inference inconsistency (frame175:2400/fraction1)
  is exposed rather than rewritten. Actual per-root HP/maxHP and fraction
  consistency are audited without another root/RNG call.
- Window is displayed floor(clock_s)134…176 inclusive. Last clock is134.741730583;
  no exact134.000 state is invented. King59 is already visible at136.964027333.
- Original live writer adds fractional tick only as log metadata. The recorded
  driver removes it and uses the actual anchored ClockTracker. Frame207 is the
  concrete99.60 -> poll100 boundary that flooring would get wrong.
- Parent explicitly chose conditional reconstruction of action233 at
  frame234/poll170 as an **UNVERIFIED INTERNAL RESERVATION**, never a sixth
  tap/ack/verified actual play. Queue evidence must show exact Giant813/160
  replacement by233/170, or abort. The observer preserves unchanged
  LiveSession._confirm_pending/_reconcile. Any later public-HUD inferred event
  and subsequent context are tagged conditional, never acknowledged/verified.
  Action233 alone creates no public event. A focused fixture reproduces the
  unchanged pending-length failure and conditional later HUD confirmation.
- The writer omitted wait durations and hid timed-wait IDs in filtered stats.
  No duration is guessed: recorded `source:search` gating selects matched
  opportunities; blocked/off-cadence polls still update both D1 pollers.
  Common session timer and effective shadow search gating are documented
  separately. Any unexplained channel/context contradiction fails closed.
- The recorded Mac rl5-v10 checkpoint is not substituted. Recorded commands and
  gating drive the common session, so its fast policy is irrelevant to the
  unbounded serial shadows. This is not literal original-command reproduction.

## Implementation/evidence contract

Real LiveTranslator/LiveSession public pipeline; one recorded common command
channel; independent deep-copied A/B views; direct headline serial base objects;
post-start root/leaf hooks; no RoyaleSim placement import/install. B uses the
fixed public account levels (Cannon6 deck), towers6/6 and fixed OpponentEstimate,
not true enemy levels/deck/order. Accepted conditional prior installed before
players and checked per actual controller before/after every poll. Accepted
original/restricted ordered scope digests are pinned.

Existing-only parsed cache with qualified native-json-v1 support receipt,
complete supported-card entry-or-error coverage, raw+canonical loaded-object
digests and frozen future loads. No exporter/receipt creation. Known unused
errors remain visible; playable unsupported cards/bodies fail in ExactLevelRoot.

Fresh outputs include preserved launch receipt, states/error JSONL, full identity
receipt and paired report JSON/Markdown. Identity covers all bot/runtime Python,
native/checkpoint/catalog/pool bytes, env.sh/effective behavior env, actual loaded
dependencies, public vocabulary/statics/config/templates and loaded learned
model weights/metadata. Source/runtime/cache mutations fail closed. Every
failed state remains in the opportunity denominator; native fallback is an
error, not an accepted decision. Reports expose matched opportunities, action
changes, Cannon availability/affordability/legality/home-defense examples,
first differences, actual roots/config reports and CPU/wall diagnostics.

No causal, win-rate, counterfactual-outcome, literal-live-equivalence or primary
pilot-readiness claim is made.

## Validation status and next

Only source reading, data-only JSON inspection and shell SHA256/source checks
have occurred. No syntax compilation, pytest or Runtime/model work has run.
Fixture source covers independent shadows/common command ownership, clone
isolation, missing/catch-up polls, known own-slot contradictions, unacknowledged
commands, pending replacement plus unchanged conditional HUD inference, public
clock rounding, tower59/maxHP regression, missing towers, failed paired coverage,
native fallback rejection, actual post-start B hook/no additional RNG, existing
cache immutability/errors/partial coverage, model/native/data/env tampering,
duplicate indices/input hash rejection and receipt serialization.

Next action belongs to parent: fresh independent review of these exact sources,
then reviewed sync and bounded01 fixture/replay commands in README. Source
implementation has no unresolved design question; execution remains unapproved.
Do not treat fixtures or source reading as a passing replay.

Communication/handoff rule retained: no routine progress, acknowledgement or
milestone messages. Whole-assignment automatic final result once; questions or
essential dependency handoffs only to owning parent, max two sentences plus one
receipt path. No descendants were spawned.
