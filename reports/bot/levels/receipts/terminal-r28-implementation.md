# R28 common command-phase bookkeeping — SOURCE ONLY

2026-10-16T13:16Z (06:16 PDT). Implementation complete for fresh independent
review, **not executed or qualified**. Worktree05:
`/mpac/sdicks02/repos/clasher-bot-levels` (W); job directory:
`/mpac/sdicks02/jobs/clasher/bot-levels` (J). No project imports, syntax parsing,
compilation, tests, native/model/Runtime construction, sync, CPU jobs, source
commits, descendants, new bank or restart. Read-only SSH01 inspected existing
API/source contracts. Local work was source editing, text/diff/hash inspection
and receipt writes only. Whitespace inspection passed; it is not a syntax or
test result. Parent obtains a fresh different Sol review before any execution.

## Exact scope and source identity

Only these three implementation files changed/appeared:

| path under W | SHA256 |
| --- | --- |
| bot/players/royalesim_match.py | 5f1a5987c0fd9cd44f889fda83c971374e148cd1cde1665b080a3cb6d35c25c6 |
| bot/levels/terminal_probe.py (new) | bc0ea5f54103aa84944318513757e3aea85e2015e3bf0f087a68e2d18d534d63 |
| bot/levels/test_terminal.py (new) | bb442ac23d042d20394787900caecb2bb2326bbe29d8e9270f4c3f60ea33c739 |

Focused patch:J/terminal-r28-implementation.patch, SHA256
`dc0749e80e5b616d6c6c52222bb2caf3f7caffa27885c0cf887cecd0fd632a42`.
This is against the exact pre-R28 match bytes, **not old local git HEAD**,
and includes both new files. All109 primary source entries are in
J/terminal-r28-source.sha256, SHA256
`3b5e45cdbec0adeb5bd8144c32af21abea9be186e911023d4c1e9361cba64510`;
J/terminal-r28-source-check.txt records109 matching local hashes. Compared
with the107-entry R27 source closure, only royalesim_match.py changed and
the two new immediate levels files were added. All106 other entries, including
run.py/report.py/run.sh/root/configs/player/placement/probe/scope/diagnostics
dependencies, are unchanged. Existing source_hashes automatically includes the
new immediate levels files and the changed common match; no identity protocol
or row-validator edit was needed. Source identity therefore prevents successful
R27 rows from resuming under these bytes.

Pre-R28 match backup:J/terminal-r28-royalesim_match-before.py, SHA256
`35b70b459a4a5acc66608494de452d16b7b0e9a8e1d8b15da3a8b066ebee7029`.
All58 preserved R27 output files still match their original inventory;
J/terminal-r28-preserved-R27-check.txt records the check. No old row, event,
score, report, launch, registration or bank was changed. R27 remains
INVALID/INCOMPLETE:47terminal(43clean+4failedwinningrows),8SIGTERM rows,
16GAME_OVER refusals, parent143; no primary strength decision or exclusions.

## Repair and each failure response

`royalesim_match.py:43–93` adds CommandPhase. It binds the compiled calibration
and the actual Battle.calibration_overrides once, decoding its documented
JSON-text values. It validates positive integral clock periods, exact public
tick_ms/regular_ticks/overtime_ticks, nonnegative integer tick, boolean flags
and nonterminal overtime/clock consistency. Known documented tiebreaks are
explicit; unknown/malformed rules/schema and replay-only BATTLE_END refuse
actionably. Normal16.402 and15.535.29 clients retain their actual overrides.
The supported non-drain older rules receive no early freeze. There is no
hardcoded6000 in the production predicate and no hidden or legality query.

Binding occurs after native reset and before Translator construction or any
player.start. Public clock consistency is checked on refresh and before phase
use. This validates lifecycle information, not physics or player features.

