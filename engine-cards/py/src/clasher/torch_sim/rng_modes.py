"""Explicit resident RNG policy for parity and native training workloads.

The default policy wraps :class:`TensorPythonRandom` and remains eligible for
oracle-parity claims. ``NATIVE_TRAINING`` is a deliberate opt-in wrapper around
:class:`NativeTrainingRNG`; its telemetry and checkpoint metadata permanently
label it non-parity so a faster training stream cannot be reported as exact.

This module is intentionally not wired into the resident engine yet. It gives
future training integration one tensor-only interface for player-order draws,
masked rows, cloning/forking, and checkpoint state without weakening the
simulator's current exact default.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

import torch

from .native_rng import NativeTrainingRNG
from .rng import TensorPythonRandom

_STATE_FORMAT_VERSION = 1


class ResidentRNGMode(IntEnum):
    """Stable checkpoint codes for resident RNG policy."""

    EXACT_PYTHON = 0
    NATIVE_TRAINING = 1


@dataclass(frozen=True)
class ResidentRNGTelemetry:
    """Log-safe policy identity carried alongside rollout measurements."""

    mode: ResidentRNGMode
    label: str
    algorithm: str
    parity_eligible: bool
    native_training_opt_in: bool
    batch_size: int
    device: str


@dataclass(frozen=True)
class ResidentRNG:
    """Mode-safe tensor RNG facade used by future resident training code."""

    _source: TensorPythonRandom | NativeTrainingRNG
    mode: ResidentRNGMode = ResidentRNGMode.EXACT_PYTHON

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", ResidentRNGMode(self.mode))
        if self.mode is ResidentRNGMode.EXACT_PYTHON:
            if not isinstance(self._source, TensorPythonRandom):
                raise TypeError("exact RNG mode requires TensorPythonRandom state")
        elif not isinstance(self._source, NativeTrainingRNG):
            raise TypeError("native training RNG mode requires NativeTrainingRNG state")

    @classmethod
    def exact_from_randoms(
        cls,
        randoms: Sequence[random.Random],
        *,
        device: str | torch.device = "cpu",
    ) -> ResidentRNG:
        return cls(
            TensorPythonRandom.from_randoms(randoms, device=device),
            ResidentRNGMode.EXACT_PYTHON,
        )

    @classmethod
    def native_training_from_seed(
        cls,
        seed: int,
        batch_size: int,
        *,
        device: str | torch.device = "cpu",
    ) -> ResidentRNG:
        return cls(
            NativeTrainingRNG.from_seed(seed, batch_size, device=device),
            ResidentRNGMode.NATIVE_TRAINING,
        )

    @property
    def device(self) -> torch.device:
        return self._source.device

    @property
    def batch_size(self) -> int:
        return self._source.batch_size

    @property
    def parity_eligible(self) -> bool:
        return self.mode is ResidentRNGMode.EXACT_PYTHON

    @property
    def telemetry(self) -> ResidentRNGTelemetry:
        if self.parity_eligible:
            return ResidentRNGTelemetry(
                mode=self.mode,
                label="exact_python_parity",
                algorithm="CPython MT19937",
                parity_eligible=True,
                native_training_opt_in=False,
                batch_size=self.batch_size,
                device=str(self.device),
            )
        return ResidentRNGTelemetry(
            mode=self.mode,
            label="NON_PARITY_native_training",
            algorithm="SplitMix64 counter streams",
            parity_eligible=False,
            native_training_opt_in=True,
            batch_size=self.batch_size,
            device=str(self.device),
        )

    def require_parity(self) -> None:
        """Fail closed when a caller tries to use native state as evidence."""

        if not self.parity_eligible:
            raise RuntimeError(
                "native training RNG is not eligible for behavioral parity claims"
            )

    def _active_mask(self, active: torch.Tensor | None) -> torch.Tensor:
        if active is None:
            return torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
        mask = torch.as_tensor(active, dtype=torch.bool, device=self.device)
        if mask.shape != (self.batch_size,):
            raise ValueError("active RNG mask must have shape [batch_size]")
        return mask

    def draw_player_order(self, active: torch.Tensor | None = None) -> torch.Tensor:
        """Draw exact-shuffle-compatible two-player order for selected rows.

        Inactive rows publish the canonical ``[0, 1]`` order and do not advance
        either RNG implementation. Active exact rows consume precisely the one
        ``randrange(2)`` draw used by ``random.shuffle([0, 1])``.
        """

        mask = self._active_mask(active)
        if self.mode is ResidentRNGMode.EXACT_PYTHON:
            assert isinstance(self._source, TensorPythonRandom)
            choice = self._source.randrange(2, mask)
        else:
            assert isinstance(self._source, NativeTrainingRNG)
            choice = (self._source.random(active=mask, dtype=torch.float64) * 2.0).to(
                torch.int64
            )
        drawn = torch.stack((1 - choice, choice), dim=1)
        canonical = torch.tensor((0, 1), dtype=torch.int64, device=self.device)
        return torch.where(mask[:, None], drawn, canonical[None, :])

    def clone(self) -> ResidentRNG:
        return type(self)(self._source.clone(), self.mode)

    def fork(self, rows: Sequence[int] | torch.Tensor) -> ResidentRNG:
        return type(self)(self._source.fork(rows), self.mode)

    def state_dict(self) -> dict[str, torch.Tensor]:
        """Return tensor-only state with validated mode/parity metadata."""

        metadata = {
            "format_version": torch.tensor(
                _STATE_FORMAT_VERSION, dtype=torch.int64, device=self.device
            ),
            "mode": torch.tensor(int(self.mode), dtype=torch.int64, device=self.device),
            "parity_eligible": torch.tensor(
                self.parity_eligible, dtype=torch.bool, device=self.device
            ),
        }
        if self.mode is ResidentRNGMode.EXACT_PYTHON:
            assert isinstance(self._source, TensorPythonRandom)
            return {
                **metadata,
                "words": self._source.words.clone(),
                "index": self._source.index.clone(),
                "gauss_value": self._source.gauss_value.clone(),
                "gauss_cached": self._source.gauss_cached.clone(),
            }
        assert isinstance(self._source, NativeTrainingRNG)
        return {**metadata, "native_state": self._source.state.clone()}

    def load_state_dict_(self, state: dict[str, torch.Tensor]) -> None:
        """Restore only a checkpoint whose policy identity matches this mode."""

        required = {"format_version", "mode", "parity_eligible"}
        missing = required - state.keys()
        if missing:
            raise ValueError(f"resident RNG state is missing {sorted(missing)!r}")
        version = int(state["format_version"].item())
        incoming_mode = ResidentRNGMode(int(state["mode"].item()))
        incoming_parity = bool(state["parity_eligible"].item())
        if version != _STATE_FORMAT_VERSION:
            raise ValueError(f"unsupported resident RNG state version {version}")
        if incoming_mode is not self.mode or incoming_parity != self.parity_eligible:
            raise ValueError("resident RNG checkpoint mode/parity identity differs")

        if self.mode is ResidentRNGMode.NATIVE_TRAINING:
            assert isinstance(self._source, NativeTrainingRNG)
            native_state = state.get("native_state")
            if native_state is None:
                raise ValueError("native resident RNG state is missing 'native_state'")
            self._source.load_state_dict_({"state": native_state})
            return

        assert isinstance(self._source, TensorPythonRandom)
        exact_fields = {
            "words": self._source.words,
            "index": self._source.index,
            "gauss_value": self._source.gauss_value,
            "gauss_cached": self._source.gauss_cached,
        }
        for name, destination in exact_fields.items():
            incoming = state.get(name)
            if incoming is None:
                raise ValueError(f"exact resident RNG state is missing {name!r}")
            value = incoming.to(device=self.device, dtype=destination.dtype)
            if value.shape != destination.shape:
                raise ValueError(f"exact resident RNG field {name!r} changed shape")
            destination.copy_(value)


def create_resident_rng(
    randoms: Sequence[random.Random],
    *,
    mode: ResidentRNGMode = ResidentRNGMode.EXACT_PYTHON,
    native_seed: int | None = None,
    device: str | torch.device = "cpu",
) -> ResidentRNG:
    """Create the explicit resident RNG policy, defaulting to exact parity."""

    selected = ResidentRNGMode(mode)
    if selected is ResidentRNGMode.EXACT_PYTHON:
        if native_seed is not None:
            raise ValueError(
                "native_seed is invalid unless native training mode is set"
            )
        return ResidentRNG.exact_from_randoms(randoms, device=device)
    if native_seed is None:
        raise ValueError("native training RNG requires an explicit native_seed")
    if not randoms:
        raise ValueError("at least one resident RNG row is required")
    return ResidentRNG.native_training_from_seed(
        native_seed,
        len(randoms),
        device=device,
    )


__all__ = [
    "ResidentRNG",
    "ResidentRNGMode",
    "ResidentRNGTelemetry",
    "create_resident_rng",
]
