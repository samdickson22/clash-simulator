This collector executes the unchanged 4,608-game expansion schedule in eight
isolated processes. The policy, simulator, public projection, cards, seeds,
relative deals, learner seats and full-game retention rules are unchanged.
The parallel plan requires exact schedule and reserved-role equality with the
sequential plan.

Four- and eight-process probes reproduced every stored array in all twelve
excluded sequential preflight games. Only provenance metadata differed. Before
production collection, this implementation must run its own twelve-game
preflight, compare all arrays again and pass the existing independent preflight
audit. Source and resource hashes cover the worker, scheduler and reused engine.

Each worker initializes the fixed engine, runs one complete game with isolated
RNG streams, validates the archive, and links it atomically to its final name.
Existing archives can only be revalidated on an explicit matching resume.
Worker logs use distinct attempt numbers. The parent preserves original schedule
order in the completion manifest and enforces 18 GiB combined process RSS.

Preflight is an excluded bounded diagnostic and uses its own output lease.
Production holds the shared experiment lock. It cannot overlap the sequential
collector. The sequential run must be stopped deliberately only after the
parallel replacement is ready, and its files must remain intact. Snapshot its
validated prefix with `prefix_audit.py --mode snapshot`. After parallel collection
finishes, compare every stored array in that prefix with `--mode compare`.

The parallel run recollects the entire fixed schedule. The retired prefix is
execution evidence, not an additional training cohort. Fitting requires the full
6,144-game combined audit, prefix parity, new feature authority and memory gate.
No reserved collection or policy update is authorized.

Use the shared Python environment with this directory,
`hog26_parallel_collection_probe`, `hog26_training_expansion`,
`hog26_scalar_pilot`, `src` and the root on `PYTHONPATH`. Run
`collect_parallel.py --mode preflight`, then `publish_parallel_plan.py` after
review. Production uses `collect_parallel.py --mode collect`; a matching partial
resume also supplies `--resume --attempt N` with a new log attempt.
