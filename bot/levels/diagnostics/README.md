# s27-m02 recorded-world diagnostic (source review pending)

This package is isolated from the primary pilot. It is not imported by its
runner/factories and installs no RoyaleSim placement compatibility mask.
No diagnostic execution, imports, tests, sync or jobs have been authorized yet.

## Input/source audit

The copied perception SHA256 is
`0238b560389741ad4d84240af6bf4d9d786d57c858a4abafa94567ab17a764c2`;
session-config is
`dc77804fbe52b541341dd974157f4e72b0b6849a315dbf436dbd7bf6a285457e`.
All seven exact input hashes are pinned in `protocol.INPUT_SHA256`.
Reading the JSON as data found 343 perceptions (frames175–517), 164 decision
polls90–905, 23 original search opportunities and five acknowledged taps.
These are input counts, not replay results.

Portable raw writer audits live in `audit/drive.py.txt` and `audit/towers.py.txt`
with a pinned `audit/provenance.json`. They match the05 bytes independently
audited in R18. Their origin/read UTC/hash are recorded; they support this
conditional reconstruction and do **not** prove the original Mac revision.
They are read as bytes and never imported/executed. No live checkout is needed
on01. Missing/changed audit bytes fail before an output name is reserved.

**Conditional driver evidence:** frame234/poll170 logs action233 but
`submitted:false`, no card/tap ID and no corresponding tap acknowledgement.
The next readings are floored at three elixir. In the source driver,
`submitted = len(pending_after) > len(pending_before)` can miss replacing a
completed reservation with a new one within the same poll. This suggests an
internal untapped reservation, but the copied logs do not explicitly prove it.
Owner explicitly authorized reconstructing this as an **UNVERIFIED INTERNAL
RESERVATION**, never a sixth tap/ack/verified actual play. A small LiveSession subclass
observes the exact Giant813/160 -> action233/170 replacement and aborts on
contradictions. Confirmation and reconciliation remain unchanged. Action233
alone never creates a public play. If later public HUD evidence makes the
original pipeline infer one, that event and subsequent context are explicitly
tagged **conditional on the unverified reservation**, never an acknowledged
tap or verified actual play. Both
shadows see the same conditional reservation context. Five acknowledged taps
and the one unverified reservation are reported separately.

Tower normalization is unambiguous in these inputs. `live/loop/towers.py`
already writes `round(hp_read / inferred_max_hp, 4)`. The actual
`LiveTranslator.towers()` consumes this `hp_frac` unchanged; the template-HP
division in `_rows()` applies to **unit** `hp_abs`, not these crown records.
At frames500–509 the own king has `hp_read:59, hp_frac:0.0178`. B's L6 root
therefore represents approximately58.9536/3312 HP, retaining OCR rounding;
A represents the same fraction against its L11 maximum. There is no second
division and no normalization bridge is needed. Both arms receive identical
public fraction values. The first enemy king record is an early maximum
inference inconsistency (2400 with fraction1 rather than3312); retain and flag
it rather than editing public input.

The requested displayed clock window is inclusive floor(clock_s) in134…176
(2:56 through2:14). The final recorded clock is134.741730583; no state at
exact134.000 or later is fabricated. Own king59 is already visible at136.964.
The log's fractional `tick` is writer metadata, not the original input tick.
Remove it and use the actual anchored ClockTracker: frame207's99.6047 rounds
to100, whereas flooring metadata would wrongly put it on poll95.

## Protocol

One actual `LiveSession`/`LiveTranslator` owns the command queue, own HUD/cycle
tracking, public birth events and reservations. The recorded-input facade
implements LivePlayer's start/act/close contract and its start-time live belief
replacement. A and B are independent headline `K4L-R-gs-rw-fc` serial objects,
queried on deep copies of the same public view. Shadow actions/waits never
drive future input, reservations or perceptions. No true enemy deck, level,
order or battle-log outcome is read. Original unknown AnyTroop/AnyBuilding
duplicates remain in raw input and are handled by the actual drop translator;
its counters and public/root rows are retained as evidence.

Only recorded `source:search` polls in the requested window are searched.
Every other 5-tick poll updates both D1 pollers with `can_act=False`.
The live writer omitted `Decision.wait_ticks` and its filtered stats hide
timed-wait IDs; no duration is guessed from the gap between searches. Instead,
recorded search gating is explicit, and the common session's timer stays at
zero unless a duration is explicitly present. Queue availability is still
checked against every recorded searched/submitted command. Missing polls are
logged as LiveSession's borrowed-current-frame, blocked maintenance, never new
search opportunities. No Mac fast checkpoint is loaded: recorded actions and
gating drive the world, unbounded shadows have no wall cutoff. This does not
claim literal reproduction of original live search commands.

