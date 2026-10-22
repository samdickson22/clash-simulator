# Exact-quota coordinator component

`bot/pretrain_v1/rl_coordinator.py` joins the reviewed actor, atomic queue and
learner APIs in process. This component does not grant integrated harness or
launch GO. It adds no topology, model choice, strategy, bank, host allocation,
process supervisor, transport or engine workload.

## Construction and admission

Construct a fresh `Coordinator(learner, queue, quotas=..., checkpoint_dir=...,
config=CoordinatorConfig(...), stop_notifier=...)`. Use the actual
`stream_actor.AtomicChunkQueue`. The learner, queue and checkpoint directory
must be fresh. A loaded learner or existing queue is rejected. The runtime
manifest must match the learner exactly. The full model configuration,
including `drop`, vocabulary sizes and feature hash, is recorded; its SHA is
computed over sorted compact JSON, with nonfinite JSON values forbidden.

The caller freezes an `actor_id -> positive quota` mapping. Its sum must equal
262,144 in production. Every actor receives that same quota at each update and
a lifetime generation budget of `quota * 32`. The mapping is copied at admission.
No default actor count, process placement or host mapping is selected. Production
rejects a learner marked `test_only`; toy budgets require an explicitly test-only
coordinator and learner. The learner's registered production constraints still
apply.

Use `queue_capacity(steps_per_update)` for the minimum admitted chunk and byte
caps. The bound reserves one full update with maximum feature widths and up to
one file shard per poll, covering worst-case short games. It allows 131,072 bytes
of manifest/NPY overhead per row beyond the maximum feature/vector row size.
Actual receipt sizes must fit the same bound. This is conservative disk capacity,
not a claim about measured storage use or available free disk. The parent must
keep the canonical serialized runtime manifest within the coordinator's explicit
96 KiB admission limit. This is an additional bound beyond the learner's
128-entry/256-character schema, because JSON escaping can expand Unicode strings.
Oversized manifests fail construction before any publication. The parent must
reserve that space and enforce its own disk budget. Abandoned partial files and
external queue writers are forbidden for this coordinator's queue. QueueFull,
lost files or failed digests stop the seed; they never buy new generation.

The core retains receipt metadata and game records bounded by the fixed total
poll budget. Array storage stays in queue files. It maps one publication for
validation, closes it, and later maps the exact complete update for the learner.
The learner owns its existing bounded vectors and microbatch copies. Actor
callbacks retain at most their current chunk while waiting. No whole-run feature
arrays are retained. File descriptors, virtual mappings and metadata at extreme
one-row chunk counts still need a production soak and resource admission.

## Callback and version barrier

A transport adapter supplies the callback actor identity independently of the
chunk. It calls `publish(actor_id, chunk, boundary, publication)`. `chunk` and
`Boundary` are the unchanged actor types. `Publication` adds these caller-audited
fields without private engine reads:

- `sequence` starts at zero per actor and increments for every publication across
  all updates. Retrying the same callback is a fatal duplicate.
- `game_id` is nonempty and unique per actor over the whole seed.
- `game_sequence` starts at zero per actor and increments only for a new game.
- `engine_tick` is the actual public engine tick at callback time. Nonterminal
  flushes occur at the next five-tick bootstrap poll. Terminal close occurs from
  the last poll through the following interval, including its endpoint if the
  engine ends on the next grid tick before another poll is sampled.
- `terminal` matches the actual producer's final terminated row and Boundary.
- `completed` is a parent-audited `Learner.PlayRate` with matching game ID,
  accepted own plays and positive simulated game duration. It is required for
  every terminal publication and forbidden on unfinished publications.

The adapter obtains this context from its public game lifecycle, producer
terminal context and audited accepted-command accounting. Chunk policy samples
alone do not prove an accepted own play. The coordinator never infers a terminal
reward from a tick, outcome request, budget or lease. It checks the producer's
existing reward/terminal schema without creating +/-1/0 labels.

The coordinator binds each publication to its independently supplied actor ID,
seed, exact current version, anchor FILE SHA, runtime provenance, complete
current MODEL STATE SHA, cumulative generated count, remaining quota/budget,
boundary reason and decline count, per-chunk N, sequence and game metadata.
The queue assigns the actual random `chunk-<32 hex>` name and manifest digest.
Each ledger entry records the full receipt and metadata, plus a per-actor hash
chain. Duplicate receipt/content identities are fatal.
Barrier eligibility is committed only after that publication's validation maps
have closed. The worker cannot consume or acknowledge a receipt while any
coordinator-owned validation mapping for it remains open. Per-actor chronology is
preserved even when actors interleave. Cross-update continuation requires the
same game ID, game sequence, opponent family and next five-tick poll. A new game
must start at tick 90 after a true terminal. Completed games cannot replay under
the same actor. Bootstrap/next-old-value equality is checked within a version;
the new critic may change the value across an update.

An ordinary chunk or terminal flush returns a same-version acknowledgement with
no weights or quota. A quota flush blocks on a thread-safe condition. A dedicated
worker performs exactly one `Learner.update` when every actor reaches its quota.
It passes `Learner.Chunk(**vars(mapped_actor_chunk))` with read-only mmap arrays,
in publication order, which preserves each actor's chronology. No partial
update, trimming, stale version, extra attempt, optimizer retry or premature
permit is allowed.

After update returns, the core closes every mapped array before acknowledgement
or unlink. It saves the learner checkpoint and durable coordinator ledger,
acknowledges queue receipts, then releases the next version, full state and
frozen next quota. A checkpoint or acknowledgement failure releases no permit.
The learner's own KL or play-rate stop also releases no permit.