At the top of the actual common play_match loop(:210), command closure is
checked **before** due-slot inspection or execute. In that phase neither seat
is polled, no new reservation or command is sent, and no rejection/accepted
play/public event/hash entry/decision charge is synthesized. The engine still
steps with empty commands at the existing poll cadence and refreshes until its
actual game_over. Frozen pending due times do not schedule one-tick busy work.
Normal preclosure dispatch, lag, polling, command hashing and final scoring
are unchanged; the max_ticks safety cap still produces a failed nonterminal
result when exhausted. An additional guard before the ordinary poll branch
keeps the no-act contract explicit after execute/refresh too.

The additive result field `command_phase` records version, effective rules
and overrides, validated clock, closed_tick (public expiry), observed_closed_tick
(the first wrapper observation), and per-seat exact pending snapshots with
submitted/due/action/card/cost/status=not_dispatched/reason=command_phase_closed.
If a fixture starts already closed at6010, expiry6000 is distinguished from
observed6010; no historical pending snapshot is invented. Unsent reservations
remain in the real CommandQueue so submitted=executed+pending still holds.
No finish(False), refund, fake cancellation-as-play or counter rewrite occurs.
Natural pending commands at an earlier crown/king final retain their prior
pending-at-end semantics. Child rows already copy arbitrary match result
fields; run/report plumbing is unchanged.

The four actual failed winning rows and all16 refusal events are preserved.
A native preclosure WATER refusal still follows the normal execution/log/hash/
parent/report failure path. No GAME_OVER filtering, rejection waiver or early
terminal label exists. Weights/features/estimates/prior/true levels/decks/
candidate eligibility/translator/native physics/frozen runtime/cache remain
unchanged; the shared guard applies symmetrically to both seats/all arms.

## Meaningful fixtures and API contracts

The new standalone terminal_probe performs only pinned native API fixtures,
without Runtime, models, builders, learned policies or caches. It reuses the
existing exact binary/calibration/arena/card identity checks, records its own
source/environment/env.sh digests and effective rules/public clocks, and
preserves partial cases plus traceback in an exclusive fresh receipt on error.
Its expected native refusals are isolated API observations, never pilot plays.

Six boundary cases cover both clients, each weaker seat and an exact weakest
HP tie. The engine accepts a legal Knight at5997, refuses an unused-seat legal
command at6000 while game_over is false and physical state unchanged, then
continues real native one-tick drain to the final winner/crowns/ALL tower HP/
tick. Untied fixtures require exactly the weaker900HP to drain out; the tie
requires one50HP drain from equal1000HP weakest towers and a delayed draw.
These are assertions awaiting execution, not empirical results or inferred
reconstructions of R27 historical states.

**Tick convention correction at source level:** calibration describes the
upkeep/input tick6067 and judgment/input tick6147. Their changes are visible
in returned states6068 and6148. The existing supplementary
`RoyaleGym/royalegym/mock_engine.py:1305–1365` increments before exporting,
and `tests/test_overtime_tiebreak.py:170–204` explicitly asserts that convention.
The fixture asserts returned6068/6148, not an early draw at6147. This is
corroborating source, not a claim of exact installed Rust revision; the pinned
binary probe remains the required next empirical check. A contradiction must
be preserved and reviewed, not silently weakened or relabelled.

`test_terminal.py` uses the production common loop, production execute/refresh/
hand_card, actual frozen CommandQueue and real native Battle. A minimal explicit
own-HUD/reservation facade supplies a dataclass/arrays consumed by own_packet;
it constructs no actual feature builder or Translator and makes no learned-
feature invariance claim. Frozen helper imports (PublicEvent, queue, latency,
GC window) construct no spell/game-data object. Its paths-only setup therefore
cannot reproduce R24's early-builder spell registry defect. In the mandatory
six-file suite the existing placement integration still initializes actual
Runtime exactly once before any real builder; this new module never initializes
a second one or calls LevelConfigs supported/build/export. Mandatory native
dependencies or preserved R27 artifacts failing to exist cause failure, not SKIP.

The actual-loop fixtures cover:

-5970→5997 accepted command plus5975→6002 late pending, with both seats
 exchanged, for actual wins and delayed draws. They require the exact accepted
 log/event/hash, no later polls or charged decisions, exact unsent evidence and
 queue accounting. They save the native state immediately after accepted5997,
 load it into an independent matching Battle, require identical state_hash,
 and compare complete final score/HP/tick/state_hash with a one-tick native
 empty-command continuation. The common loop uses its usual five-tick steps.
