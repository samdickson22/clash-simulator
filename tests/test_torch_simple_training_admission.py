from __future__ import annotations

import json
from pathlib import Path

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.rl.common import NUM_TILES
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_actions import FastActionKernel, FastActionState
from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_DIRECT,
    FastCardCatalog,
)

BASELINE_USEFUL = (
    "Archers",
    "Arrows",
    "BabyDragon",
    "Bats",
    "Bomber",
    "Cannon",
    "DartGoblin",
    "Fireball",
    "Giant",
    "HogRider",
    "IceSpirit",
    "Knight",
    "MegaMinion",
    "MiniPekka",
    "Minions",
    "Musketeer",
    "Pekka",
    "Rocket",
    "RoyalHogs",
    "Skeletons",
    "SpearGoblins",
    "Wallbreakers",
    "Xbow",
)

ZERO_PAYLOAD_SPELLS = ("BarbarianBarrel", "GoblinBarrel", "Log")
UNRESOLVED_DEATH_PARENTS = (
    "Balloon",
    "BattleRam",
    "BombTower",
    "Golem",
    "LavaHound",
    "Lumberjack",
    "NightWitch",
    "SkeletonBarrel",
    "Tombstone",
)


def _enabled_catalog() -> tuple[TensorCardCatalog, FastCardCatalog]:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    names = {
        resolve_card_name(card, definitions) for deck in decks for card in deck["cards"]
    }
    tensor = TensorCardCatalog.compile(loader, names)
    return tensor, FastCardCatalog.from_tensor_catalog(tensor, loader=loader)


def test_training_admission_fails_closed_for_false_positive_payloads() -> None:
    tensor, catalog = _enabled_catalog()

    rejected = (*ZERO_PAYLOAD_SPELLS, *UNRESOLVED_DEATH_PARENTS)
    assert not catalog.training_supported[
        torch.tensor([tensor.name_to_id[name] for name in rejected])
    ].any()
    assert catalog.training_supported[
        torch.tensor([tensor.name_to_id[name] for name in BASELINE_USEFUL])
    ].all()


def test_action_mask_requires_truthful_training_admission() -> None:
    tensor, catalog = _enabled_catalog()
    names = (*ZERO_PAYLOAD_SPELLS, *UNRESOLVED_DEATH_PARENTS, *BASELINE_USEFUL)
    card_ids = torch.tensor([tensor.name_to_id[name] for name in names])
    decks = card_ids[:, None, None].expand(-1, 2, 8).clone()
    state = FastActionState.from_decks(decks, starting_elixir=10.0)
    mask = FastActionKernel(catalog).legal_action_mask(state)
    slot_zero = mask[:, :, :NUM_TILES].any(dim=2).all(dim=1)

    rejected_count = len(ZERO_PAYLOAD_SPELLS) + len(UNRESOLVED_DEATH_PARENTS)
    assert not slot_zero[:rejected_count].any()
    assert slot_zero[rejected_count:].all()


def test_loader_spell_overlay_does_not_replace_mega_knight_attack() -> None:
    loader = CardDataLoader()
    tensor = TensorCardCatalog.compile(loader, ["MegaKnight"])
    catalog = FastCardCatalog.from_tensor_catalog(tensor, loader=loader)
    mega_knight = tensor.name_to_id["MegaKnight"]

    assert int(catalog.effect_kind[mega_knight]) == FAST_CARD_EFFECT_DIRECT
    assert float(catalog.effect_damage[mega_knight]) == float(
        tensor.damage[mega_knight]
    )
    # The root MegaKnightAppear payload must not replace ordinary attacks, but
    # the normal melee hit still carries its serialized target-centered splash.
    assert int(catalog.effect_radius_units[mega_knight]) == 1_300
    assert bool(catalog.training_supported[mega_knight])
