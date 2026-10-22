# Outcome-PPO learner component

`bot/pretrain_v1/rl_learner.py` implements the registered S100/M learner only.
It has no actor loop, queue, launch CLI, scheduling, signal handler or resource
allocation. This component does not grant launch GO. Independent Sol high review
and all preregistered harness/admission gates remain open.

## Construction and identities

Construct `Learner(anchor_path, anchor_sha256=..., model_cfg=...,
runtime_manifest=..., config=LearnerConfig(...), device='cpu')`.

The path must be `anchor.pt` beside the admitted, non-smoke `selection.json`
produced by `select_bc.py`. The supplied SHA must match both the file and receipt;
the checkpoint must have eligible admission, the current `F.feature_hash()`,
exact model configuration, state keys/shapes/dtypes and frozen gate bias. Supply
the full selected `cfg`, including `drop`, `n_cards` and `n_bodies`. Dropout remains
disabled because both networks use `eval()` for every forward, including gradients.
The anchor is a frozen independent copy of that size's own admitted BC model.
The parent must first freeze the selected 83-batch follow-up receipt and exact
runtime/source manifest; the learner does not discover or substitute checkpoints.

`runtime_manifest` is a bounded mapping of at most 128 string keys and string
values, each 1..256 characters. It must contain the preregistered
`native_sha256`, `gamedata_sha256`, and a SHA-256 `actor_source_sha256`. Include
the complete assembler/runtime/source pins frozen by the parent. The learner
checks the registered native/gamedata values and binds every supplied entry.
`manifest_sha256` is SHA-256 of compact sorted-key JSON with separators `,` and
`:`. Each chunk must carry this manifest's `provenance_sha256`.

`anchor_sha256` always identifies the selected anchor FILE. `policy_sha256`
identifies the current MODEL STATE and is different. The public helper
`policy_sha256(model, feature_hash)` computes it as follows:

1. Hash compact sorted JSON `{"cfg": model.cfg, "feature_hash": feature_hash}`.
2. Initialize a new SHA-256 with the ASCII hexadecimal digest from step 1.
3. In sorted `state_dict()` key order, append compact JSON
   `[name, str(numpy_dtype), list(shape)]` and the contiguous CPU tensor bytes.

Version starts at 0 and increments once per successful full update, including
critic-only updates. The current policy SHA includes the critic. Actors must
receive the current complete model state before generating the next version.
The component accepts exactly its expected version, with zero lag.

## Chunk schema

`Chunk` is a frozen dataclass. Its arrays remain host-owned; they must stay alive
and stable until `update` returns. Read-only NumPy arrays, read-only `.npy`
memmaps and detached dense CPU tensors are accepted. No object arrays, pickle
payloads, private feature keys or device tensors are accepted as chunk inputs.
The learner copies only microbatches of features to its device.

`features` contains exactly the tensors returned by `model.collate`, converted
to CPU arrays if desired. Every field has leading dimension `N`:

- `ent`: int16 `[N,E,13]`, `ent_mask`: bool `[N,E]`, with `1 <= E <= 256`.
- `ev`: int16 `[N,V,7]`, `ev_mask`: bool `[N,V]`, with `1 <= V <= 32`.
- `rev`: int16 `[N,R,7]`, `rev_mask`: bool `[N,R]`, with `1 <= R <= 16`.
- `tow`: int16 `[N,6,3]`; `hand`: int16 `[N,5,6]`.
- `glob`: int32 `[N,17]`; `lag`: int16 `[N,4,15]`.
- `slot_ok`: bool `[N,4]`; `alive`: bool `[N,6]`.

Ragged widths may differ across chunks. The learner pads only the microbatch
being read. Masks must be prefix masks; event/reveal presence columns must agree
with their masks. Embedding IDs, slot legality, channel busy state, placement
codes and sampled tile geometry are checked before optimization.

The transition vectors have shape `[N]`:

- `action`: int64 preferred, int16/int32 also accepted; NOOP is 2304,
  otherwise `slot*576+tile`. Accepted action arrays are copied/canonicalized
  to int64 before PyTorch indexing; the supplied arrays are never changed.
- `old_logp`, `old_value`, `reward`: float64 preferred, float32 also accepted.
  Float64 preserves the actor's float32-softmax-to-double sampled likelihood.
- `terminated`, `actor`: bool.
- `dt`: int16 preferred, int32/int64 also accepted. Every entry must equal 5.

Required scalars are `bootstrap`, `version`, `actor_id`, `seed`,
`anchor_sha256`, `policy_sha256`, `generated_steps`, `provenance_sha256`, and
`opponent_id`. Optional scalar `boundary_declined_steps` defaults to 0 and
must be an integer 0 or 1. The two IDs are nonempty strings of at most 256 characters.
`generated_steps` is PER CHUNK, exactly `N`, not an actor's cumulative count.
`bootstrap` is a finite WDL expectation in [-1,1]; a terminal tail requires zero.
`opponent_id` identifies one opponent family for the chunk's per-opponent KL.
The producer currently flushes at game boundaries, so each published chunk has
one game and opponent. Validation also supports true terminal resets within a
chronological chunk, provided the opponent family stays the same.

