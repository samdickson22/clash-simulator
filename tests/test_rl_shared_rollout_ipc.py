import numpy as np

from clasher.rl.shared_rollout_ipc import (
    SharedRolloutPoolOwner,
    SharedRolloutWriter,
    build_rollout_field_specs,
)


def test_shared_rollout_ipc_roundtrip():
    specs = build_rollout_field_specs(
        transitions_per_batch=8,
        board_shape=(4, 6, 6),
        hud_size=12,
        num_actions=17,
        obs_dtype="float16",
    )
    pool = SharedRolloutPoolOwner(num_actors=1, slots_per_actor=1, field_specs=specs)
    writer = SharedRolloutWriter(pool.actor_slot_handles(0))
    try:
        batch = {
            "boards": np.random.randn(8, 4, 6, 6).astype(np.float16),
            "huds": np.random.randn(8, 12).astype(np.float16),
            "masks": (np.random.rand(8, 17) > 0.5).astype(np.bool_),
            "actions": np.random.randint(0, 17, size=(8,), dtype=np.int64),
            "old_log_probs": np.random.randn(8).astype(np.float32),
            "values": np.random.randn(8).astype(np.float32),
            "rewards": np.random.randn(8).astype(np.float32),
            "dones": (np.random.rand(8) > 0.5).astype(np.bool_),
            "player_ids": np.random.randint(0, 2, size=(8,), dtype=np.int8),
            "next_values": np.random.randn(8).astype(np.float32),
            "mask_shadow_checks": np.asarray([3.0], dtype=np.float32),
            "mask_shadow_mismatches": np.asarray([1.0], dtype=np.float32),
        }
        writer.write_batch(0, batch)
        out = pool.read_batch_copy(0, 0)
        for key in batch:
            np.testing.assert_array_equal(batch[key], out[key])
    finally:
        writer.close()
        pool.close()
