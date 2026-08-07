from __future__ import annotations

import argparse
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pygame
import torch

from clasher.battle import BattleState
from clasher.engine import BattleEngine
from clasher.entities import Entity
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import latest_checkpoint, resolve_path
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.reward_model import objective_potential_p0
from clasher.rl.train_recurrent import _stack_step_inputs
from clasher.rl.train_selfplay import resolve_torch_device
from visualize_battle import (
    ARENA_HEIGHT,
    ARENA_WIDTH,
    ARENA_X,
    ARENA_Y,
    SCREEN_WIDTH,
    TILE_SIZE,
    BattleVisualizer,
)

TEAM_COLORS = {0: (75, 145, 255), 1: (246, 91, 103)}
TEAM_DARK = {0: (32, 80, 155), 1: (145, 35, 52)}
INK = (230, 236, 245)
MUTED = (147, 159, 178)
BACKGROUND = (13, 18, 28)
PANEL = (24, 31, 45)
PANEL_ALT = (31, 40, 57)
BORDER = (58, 70, 91)
SUCCESS = (76, 204, 137)
WARNING = (255, 194, 92)
DANGER = (255, 102, 118)
ELIXIR = (202, 83, 232)
SPEED_STEPS = (1, 2, 4, 8, 16)


@dataclass(frozen=True)
class PolicyIdentity:
    filename: str
    update: int
    transitions: int

    @property
    def short_label(self) -> str:
        return f"V2 update {self.update:,}"


def policy_identity(path: Path, loaded: LoadedPolicy) -> PolicyIdentity:
    return PolicyIdentity(
        filename=path.name,
        update=int(loaded.checkpoint.get("update", 0)),
        transitions=int(loaded.checkpoint.get("total_transitions", 0)),
    )


def humanize_card_name(name: str | None) -> str:
    if not name:
        return "Empty"
    text = name.replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return " ".join(text.split())


def card_abbreviation(name: str | None, max_chars: int = 3) -> str:
    words = humanize_card_name(name).split()
    if not words or name is None:
        return "--"
    if len(words) > 1:
        return "".join(word[0] for word in words[:max_chars]).upper()
    return words[0][:max_chars].upper()


def format_match_clock(
    elapsed_seconds: float,
    *,
    regulation_seconds: float = 180.0,
    match_seconds: float = 300.0,
) -> str:
    if elapsed_seconds < regulation_seconds:
        remaining = max(0, int(np.ceil(regulation_seconds - elapsed_seconds)))
        prefix = ""
    else:
        remaining = max(0, int(np.ceil(match_seconds - elapsed_seconds)))
        prefix = "OT "
    return f"{prefix}{remaining // 60}:{remaining % 60:02d}"