Polls use the five-tick grid from tick 90. Interior nonterminal rows must advance
by five ticks. A real terminal reset restarts at 90. `glob[G_GAP]` is -1 for the
first observation of a game and 5 thereafter. This is the featurizer's stored
history gap; sampling `dt` remains 5 even at the first observation.
Chunks for each actor must arrive in chronological order within the update;
interleaving actors is allowed. Adjacent continuing chunks must agree on the
next old value and previous bootstrap within `2e-6`. The queue/coordinator owns
game IDs, replay protection, cross-update history continuity and publication
integrity. It must not duplicate terminal games under the same actor identifier.

`actor` must equal `slot_ok.any(axis=1)`, except the explicit boundary decline
below. Forced and busy rows must have NOOP,
zero old log probability and false eligibility. They count toward the full
budget and train value. All other rows, including sampled waits, are eligible.
`boundary_declined_steps=1` declares exactly one declined poll: the final row
of the chunk, at tick 3600 or 6000. That row must have `actor=False`, NOOP and
zero old log probability, even when public features still have legal slots.
This records the frontend's nominal-boundary decline while the engine has not
actually terminated. The actor computes critic/features from the record and a
COPY of `Session.hist`, without calling Session.step, sampling, accepting or
advancing the real history/RNG. The prior row completes nonterminal with reward
zero; the boundary row receives terminal reward only if the engine actually ends
at close, such as tick 3601/6001. An unfinished boundary remains nonterminal and
bootstraps. The learner never infers terminal status from the tick or metadata.

For this row both policy and anchor use a certain-NOOP gate for likelihood,
entropy and KL, while the critic reads the original unchanged public features.
It counts toward the poll budget, trains value, has no policy loss and has zero
entropy/KL. Updated metrics report the count in `boundary_declined_steps`.
No other eligibility exception is accepted, and omitted metadata defaults to
the original strict eligibility rule.

Rewards are zero except a real engine terminal's -1/0/+1. The producer must never
label a chunk boundary, lease stop or unfinished game as a terminal draw.

The public `validate_chunk(chunk, config=..., version=..., anchor_sha256=...,
policy_sha256=..., provenance_sha256=..., model_cfg=...)` checks a single chunk
on CPU and returns feature/vector NumPy views plus the derived boundary-decline
mask. It does not run network parity or
validate a full update's aggregate budget. `Learner.update` performs those checks.

## Updates and accounting

Production `LearnerConfig` allows only S100/M, seeds 2026102101/02/03,
262,144 polls per update, 32 updates, effective batch 2,048 and microbatch 128 or
256. `record()` includes gradient accumulation count and optimizer-step count.
Two epochs give 256 optimizer steps per update. Explicit `test_only=True`
permits toy budgets and batches for component tests. A launch integrator must
reject that flag. It is recorded in every checkpoint.

Call `update(list_of_chunks, play_rates=...)` once with the complete exact quota.
No partial update, trimming, overshoot, lagged data or automatic retry is allowed.
Before the first optimizer step, every stored action's baseline log probability
and old value must agree with the learner within absolute `2e-6`.
CPU Session capture parity is covered by tests. **CPU-actor versus GPU-learner
parity must be measured for the exact admitted models, device settings and
batch shapes before launch. The threshold must not be silently loosened.**

The objective uses `rl_math.joint_terms` and `joint_kl` on the gate and ALL four
conditional tile distributions. Value is softmax WDL P(win)-P(loss). GAE runs
separately through each chronological chunk with gamma 1, lambda .95, actual
terminal resets and nonterminal bootstrap. Eligible advantages normalize once
across the full update. Microbatch policy/entropy/KL sums divide by the entire
optimizer minibatch's eligible count; value divides by its all-poll count.
The first three updates train only `model.value`; update 4 unfreezes the trunk
and policy. AdamW uses constant LR 1e-5, zero decay, PPO clip .2, value .5,
entropy .001, anchor KL .05 and gradient clip 1.

Returned metrics include updated-policy KL mean/p95 over ALL polls, per-opponent
KL, eligible entropy, forced/busy counts, cadence/legal-action check counts,
baseline maximum errors, consumed/trained polls, optimizer steps and state SHA.
Three consecutive PPO updates with updated mean KL > .5 nats/poll halt the seed.
Warmup updates do not count toward that streak.

`PlayRate(game_id, accepted_plays, seconds)` is optional parent-audited completed
game metadata. `seconds` is simulated game duration. The component reports
`300*accepted_plays/seconds` for each supplied game and stops before optimizing
if any rate is below 15 or above 80. Missing metadata is explicitly reported as
`play_rates_reported=False`; that does not pass the parent-owned play-rate gate.
Engine ticks, completed/unfinished games, actor CPU/wall time and per-case pairing
remain coordinator metrics.

