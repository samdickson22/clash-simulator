# Conditional R2 implementation notes

Read-only source review at2026-10-10T02:40Z. No R2 admission, generation,
fit or qualification has occurred. This is implementation guidance, not a
new scientific freeze. PLAN.md remains authoritative. Implement and qualify
the conditional code when a stage2 survivor exists, then commit/push the
source/input/seed/operational records before generation or refitting.

The existing imitation.exit_r1.emitter.run_game drives the main actor with
the teacher's selected action and selected_wait_ticks. It cannot be reused
unchanged for R2. Use a separate owned collector with a final-EMA survivor
StandalonePlayer as the behavior actor and independent unlimited W as the
labeler. Poll the survivor adapter on every eligible public5-tick poll,
including pending polls, preserving its D1 state. Submit only the behavior
actor's legal actions through its own delayed CommandQueue. The teacher's
choice and wait duration must never determine behavior submissions, pending
commands or future decision times. Both RNG streams and actor roles need
explicit receipt bindings. Opponent/deck sampling must be frozen before games.

Teacher labels must describe the behavior actor's actual current public
state: packet, own HUD/order, public events and pending reservations where
applicable. Only complete unlimited-W scores are valid. Label teacher_root,
teacher_search_action, expert_actions and sparse root score arrays using the
same v6 semantics as r1, while recording behavior actions/submissions and
teacher actions separately. Existing emitter replay assumes labels equal
submissions; a new replay check must compare actual behavior commands and
public observations, rather than treating teacher labels as executed actions.

Generation is home01/03 only, nice>=10/SCHED_IDLE/Torch1 and physical cores,
with G drain, K coordination, memory floor and owned stop/deadline guards.
Use reserved4503601707370496+[0,32768), independently audited helper offsets.
Count scored root states rather than poll rows or individual score entries.
Seal approximately2M roots only at terminal-game boundaries and retain an
exact completed contiguous prefix, provenance and every failed attempt.
Reclaim/deadline may leave an unfinished game unsealed; meter its whole
process CPU and wall time anyway. Never add game meters to a whole pool tree
meter that already contains them. Stops and resources do not imply a kill.

The frozen trainer accepts either one packed corpus or up to64 game-* shard
directories in a root without manifest.json. R1 is already packed. A possible
union adapter is two game-* links to sealed packed r1 and packed r2 corpora,
with a union provenance receipt outside that root. Do not put a top-level
manifest.json there unless implementing an explicitly qualified union reader;
the existing trainer would treat it as a single TeacherStore. The sealed
original r1 corpus stays immutable. Verify both complete input inventories,
and qualify row indexing, root masks and combined_batch across the boundary.

R2 starts a new4883-step fit from the selected survivor's final EMA, not an
optimizer resume with changed data. Preserve the selected target/fraction,
micro3584 when human rows are present, loader6/core layout, playweight1,
seed2026101001 and finalEMA. Qualify initialization and new input pins; use
versioned owned runner/freeze while retaining original six-arm source hashes.
Resolve R2 gate/case identities explicitly before reusing the specified
heldout and reporting ranges. Run stages1/2 and conditional S-default stage3
again; disclose adaptive reuse. If the remaining lease cannot accommodate
generation, refit and screens, report resource censoring with exact completed
work, not a completed R2 or scientific kill.