- Already-closed6010 with injected overdue6002 reservations and poisoned
 information/hand access. Both actors must remain unpolled, all steps must be
 empty five-tick advances, hash remains empty, pending/counters remain honest.
- Earlier normal crown end with unsent reservations; earlier actual king death
 from a fixture Knight attacking a1HP living king during the common loop.
 No dead king is fabricated at reset. No further steps/acts are permitted
 after native final, and earlier pending semantics are retained.
- Safety-cap nonterminal failure, malformed/unknown calibration and public
 clocks, once-only override binding, a changed public-duration boundary, and
 documented other tiebreak rules receiving no early freeze.
- Real preclosure WATER refusal remains a detailed failed row after parent
 record_exit and makes the registered report fail. The original immutable
 R2758-file inventory is checked before/after read-only summarization; all16
 original refusals and four failed winning outcomes must remain failure.
- Probe partial-error receipts retain evidence/traceback and refuse overwrite.

Validated API contracts were read, not executed: pinned binary-embedded
step/apply-before-advance, state_json, calibration_overrides, save/load and
state_hash docs; J/pilot-r27-pinned-api.txt plus read-only save documentation.
Supplementary01 `RoyaleGym/royalegym/rust_engine.py:1202–1211` uses
bytes(Battle.save()), Battle.load(bytes) and state_hash; its
tests/test_calibration_overrides.py:109–120 asserts the actual dict of JSON-text
overrides. No unsupported clone API is assumed. Static source HEAD remains
ab0df8ff92f194276e2aa852834053cb2202f59a; prior source audit already records
that this is not proven the wheel's exact Rust revision.

## Proposed bounded sequence — TEXT ONLY, after fresh matching-byte review

Owner first reviews this patch and obtains independent approval; only then
syncs these three source files plus the data-only109-entry source manifest to
their exact01 paths and verifies `sha256sum -c J/terminal-r28-source.sha256`.
No broad runtime sync, deletion or input overwrite. Confirm no conflicting
owned job/writer and fresh destinations. Use existing env.sh/cpu_job.sh/nice,
normal owned runtime, hashseed0/math1/CUDA hidden/bytecode off. Commands below
are individually inspected stages, not an automatic script or permission to
launch now. A failure, incomplete receipt, timeout/admission delay or mandatory
SKIP stops dependent stages and preserves its output. No automatic retry.

Common01 preamble (normal owned runtime; output names must be unused):

```bash
set -euo pipefail
set -o noclobber
test "$(hostname -s)" = 127x01
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
J=/mpac/sdicks02/jobs/clasher/bot-levels
test "$CLASHER_BOT_RUNTIME" = "$J/runtime/live16402b-r2"
test -z "${CLASHER_EVAL_RUNTIME_ROOT:-}" || test "$(readlink -f "$CLASHER_EVAL_RUNTIME_ROOT")" = "$CLASHER_BOT_RUNTIME"
test -z "${LEVELS_RUNTIME:-}" || test "$(readlink -f "$LEVELS_RUNTIME")" = "$CLASHER_BOT_RUNTIME"
export CLASHER_LEVELS_PLACEMENT_PROOF="$J/dev/placement-micro-r21.json"
sha256sum -c "$J/terminal-r28-source.sha256"
sha256sum -c "$J/dev/cache-restored-r25.sha256"
```

1. Pure exact-binary boundary probe first, CPU1/outer5m; no Runtime initialization
is needed. Inspect terminal0, full six-case receipt and actual public phase/
state tick/HP/crown evidence before proceeding. Proof SHA/binary/calibration
are checked by the probe; no new placement matrix is requested.

```bash
test ! -e "$J/dev/terminal-boundary-r28.json"
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.terminal_probe --out "$J/dev/terminal-boundary-r28.json" > "$J/dev/terminal-boundary-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-terminal-probe-r28.txt"
```