Known positive reported generated steps are charged before validation. A failed
update permanently halts this component, even when no optimizer step ran. The
parent also owns the generator's separate cumulative ledger, including lost or
discarded chunks. If generation fails before publication, call
`halt(reason, generated_steps=additional_unreported_polls)` and stop that seed.
Other known positive integer counts are charged even if a chunk reports a malformed count.
Those steps cannot buy replacement data. A halted checkpoint remains halted.

## Checkpoints and remaining integration

`save_checkpoint(path)` writes a temporary file in the destination directory,
flushes/fsyncs it, atomically replaces the destination and fsyncs the directory.
It stores both model states, anchor file/state hashes, feature hash, exact cfg,
selection receipt, full runtime manifest, optimizer, update/budget/optimizer
counters, KL streak, halt state, last metrics, local shuffle RNG, Python RNG,
legacy NumPy RNG, Torch CPU RNG and CUDA RNG states if CUDA was initialized.
Checkpoints use trusted local `torch.save` state serialization. Queue arrays
must use the separate no-pickle stream format; these are distinct formats.

Create a fresh learner with the same admitted anchor, exact config and pins,
then call `load_checkpoint(path)`. It checks identities, counters and optimizer
settings and restores RNGs. CPU continuation is bit-for-bit tested across the
critic-only/PPO boundary. A nonfinite or failed mid-update stops permanently.
Its diagnostic checkpoint can be inspected, but loading requires a provable
completed-update boundary as specified below. It cannot retry the update.
There is no mid-update continuation algorithm or SIGTERM handler here. The parent
must coordinate safe checkpoint boundaries and attach signal/lease handling.
It must checkpoint initial state, milestones 10/20/30, final 32 and stopped arms.

### AdamW resume invariant

The optimizer's single parameter group uses canonical IDs `0..P-1`, in
`model.named_parameters()` order. Group settings and the complete ordered ID
list must match a fresh learner exactly. A permutation, duplicate, relabeling or
subset is invalid, even when the moments have compatible shapes. Optimizer state
keys must be exactly the parameters with positive expected counters. Each entry
contains only `step`, `exp_avg` and `exp_avg_sq`. Moments retain parameter dtype
and shape. `step` is a finite float32 scalar equal to the derived integer count.

For `u` completed updates and `s = 2*steps_per_update/batch_size`:

- Every `value.*` parameter has `u*s` steps.
- Trunk parameters have `max(0,u-3)*s` steps.
- `noop.*`, `ptr.*` and `tile.*` have one step per PPO optimizer minibatch with
  at least one eligible actor row, across both epochs. An all-forced minibatch
  omits the policy loss entirely and gives these heads no gradient. Inside an
  included policy graph, masking can give zero gradients, which still initialize
  and advance AdamW. Absent event/reveal tokens similarly produce zero gradients
  in connected trunk parameters, not missing optimizer states.

Checkpoints retain format 1 and add the required field
`optimizer_resume = {'version': 1, 'ppo_actor_masks': [bytes, ...]}`. Each bytes
value packs the chronological `actor` eligibility vector for one completed PPO
update using NumPy `packbits(..., bitorder='little')`. There must be exactly
`max(0,u-3)` entries, each `ceil(steps_per_update/8)` bytes with zero unused high
bits. A boundary-declined row is false even if its public features have legal
slots. At registered budgets the maximum evidence size is 950,272 bytes.

The loader replays two permutations per completed update from the registered
seed using the unchanged NumPy shuffle algorithm. It applies these permutations
to the stored PPO eligibility vectors to derive head participation, and requires
the resulting RNG state to equal the saved shuffle RNG. The expected parameter
set is never a stored allowlist or a subset of the optimizer state. Deleting the
evidence, deleting an update entry alongside its moments, or deleting any
initialized state fails closed. Older checkpoints without this evidence are
diagnostic inputs only; this loader does not guess their PPO participation.

Both `trained_steps` and `optimizer_steps` must equal their completed-update
formula even for halted checkpoints. A failure after an optimizer step, or after
consuming a shuffle permutation before a step, cannot load. An upstream halt or
validation failure before shuffling may still load as a halted diagnostic state
when all boundary invariants hold. Saving diagnostic partial states remains
available. There is no partial-update recovery or continuation.

These checks detect structural/state corruption in trusted local checkpoints;
they do not authenticate a coordinated rewrite of eligibility bytes, counters,
moments and other checkpoint claims. Full runtime resume qualification, including
queue, engine and distributed coordinator state, remains a parent-owned gate.

Still open: stream writer/queue/coordinator integration, producer/learner parity
on admitted S100 and M, CPU/GPU numerical measurement, queue/memory soak,
generation/discard ledger integration, game/play-rate accounting, DEV/final-bank
registration, snapshot publication, host/lease guards, safe SIGTERM handling and
independent Sol high review of the exact integrated harness/config. No RL
workload has been launched by this component work.
