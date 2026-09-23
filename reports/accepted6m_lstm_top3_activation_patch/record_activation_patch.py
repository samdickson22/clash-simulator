from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import numpy as np
import pygame
import torch

from clasher.rl.strategy_bots import StrategyBot


VISUALIZER_FILE = Path(
    "/Users/sam/.codex/worktrees/34d3/clasher/"
    "src/clasher/rl/watch_policy_battle.py"
)
VISUALIZER_ROOT = VISUALIZER_FILE.parents[3]
CHECKPOINT_SHA256 = "cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305"
BASIS_SHA256 = "24f29f6a512efbafcbd3071296deeb9e3dd7df37b95d1f8d0732f7ce12f920a4"
VALID_STRATEGIES = (
    "bridge-pressure",
    "slow-push",
    "spell-control",
    "reactive-defense",
    "split-lane",
    "balanced",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_visualizer_module():
    root = str(VISUALIZER_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(
        "clasher_activation_patch_visualizer",
        VISUALIZER_FILE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load visualizer from {VISUALIZER_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class DisplayIdentity:
    filename: str
    transitions: int
    label: str

    @property
    def short_label(self) -> str:
        return self.label


class StrategyEnvironmentAdapter:
    def __init__(self, viewer: Any) -> None:
        self.viewer = viewer
        self.action_space = viewer.action_space

    @property
    def battle(self):
        return self.viewer.battle

    def get_action_mask(self, player_id: int):
        return self.action_space.legal_action_mask(self.battle, player_id)


def action_summary(viewer: Any, actions: list[int]) -> dict[str, Any]:
    kinds: Counter[str] = Counter()
    for action in actions:
        selection = viewer.action_space.decode_action(action, 0)
        if selection.is_no_op:
            kinds["wait"] += 1
        elif selection.is_ability:
            kinds["ability"] += 1
        else:
            kinds["placement"] += 1
    packed = np.asarray(actions, dtype=np.int32).tobytes()
    return {
        "count": len(actions),
        "sha256_int32_le": hashlib.sha256(packed).hexdigest(),
        "counts": dict(sorted(kinds.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record one deterministic baseline or LSTM activation-patched battle"
    )
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, required=True)
    parser.add_argument("--strategy", choices=VALID_STRATEGIES, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--arm", choices=("baseline", "patched"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--ticks-per-frame", type=int, default=4)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--final-hold-seconds", type=float, default=3.0)
    parser.add_argument("--max-native-ticks", type=int, default=6_200)
    parser.add_argument("--crf", type=int, default=28)
    args = parser.parse_args()

    checkpoint = args.checkpoint.resolve(strict=True)
    basis_path = args.basis.resolve(strict=True)
    decks_path = args.decks_path.resolve(strict=True)
    output = args.output.resolve()
    if sha256_file(checkpoint) != CHECKPOINT_SHA256:
        raise RuntimeError("checkpoint SHA-256 does not match the accepted immutable input")
    if sha256_file(basis_path) != BASIS_SHA256:
        raise RuntimeError("basis SHA-256 does not match the frozen immutable input")
    if args.fps <= 0 or args.ticks_per_frame <= 0:
        raise ValueError("fps and ticks-per-frame must be positive")
    if output.suffix.lower() != ".mp4":
        raise ValueError("output must be an MP4")

    basis = np.load(basis_path)
    hidden_mean_np = np.asarray(basis["hidden_mean"], dtype=np.float32)
    components_np = np.asarray(basis["hidden_components"], dtype=np.float32)
    explained = np.asarray(basis["explained_variance_ratio"], dtype=np.float64)
    if hidden_mean_np.shape != (384,) or components_np.shape != (3, 384):
        raise RuntimeError(
            f"unexpected basis shapes: mean={hidden_mean_np.shape}, "
            f"components={components_np.shape}"
        )
    gram_error = float(np.max(np.abs(components_np @ components_np.T - np.eye(3))))
    if gram_error > 1e-4:
        raise RuntimeError(f"basis components are not orthonormal: max error {gram_error}")

    visualizer_module = load_visualizer_module()

    class ActivationPatchVisualizer(visualizer_module.PolicyBattleVisualizer):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(opponent_random=True, **kwargs)
            self.strategy_bot = StrategyBot(args.strategy)
            self.strategy_env = StrategyEnvironmentAdapter(self)
            self.decision_actions: dict[int, list[int]] = {0: [], 1: []}
            self.decision_ticks: list[int] = []
            self.policy_identities[0] = DisplayIdentity(
                filename=checkpoint.name,
                transitions=6_190_000,
                label=(
                    "Accepted 6.19M • baseline"
                    if args.arm == "baseline"
                    else "Accepted 6.19M • LSTM top-3 PCs removed"
                ),
            )
            self.policy_identities[1] = DisplayIdentity(
                filename=f"strategy_bot_{args.strategy}",
                transitions=0,
                label=f"StrategyBot • {args.strategy}",
            )

        def _policy_action(self, player_id: int) -> int:
            if player_id == 1:
                action_mask = self.action_space.legal_action_mask(
                    self.battle,
                    player_id,
                )
                return int(
                    self.strategy_bot.select_action(
                        self.strategy_env,
                        player_id,
                        action_mask=action_mask,
                    )
                )
            return super()._policy_action(player_id)

        def _maybe_take_actions(self) -> None:
            previous_tick = self.last_decision_tick
            super()._maybe_take_actions()
            if self.last_decision_tick != previous_tick:
                self.decision_ticks.append(int(self.last_decision_tick))
                for player_id in (0, 1):
                    self.decision_actions[player_id].append(
                        int(self.previous_actions[player_id])
                    )

    viewer = ActivationPatchVisualizer(
        checkpoint=str(checkpoint),
        decks_path=str(decks_path),
        decision_interval=args.decision_interval,
        device="cpu",
        deterministic=True,
        seed=args.seed,
        mirror_match=True,
        auto_reset_seconds=0.0,
    )
    if viewer.screen.get_size() != (1200, 900):
        raise RuntimeError(f"unexpected render size: {viewer.screen.get_size()}")
    if not viewer.show_targets:
        raise RuntimeError("sight ranges and target locks must be enabled")

    candidate = viewer.policies[0]
    if candidate is None:
        raise RuntimeError("candidate policy did not load")
    cells = [
        (name, module)
        for name, module in candidate.model.named_modules()
        if isinstance(module, torch.nn.LSTMCell)
    ]
    if len(cells) != 1:
        raise RuntimeError(f"expected exactly one nn.LSTMCell, found {len(cells)}")
    cell_name, cell = cells[0]
    if cell.hidden_size != hidden_mean_np.shape[0]:
        raise RuntimeError(
            f"LSTM hidden size {cell.hidden_size} does not match basis "
            f"{hidden_mean_np.shape[0]}"
        )

    hook_calls = 0
    removed_norm_sum = 0.0
    removed_norm_sq_sum = 0.0
    removed_norm_max = 0.0
    hook_handle = None
    if args.arm == "patched":
        hidden_mean = torch.from_numpy(hidden_mean_np).to(viewer.device)
        components = torch.from_numpy(components_np).to(viewer.device)

        def remove_top_components(_module, _inputs, output_tensors):
            nonlocal hook_calls, removed_norm_sum, removed_norm_sq_sum, removed_norm_max
            h, c = output_tensors
            mean = hidden_mean.to(dtype=h.dtype, device=h.device)
            pcs = components.to(dtype=h.dtype, device=h.device)
            removed = ((h - mean) @ pcs.T) @ pcs
            patched_h = h - removed
            norms = torch.linalg.vector_norm(removed, dim=-1)
            norm_sum = float(norms.sum().item())
            hook_calls += int(norms.numel())
            removed_norm_sum += norm_sum
            removed_norm_sq_sum += float((norms * norms).sum().item())
            removed_norm_max = max(removed_norm_max, float(norms.max().item()))
            return patched_h, c

        hook_handle = cell.register_forward_hook(remove_top_components)

    output.parent.mkdir(parents=True, exist_ok=True)
    sidecar = output.with_suffix(".json")
    partial = output.with_suffix(".partial.mp4")
    for owned_path in (partial,):
        if owned_path.exists():
            owned_path.unlink()

    ffmpeg_command = [
        "/opt/homebrew/bin/ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        "1200x900",
        "-r",
        str(args.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(args.crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(partial),
    ]
    encoder = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE)
    if encoder.stdin is None:
        raise RuntimeError("FFmpeg stdin pipe was not created")

    frames = 0
    gameplay_frames = 0
    started = time.monotonic()
    next_progress_tick = 1_000
    run_error: BaseException | None = None
    try:
        while not viewer.battle.game_over and viewer.battle.tick < args.max_native_ticks:
            for _ in range(args.ticks_per_frame):
                if viewer.battle.game_over:
                    break
                viewer._maybe_take_actions()
                viewer.battle.step(speed_factor=1.0)
            viewer.draw_frame()
            encoder.stdin.write(pygame.image.tobytes(viewer.screen, "RGB"))
            pygame.event.pump()
            frames += 1
            gameplay_frames += 1
            if viewer.battle.tick >= next_progress_tick:
                print(
                    f"progress strategy={args.strategy} arm={args.arm} "
                    f"tick={viewer.battle.tick} frames={frames}",
                    flush=True,
                )
                next_progress_tick += 1_000

        if not viewer.battle.game_over:
            raise RuntimeError(
                f"battle did not reach natural game_over by tick {args.max_native_ticks}"
            )
        viewer.game_over_since = time.monotonic()
        viewer.draw_frame()
        final_frame = pygame.image.tobytes(viewer.screen, "RGB")
        hold_frames = round(args.final_hold_seconds * args.fps)
        for _ in range(hold_frames):
            encoder.stdin.write(final_frame)
            frames += 1
    except BaseException as exc:
        run_error = exc
    finally:
        if hook_handle is not None:
            hook_handle.remove()
        try:
            encoder.stdin.close()
        except BrokenPipeError:
            pass
        return_code = encoder.wait()
        pygame.quit()

    if run_error is not None:
        if partial.exists():
            partial.unlink()
        raise run_error
    if return_code != 0:
        if partial.exists():
            partial.unlink()
        raise RuntimeError(f"FFmpeg exited with status {return_code}")
    if output.exists():
        output.unlink()
    partial.replace(output)

    crowns = [
        int(viewer.battle.get_crown_count(0)),
        int(viewer.battle.get_crown_count(1)),
    ]
    winner = viewer.battle.winner
    result = "draw" if winner is None else f"p{int(winner)}_win"
    hook_stats = {
        "enabled": args.arm == "patched",
        "module": cell_name,
        "calls": hook_calls,
        "removed_l2_mean": (
            removed_norm_sum / hook_calls if hook_calls else 0.0
        ),
        "removed_l2_rms": (
            math.sqrt(removed_norm_sq_sum / hook_calls) if hook_calls else 0.0
        ),
        "removed_l2_max": removed_norm_max,
        "cell_state_unchanged": True,
    }
    command = " ".join(sys.argv)
    metadata = {
        "schema_version": 1,
        "strategy": args.strategy,
        "seed": args.seed,
        "arm": args.arm,
        "result": result,
        "winner": winner,
        "crowns": crowns,
        "native_ticks": int(viewer.battle.tick),
        "battle_seconds": float(viewer.battle.time),
        "frames": frames,
        "gameplay_frames": gameplay_frames,
        "hold_frames": round(args.final_hold_seconds * args.fps),
        "fps": args.fps,
        "ticks_per_frame": args.ticks_per_frame,
        "resolution": [1200, 900],
        "crf": args.crf,
        "decision_interval": args.decision_interval,
        "mirror_match": True,
        "deterministic": True,
        "seat": {"candidate": 0, "strategy_bot": 1},
        "decks": {str(key): value for key, value in viewer.current_decks.items()},
        "labels": {
            "p0": viewer.policy_identities[0].short_label,
            "p1": viewer.policy_identities[1].short_label,
        },
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "basis": str(basis_path),
        "basis_sha256": BASIS_SHA256,
        "basis_explained_variance_ratio": explained.tolist(),
        "basis_explained_variance_ratio_sum": float(explained.sum()),
        "basis_component_orthonormal_max_error": gram_error,
        "hook": hook_stats,
        "actions": {
            "p0": action_summary(viewer, viewer.decision_actions[0]),
            "p1": action_summary(viewer, viewer.decision_actions[1]),
            "decision_tick_sha256_int32_le": hashlib.sha256(
                np.asarray(viewer.decision_ticks, dtype=np.int32).tobytes()
            ).hexdigest(),
        },
        "output": str(output),
        "exact_command": command,
        "ffmpeg_command": ffmpeg_command[:-1] + [str(output)],
        "wall_seconds": time.monotonic() - started,
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
