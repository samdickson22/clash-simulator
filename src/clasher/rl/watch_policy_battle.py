from __future__ import annotations

import argparse
import random

import numpy as np
import torch

from clasher.engine import BattleEngine
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import latest_checkpoint, resolve_path
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.reward_model import objective_potential_p0
from clasher.rl.train_recurrent import _stack_step_inputs
from clasher.rl.train_selfplay import resolve_torch_device
from visualize_battle import PURPLE, RED, WHITE, BattleVisualizer


class PolicyBattleVisualizer(BattleVisualizer):
    def __init__(
        self,
        checkpoint: str,
        decks_path: str,
        decision_interval: int,
        device: str,
        deterministic: bool,
        seed: int,
        opponent_checkpoint: str | None = None,
        opponent_random: bool = False,
        mirror_match: bool = False,
    ) -> None:
        self.decks_path = decks_path
        self.decks = load_deck_pool(decks_path)
        self.decision_interval = decision_interval
        self.deterministic = deterministic
        self.mirror_match = mirror_match

        self.py_rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        torch.manual_seed(seed)

        self.device = resolve_torch_device(device)
        self.action_space = DiscreteTileActionSpace(canonical_perspective=True)

        checkpoint_path = resolve_path(checkpoint, must_exist=True)
        candidate = load_policy_checkpoint(
            checkpoint_path,
            device=self.device,
            decks_path=decks_path,
        )
        self.policies: dict[int, LoadedPolicy | None] = {
            0: candidate,
            1: None,
        }
        self.player_labels = {
            0: f"V2 u{candidate.checkpoint.get('update', 0)}",
            1: "random",
        }

        if not opponent_random:
            opp_ckpt = (
                resolve_path(opponent_checkpoint, must_exist=True)
                if opponent_checkpoint
                else checkpoint_path
            )
            opponent = (
                candidate
                if opp_ckpt == checkpoint_path
                else load_policy_checkpoint(
                    opp_ckpt,
                    device=self.device,
                    decks_path=decks_path,
                )
            )
            self.policies[1] = opponent
            self.player_labels[1] = f"V2 u{opponent.checkpoint.get('update', 0)}"

        self.last_decision_tick = 0
        self.current_decks: dict[int, list[str]] = {0: [], 1: []}
        self.recurrent_states: dict[int, tuple[torch.Tensor, torch.Tensor] | None] = {
            0: None,
            1: None,
        }
        self.previous_actions = {
            0: self.action_space.no_op_action,
            1: self.action_space.no_op_action,
        }
        self.previous_rewards = {0: 0.0, 1: 0.0}
        self.episode_starts = {0: True, 1: True}
        self.previous_objective_p0 = 0.0

        super().__init__()

    def setup_test_battle(self) -> None:
        self.engine = BattleEngine()
        self.battle = self.engine.create_battle()

        deck0, deck1 = sample_decks(
            self.decks, self.py_rng, mirror_match=self.mirror_match
        )
        self.current_decks = {0: list(deck0), 1: list(deck1)}
        apply_deck_to_player(self.battle.players[0], deck0, self.py_rng)
        apply_deck_to_player(self.battle.players[1], deck1, self.py_rng)
        self.last_decision_tick = self.battle.tick
        self.previous_objective_p0 = objective_potential_p0(self.battle)
        for player_id, policy in self.policies.items():
            self.recurrent_states[player_id] = (
                policy.model.initial_state(1, device=self.device)
                if policy is not None
                else None
            )
            self.previous_actions[player_id] = self.action_space.no_op_action
            self.previous_rewards[player_id] = 0.0
            self.episode_starts[player_id] = True

    def _policy_action(self, player_id: int) -> int:
        policy = self.policies[player_id]
        if policy is None:
            return int(
                self.action_space.random_legal_action(
                    self.battle, player_id, self.np_rng
                )
            )

        observation = policy.builder.build(self.battle, player_id)
        mask = self.action_space.legal_action_mask(self.battle, player_id)[None, :]
        inputs = _stack_step_inputs(
            [observation],
            mask,
            np.asarray([self.previous_actions[player_id]], dtype=np.int64),
            np.asarray([self.previous_rewards[player_id]], dtype=np.float32),
            np.asarray([self.episode_starts[player_id]], dtype=np.bool_),
            self.device,
        )
        recurrent_state = self.recurrent_states[player_id]
        if recurrent_state is None:
            raise RuntimeError(f"missing recurrent state for policy player {player_id}")

        with torch.no_grad():
            action_t, _, _, next_state, _ = policy.model.act(
                inputs,
                recurrent_state,
                deterministic=self.deterministic,
            )
        self.recurrent_states[player_id] = next_state
        return int(action_t[0, 0].item())

    def _maybe_take_actions(self) -> None:
        if self.battle.tick - self.last_decision_tick < self.decision_interval:
            return

        current_objective_p0 = objective_potential_p0(self.battle)
        objective_delta = current_objective_p0 - self.previous_objective_p0
        self.previous_rewards = {0: objective_delta, 1: -objective_delta}
        self.previous_objective_p0 = current_objective_p0

        action0 = self._policy_action(0)
        action1 = self._policy_action(1)
        self.action_space.apply_action(self.battle, 0, action0)
        self.action_space.apply_action(self.battle, 1, action1)
        self.previous_actions = {0: action0, 1: action1}
        self.episode_starts = {0: False, 1: False}
        self.last_decision_tick = self.battle.tick

    def draw_ui(self) -> None:
        super().draw_ui()

        # Add policy/simulation info in the right panel.
        x = 920
        y = 680
        line = 20

        mode_text = self.small_font.render(
            f"P0={self.player_labels[0]} P1={self.player_labels[1]}",
            True,
            (0, 0, 0),
        )
        self.screen.blit(mode_text, (x, y))
        y += line

        interval_text = self.small_font.render(
            f"Decision every {self.decision_interval} ticks",
            True,
            (0, 0, 0),
        )
        self.screen.blit(interval_text, (x, y))
        y += line

        deck0 = ", ".join(self.current_decks[0][:4]) if self.current_decks[0] else "-"
        deck1 = ", ".join(self.current_decks[1][:4]) if self.current_decks[1] else "-"
        self.screen.blit(
            self.small_font.render(f"P0 deck: {deck0}", True, (0, 0, 0)), (x, y)
        )
        y += line
        self.screen.blit(
            self.small_font.render(f"P1 deck: {deck1}", True, (0, 0, 0)), (x, y)
        )

    def run(self) -> None:
        print("Starting policy battle visualizer")
        print(f"device={self.device}")
        print("Controls:")
        print("  SPACE: Pause/Resume")
        print("  R: Reset Match")
        print("  1-5: Speed multiplier")
        print("  ESC: Exit")

        self.paused = False
        self.speed = 1
        running = True

        while running:
            running = self.handle_events()

            if not self.paused and not self.battle.game_over:
                for _ in range(self.speed):
                    self._maybe_take_actions()
                    self.battle.step(speed_factor=1.0)

            self.screen.fill(WHITE)
            self.draw_arena()
            self.draw_towers()
            self.draw_entities()
            self.draw_ui()

            if self.paused:
                pause_text = self.large_font.render("PAUSED", True, RED)
                pause_rect = pause_text.get_rect(center=(600, 30))
                self.screen.blit(pause_text, pause_rect)

            if self.speed > 1:
                speed_text = self.font.render(f"Speed: {self.speed}x", True, PURPLE)
                self.screen.blit(speed_text, (10, 10))

            torch_device_type = self.device.type
            dev_text = self.small_font.render(
                f"torch={torch_device_type}", True, (0, 0, 0)
            )
            self.screen.blit(dev_text, (10, 35))

            self.clock.tick(60)
            import pygame

            pygame.display.flip()

        import pygame

        pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a recurrent V2 policy play in pygame"
    )
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument(
        "--checkpoint-dir", type=str, default="checkpoints/entity_selfplay"
    )
    parser.add_argument("--opponent-checkpoint", type=str, default=None)
    parser.add_argument("--opponent-random", action="store_true")
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument(
        "--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument("--seed", type=int, default=17)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.checkpoint:
        checkpoint = resolve_path(args.checkpoint, must_exist=True)
    else:
        ckpt = latest_checkpoint(args.checkpoint_dir, pattern="policy_v2_update_*.pt")
        if ckpt is None:
            raise FileNotFoundError(
                f"no policy checkpoints found in {resolve_path(args.checkpoint_dir, must_exist=False)}"
            )
        checkpoint = ckpt
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    opponent_ckpt = (
        str(resolve_path(args.opponent_checkpoint, must_exist=True))
        if args.opponent_checkpoint
        else None
    )
    print(f"checkpoint={checkpoint}")
    print(f"decks={decks_path}")
    visualizer = PolicyBattleVisualizer(
        checkpoint=str(checkpoint),
        opponent_checkpoint=opponent_ckpt,
        opponent_random=args.opponent_random,
        decks_path=str(decks_path),
        decision_interval=args.decision_interval,
        device=args.device,
        deterministic=args.deterministic,
        mirror_match=args.mirror_match,
        seed=args.seed,
    )
    visualizer.run()


if __name__ == "__main__":
    main()
