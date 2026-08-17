"""Fail-closed topology validation for CUDA-resident simulation training.

CUDA simulation is safe in one actor process today. Spawning several actor
processes with ``simulation_device=cuda`` would create one independent CUDA
context and one copy of retained simulator state per process, defeating batch
sharing and risking H100 memory exhaustion. This module is intentionally pure
configuration logic so trainers can call it before importing models, creating
environments, or spawning workers.
"""

from __future__ import annotations

from dataclasses import dataclass

_SIMULATION_DEVICES = frozenset({"cpu", "cuda", "mps"})
_ACTOR_DEVICES = frozenset({"auto", "cpu", "cuda", "mps"})


class CudaSimulationTopologyError(ValueError):
    """Raised before worker creation for an unsafe CUDA simulator topology."""


@dataclass(frozen=True)
class SimulationTopology:
    """Validated simulator and policy-inference process placement."""

    simulation_device: str
    actor_workers: int
    num_envs: int
    actor_device: str
    cuda_simulator_contexts: int
    topology: str

    @property
    def envs_per_worker_upper_bound(self) -> int:
        return (self.num_envs + self.actor_workers - 1) // self.actor_workers

    def summary(self) -> str:
        """Return stable key/value text suitable for startup logs."""

        return (
            "simulation_topology=admitted "
            f"simulation_device={self.simulation_device} "
            f"actor_workers={self.actor_workers} "
            f"num_envs={self.num_envs} "
            f"envs_per_worker_max={self.envs_per_worker_upper_bound} "
            f"actor_device={self.actor_device} "
            f"cuda_simulator_contexts={self.cuda_simulator_contexts} "
            f"topology={self.topology}"
        )

    def as_cli_metadata(self) -> dict[str, str | int]:
        """Return JSON/report-friendly validated configuration metadata."""

        return {
            "simulation_device": self.simulation_device,
            "actor_workers": self.actor_workers,
            "num_envs": self.num_envs,
            "envs_per_worker_upper_bound": self.envs_per_worker_upper_bound,
            "actor_device": self.actor_device,
            "cuda_simulator_contexts": self.cuda_simulator_contexts,
            "topology": self.topology,
        }


def validate_cuda_simulation_topology(
    *,
    simulation_device: str = "cpu",
    actor_workers: int,
    num_envs: int,
    actor_device: str = "cpu",
) -> SimulationTopology:
    """Validate production placement before any actor process is launched.

    ``actor_device`` describes policy inference only and never changes the
    simulator ownership rule. A CUDA actor and CUDA simulator may share the
    one admitted actor process. Multi-process CUDA simulation remains rejected
    until the project has a central GPU simulation service.
    """

    if simulation_device not in _SIMULATION_DEVICES:
        choices = ", ".join(sorted(_SIMULATION_DEVICES))
        raise ValueError(f"simulation_device must be one of: {choices}")
    if actor_device not in _ACTOR_DEVICES:
        choices = ", ".join(sorted(_ACTOR_DEVICES))
        raise ValueError(f"actor_device must be one of: {choices}")
    if actor_workers < 1:
        raise ValueError("actor_workers must be positive")
    if num_envs < 1:
        raise ValueError("num_envs must be positive")
    if actor_workers > num_envs:
        raise ValueError("actor_workers cannot exceed num_envs")

    if simulation_device == "cuda" and actor_workers != 1:
        raise CudaSimulationTopologyError(
            "unsafe CUDA simulator topology: "
            f"--simulation-device cuda with --actor-workers {actor_workers} "
            f"would create {actor_workers} independent CUDA contexts for "
            f"--num-envs {num_envs}. Until a central GPU simulation service "
            "exists, use --actor-workers 1 so all environments share one "
            "batched H100 context, or use --simulation-device cpu for "
            "multi-process actors. --actor-device controls policy inference "
            "separately and does not make multiple simulator contexts safe."
        )

    cuda_contexts = 1 if simulation_device == "cuda" else 0
    topology = (
        "single-process-cuda-batch"
        if simulation_device == "cuda"
        else "multi-process-non-cuda-simulation"
        if actor_workers > 1
        else "single-process-non-cuda-simulation"
    )
    return SimulationTopology(
        simulation_device=simulation_device,
        actor_workers=actor_workers,
        num_envs=num_envs,
        actor_device=actor_device,
        cuda_simulator_contexts=cuda_contexts,
        topology=topology,
    )


__all__ = [
    "CudaSimulationTopologyError",
    "SimulationTopology",
    "validate_cuda_simulation_topology",
]
