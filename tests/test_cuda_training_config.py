from __future__ import annotations

import pytest

from clasher.rl.cuda_training_config import (
    CudaSimulationTopologyError,
    validate_cuda_simulation_topology,
)


def test_cpu_default_allows_production_multiprocess_actors() -> None:
    topology = validate_cuda_simulation_topology(
        actor_workers=12,
        num_envs=64,
    )

    assert topology.simulation_device == "cpu"
    assert topology.actor_device == "cpu"
    assert topology.cuda_simulator_contexts == 0
    assert topology.envs_per_worker_upper_bound == 6
    assert topology.topology == "multi-process-non-cuda-simulation"
    assert topology.summary() == (
        "simulation_topology=admitted simulation_device=cpu actor_workers=12 "
        "num_envs=64 envs_per_worker_max=6 actor_device=cpu "
        "cuda_simulator_contexts=0 topology=multi-process-non-cuda-simulation"
    )


@pytest.mark.parametrize("actor_device", ["auto", "cpu", "cuda", "mps"])
def test_single_worker_cuda_batches_all_envs_in_one_context(
    actor_device: str,
) -> None:
    topology = validate_cuda_simulation_topology(
        simulation_device="cuda",
        actor_workers=1,
        num_envs=64,
        actor_device=actor_device,
    )

    assert topology.cuda_simulator_contexts == 1
    assert topology.envs_per_worker_upper_bound == 64
    assert topology.actor_device == actor_device
    assert topology.topology == "single-process-cuda-batch"
    assert topology.as_cli_metadata() == {
        "simulation_device": "cuda",
        "actor_workers": 1,
        "num_envs": 64,
        "envs_per_worker_upper_bound": 64,
        "actor_device": actor_device,
        "cuda_simulator_contexts": 1,
        "topology": "single-process-cuda-batch",
    }


@pytest.mark.parametrize("actor_device", ["auto", "cpu", "cuda"])
def test_multiworker_cuda_is_rejected_independently_of_actor_device(
    actor_device: str,
) -> None:
    with pytest.raises(CudaSimulationTopologyError) as captured:
        validate_cuda_simulation_topology(
            simulation_device="cuda",
            actor_workers=12,
            num_envs=64,
            actor_device=actor_device,
        )

    message = str(captured.value)
    assert "12 independent CUDA contexts" in message
    assert "--actor-workers 1" in message
    assert "one batched H100 context" in message
    assert "--simulation-device cpu" in message
    assert "--actor-device controls policy inference separately" in message


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"actor_workers": 0, "num_envs": 4}, "actor_workers must be positive"),
        ({"actor_workers": 1, "num_envs": 0}, "num_envs must be positive"),
        (
            {"actor_workers": 5, "num_envs": 4},
            "actor_workers cannot exceed num_envs",
        ),
        (
            {
                "simulation_device": "auto",
                "actor_workers": 1,
                "num_envs": 4,
            },
            "simulation_device must be one of",
        ),
        (
            {"actor_workers": 1, "num_envs": 4, "actor_device": "tpu"},
            "actor_device must be one of",
        ),
    ],
)
def test_invalid_topologies_fail_before_process_launch(
    kwargs: dict[str, str | int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_cuda_simulation_topology(**kwargs)  # type: ignore[arg-type]


def test_mps_topology_is_not_mislabeled_as_cuda() -> None:
    topology = validate_cuda_simulation_topology(
        simulation_device="mps",
        actor_workers=3,
        num_envs=8,
        actor_device="cpu",
    )
    assert topology.cuda_simulator_contexts == 0
    assert topology.topology == "multi-process-non-cuda-simulation"
