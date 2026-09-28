# Concurrent exact phase reviews

This execution-only scheduler waits until the original phase supervisor completes all eight fixed bundles and launches the first exact seed review. It verifies every fitting completion, artifact and guard, then pins the schedule, pauses the original parent, and runs the second unchanged reviewer alongside the first.

The paused parent retains the shared experiment lease during the two reviews. One aggregate 18 GiB guard covers both processes. Both reviewers keep one thread and their original source, seeds, metrics, bootstrap rules and output paths. The original worker's exit code is unavailable to the replacement parent; its exclusive completion artifact and reviewed OOF hash must pass, and its receipt states the takeover memory scope explicitly.

After both exact reviews complete, the scheduler retires the owned paused parent, acquires the shared lease, invokes the unchanged scientific-review worker, and publishes root completion with scheduling provenance. Failures preserve every artifact and retire owned processes; they never resume a parent that would duplicate completed reviews.

The source becomes immutable when the waiting process starts; the runtime schedule pin is published only after all fitting inputs are complete and validated. This changes no model fitting, data role, threshold or acceptance claim. Run this scheduler once, from the phase comparison environment. The previous serial parent must not be manually resumed after handoff.