2. Cold9 no-write regression remains mandatory before full integration,
CPU1/outer5m, followed by inspection; the source is unchanged.

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -p no:cacheprovider 'bot/levels/test_harness.py::test_preload_bad_support_or_L11_never_repairs_cache' > "$J/dev/pytest-preload-isolated-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-isolated-r28.txt"
```

3. Full six-file meaningful suite, CPU1/outer15m, actual Runtime once in the
existing integration fixture before builders; new terminal module appended.
Require all existing and new obligations, no mandatory skips, no cache writes,
exact spell/reference anchors, positive actual B roots and honest real refusals.
No guessed PASS count is asserted in this source receipt.

```bash
CLASHER_PLACEMENT_INTEGRATION=1 timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m pytest -q -s -p no:cacheprovider bot/levels/test_harness.py bot/levels/test_scope.py bot/levels/test_configs.py bot/levels/test_bank.py bot/levels/test_placement.py bot/levels/test_terminal.py > "$J/dev/pytest-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-pytest-r28.txt"
```

4. Only after inspected integration success, native gates CPU2/outer15m
(parent plus one raw-fc worker). Require the unchanged254 substantive native
obligations, original exact spell/export/cache anchors, four actual fair B
decisions, all transport/qualified-key checks and complete raw-diff inspection.
Only the prior proven missing spell_name→empty-string representation is allowed.

```bash
timeout --kill-after=10s 15m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 nice -n 10 "$PY" -u -m bot.levels.gates > "$J/dev/gates-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-gates-r28.txt"
```

5. After all prior stages qualify, same original4-case all11 bank, new output,
reviewed run.sh2/outer15m/max3 Python including parent. Independently verify
bank SHA b4145717d0122d0f249bddce894be15748ac4c2b59cb190868c1039dabf8d15a.
Require8unique terminal clean rows/4full-command pairs/all4positive B roots,
both seats/controllers, complete identity/prior/command/phase evidence,
parent/children0 and zero errors/native failures/rejections. No failed-output
resume, source/pin/cache/input change or row exclusion.

```bash
test ! -e "$J/dev/all11-terminal-r28"
timeout --kill-after=10s 15m bash bot/levels/run.sh 2 --bank reports/bot/levels/receipts/all11-dev-cases.json --out "$J/dev/all11-terminal-r28" --arms A,B --all11-gate --start 0 --count 4 > "$J/dev/all11-terminal-r28.txt" 2>&1
sha256sum -c "$J/dev/cache-restored-r25.sha256" > "$J/dev/cache-after-all11-r28.txt"
```

6. Only after clean runner completion, report CPU1/outer5m; require registered
completeness/provenance/quality PASS at matching source and inspect raw rows.

```bash
timeout --kill-after=10s 5m /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 1 nice -n 10 "$PY" -u -m bot.levels.report "$J/dev/all11-terminal-r28" > "$J/dev/all11-terminal-r28-report.txt" 2>&1
```

Stages are sequential; maximum reserved Python count is3, with no extra jobs.
Existing full-pool priority applies. No GPU/05compute/09–18/03 retries,
exporter, frozen/live write, emulator/account action, broad pkill or new host
script. No processes need signalling now. Previous static145/1024 placement
proof remains reusable only because placement/probe/pins are unchanged.

## Rollback and scientific recovery

The saved pre-R28 match bytes and complete focused patch provide source-only
rollback; reverting returns the known failed lifecycle and grants no execution
authority. Select standard A outside the experiment/remove experimental hooks
for experimental rollback. Preserve original/restricted prior references,
good/bad support, all exports, frozen models/pins and every earlier failed gate.

R27 is permanently invalid exploration. There is no selective reuse, changed
population/level assumption/model/policy/scope/decision rule or outcome exclusion.
Only after fresh independent review and passing final gates may the parent
draw/publish a new full100-case bank with fresh os.urandom BASE before games.
No BASE/bank/pilot/confirmation/LIVE promotion authority is exercised here.

No routine DM/ack/status/result spam was sent. This source assignment returns
once automatically with its receipt; parent owns review/execution/commits.
