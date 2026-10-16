# R27 terminal command closure audit — proposal only

2026-10-16T12:50Z. R27 is **STOPPED, INVALID and INCOMPLETE**. No source was
changed, no test or simulator experiment was run for this audit, and no game
was retried or excluded. The existing report alone was regenerated after stop
under its CPU1 lease/nice command; it exited1. Owner review is required before
implementation, tests or restart.

J = `/mpac/sdicks02/jobs/clasher/bot-levels`; W =
`/mpac/sdicks02/repos/clasher-bot-levels`; S =
`/mpac/sdicks02/repos/clasher-bot/.venv/lib/python3.12/site-packages/royalesim`
on01. All original rows/log/launch receipts remain under J on01 and have been
copied byte-for-byte to05. `pilot-r27-stop-audit.json` records the stopped run;
`pilot-r27-preserved-files.sha256` and `pilot-r27-copyback-check.txt` verify all58
files in its output directory, including all55 rows.

## Finding and evidence boundary

The adapter confuses **command acceptance ending at overtime expiry** with
**the final `game_over` after HP drain**. The pinned16.402 calibration explicitly
describes this distinction. GAME_OVER at6027–6087 does not imply a stale
`state_json` or an already-final game at5997. Stopping the match at6000 would
instead corrupt terminal crowns, HP, ticks and scoring.

The installed native binary is RoyaleSim0.1.34, SHA256
`97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb`.
Its calibration JSON SHA256 is
`4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf`.
Both are bound in the launch identity and unchanged after stop. No exact Rust
implementation source is installed in this wheel. This audit uses the shipped
calibration, binary-embedded API documentation, a small read-only disassembly,
the actual adapter and preserved command rows. No new boundary probe was run.
We do not have historical full state snapshots from the failed game.

`S/data/calibration.json:3210–3218`, `match.OVERTIME_TIEBREAK=client_hp_drain`,
states that no play is accepted from6000; the board is subsequently cleared
without death effects; HP drain starts at6067 and continues until a tower falls,
with a separate delayed exact-draw path. Regulation180s plus overtime120s at
50ms gives6000. These are descriptions of the pinned engine's rule, not a new
empirical measurement of every boundary in R27. Client16.402 uses no calibration
overrides (`W/bot/players/royalesim_vocab.py:69–74`; the pinned binary's
`client_arms` documentation also says16.402 returns{}).

The binary-embedded `Battle.step(commands,ticks)` documentation specifies:
validate/apply commands against the **current state first**, then advance up
to `ticks`, stopping only at final game over. Thus `step(sent,0)` can refuse a
command in the no-play drain phase without advancing time or setting terminal.
Its separate delayed-command documentation explicitly names GAME_OVER for a
command dropped at a level overtime's end. The harness uses simulator delay0,
so its own27-tick reservations are still outside the simulator until dispatch.
Extracted documentation: `pilot-r27-pinned-api.txt`.

Read-only disassembly of this exact binary's `BattleState::check_deploy_slot`
at0xcef1a4–0xcef204 shows an initial terminal branch followed by an additional
calibration/overtime/time comparison that branches to the same refusal return.
The latter compares elapsed tick×tick_ms against1000×(regular_s+overtime_s)
with `jge`. The field interpretation is corroborated by the shipped rule and
public protocol; the assembly alone is not a source-level field-name proof.
See `pilot-r27-pinned-deploy-closure.asm`.

There is also explicit corroborating public-facade source already present on01:
`/mpac/sdicks02/repos/clasher-bot-rsim/upstream/RoyaleGym`, HEAD
`ab0df8ff92f194276e2aa852834053cb2202f59a`.
`royalegym/protocol.py:731–744` exposes tick, tick_ms, regular_ticks,
overtime_ticks, overtime and game_over. Its `DeployRules.plays_stopped` at
1357–1366 is exactly:

```
rule == 'client_hp_drain' and state.overtime and not state.game_over
and state.tick >= state.regular_ticks + state.overtime_ticks
```

The preceding comment at1230–1233 warns specifically that waiting for
`game_over` admits commands the engine rejects. `royalegym/action.py:970–989`
returns only NOOP in that phase. These Python files are supplementary source,
not established as the installed binary's exact Rust revision, and must not
be imported wholesale into the pilot. Their excerpts and exact hashes are in
`pilot-r27-public-phase-source.{txt,sha256}`. The proposed boundary needs only
public clock/rules fields; it needs no hidden deck/level/RNG or full-state
legalmask query.

## Actual harness ordering and preserved failed game

`W/bot/players/royalesim_match.py` has the following order:

1. `refresh()` decodes `state_json` (77–79); the outer loop tests only final
   `game_over` and the7200 safety cap (149).
2. At the current tick, ready reservations are checked against the physical
   hand and dispatched (151–160), before the policy-poll branch. `execute`
   calls `step(sent,0)`, records its true result, and refreshes (100–123).
3. Every actual dispatch, including GAME_OVER, enters command hash/play log,
   deploy reason counters and `CommandQueue.finish(ok)` (160–167). Failed
   commands free the capacity without a physical refund or public play event.
4. If this is a5-tick poll and final `game_over` is false, both players are
   polled; available channels may reserve new commands (168–192). There is
   no separate no-play phase guard, so the drain can generate repeated attempts.
5. Time advances to the next poll/due command using `step([],delta)` and then
   refreshes (193–200). Final result and score inputs are collected only after
   the loop ends (204–220). This final drain/scoring path must stay.

The translator likewise labels `observation.terminal` solely from final
`state['game_over']` (`royalesim_translate.py:257`). It is correct that the
drain is not yet terminal; changing this public flag early would be wrong.