`Boundary.reason == 'budget'` takes precedence over `quota` in the unchanged
actor. Its return value is ignored. These final callbacks persist their rows
and return a same-version acknowledgement immediately; the dedicated worker
still consumes the complete last update. The parent must call `finalize()`
before claiming completion. A callback return alone does not prove training.

The registered `boundary_declined` exception remains exactly the reviewed
actor/learner rule: one final value-only certain-NOOP row at tick 3600 or 6000,
no Session sampling/history mutation and a terminal outcome only from actual
producer close. Cumulative Boundary decline counts must match chunk counts.
A nonterminal declined row cannot be followed by another poll for that game.

## Stops and final accounting

`wait_seconds` bounds each quota callback, whole-update collection and
finalization wait. The parent chooses this operational deadline from measured
throughput. Collection may time out even before the first callback. A timeout
permanently aborts the seed and wakes waiters. `stop_event` is cooperative;
`stop_notifier(reason)` must be nonblocking and must stop all generation. Its
exception cannot suppress the core's halt. Do not use notifier code that waits
for the blocked actor callbacks.

Positive known chunk sizes, declared generated counts and cumulative Boundary
increases are charged before contract checks. A duplicate with an unchanged
cumulative count still charges its known positive attempt size and stops the
seed. A discard or failed attempt causes generated and accepted counts to
separate and permanently stops generation. There is no replacement path.
`abort(reason, generated_counts={actor_id: cumulative_count})` accepts the latest
authoritative actor counters, including pending rows, failed inference and
unreported discarded data. It can be called again after cooperative shutdown;
counts already known are never charged twice. Cumulative actor counters use a
separate coverage frontier from additional duplicate-attempt charges, so later
reports cannot absorb those charges. The parent must report the final
counters even if an earlier publication is still in transit. A first delivery
of those reported rows consumes their recorded coverage without an additional
charge; a repeated sequence or already-covered row interval remains a charged
duplicate. Delivery after abort still raises and does not admit learner data.
Reports must include every actor, including actors that never published. The
core cannot discover unreported work in another process. A malformed stop report
raises a contract error after setting the stop event, notifying actors and
halting the learner. Valid counts in the same report are still charged.
Boundary cumulative reports also record coverage for generated rows not yet
delivered. A later first delivery of those rows is already charged, even if an
earlier out-of-order callback caused the permanent halt. This affects stopped
accounting only and never admits replacement generation or learner data.

`Learner.halt` receives only additional known counts beyond its own generated
ledger. An in-flight update must return or fail before halt touches the learner;
abort never closes maps still used by the optimizer. After reloading receipts,
the worker commits entry
into `Learner.update` under the condition lock only while the seed is live. An
abort before this admission prevents optimizer entry; an abort after admission
treats that update as in flight. It cannot forcibly cancel
a hung optimizer or notifier. `join()` is bounded and reports whether the worker
actually stopped. Own signals, leases, engine recycling, process termination
and stopping the actual engine between polls remain parent responsibilities.

`finalize()` requires all actors and learner to have generated, accepted and
trained exactly `32 * 262144`, with zero discarded rows and exactly 32 updates.
It saves `final-manifest.json` with actor counts and receipt-chain digests, game
records and their SHA, completed/unfinished counts, model/config/runtime hashes
and the final checkpoint-chain SHA. Each completed game must supply valid audited
play-rate metadata, and every reported rate must be within 15..80 accepted own
plays per 300 simulated seconds. If the entire run has no completed game,
finalization fails with an unassessed play-rate gate. An unfinished budget tail
is recorded as unfinished and supplies no invented game duration/outcome.
A halted arm cannot produce a completed final manifest. Parent reporting must
preserve its stopped status, final reported generation count and learner state.

## Durability and resume limits

At initialization and every clean successful update, `update-NN.pt` is the
reviewed learner's atomic checkpoint. `update-NN.json` is an fsynced atomic ledger
with full receipt bindings and hash chains, all actor counters, active game
context, completed game audits, config/runtime/policy pins, the learner file SHA
and the preceding ledger SHA. The JSON rename and directory fsync complete before
any next-version permit. Queue acknowledgement follows this checkpoint. A crash
may leave files or a checkpoint without a returned permit; this does not permit
retrying optimization or restarting an engine from that point. Stop during an
update may leave a checkpoint whose learner version advanced while the
coordinator denied all next permits. That seed is stopped.

Resume is deliberately denied. Constructor admission requires a pristine learner
and queue, and every ledger states `engine_resume_qualified=false`. There is no
mid-game resume API and no claim that idempotent file receipts make engines
resumable. A future qualified transport/supervisor must supply and review a full
engine snapshot or deterministic replay proof covering environment/opponent RNG,
command queues, both players, public producer builder, Session history/RNG,
shadow replay history, pending actor row, generation counters, last policy and
unacknowledged publication identities. It must bind original actor/game IDs and
continuation tick without replaying completed games or resampling polls. A lease
restart is a new failure unless that proof is qualified by the parent.

The parent must separately freeze opponent and level factories, seeds, decks,
league/snapshot indices, assembler/source/runtime hashes, selection receipts and
transport metadata provenance. This core checks the supplied runtime identity
and opponent continuity; it does not implement or audit those factories. CPU/GPU
parity, measured actor throughput, memory/queue soak, bank registration, exact
integrated review, lease/signal handling and full RL launch remain separate gates.
