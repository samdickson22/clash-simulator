from __future__ import annotations

import argparse
from pathlib import Path
import random
import time
import sys

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clasher.engine import BattleEngine
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from clasher.rl.model import MaskedPolicyValueNet
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.train_selfplay import resolve_torch_device
from visualize_battle import BattleVisualizer, PURPLE, RED, WHITE


def load_policy(checkpoint_path: Path, device: torch.device) -> MaskedPolicyValueNet:
    state = torch.load(checkpoint_path, map_location=device)
    model = MaskedPolicyValueNet(
        board_channels=state["board_channels"],
        hud_size=state["hud_size"],
        num_actions=state["num_actions"],
        hidden_size=state.get("args", {}).get("hidden_size", 256),
        recurrent=False,
    ).to(device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    return model


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

        self.device = resolve_torch_device(device)
        self.obs_builder = CvObservationBuilder(
            card_vocab=None,
            decks_path=decks_path,
            canonical_perspective=True,
        )
        self.action_space = DiscreteTileActionSpace(canonical_perspective=True)

        self.models: dict[int, MaskedPolicyValueNet | None] = {
            0: load_policy(Path(checkpoint), self.device),
            1: None,
        }
        self.player_labels = {0: "policy", 1: "random"}

        if not opponent_random:
            opp_ckpt = Path(opponent_checkpoint) if opponent_checkpoint else Path(checkpoint)
            self.models[1] = load_policy(opp_ckpt, self.device)
            self.player_labels[1] = "policy"

        self.last_decision_tick = 0
        self.current_decks: dict[int, list[str]] = {0: [], 1: []}

        super().__init__()

    def setup_test_battle(self):
        self.engine = BattleEngine()
        self.battle = self.engine.create_battle()

        deck0, deck1 = sample_decks(self.decks, self.py_rng, mirror_match=self.mirror_match)
        self.current_decks = {0: list(deck0), 1: list(deck1)}
        apply_deck_to_player(self.battle.players[0], deck0, self.py_rng)
        apply_deck_to_player(self.battle.players[1], deck1, self.py_rng)
        self.last_decision_tick = self.battle.tick

    def _policy_action(self, player_id: int) -> int:
        model = self.models[player_id]
        if model is None:
            return self.action_space.random_legal_action(self.battle, player_id, self.np_rng)

        obs = self.obs_builder.build(self.battle, player_id)
        mask = self.action_space.legal_action_mask(self.battle, player_id)
        board = torch.tensor(obs.board, dtype=torch.float32, device=self.device).unsqueeze(0)
        hud = torch.tensor(obs.hud, dtype=torch.float32, device=self.device).unsqueeze(0)
        action_mask = torch.tensor(mask, dtype=torch.bool, device=self.device).unsqueeze(0)

        with torch.no_grad():
            action_t, _, _, _ = model.act(
                board=board,
                hud=hud,
                action_mask=action_mask,
                deterministic=self.deterministic,
            )
        return int(action_t.item())

    def _maybe_take_actions(self) -> None:
        if self.battle.tick - self.last_decision_tick < self.decision_interval:
            return

        action0 = self._policy_action(0)
        action1 = self._policy_action(1)
        self.action_space.apply_action(self.battle, 0, action0)
        self.action_space.apply_action(self.battle, 1, action1)
        self.last_decision_tick = self.battle.tick

    def draw_ui(self):
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
        self.screen.blit(self.small_font.render(f"P0 deck: {deck0}", True, (0, 0, 0)), (x, y))
        y += line
        self.screen.blit(self.small_font.render(f"P1 deck: {deck1}", True, (0, 0, 0)), (x, y))

    def run(self):
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
            dev_text = self.small_font.render(f"torch={torch_device_type}", True, (0, 0, 0))
            self.screen.blit(dev_text, (10, 35))

            self.clock.tick(60)
            import pygame

            pygame.display.flip()

        import pygame

        pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch checkpoint policy play in pygame")
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--opponent-checkpoint", type=str, default=None)
    parser.add_argument("--opponent-random", action="store_true")
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument("--seed", type=int, default=17)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    visualizer = PolicyBattleVisualizer(
        checkpoint=args.checkpoint,
        opponent_checkpoint=args.opponent_checkpoint,
        opponent_random=args.opponent_random,
        decks_path=args.decks_path,
        decision_interval=args.decision_interval,
        device=args.device,
        deterministic=args.deterministic,
        mirror_match=args.mirror_match,
        seed=args.seed,
    )
    visualizer.run()


if __name__ == "__main__":
    main()