B/case0 (our seat0, R3a) preserves the last accepted Musketeer at5997, then
seat1 Knight rejections6027/6057 and seat0 Giant plus seat1 Knight at6087.
With fixed27-tick lag,6027 is consistent with an attempted reservation at6000;
submission-time reservation traces were not captured, so that is an ordering
inference, not a recorded queue snapshot. Final tick is6105, crowns1–0,
score1, HP seat0[2846,1317,658], seat1[3026,0,1274]. The final score remains
recorded even though this row correctly failed acceptance and exited1.
Its accepted counts are57/59; executed attempts58/62, rejected1/3 and one
pending reservation per seat. Do not confuse executed attempts with accepted
plays. All four rejection events remain intact.

At stop there are four affected terminal rows across all arms: A/case10
(3 rejections, terminal6096), A/case12(4,6100), B/case0(4,6105), B0/case13
(5,6116). Every one has raw score1; all16 reasons are GAME_OVER, native
FAILURES are0 in all47 terminal rows. Eight other children were interrupted
by the directed stop. The report's43-clean-row metrics omit the four failed
winning rows and therefore are not an accepted primary estimate. Missing
diagnostics in interrupted rows are absence, not evidence of prior mutation.

## Recommended minimal common repair, not implemented

Put one public no-dispatch phase predicate in the common RoyaleSim match
adapter, shared by both seats in every A/B/B0 game. Bind the effective static
tiebreak rule once from the pinned compiled calibration plus the Battle's
reported calibration overrides, and use exported public tick/duration/overtime
fields. Validate the supported rule/clock contract; do not silently assume a
6000 cutoff under an unknown calibration. `game_over` remains the only normal
terminal condition, and the7200 cap remains a failed nonterminal safeguard.

Before ready-command hand checks or dispatch, and before policy polls, check
whether command acceptance is closed. In the closed phase, do neither: no
`player.act`, new reservation, `execute`, slot assertion, synthetic rejection,
accepted event, hash entry or charged decision. Continue advancing the real
engine with empty commands and refreshing until its actual final game_over.
Use the ordinary poll-sized advance; ignore frozen pending due times in that
advance scheduler so an overdue reservation cannot force a one-tick busy loop.

Keep unsent reservations as pending in the harness through final scoring.
This is the smallest accounting change: current `CommandQueue.diagnostics`
already requires submitted=executed+pending. Record a separate phase-close
tick and per-seat unsent reservation snapshot (submitted/due/action/card/cost,
reason=command_phase_closed), with an explicit **not dispatched** status.
Do not call `finish(False)` or invent a cancellation-as-play. No physical
elixir was debited, so there is no refund. Source: pinned
`src/clasher/analysis/loss_review/delay_fixes.py:35–112`, SHA256
`8b539bfd6226176e9314c32d3c716cb8cc7b709d2863127aa8cd1a6b814cc8cb`.
Naturally pending commands at an earlier final crown/king end should retain
their existing pending-at-end semantics too.

Preserve preclosure commands in full, including a command accepted at5997
whose spawned body is later cleared by native tiebreak rules. A command
reserved before6000 but due at6000 or later is still unsent when the public
phase closes; preserve its queue evidence instead of sending it. Never scan
recorded GAME_OVER reasons and filter them retroactively. Keep rejection,
native-failure, child-exit, provenance and terminal-score gates unchanged.
This is common simulator command bookkeeping, not a placement/policy/native
physics repair. Leave root/configs/weights/features/scope/translator and frozen
runtime bytes unchanged. New source identity/output and renewed independent
review/gates would be required before any newly authorized games. R27 stays
invalid and is never resumed or relabelled PASS.

## Meaningful validation proposal — no tests run or written

- First, a bounded exact-pinned-API fixture should reset a balanced overtime
  just before expiry with unequal surviving tower HP and sufficient public
  own elixir. Establish accepted legal commands before expiry, refusal at
  expiry while game_over=false, and continued empty-command drain to actual
  terminal winner/crowns/HP/tick. Include an exact weakest-HP tie for the
  separate delayed draw path. This validates the public predicate against
  the real binary; do not rely only on a mocked6000 boolean.
- An end-to-end common-match scripted fixture should use actual5-tick polls
  and27-tick queue delay: seat0 reserves at5970 and executes at5997; seat1
  reserves at5975 with due6002. With unequal tower HP, verify the last accepted
  command/public event remains, the late pending command is recorded unsent,
  neither seat is polled/dispatched after closure, queue accounting stays
  balanced, command hashes contain only actual dispatches, and the engine
  reaches a later terminal score matching an independent empty-command drain
  continuation from the same post-last-accepted state. Compare winner, crowns,
  all tower HP and final tick, not just terminal=true. Repeat with seats
  exchanged and a pre6000 final king/crown end to catch accidental extra steps.
- Add a targeted loop test that begins already in the closed public phase
  with an overdue pending command and a poisoned hand-slot accessor/player.act
  that raises if touched. The engine must still advance/drain and score, with
  the pending evidence retained. This catches guard placement after the due
  branch, a policy-only WAIT patch, and scheduler spin.
- Keep a real preclosure rejection failing row/parent/report acceptance, and
  require the preserved R27 failure artifact still reports FAIL. A regression
  that merely hides GAME_OVER or calls6000 terminal must fail the preceding
  last-accepted/late-pending/final-score assertions. Review before execution;
  exact-binary DEV evidence and all required renewed gates before a new pilot.

No claim is made that the proposed repair has passed these checks. The owner
must review this preserved failure and proposal before code/tests/restart.
