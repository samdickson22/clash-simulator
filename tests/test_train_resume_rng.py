"""Resume RNG continuity (pilot/diagnosis-1M bug 3).

A resumed run used to re-seed every stream from ``--seed`` and replay the first
segment's games. The learning rate is 0 here so the policy is identical across
segments: any repeated game record could only come from replayed RNG streams.
"""

import json
import sys

import numpy as np
import torch

from clasher.rl import train_recurrent

ARGS = [
    "--num-envs", "2",
    "--actor-workers", "1",
    "--opponent-mode", "random",
    "--max-ticks", "100",
    "--decision-interval", "5",
    "--rollout-steps", "16",
    "--d-model", "32",
    "--num-heads", "4",
    "--actor-layers", "1",
    "--critic-layers", "1",
    "--memory-size", "32",
    "--epochs", "1",
    "--sequence-batch-size", "2",
    "--learning-rate", "0",
    "--no-lr-anneal",
    "--device", "cpu",
    "--actor-device", "cpu",
    "--torch-threads", "1",
    "--seed", "11",
    "--save-every", "100",
]


def _segment(monkeypatch, checkpoint_dir, *extra):
    """Run one trainer segment; return its completed games as action/reward records."""
    rollouts = []
    original = train_recurrent.compute_gae

    def capture(rollout, **kwargs):
        rollouts.append((rollout.actions.copy(), rollout.rewards.copy(), rollout.dones.copy()))
        return original(rollout, **kwargs)

    monkeypatch.setattr(train_recurrent, "compute_gae", capture)
    monkeypatch.setattr(
        sys, "argv", ["trainer", "--checkpoint-dir", str(checkpoint_dir), *ARGS, *extra]
    )
    train_recurrent.main()
    games, buffers = [], {}
    for actions, rewards, dones in rollouts:
        for row in range(actions.shape[0]):
            buffer = buffers.setdefault(row, [])
            for step in range(actions.shape[1]):
                buffer.append((int(actions[row, step]), round(float(rewards[row, step]), 6)))
                if dones[row, step]:
                    games.append((row, tuple(buffer)))
                    buffer.clear()
    assert rollouts, "trainer collected no rollout"
    return games


def test_resume_continues_without_replaying_pre_resume_games(monkeypatch, tmp_path):
    torch.set_num_threads(1)
    directory = tmp_path / "run"
    first = _segment(monkeypatch, directory, "--updates", "6")
    assert len(first) >= 4
    checkpoint = directory / "policy_v2_update_000006.pt"
    sidecar = train_recurrent.rng_state_path(directory, 6)
    assert checkpoint.exists() and sidecar.exists()
    assert train_recurrent.load_rng_state(directory, checkpoint=checkpoint, update=6)

    resumed = _segment(monkeypatch, directory, "--updates", "12", "--resume-latest")
    assert len(resumed) >= 4
    first_records = {record for _, record in first}
    assert not first_records & {record for _, record in resumed}

    # Resuming the same checkpoint again (a crash after it) is a new segment
    # with its own streams, so it repeats neither earlier segment.
    again = _segment(
        monkeypatch, directory, "--updates", "12", "--resume-from", str(checkpoint)
    )
    assert not {record for _, record in again} & (
        first_records | {record for _, record in resumed}
    )

    segments = [
        json.loads(line)
        for line in (directory / train_recurrent.RUN_SEGMENTS_FILE).read_text().splitlines()
    ]
    assert [item["segment"] for item in segments] == [0, 1, 2]
    assert [item["start_update"] for item in segments] == [1, 7, 7]
    # Only the first resume from update 6 restores its learner RNG; the second
    # reseeds, or it would replay the first continuation.
    assert [item["rng_state_restored"] for item in segments] == [False, True, False]
    seeds = [item["rollout_seed"] for item in segments]
    assert seeds[0] == 11 and len(set(seeds)) == 3
    assert all(0 <= seed < 2**31 - 2**27 for seed in seeds)


def test_rng_sidecar_round_trip_restores_learner_streams(tmp_path):
    import random

    checkpoint = tmp_path / "policy_v2_update_000007.pt"
    checkpoint.write_bytes(b"checkpoint bytes")
    random.seed(5)
    np.random.seed(5)
    torch.manual_seed(5)
    train_recurrent.save_rng_state(tmp_path, checkpoint=checkpoint, update=7, rollout_seed=5)
    expected = (random.random(), float(np.random.rand()), float(torch.rand(())))
    random.seed(99)
    np.random.seed(99)
    torch.manual_seed(99)
    payload = train_recurrent.load_rng_state(tmp_path, checkpoint=checkpoint, update=7)
    train_recurrent.restore_rng_state(payload["state"])
    assert (random.random(), float(np.random.rand()), float(torch.rand(()))) == expected
    # A sidecar never restores against different checkpoint bytes or update.
    checkpoint.write_bytes(b"other bytes")
    assert train_recurrent.load_rng_state(tmp_path, checkpoint=checkpoint, update=7) is None
    assert train_recurrent.find_latest_checkpoint(tmp_path) == checkpoint
