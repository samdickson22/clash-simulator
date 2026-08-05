from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from gymnasium.envs.registration import register, registry

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .selfplay_env import SelfPlayBattleEnv
from clasher.battle import STANDARD_MATCH_TICKS

ActionMode = Literal["flat", "xyz"]
OpponentPolicy = Literal["random", "noop"]


@contextmanager
def _maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def _summarize_mask(flat_mask: np.ndarray, max_legal: int) -> Dict[str, Any]:
    legal = np.flatnonzero(flat_mask.astype(np.bool_, copy=False))
    hasher = hashlib.sha256(np.ascontiguousarray(flat_mask).tobytes())
    return {
        "legal_action_count": int(legal.size),
        "legal_actions": [int(x) for x in legal[:max_legal]],
        "legal_actions_truncated": bool(legal.size > max_legal),
        "mask_sha256": hasher.hexdigest(),
    }


class ClasherSelfPlayGymEnv(gym.Env):
    """Single-agent Gym wrapper with CV-dict observations only."""

    metadata = {"render_modes": ["rgb_array"], "render_fps": 16}

    def __init__(
        self,
        render_mode: Optional[str] = None,
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
        decks_path: str = "decks.json",
        seed: Optional[int] = None,
        mirror_match: bool = False,
        canonical_perspective: bool = True,
        opponent_policy: OpponentPolicy = "random",
        quiet_engine: bool = True,
        action_mode: ActionMode = "flat",
    ) -> None:
        super().__init__()
        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(f"Unsupported render_mode={render_mode!r}")
        if action_mode not in {"flat", "xyz"}:
            raise ValueError(f"Unsupported action_mode={action_mode!r}")
        if opponent_policy not in {"random", "noop"}:
            raise ValueError(f"Unsupported opponent_policy={opponent_policy!r}")

        self.render_mode = render_mode
        self.action_mode = action_mode
        self.opponent_policy = opponent_policy
        self.quiet_engine = quiet_engine
        self._rng = np.random.default_rng(seed)

        self._env = SelfPlayBattleEnv(
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=max_ticks,
            decks_path=decks_path,
            seed=seed,
            mirror_match=mirror_match,
            canonical_perspective=canonical_perspective,
        )
        with _maybe_silence_stdio(self.quiet_engine):
            self._env.reset(seed=seed)

        spec = self._env.obs_builder.spec
        self._flat_action_space = spaces.Discrete(self._env.action_space.num_actions)
        if self.action_mode == "flat":
            self.action_space = self._flat_action_space
        else:
            self.action_space = spaces.MultiDiscrete(
                np.array([BOARD_WIDTH, BOARD_HEIGHT, NUM_HAND_SLOTS + 2], dtype=np.int64)
            )

        self.observation_space = spaces.Dict(
            {
                "board": spaces.Box(
                    low=0.0,
                    high=3.0,
                    shape=(spec.board_channels, BOARD_HEIGHT, BOARD_WIDTH),
                    dtype=np.float32,
                ),
                "hud": spaces.Box(
                    low=0.0,
                    high=1.0,
                    shape=(spec.hud_size,),
                    dtype=np.float32,
                ),
            }
        )

    def _small_rgb_from_board(self, board: np.ndarray) -> np.ndarray:
        terrain = board[:3].sum(axis=0)
        own_troops = board[7] + board[9]
        enemy_troops = board[8] + board[10]
        own_structures = board[3] + board[5]
        enemy_structures = board[4] + board[6]
        frame = np.stack(
            [
                np.clip(terrain + enemy_troops + enemy_structures, 0.0, 1.0),
                np.clip(terrain + own_troops + own_structures, 0.0, 1.0),
                np.clip(terrain, 0.0, 1.0),
            ],
            axis=-1,
        )
        return (frame * 255.0).astype(np.uint8, copy=False)

    def _obs_for_player_zero(self) -> Dict[str, np.ndarray]:
        obs = self._env.get_observation(0)
        return {"board": obs.board, "hud": obs.hud}

    def _select_opponent_action(self) -> int:
        if self.opponent_policy == "random":
            assert self._env.battle is not None
            return self._env.action_space.random_legal_action(
                self._env.battle, player_id=1, rng=self._rng
            )
        return self._env.action_space.no_op_action

    def _flat_mask_to_xyz(self, flat_mask: np.ndarray) -> np.ndarray:
        xyz = np.zeros((BOARD_WIDTH, BOARD_HEIGHT, NUM_HAND_SLOTS + 2), dtype=np.bool_)
        for slot in range(NUM_HAND_SLOTS):
            start = slot * NUM_TILES
            stop = start + NUM_TILES
            tile_mask = flat_mask[start:stop].reshape(BOARD_HEIGHT, BOARD_WIDTH)
            xyz[:, :, slot] = tile_mask.T
        xyz[:, :, NUM_HAND_SLOTS] = True
        xyz[:, :, NUM_HAND_SLOTS + 1] = flat_mask[self._env.action_space.ability_action]
        return xyz

    def legal_action_mask_flat(self) -> np.ndarray:
        return self._env.get_action_mask(0)

    def legal_action_mask(self) -> np.ndarray:
        flat = self.legal_action_mask_flat()
        if self.action_mode == "flat":
            return flat
        return self._flat_mask_to_xyz(flat)

    def _decode_agent_action(self, action: Any) -> tuple[int, bool]:
        no_op = self._env.action_space.no_op_action
        if self.action_mode == "flat":
            try:
                flat = int(action)
            except (TypeError, ValueError):
                return no_op, False
            if flat < 0 or flat >= self._env.action_space.num_actions:
                return no_op, False
            return flat, True

        arr = np.asarray(action, dtype=np.int64).reshape(-1)
        if arr.size != 3:
            return no_op, False
        x, y, slot = int(arr[0]), int(arr[1]), int(arr[2])
        if not self.action_space.contains(np.array([x, y, slot], dtype=np.int64)):
            return no_op, False
        if slot == NUM_HAND_SLOTS:
            return no_op, True
        if slot == NUM_HAND_SLOTS + 1:
            return self._env.action_space.ability_action, True
        return self._env.action_space.encode_action(slot=slot, world_x=x, world_y=y, player_id=0), True

    def _build_info(
        self,
        *,
        opponent_action: int,
        action_success: bool,
        ticks_advanced: int,
        agent_action_valid: bool,
        agent_action_flat: int,
    ) -> Dict[str, Any]:
        flat_mask = self.legal_action_mask_flat()
        action_mask = flat_mask if self.action_mode == "flat" else self._flat_mask_to_xyz(flat_mask)
        return {
            "action_mask": action_mask.astype(np.int8, copy=False),
            "action_mask_flat": flat_mask.astype(np.int8, copy=False),
            "opponent_action": opponent_action,
            "action_success": action_success,
            "agent_action_valid": agent_action_valid,
            "agent_action_flat": agent_action_flat,
            "ticks_advanced": ticks_advanced,
            "battle_tick": int(self._env.battle.tick) if self._env.battle is not None else 0,
            "winner": self._env.battle.winner if self._env.battle is not None else None,
        }

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        _ = options
        with _maybe_silence_stdio(self.quiet_engine):
            self._env.reset(seed=seed)
        no_op = self._env.action_space.no_op_action
        return self._obs_for_player_zero(), self._build_info(
            opponent_action=no_op,
            action_success=True,
            ticks_advanced=0,
            agent_action_valid=True,
            agent_action_flat=no_op,
        )

    def step(
        self, action: Any
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        if self._env.battle is None:
            raise RuntimeError("Environment is not initialized. Call reset() first.")

        agent_action, agent_action_valid = self._decode_agent_action(action)
        opponent_action = self._select_opponent_action()

        with _maybe_silence_stdio(self.quiet_engine):
            rewards, done, step_info = self._env.step({0: agent_action, 1: opponent_action})
        reward = float(rewards[0])

        battle = self._env.battle
        terminated = bool(done and battle is not None and battle.game_over)
        truncated = bool(done and not terminated)

        obs = self._obs_for_player_zero()
        info = self._build_info(
            opponent_action=opponent_action,
            action_success=bool(step_info.action_success.get(0, True)),
            ticks_advanced=step_info.ticks_advanced,
            agent_action_valid=agent_action_valid,
            agent_action_flat=agent_action,
        )
        return obs, reward, terminated, truncated, info

    def render(self) -> Optional[np.ndarray]:
        if self.render_mode != "rgb_array":
            return None
        obs = self._env.get_observation(0)
        return self._small_rgb_from_board(obs.board)

    def close(self) -> None:
        return None


def register_gym_envs() -> None:
    variants = [
        ("clasher-selfplay-v0", {}),
        ("clasher-selfplay-xyz-v0", {"kwargs": {"action_mode": "xyz"}}),
    ]
    for env_id, extra in variants:
        if env_id in registry:
            continue
        register(
            id=env_id,
            entry_point="clasher.rl.gym_env:ClasherSelfPlayGymEnv",
            **extra,
        )


register_gym_envs()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gymnasium smoke-runner for Clasher env")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=256)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--opponent-policy", type=str, choices=["random", "noop"], default="random")
    parser.add_argument("--action-mode", type=str, choices=["flat", "xyz"], default="flat")
    parser.add_argument("--quiet-engine", dest="quiet_engine", action="store_true", default=True)
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    parser.add_argument("--debug-dump", type=str, default=None, help="write JSONL episode dumps")
    parser.add_argument("--dump-max-legal", type=int, default=256)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    env = ClasherSelfPlayGymEnv(
        seed=args.seed,
        decks_path=args.decks_path,
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        opponent_policy=args.opponent_policy,
        quiet_engine=args.quiet_engine,
        action_mode=args.action_mode,
    )
    debug_dump_path: Optional[Path] = None
    if args.debug_dump:
        debug_dump_path = Path(args.debug_dump).expanduser().resolve()
        debug_dump_path.parent.mkdir(parents=True, exist_ok=True)

    for episode in range(1, args.episodes + 1):
        obs, info = env.reset(seed=args.seed + episode)
        _ = obs
        total_reward = 0.0
        steps = 0
        terminated = False
        truncated = False
        done = False
        step_records: list[Dict[str, Any]] = []
        while not done and steps < args.max_steps:
            if args.action_mode == "flat":
                mask = info["action_mask"].astype(np.bool_, copy=False)
                legal = np.flatnonzero(mask)
                action: Any = int(legal[0]) if legal.size > 0 else int(env.action_space.sample())
            else:
                mask_xyz = info["action_mask"].astype(np.bool_, copy=False)
                legal_xyz = np.argwhere(mask_xyz)
                if legal_xyz.size == 0:
                    action = np.asarray(env.action_space.sample(), dtype=np.int64)
                else:
                    x, y, slot = legal_xyz[0]
                    action = np.asarray([x, y, slot], dtype=np.int64)

            obs, reward, terminated, truncated, info = env.step(action)
            _ = obs
            total_reward += float(reward)
            done = terminated or truncated
            flat_mask = info["action_mask_flat"]
            step_records.append(
                {
                    "step": steps,
                    "agent_action_input": (
                        int(action)
                        if args.action_mode == "flat"
                        else [int(action[0]), int(action[1]), int(action[2])]
                    ),
                    "agent_action_flat": int(info["agent_action_flat"]),
                    "agent_action_valid": bool(info["agent_action_valid"]),
                    "opponent_action": int(info["opponent_action"]),
                    "action_success": bool(info["action_success"]),
                    "reward": float(reward),
                    "cumulative_reward": float(total_reward),
                    "battle_tick": int(info["battle_tick"]),
                    **_summarize_mask(flat_mask, max_legal=max(1, int(args.dump_max_legal))),
                }
            )
            steps += 1
        print(
            f"episode={episode:03d} steps={steps} reward={total_reward:+.4f} "
            f"terminated={terminated} truncated={truncated} winner={info.get('winner')}"
        )
        if debug_dump_path is not None:
            payload = {
                "episode": episode,
                "seed": args.seed + episode,
                "action_mode": args.action_mode,
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "winner": info.get("winner"),
                "final_battle_tick": int(info.get("battle_tick", 0)),
                "total_reward": float(total_reward),
                "records": step_records,
            }
            with debug_dump_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
            print(f"debug_dump_appended={debug_dump_path}")
    env.close()


if __name__ == "__main__":
    main()
