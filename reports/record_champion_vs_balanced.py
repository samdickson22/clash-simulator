from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

import pygame

from clasher.rl.strategy_bots import BALANCED, StrategyBot


VISUALIZER_FILE = Path(
    "/Users/sam/.codex/worktrees/34d3/clasher/"
    "src/clasher/rl/watch_policy_battle.py"
)
VISUALIZER_ROOT = VISUALIZER_FILE.parents[3]


@dataclass(frozen=True)
class StrategyIdentity:
    filename: str = "strategy_bot_balanced"
    update: int = 0
    transitions: int = 0

    @property
    def short_label(self) -> str:
        return "Strategy bot • balanced"


class StrategyEnvironmentAdapter:
    def __init__(self, viewer) -> None:
        self.viewer = viewer
        self.action_space = viewer.action_space

    @property
    def battle(self):
        return self.viewer.battle

    def get_action_mask(self, player_id: int):
        return self.action_space.legal_action_mask(self.battle, player_id)


def load_visualizer_module():
    root = str(VISUALIZER_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(
        "clasher_polished_visualizer",
        VISUALIZER_FILE,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load visualizer from {VISUALIZER_FILE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1_044_801)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--final-hold-seconds", type=float, default=3.0)
    parser.add_argument("--max-battle-seconds", type=float, default=305.0)
    args = parser.parse_args()

    if args.fps % 20 != 0:
        raise ValueError("fps must be divisible by the native 20 Hz tick rate")
    renders_per_tick = args.fps // 20
    visualizer_module = load_visualizer_module()

    class ChampionVsBalancedVisualizer(visualizer_module.PolicyBattleVisualizer):
        def __init__(self, **kwargs) -> None:
            super().__init__(opponent_random=True, **kwargs)
            self.strategy_bot = StrategyBot(BALANCED)
            self.strategy_env = StrategyEnvironmentAdapter(self)
            self.policy_identities[1] = StrategyIdentity()

        def _policy_action(self, player_id: int) -> int:
            if player_id == 1:
                action_mask = self.action_space.legal_action_mask(
                    self.battle,
                    player_id,
                )
                return self.strategy_bot.select_action(
                    self.strategy_env,
                    player_id,
                    action_mask=action_mask,
                )
            return super()._policy_action(player_id)

    viewer = ChampionVsBalancedVisualizer(
        checkpoint=str(args.checkpoint.resolve()),
        decks_path=str(args.decks_path.resolve()),
        decision_interval=8,
        device="cpu",
        deterministic=False,
        seed=args.seed,
        mirror_match=True,
        auto_reset_seconds=0.0,
    )
    if not viewer.show_targets:
        raise RuntimeError("tactical overlays must be enabled for this recording")

    candidate = viewer.policy_identities[0]
    if candidate is None or candidate.update != 40:
        raise RuntimeError(f"unexpected candidate checkpoint identity: {candidate}")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoder = subprocess.Popen(
        [
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
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    if encoder.stdin is None:
        raise RuntimeError("FFmpeg stdin pipe was not created")

    max_ticks = round(args.max_battle_seconds * 20)
    frames = 0
    started = time.monotonic()
    next_progress = 30.0
    try:
        while not viewer.battle.game_over and viewer.battle.tick < max_ticks:
            # Each native state is rendered for exactly three 60 Hz frames.
            for _ in range(renders_per_tick):
                viewer.draw_frame()
                encoder.stdin.write(pygame.image.tobytes(viewer.screen, "RGB"))
                pygame.event.pump()
                viewer.clock.tick(args.fps)
                frames += 1

            viewer._maybe_take_actions()
            viewer.battle.step(speed_factor=1.0)

            elapsed = time.monotonic() - started
            if elapsed >= next_progress:
                print(
                    f"progress wall={elapsed:.0f}s battle={viewer.battle.time:.1f}s "
                    f"frames={frames} tick={viewer.battle.tick}",
                    flush=True,
                )
                next_progress += 30.0

        if not viewer.battle.game_over:
            raise RuntimeError("battle did not finish before the native-time guard")

        viewer.game_over_since = time.monotonic()
        viewer.draw_frame()
        final_frame = pygame.image.tobytes(viewer.screen, "RGB")
        for _ in range(round(args.final_hold_seconds * args.fps)):
            encoder.stdin.write(final_frame)
            viewer.clock.tick(args.fps)
            frames += 1
    finally:
        encoder.stdin.close()
        return_code = encoder.wait()
        pygame.quit()

    if return_code != 0:
        raise RuntimeError(f"FFmpeg exited with status {return_code}")

    print(f"output={output}")
    print(f"candidate={candidate}")
    print("opponent=strategy:balanced")
    print(f"winner={viewer.battle.winner}")
    print(
        f"crowns={viewer.battle.get_crown_count(0)}-"
        f"{viewer.battle.get_crown_count(1)}"
    )
    print(f"battle_seconds={viewer.battle.time:.2f}")
    print(f"frames={frames}")
    print(f"video_seconds={frames / args.fps:.2f}")
    print(f"wall_seconds={time.monotonic() - started:.2f}")


if __name__ == "__main__":
    main()