Scope installation occurs immediately after Runtime and before every player.
Both arms use the same supported-card conditional prior, and each actual
controller's prior digest is checked before/after each poll. LiveBelief's
publicly revealed-card completion is retained and rebuild counts reported.
A uses the existing L11 config/root/native. B gets ExactLevelRoot with the
fixed account Cannon deck levels from profile (Cannon6), public towers6/6,
fixed population OpponentEstimate, qualified exports and `leaf_native`.
Hooks are installed **after** serial start rebuilt the actual core. The
RoyaleSim arm factory and placement installer are never called.

Existing exports4/5/6/7/9/11 and the versioned supported receipt are parsed
once. Raw and loaded-object canonical digests bind them; no export, receipt
creation or later cache read is allowed. Supported cards must have either an
entry or an explicit error. Known unused export errors remain in the manifest;
actually playable unsupported cards/bodies raise in ExactLevelRoot. A native
failure/fallback is an error, never an accepted decision or L11 substitution.

Read-only wrappers snapshot each root actually constructed, including body
and tower HP/maxHP/damage, without another root/sample/RNG call. No learned
feature definitions or static columns are changed; loaded model weights and
metadata are hashed before/after. This does not imply identical learned inputs
inside rollouts with different physical levels. Rows include exact per-arm
public-view digests and tower fractions, actual root physics, root counters,
built-seat config reports, candidates/Cannon legality, public threats, errors,
native FAILURES deltas and timing. Home defense means Cannon chosen at row<16
with a public enemy non-crown body in our half, not proven defensive success.

Fresh output directories only. `launch.json` preserves the intended invocation;
`receipt.json` binds inputs, sources, runtime/model/cache/env and states/report
digests. `states.jsonl` retains failed polls and fatal errors. `report.json`
contains matched opportunities, failed/unmatched states, action differences,
Cannon availability/affordability/choices, home-defense examples and first
differences. Before replay, the pinned recorded search decisions and their
corresponding public clock frames define the full expected opportunity roster.
Each planned (frame,poll) has exactly one success/error/not_reached status in
the report. Expected, attempted, successful, failed and unvisited counts are
separate. A fatal error before the facade appends a row remains an error at its
planned key; later keys remain not_reached without fabricated arm choices or
public states. A post-row queue contradiction invalidates that key's apparent
success while preserving the original state/error rows. A successful prefix
can never satisfy matched_all_opportunities. Any missing decision,
command/context mismatch, search error,
native failure or submit refusal returns nonzero. A PASS only means diagnostic
evidence checks passed; it is not pilot readiness or an outcome result.

Frame234's reconstruction is owner-authorized but remains an explicit
assumption, not verified original queue telemetry. The reported number of
matched opportunities includes failed states in its denominator; native errors
cannot improve agreement by removing their state from the report. A timer or
public-state reconstruction contradiction aborts the run and preserves rows
already written. Inputs, factory behavior and this assumption require source
review together before execution.

The authorized own runtime copy is also the only permitted evaluation serving
root. `CLASHER_EVAL_RUNTIME_ROOT` defaults there when unset; a resolved external
override is refused before output reservation. The existing game/native fences
remain. All Python below the actual serving root (including imitation
evaluation/model/masks/engine sources) is hashed before Runtime imports and
compared afterward. Exact `src/clasher/rl/contract_v5_tokens.json` bytes are
bound alongside loaded token identities. Loaded-dependency observations at the
end supplement this immutable baseline. The actual01 bot tree is captured at
launch and must stay frozen for the whole run; unrelated unfinished05 primary
files must not be synced to equalize its broad all-bot source manifest.

## Proposed bounded commands — review required, not run

After fresh independent review, owner
syncs only this reviewed package (including portable audit assets) and the
pinned inputs from05 to01 (never `--delete`). Do not sync primary code or create
a live checkout. On01 only, with fresh output/temp names:

```bash
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
unset CLASHER_LEVELS_PLACEMENT_PROOF
cd "$REPO"
timeout --signal=INT --kill-after=15s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -m pytest -q -p no:cacheprovider --basetemp /mpac/sdicks02/jobs/clasher/bot-levels/dev/s27-r20-pytest bot/levels/diagnostics/test_replay.py
# Only after inspecting a terminal test PASS; never automatically after failure:
timeout --signal=INT --kill-after=15s 25m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.diagnostics.replay --inputs /mpac/sdicks02/jobs/clasher/bot-levels/s27-m02 --out /mpac/sdicks02/jobs/clasher/bot-levels/s27-diagnostic-dev-r20
```

One Python process, no fork/pool/threads beyond the pinned single-thread CPU
settings, no GPUs, no emulator/account actions. The runner checks01, hash seed,
CUDA/BLAS settings, own runtime copy and fresh job output before Runtime.
The outer timeout includes CPU admission time. Fixtures disable pytest's cache
provider. Preserve any failure artifacts and obtain repair review before a new
attempt; these command examples grant no execution approval.
Rollback is simply to stop invoking this isolated package and retain its
diagnostic artifacts. It writes neither live sources nor frozen runtime data.
Tests are synthetic public/source fixtures; none has run at this source-only
stage. Tests do not load Runtime or models.
