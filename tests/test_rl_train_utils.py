from __future__ import annotations

import concurrent.futures
import sys

import torch

from clasher.rl import train_selfplay, train_selfplay_async
from clasher.rl.train_selfplay import collect_rollout_parallel, split_rollout_steps


def test_split_rollout_steps_even():
    assert split_rollout_steps(16, 4) == [4, 4, 4, 4]


def test_split_rollout_steps_with_remainder():
    assert split_rollout_steps(10, 3) == [4, 3, 3]


def test_split_rollout_steps_more_workers_than_steps():
    assert split_rollout_steps(3, 8) == [1, 1, 1]


class _CapturingExecutor:
    def __init__(self) -> None:
        self.tasks = []

    def submit(self, _function, task):
        self.tasks.append(task)
        future: concurrent.futures.Future[list] = concurrent.futures.Future()
        future.set_result([])
        return future


class _FakeProcess:
    def __init__(self, *, target, args, daemon) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        return None


class _FakeProcessContext:
    def __init__(self) -> None:
        self.processes = []

    def Queue(self, *, maxsize):  # noqa: N802 - multiprocessing API spelling
        return ("queue", maxsize)

    def Process(self, *, target, args, daemon):  # noqa: N802
        process = _FakeProcess(target=target, args=args, daemon=daemon)
        self.processes.append(process)
        return process


def test_parallel_selfplay_routes_opt_in_backend_to_every_worker() -> None:
    executor = _CapturingExecutor()
    model = torch.nn.Linear(1, 1)

    transitions = collect_rollout_parallel(
        executor=executor,  # type: ignore[arg-type]
        model=model,  # type: ignore[arg-type]
        rollout_steps=3,
        num_workers=2,
        board_channels=1,
        hud_size=1,
        num_actions=1,
        hidden_size=1,
        decision_interval_ticks=8,
        max_ticks=16,
        decks_path="decks.json",
        mirror_match=False,
        quiet_engine=True,
        seed=7,
        worker_retries=0,
        simulation_backend="pytorch-shadow",
    )

    assert transitions == []
    assert [task.simulation_backend for task in executor.tasks] == [
        "pytorch-shadow",
        "pytorch-shadow",
    ]


def test_selfplay_backend_cli_defaults_and_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["train_selfplay"])
    assert train_selfplay.parse_args().simulation_backend == "python"
    monkeypatch.setattr(
        sys,
        "argv",
        ["train_selfplay", "--simulation-backend", "pytorch"],
    )
    assert train_selfplay.parse_args().simulation_backend == "pytorch"

    monkeypatch.setattr(sys, "argv", ["train_selfplay_async"])
    assert train_selfplay_async._parse_args().simulation_backend == "python"
    monkeypatch.setattr(
        sys,
        "argv",
        ["train_selfplay_async", "--simulation-backend", "pytorch-shadow"],
    )
    assert train_selfplay_async._parse_args().simulation_backend == "pytorch-shadow"


def test_async_selfplay_routes_opt_in_backend_to_actor_config() -> None:
    context = _FakeProcessContext()
    actor_cfg_base = {
        "seed": 13,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 32,
        "mirror_match": False,
        "quiet_engine": True,
        "actor_rollout_steps": 2,
        "board_channels": 1,
        "hud_size": 1,
        "num_actions": 2,
        "hidden_size": 4,
        "engine_fast_path": "off",
        "inference_mode": "actor_local",
        "simulation_backend": "pytorch",
    }

    processes, _ = train_selfplay_async._launch_actors(
        ctx=context,
        num_actors=2,
        actor_cfg_base=actor_cfg_base,
        initial_state_dict={},
        data_queue=None,
        error_queue=None,
        stop_event=None,
        compress_obs_to_fp16=False,
    )

    assert len(processes) == 2
    assert [process.args[0].simulation_backend for process in processes] == [
        "pytorch",
        "pytorch",
    ]
