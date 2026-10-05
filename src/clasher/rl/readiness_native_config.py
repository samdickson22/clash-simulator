"""Materialize readiness episode configs without connecting to the native engine.

The converter copies a verified, previously exercised synthetic configuration.
Only the episode seed and ordered card-ID lists change. Prefix controllers and
root selection belong to the capture adapter, not undocumented native fields.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from clasher.data import CardDataLoader

from .readiness_execution import canonical_sha, file_sha
from .readiness_root_bank import RootBank, RootRequest
from .training_readiness_v2 import SHA, Record


class ConfigEntry(Record):
    family_id: str
    source_episode_id: str
    root_request_sha256: SHA
    root_owner: Literal[0, 1]
    episode_seed: int
    ordered_decks: tuple[tuple[str, ...], tuple[str, ...]]
    prefix_styles: tuple[str, str]
    level: Literal[11] = 11
    base_forms_only: Literal[True] = True
    status: Literal["configured", "unsupported"]
    config_path: str | None = None
    config_file_sha256: SHA | None = None
    config_sha256: SHA | None = None
    native_card_ids: tuple[tuple[int, ...], tuple[int, ...]] | None = None
    failure: str | None = None


class ConfigManifest(Record):
    schema_version: Literal["readiness-v2-native-configs-v1"] = (
        "readiness-v2-native-configs-v1"
    )
    status: Literal["uncaptured_unregistered"] = "uncaptured_unregistered"
    native_ruleset: Literal["Nulls-15.535.86"] = "Nulls-15.535.86"
    root_bank_sha256: SHA
    root_bank_file_sha256: SHA
    template_config_sha256: SHA
    template_input_pins: dict[str, SHA]
    gamedata_sha256: SHA
    gamedata_path: str
    source_pins: dict[str, SHA]
    episodes: tuple[ConfigEntry, ...]
    configured_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


def load_verified_template(capture: Path, expected_plan_sha256: str) -> dict[str, Any]:
    """Validate a read-only opened capture before copying its exercised settings."""
    if file_sha(capture / "plan.json") != expected_plan_sha256:
        raise ValueError("template plan hash changed")
    plan = json.loads((capture / "plan.json").read_text())
    result = json.loads((capture / "result.json").read_text())
    initial = json.loads((capture / "initial.json").read_text())
    if (
        plan.get("role") != "development"
        or result.get("failure") is not None
        or result.get("producer_sources_unchanged") is not True
    ):
        raise ValueError(
            "template must be an exercised, successful opened-development capture"
        )
    config = plan["config"]
    battle = config["battle"]
    if config.get("cmd") != [] or config.get("evt") != [] or config.get("time") != -1:
        raise ValueError(
            "template has scripted commands, events, or a nondefault clock"
        )
    if (
        battle.get("gamemode") != 72000006
        or battle.get("lvlcap") != 11
        or battle.get("cardlvlmin") != 11
        or battle.get("hm") is not False
        or battle.get("tps") != 1
    ):
        raise ValueError(
            "template must use the exercised level-11 default Ladder rules"
        )
    if initial.get("tick") != 0 or initial.get("truncated") is not False:
        raise ValueError("template lacks a complete initial state")
    for owner in (0, 1):
        deck = battle[f"deck{owner}"]
        if deck.get("hdr") != "BD01" or len(deck["sp"]) != 8:
            raise ValueError("template must contain two BD01 eight-card decks")
        if any(set(card) != {"d"} or type(card["d"]) is not int for card in deck["sp"]):
            raise ValueError(
                "template must declare base cards with default per-card fields"
            )
        if deck.get("sc") != [{"d": 159000000, "l": 1, "t": 0, "c": 1}]:
            raise ValueError(
                "template must retain the exercised Tower Princess support payload"
            )
        if (
            battle["hbd"][owner]["kt"] != 11
            or battle[f"avatar{owner}"]["expLevel"] != 11
        ):
            raise ValueError("template tower and player levels must be 11")
        player = next(p for p in initial["players"] if p["owner"] == owner)
        observed = sorted(player["deck"], key=lambda card: card["deckSlot"])
        expected = [card["d"] for card in deck["sp"]]
        if [card["cardId"] for card in observed] != expected:
            raise ValueError(
                "template ordered card IDs differ from observed native deck slots"
            )
        if any(card["commandCardId"] != card["cardId"] for card in observed):
            raise ValueError(
                "template initial command identities do not match base cards"
            )
    return copy.deepcopy(config)


def config_for_request(
    request: RootRequest,
    template: dict[str, Any],
    loader: CardDataLoader,
    template_loader: CardDataLoader,
) -> dict[str, Any]:
    """Use the historical ordered-deck substitution with checked native identities."""
    config = copy.deepcopy(template)
    for owner, deck in enumerate(request.decks):
        ids = []
        for name in deck:
            card, original = loader.get_card(name), template_loader.get_card(name)
            if card is None or original is None:
                raise ValueError(f"unsupported native card {name}")
            native_id = card._raw_entry.get("id")
            if type(native_id) is not int or native_id != original._raw_entry.get("id"):
                raise ValueError(f"native identity changed or missing for {name}")
            ids.append(native_id)
        if len(set(ids)) != 8:
            raise ValueError(
                "aliases collapse the requested deck to duplicate native cards"
            )
        config["battle"][f"deck{owner}"]["sp"] = [{"d": native_id} for native_id in ids]
    config["rndSeed"] = request.episode_seed
    return config


def materialize_configs(
    bank: RootBank,
    *,
    template_capture: Path,
    expected_template_plan_sha256: str,
    gamedata: Path,
    expected_gamedata_sha256: str,
    output: Path,
) -> ConfigManifest:
    """Write configs and retain per-request failures; do not register or capture."""
    if file_sha(gamedata) != expected_gamedata_sha256:
        raise ValueError("declared gamedata hash changed")
    template = load_verified_template(template_capture, expected_template_plan_sha256)
    loader = CardDataLoader(gamedata)
    template_loader = CardDataLoader(template_capture / "gamedata.json")
    output.mkdir(parents=True, exist_ok=False)
    (output / "configs").mkdir()
    bank_path = output / "root-bank.json"
    bank_path.write_text(bank.model_dump_json(indent=2) + "\n")
    (output / "template-config.json").write_text(json.dumps(template, indent=2) + "\n")
    entries = []
    for index, request in enumerate(bank.requests):
        common: dict[str, Any] = {
            "family_id": request.family_id,
            "source_episode_id": request.source_episode_id,
            "root_request_sha256": canonical_sha(request.model_dump(mode="json")),
            "root_owner": request.root_owner,
            "episode_seed": request.episode_seed,
            "ordered_decks": request.decks,
            "prefix_styles": request.prefix_styles,
        }
        try:
            config = config_for_request(request, template, loader, template_loader)
        except (ValueError, KeyError, TypeError) as exc:
            entries.append(
                ConfigEntry(**common, status="unsupported", failure=str(exc))
            )
            continue
        relative = f"configs/episode-{index:02d}.json"
        path = output / relative
        path.write_text(json.dumps(config, indent=2) + "\n")
        entries.append(
            ConfigEntry(
                **common,
                status="configured",
                config_path=relative,
                config_file_sha256=file_sha(path),
                config_sha256=canonical_sha(config),
                native_card_ids=(
                    tuple(c["d"] for c in config["battle"]["deck0"]["sp"]),
                    tuple(c["d"] for c in config["battle"]["deck1"]["sp"]),
                ),
            )
        )
    package = Path(__file__).resolve().parents[1]
    source_paths = [
        Path(__file__),
        Path(__file__).with_name("readiness_root_bank.py"),
        Path(__file__).with_name("readiness_execution.py"),
        package.parent.parent / "scripts/materialize_readiness_configs.py",
        package.parent.parent / "scripts/compare_native_public_games.py",
        package / "data.py",
        package / "card_aliases.py",
        package / "card_types.py",
        package / "balance.py",
        package / "gamedata_normalization.py",
        *sorted((package / "factory").glob("*.py")),
    ]
    manifest = ConfigManifest(
        root_bank_sha256=canonical_sha(bank.model_dump(mode="json")),
        root_bank_file_sha256=file_sha(bank_path),
        template_config_sha256=canonical_sha(template),
        template_input_pins={
            str(template_capture / name): file_sha(template_capture / name)
            for name in ("plan.json", "initial.json", "result.json", "gamedata.json")
        },
        gamedata_sha256=file_sha(gamedata),
        gamedata_path=str(gamedata.resolve()),
        source_pins={str(path): file_sha(path) for path in source_paths},
        episodes=tuple(entries),
        configured_count=sum(e.status == "configured" for e in entries),
        failed_count=sum(e.status == "unsupported" for e in entries),
    )
    (output / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    return manifest