def match_phase(battle: BattleState) -> str:
    if battle.game_over:
        return "FINAL"
    if battle.triple_elixir:
        return "OVERTIME • 3X ELIXIR"
    if battle.sudden_death:
        return "OVERTIME • SUDDEN DEATH"
    if battle.double_elixir:
        return "REGULATION • 2X ELIXIR"
    return "REGULATION • 1X ELIXIR"


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
        auto_reset_seconds: float = 0.0,
    ) -> None:
        self.decks_path = decks_path
        self.decks = load_deck_pool(decks_path)
        self.decision_interval = decision_interval
        self.deterministic = deterministic
        self.mirror_match = mirror_match
        self.auto_reset_seconds = max(0.0, auto_reset_seconds)

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
        self.policies: dict[int, LoadedPolicy | None] = {0: candidate, 1: None}
        self.policy_identities: dict[int, PolicyIdentity | None] = {
            0: policy_identity(checkpoint_path, candidate),
            1: None,
        }

        if not opponent_random:
            opponent_path = (
                resolve_path(opponent_checkpoint, must_exist=True)
                if opponent_checkpoint
                else checkpoint_path
            )
            opponent = (
                candidate
                if opponent_path == checkpoint_path
                else load_policy_checkpoint(
                    opponent_path,
                    device=self.device,
                    decks_path=decks_path,
                )
            )
            self.policies[1] = opponent
            self.policy_identities[1] = policy_identity(opponent_path, opponent)

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
        self.last_action_labels = {
            0: "Waiting for first decision",
            1: "Waiting for first decision",
        }
        self.match_number = 0
        self.game_over_since: float | None = None
        self.paused = False
        self.speed_index = 0
        self.show_help = True
        self.show_targets = False
        self._arena_surface: pygame.Surface | None = None
        self._pending_screenshot: Path | None = None

        super().__init__()
        pygame.display.set_caption("Clasher • V2 Policy Arena")
        self.title_font = pygame.font.SysFont("Arial", 27, bold=True)
        self.heading_font = pygame.font.SysFont("Arial", 20, bold=True)
        self.body_font = pygame.font.SysFont("Arial", 16)
        self.body_bold_font = pygame.font.SysFont("Arial", 16, bold=True)
        self.caption_font = pygame.font.SysFont("Arial", 13)
        self.clock_font = pygame.font.SysFont("Arial", 34, bold=True)
        self.unit_font = pygame.font.SysFont("Arial", 10, bold=True)
        self._arena_surface = self._build_arena_surface()

    @property
    def speed(self) -> int:
        return SPEED_STEPS[self.speed_index]

    def setup_test_battle(self) -> None:
        self.engine = BattleEngine()
        self.battle = self.engine.create_battle()

        deck0, deck1 = sample_decks(
            self.decks,
            self.py_rng,
            mirror_match=self.mirror_match,
        )
        self.current_decks = {0: list(deck0), 1: list(deck1)}
        apply_deck_to_player(self.battle.players[0], deck0, self.py_rng)
        apply_deck_to_player(self.battle.players[1], deck1, self.py_rng)
        self.last_decision_tick = self.battle.tick
        self.previous_objective_p0 = objective_potential_p0(self.battle)
        self.match_number += 1
        self.game_over_since = None
        self.last_action_labels = {
            0: "Waiting for first decision",
            1: "Waiting for first decision",
        }
        for player_id, policy in self.policies.items():
            self.recurrent_states[player_id] = (
                policy.model.initial_state(1, device=self.device)
                if policy is not None
                else None
            )
            self.previous_actions[player_id] = self.action_space.no_op_action
            self.previous_rewards[player_id] = 0.0
            self.episode_starts[player_id] = True

    def world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        """Map world coordinates with player 0 at the bottom of the display."""
        return (
            int(ARENA_X + x * self.tile_size),
            int(ARENA_Y + (32.0 - y) * self.tile_size),
        )

    def _policy_action(self, player_id: int) -> int:
        policy = self.policies[player_id]
        if policy is None:
            return int(
                self.action_space.random_legal_action(
                    self.battle,
                    player_id,
                    self.np_rng,
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

    def _describe_action(
        self,
        player_id: int,
        action_id: int,
        hand_before_action: list[str | None],
        success: bool,
    ) -> str:
        selection = self.action_space.decode_action(action_id, player_id)
        if selection.is_no_op:
            return "Wait"
        if selection.is_ability:
            return "Champion ability" if success else "Champion ability • rejected"
        if selection.slot is None or selection.position is None:
            return "Unknown action"
        card = (
            hand_before_action[selection.slot]
            if selection.slot < len(hand_before_action)
            else None
        )
        suffix = "" if success else " • rejected"
        return (
            f"{humanize_card_name(card)}  @  "
            f"{selection.position.x:.1f}, {selection.position.y:.1f}{suffix}"
        )

    def _maybe_take_actions(self) -> None:
        if self.battle.tick - self.last_decision_tick < self.decision_interval:
            return

        current_objective_p0 = objective_potential_p0(self.battle)
        objective_delta = current_objective_p0 - self.previous_objective_p0
        self.previous_rewards = {0: objective_delta, 1: -objective_delta}
        self.previous_objective_p0 = current_objective_p0

        hands = {
            player_id: list(self.battle.players[player_id].hand) for player_id in (0, 1)
        }
        actions = {player_id: self._policy_action(player_id) for player_id in (0, 1)}
        success = {
            player_id: self.action_space.apply_action(
                self.battle,
                player_id,
                actions[player_id],
            )
            for player_id in (0, 1)
        }
        self.last_action_labels = {
            player_id: self._describe_action(
                player_id,
                actions[player_id],
                hands[player_id],
                success[player_id],
            )
            for player_id in (0, 1)
        }
        self.previous_actions = actions
        self.episode_starts = {0: False, 1: False}
        self.last_decision_tick = self.battle.tick

    def _build_arena_surface(self) -> pygame.Surface:
        surface = pygame.Surface((ARENA_WIDTH, ARENA_HEIGHT)).convert()
        surface.fill((72, 126, 77))

        for row in range(32):
            for column in range(18):
                shade = (76, 133, 81) if (row + column) % 2 == 0 else (70, 126, 76)
                pygame.draw.rect(
                    surface,
                    shade,
                    (column * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                )

        blue_zone = pygame.Surface((ARENA_WIDTH, 15 * TILE_SIZE), pygame.SRCALPHA)
        blue_zone.fill((*TEAM_COLORS[0], 18))
        surface.blit(blue_zone, (0, 17 * TILE_SIZE))
        red_zone = pygame.Surface((ARENA_WIDTH, 15 * TILE_SIZE), pygame.SRCALPHA)
        red_zone.fill((*TEAM_COLORS[1], 18))
        surface.blit(red_zone, (0, 0))

        river = pygame.Rect(0, 15 * TILE_SIZE, ARENA_WIDTH, 2 * TILE_SIZE)
        pygame.draw.rect(surface, (47, 139, 187), river)
        for offset in (5, 18, 31):
            pygame.draw.line(
                surface,
                (94, 181, 218),
                (0, river.y + offset),
                (ARENA_WIDTH, river.y + offset),
                1,
            )
        for bridge_x in (2 * TILE_SIZE, 13 * TILE_SIZE):
            bridge = pygame.Rect(bridge_x, river.y, 3 * TILE_SIZE, river.height)
            pygame.draw.rect(surface, (151, 126, 92), bridge)
            pygame.draw.rect(surface, (92, 72, 53), bridge, 2)
            pygame.draw.line(
                surface,
                (190, 164, 122),
                (bridge.left, bridge.centery),
                (bridge.right, bridge.centery),
                2,
            )

        for column in range(19):
            pygame.draw.line(
                surface,
                (48, 96, 58),
                (column * TILE_SIZE, 0),
                (column * TILE_SIZE, ARENA_HEIGHT),
                1,
            )
        for row in range(33):
            pygame.draw.line(
                surface,
                (48, 96, 58),
                (0, row * TILE_SIZE),
                (ARENA_WIDTH, row * TILE_SIZE),
                1,
            )
        return surface

    def draw_arena(self) -> None:
        if self._arena_surface is None:
            self._arena_surface = self._build_arena_surface()
        self.screen.blit(self._arena_surface, (ARENA_X, ARENA_Y))
        pygame.draw.rect(
            self.screen,
            (8, 12, 19),
            (ARENA_X - 3, ARENA_Y - 3, ARENA_WIDTH + 6, ARENA_HEIGHT + 6),
            3,
            border_radius=5,
        )

        top_label = self.caption_font.render("P1 • RED", True, TEAM_COLORS[1])
        bottom_label = self.caption_font.render("P0 • BLUE", True, TEAM_COLORS[0])
        self.screen.blit(top_label, (ARENA_X + 8, ARENA_Y + 7))
        self.screen.blit(
            bottom_label,
            (ARENA_X + 8, ARENA_Y + ARENA_HEIGHT - bottom_label.get_height() - 7),
        )

    def _tower_hp(self, player_id: int, slot: str) -> tuple[float, float]:
        player = self.battle.players[player_id]
        hp = float(getattr(player, f"{slot}_tower_hp"))
        starting = float(self.battle._starting_tower_hps[player_id][slot])
        return hp, max(1.0, starting)

    def _draw_health_bar(
        self,
        rect: pygame.Rect,
        ratio: float,
        *,
        fill: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(
            self.screen, (17, 23, 33), rect, border_radius=rect.height // 2
        )
        inner = rect.inflate(-2, -2)
        inner.width = max(0, int(inner.width * float(np.clip(ratio, 0.0, 1.0))))
        if inner.width:
            pygame.draw.rect(
                self.screen,
                fill,
                inner,
                border_radius=max(1, inner.height // 2),
            )

    def draw_towers(self) -> None:
        tower_slots = (
            (0, "king", 9.0, 2.5, "K"),
            (0, "left", 3.5, 6.5, "L"),
            (0, "right", 14.5, 6.5, "R"),
            (1, "king", 9.0, 29.5, "K"),
            (1, "left", 3.5, 25.5, "L"),
            (1, "right", 14.5, 25.5, "R"),
        )
        for player_id, slot, world_x, world_y, label in tower_slots:
            hp, starting_hp = self._tower_hp(player_id, slot)
            x, y = self.world_to_screen(world_x, world_y)
            is_king = slot == "king"
            size = 30 if is_king else 25
            body = pygame.Rect(x - size // 2, y - size // 2, size, size)
            if hp <= 0:
                pygame.draw.circle(self.screen, (66, 69, 72), (x, y), size // 2)
                pygame.draw.line(
                    self.screen,
                    (35, 38, 42),
                    body.topleft,
                    body.bottomright,
                    4,
                )
                pygame.draw.line(
                    self.screen,
                    (35, 38, 42),
                    body.topright,
                    body.bottomleft,
                    4,
                )
                continue

            pygame.draw.rect(
                self.screen,
                TEAM_DARK[player_id],
                body,
                border_radius=5,
            )
            pygame.draw.rect(
                self.screen,
                TEAM_COLORS[player_id],
                body,
                2,
                border_radius=5,
            )
            if is_king:
                crown = [
                    (x - 9, y - size // 2 - 2),
                    (x - 5, y - size // 2 - 9),
                    (x, y - size // 2 - 3),
                    (x + 5, y - size // 2 - 9),
                    (x + 9, y - size // 2 - 2),
                ]
                pygame.draw.polygon(self.screen, WARNING, crown)
            tower_label = self.unit_font.render(label, True, (255, 255, 255))
            self.screen.blit(tower_label, tower_label.get_rect(center=(x, y)))
            bar = pygame.Rect(x - 24, y - size // 2 - 13, 48, 6)
            self._draw_health_bar(bar, hp / starting_hp, fill=SUCCESS)
            hp_text = self.caption_font.render(f"{int(hp):,}", True, (245, 247, 250))
            self.screen.blit(hp_text, hp_text.get_rect(center=(x, y + size // 2 + 10)))

    def _draw_target_line(self, entity: Entity, x: int, y: int) -> None:
        if not self.show_targets or not getattr(entity, "target_id", None):
            return
        target = self.battle.entities.get(entity.target_id)
        if target is None or not target.is_alive:
            return
        tx, ty = self.world_to_screen(target.position.x, target.position.y)
        pygame.draw.line(
            self.screen, (*TEAM_COLORS[entity.player_id], 130), (x, y), (tx, ty), 1
        )

    def draw_entities(self) -> None:
        for entity in tuple(self.battle.entities.values()):
            if not entity.is_alive:
                continue
            raw_name = getattr(getattr(entity, "card_stats", None), "name", "")
            if raw_name in {"Tower", "KingTower"}:
                continue

            x, y = self.world_to_screen(entity.position.x, entity.position.y)
            entity_type = type(entity).__name__
            team = TEAM_COLORS.get(entity.player_id, MUTED)
            team_dark = TEAM_DARK.get(entity.player_id, (70, 77, 89))

            if entity_type == "AreaEffect":
                radius = max(5, int(float(getattr(entity, "radius", 0.5)) * TILE_SIZE))
                effect = pygame.Surface(
                    (radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA
                )
                pygame.draw.circle(
                    effect, (255, 194, 92, 28), (radius + 2, radius + 2), radius
                )
                pygame.draw.circle(
                    effect, (255, 211, 126, 150), (radius + 2, radius + 2), radius, 2
                )
                self.screen.blit(effect, (x - radius - 2, y - radius - 2))
                continue

            if entity_type in {"Projectile", "SpawnProjectile"}:
                if (
                    self.show_targets
                    and getattr(entity, "target_position", None) is not None
                ):
                    tx, ty = self.world_to_screen(
                        entity.target_position.x,
                        entity.target_position.y,
                    )
                    pygame.draw.line(self.screen, (230, 235, 242), (x, y), (tx, ty), 1)
                pygame.draw.circle(self.screen, WARNING, (x, y), 4)
                pygame.draw.circle(self.screen, (255, 246, 220), (x, y), 2)
                continue

            if entity_type == "RollingProjectile":
                rect = pygame.Rect(x - 10, y - 6, 20, 12)
                pygame.draw.rect(self.screen, team_dark, rect, border_radius=5)
                pygame.draw.rect(self.screen, team, rect, 2, border_radius=5)
                continue

            collision_radius = float(
                getattr(getattr(entity, "card_stats", None), "collision_radius", 0.5)
                or 0.5
            )
            radius = int(np.clip(collision_radius * TILE_SIZE * 0.68, 7, 14))
            if entity_type == "Building":
                body = pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)
                pygame.draw.rect(self.screen, team_dark, body, border_radius=4)
                pygame.draw.rect(self.screen, team, body, 2, border_radius=4)
            elif bool(getattr(entity, "is_air_unit", False)):
                points = [
                    (x, y - radius),
                    (x + radius, y),
                    (x, y + radius),
                    (x - radius, y),
                ]
                pygame.draw.polygon(self.screen, team_dark, points)
                pygame.draw.polygon(self.screen, team, points, 2)
            else:
                pygame.draw.circle(self.screen, team_dark, (x, y), radius)
                pygame.draw.circle(self.screen, team, (x, y), radius, 2)

            abbreviation = self.unit_font.render(
                card_abbreviation(raw_name), True, (255, 255, 255)
            )
            self.screen.blit(abbreviation, abbreviation.get_rect(center=(x, y)))

            max_hp = float(getattr(entity, "max_hitpoints", 0.0) or 0.0)
            hp = float(getattr(entity, "hitpoints", 0.0) or 0.0)
            if max_hp > 0:
                self._draw_health_bar(
                    pygame.Rect(x - 13, y - radius - 8, 26, 5),
                    hp / max_hp,
                    fill=SUCCESS if hp / max_hp > 0.35 else DANGER,
                )
            if callable(getattr(entity, "is_stunned", None)) and entity.is_stunned():
                stun = self.caption_font.render("⚡", True, WARNING)
                self.screen.blit(stun, (x + radius - 2, y - radius - 8))
            self._draw_target_line(entity, x, y)

    def _panel(self, rect: pygame.Rect, *, color: tuple[int, int, int] = PANEL) -> None:
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, BORDER, rect, 1, border_radius=10)

    def _fit_text(
        self, font: pygame.font.Font, text: str, max_width: int
    ) -> pygame.Surface:
        if font.size(text)[0] <= max_width:
            return font.render(text, True, INK)
        candidate = text
        while candidate and font.size(candidate + "…")[0] > max_width:
            candidate = candidate[:-1]
        return font.render(candidate.rstrip() + "…", True, INK)

    def _draw_card(self, player_id: int, card: str | None, rect: pygame.Rect) -> None:
        available = card is not None
        card_stats = self.battle.card_loader.get_card(card) if card else None
        affordable = bool(
            card_stats and self.battle.players[player_id].elixir >= card_stats.mana_cost
        )
        fill = PANEL_ALT if available else (28, 33, 44)
        outline = TEAM_COLORS[player_id] if affordable else BORDER
        pygame.draw.rect(self.screen, fill, rect, border_radius=7)
        pygame.draw.rect(
            self.screen, outline, rect, 2 if affordable else 1, border_radius=7
        )
        if not available:
            empty = self.caption_font.render("cycling…", True, MUTED)
            self.screen.blit(empty, empty.get_rect(center=rect.center))
            return

        cost = int(getattr(card_stats, "mana_cost", 0) or 0)
        pygame.draw.circle(self.screen, ELIXIR, (rect.x + 12, rect.y + 13), 10)
        cost_text = self.caption_font.render(str(cost), True, (255, 255, 255))
        self.screen.blit(
            cost_text, cost_text.get_rect(center=(rect.x + 12, rect.y + 13))
        )
        abbreviation = self.heading_font.render(card_abbreviation(card), True, INK)
        self.screen.blit(
            abbreviation, abbreviation.get_rect(center=(rect.centerx, rect.y + 29))
        )
        name = self._fit_text(
            self.caption_font, humanize_card_name(card), rect.width - 8
        )
        self.screen.blit(name, name.get_rect(center=(rect.centerx, rect.bottom - 10)))

    def _draw_player_panel(self, player_id: int, rect: pygame.Rect) -> None:
        self._panel(rect)
        player = self.battle.players[player_id]
        team = TEAM_COLORS[player_id]
        x = rect.x + 14
        y = rect.y + 11

        title = self.heading_font.render(
            f"P{player_id}  {'BLUE' if player_id == 0 else 'RED'}", True, team
        )
        self.screen.blit(title, (x, y))
        crowns = self.battle.get_crown_count(player_id)
        crown_text = self.body_bold_font.render(f"CROWNS {crowns}", True, WARNING)
        self.screen.blit(crown_text, (rect.right - crown_text.get_width() - 14, y + 2))
        y += 30

        elixir_text = self.body_bold_font.render(
            f"Elixir  {player.elixir:0.1f}", True, INK
        )
        self.screen.blit(elixir_text, (x, y))
        self._draw_health_bar(
            pygame.Rect(x + 80, y + 5, rect.width - 108, 10),
            player.elixir / max(1.0, player.max_elixir),
            fill=ELIXIR,
        )
        y += 28

        tower_line = (
            f"Towers  L {max(0, int(player.left_tower_hp)):,}   "
            f"K {max(0, int(player.king_tower_hp)):,}   "
            f"R {max(0, int(player.right_tower_hp)):,}"
        )
        tower_text = self.caption_font.render(tower_line, True, MUTED)
        self.screen.blit(tower_text, (x, y))
        y += 25

        hand_label = self.caption_font.render("HAND", True, MUTED)
        self.screen.blit(hand_label, (x, y))
        y += 18
        gap = 5
        card_width = (rect.width - 28 - gap * 3) // 4
        for slot, card in enumerate(player.hand[:4]):
            card_rect = pygame.Rect(x + slot * (card_width + gap), y, card_width, 60)
            self._draw_card(player_id, card, card_rect)
        y += 69

        next_card = humanize_card_name(player.get_next_card())
        next_text = self._fit_text(
            self.caption_font, f"Next: {next_card}", rect.width - 28
        )
        self.screen.blit(next_text, (x, y))
        y += 20

        action = self._fit_text(
            self.caption_font,
            f"Last: {self.last_action_labels[player_id]}",
            rect.width - 28,
        )
        self.screen.blit(action, (x, y))
        y += 22

        identity = self.policy_identities[player_id]
        if identity is None:
            model_line = "Opponent: random legal actions"
            detail_line = "No model checkpoint"
        else:
            model_line = identity.short_label
            detail_line = f"{identity.transitions:,} transitions"
        model_text = self._fit_text(self.body_bold_font, model_line, rect.width - 28)
        self.screen.blit(model_text, (x, y))
        detail_text = self._fit_text(self.caption_font, detail_line, rect.width - 28)
        self.screen.blit(detail_text, (x, y + 20))

    def _draw_status_header(self, rect: pygame.Rect) -> None:
        self._panel(rect)
        title = self.title_font.render("CLASHER  •  POLICY ARENA", True, INK)
        self.screen.blit(title, (rect.x + 16, rect.y + 11))

        clock_text = self.clock_font.render(
            format_match_clock(self.battle.time), True, INK
        )
        self.screen.blit(clock_text, (rect.x + 16, rect.y + 48))
        phase = self.body_bold_font.render(match_phase(self.battle), True, WARNING)
        self.screen.blit(phase, (rect.x + 132, rect.y + 58))

        state = (
            "PAUSED" if self.paused else ("FINAL" if self.battle.game_over else "LIVE")
        )
        state_color = (
            WARNING if self.paused else (MUTED if self.battle.game_over else SUCCESS)
        )
        state_text = self.body_bold_font.render(state, True, state_color)
        self.screen.blit(
            state_text, (rect.right - state_text.get_width() - 16, rect.y + 15)
        )
        detail = (
            f"Match {self.match_number}   •   {self.speed}x   •   tick {self.battle.tick:,}   •   "
            f"{self.clock.get_fps():.0f} FPS   •   {self.device.type.upper()}   •   "
            f"decision/{self.decision_interval} ticks"
        )
        detail_text = self.caption_font.render(detail, True, MUTED)
        self.screen.blit(detail_text, (rect.x + 16, rect.bottom - 20))

    def _draw_footer(self, rect: pygame.Rect) -> None:
        self._panel(rect)
        alive_by_player = {
            player_id: sum(
                1
                for entity in self.battle.entities.values()
                if entity.is_alive
                and entity.player_id == player_id
                and getattr(getattr(entity, "card_stats", None), "name", "")
                not in {"Tower", "KingTower"}
            )
            for player_id in (0, 1)
        }
        summary = self.body_bold_font.render(
            f"Active units   P0 {alive_by_player[0]}   •   P1 {alive_by_player[1]}",
            True,
            INK,
        )
        self.screen.blit(summary, (rect.x + 14, rect.y + 10))

        if self.show_help:
            controls = (
                "SPACE pause   R/ENTER new match   1–5 speed   D targets   "
                "H hide help   S screenshot   ESC quit"
            )
        else:
            controls = "H show controls"
        controls_text = self._fit_text(self.caption_font, controls, rect.width - 28)
        self.screen.blit(controls_text, (rect.x + 14, rect.y + 36))

        identities = [
            identity for identity in self.policy_identities.values() if identity
        ]
        checkpoint_line = (
            identities[0].filename
            if len(identities) == 1
            or (len(identities) == 2 and identities[0] == identities[1])
            else " vs ".join(identity.filename for identity in identities)
        )
        checkpoint = self._fit_text(
            self.caption_font,
            f"Checkpoint: {checkpoint_line}",
            rect.width - 28,
        )
        self.screen.blit(checkpoint, (rect.x + 14, rect.y + 58))

    def draw_ui(self) -> None:
        panel_x = ARENA_X + ARENA_WIDTH + 28
        panel_width = SCREEN_WIDTH - panel_x - 28
        self._draw_status_header(pygame.Rect(panel_x, 28, panel_width, 104))

        gap = 14
        player_width = (panel_width - gap) // 2
        player_y = 146
        player_height = 303
        self._draw_player_panel(
            0, pygame.Rect(panel_x, player_y, player_width, player_height)
        )
        self._draw_player_panel(
            1,
            pygame.Rect(
                panel_x + player_width + gap, player_y, player_width, player_height
            ),
        )
        self._draw_footer(pygame.Rect(panel_x, 465, panel_width, 92))

        deck_y = 573
        deck_height = 125
        for player_id in (0, 1):
            x = panel_x + player_id * (player_width + gap)
            rect = pygame.Rect(x, deck_y, player_width, deck_height)
            self._panel(rect, color=(20, 27, 39))
            label = self.caption_font.render(
                f"P{player_id} FULL DECK", True, TEAM_COLORS[player_id]
            )
            self.screen.blit(label, (rect.x + 12, rect.y + 9))
            cards = [humanize_card_name(card) for card in self.current_decks[player_id]]
            for index, card in enumerate(cards[:8]):
                column = index % 2
                row = index // 2
                text = self._fit_text(
                    self.caption_font, f"{index + 1}. {card}", player_width // 2 - 20
                )
                self.screen.blit(
                    text,
                    (
                        rect.x + 12 + column * (player_width // 2),
                        rect.y + 30 + row * 21,
                    ),
                )

        note_rect = pygame.Rect(panel_x, 714, panel_width, 128)
        self._panel(note_rect, color=(20, 27, 39))
        mode = (
            "argmax / deterministic" if self.deterministic else "sampled / stochastic"
        )
        lines = [
            f"Policy mode: {mode}",
            "The two seats keep independent LSTM state and canonical observations.",
            "Blue is player 0 (bottom); red is player 1 (top).",
        ]
        for index, line in enumerate(lines):
            rendered = self._fit_text(
                self.body_bold_font if index == 0 else self.caption_font,
                line,
                note_rect.width - 28,
            )
            self.screen.blit(
                rendered, (note_rect.x + 14, note_rect.y + 14 + index * 25)
            )
        if self.auto_reset_seconds > 0:
            auto_text = self.caption_font.render(
                f"Auto-reset: {self.auto_reset_seconds:g}s after match end",
                True,
                MUTED,
            )
            self.screen.blit(auto_text, (note_rect.x + 14, note_rect.bottom - 24))

    def _draw_match_over_overlay(self) -> None:
        overlay = pygame.Surface((ARENA_WIDTH, ARENA_HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 8, 13, 182))
        self.screen.blit(overlay, (ARENA_X, ARENA_Y))

        if self.battle.winner is None:
            result = "DRAW"
            color = WARNING
        else:
            result = f"PLAYER {self.battle.winner} WINS"
            color = TEAM_COLORS[self.battle.winner]
        result_text = self.clock_font.render(result, True, color)
        center_x = ARENA_X + ARENA_WIDTH // 2
        center_y = ARENA_Y + ARENA_HEIGHT // 2
        self.screen.blit(
            result_text, result_text.get_rect(center=(center_x, center_y - 38))
        )

        score = f"{self.battle.get_crown_count(0)}  —  {self.battle.get_crown_count(1)}"
        score_text = self.title_font.render(score, True, INK)
        self.screen.blit(
            score_text, score_text.get_rect(center=(center_x, center_y + 4))
        )

        prompt = "Press R or ENTER for a new matchup"
        if self.auto_reset_seconds > 0 and self.game_over_since is not None:
            remaining = max(
                0.0, self.auto_reset_seconds - (time.monotonic() - self.game_over_since)
            )
            prompt = f"New matchup in {remaining:.1f}s  •  R/ENTER now"
        prompt_text = self.body_font.render(prompt, True, MUTED)
        self.screen.blit(
            prompt_text, prompt_text.get_rect(center=(center_x, center_y + 42))
        )

    def _save_screenshot(self) -> Path:
        output_dir = Path("reports") / "viewer_screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = (
            output_dir
            / f"clasher_viewer_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
        )
        pygame.image.save(self.screen, output)
        self._pending_screenshot = output.resolve()
        print(f"screenshot={self._pending_screenshot}")
        return self._pending_screenshot

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_SPACE:
                self.paused = not self.paused
            elif event.key in {pygame.K_r, pygame.K_RETURN, pygame.K_n}:
                self.setup_test_battle()
                self.paused = False
            elif pygame.K_1 <= event.key <= pygame.K_5:
                self.speed_index = event.key - pygame.K_1
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
            elif event.key == pygame.K_d:
                self.show_targets = not self.show_targets
            elif event.key == pygame.K_s:
                self._save_screenshot()
        return True

    def _advance_simulation(self) -> None:
        if self.paused or self.battle.game_over:
            return
        for _ in range(self.speed):
            self._maybe_take_actions()
            self.battle.step(speed_factor=1.0)
            if self.battle.game_over:
                self.game_over_since = time.monotonic()
                break

    def _maybe_auto_reset(self) -> None:
        if (
            self.auto_reset_seconds <= 0
            or not self.battle.game_over
            or self.game_over_since is None
        ):
            return
        if time.monotonic() - self.game_over_since >= self.auto_reset_seconds:
            self.setup_test_battle()

    def draw_frame(self) -> None:
        self.screen.fill(BACKGROUND)
        self.draw_arena()
        self.draw_towers()
        self.draw_entities()
        self.draw_ui()
        if self.battle.game_over:
            self._draw_match_over_overlay()

    def run(self, *, max_frames: int | None = None) -> None:
        print("Starting Clasher V2 policy arena")
        print(f"device={self.device}")
        print(
            "controls=SPACE pause, R/ENTER reset, 1-5 speed, D targets, H help, S screenshot, ESC exit"
        )

        running = True
        frames = 0
        while running and (max_frames is None or frames < max_frames):
            running = self.handle_events()
            self._advance_simulation()
            self._maybe_auto_reset()
            self.draw_frame()
            pygame.display.flip()
            self.clock.tick(60)
            frames += 1
        pygame.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Watch a recurrent V2 policy play in pygame"
    )
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="checkpoints/entity_selfplay",
    )
    parser.add_argument("--opponent-checkpoint", type=str, default=None)
    parser.add_argument("--opponent-random", action="store_true")
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument(
        "--device",
        type=str,
        choices=["auto", "cpu", "mps", "cuda"],
        default="auto",
    )
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument("--auto-reset-seconds", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-frames", type=int, default=None, help=argparse.SUPPRESS)
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
        auto_reset_seconds=args.auto_reset_seconds,
        seed=args.seed,
    )
    visualizer.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()
