# Seed 1192101 mb8 observability restart

The process remained active and below the prior OOM footprint, but the frozen
runner buffered stdout and saved only every five updates.  After eight minutes
it had no recoverable learned checkpoint, so a failure before update five would
have destroyed both progress and the update-level diagnostic boundary.

The task-owned process was stopped with only update zero persisted.  The exact
same simulation seed, model, optimizer, rollout, minibatch, and league contract
is restarted under a new artifact root with unbuffered logs and
`save_every=1`.  Checkpoint serialization occurs after an update and does not
change rollout sampling or gradients.  No learned result from this root is
accepted or compared.
