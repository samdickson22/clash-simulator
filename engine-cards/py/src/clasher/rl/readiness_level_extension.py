"""Prospective level probes, Crown normalization and evidence-bound extensions.

Native uniform card levels and per-seat King levels are factual engine scopes.
Independent per-card training randomization is a separate protocol decision.
Nothing in this module changes the nominal thirty-two-family admission gate.

Every accepted value is recomputed from hash-pinned raw artifacts. Producer
``status``/``passed``/``verified`` flags are never sufficient on their own, and a
receipt cannot widen native scope beyond uniform cards with per-seat Kings.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from itertools import zip_longest
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.paths import gamedata_path
from clasher.tower_scaling import tower_stat

from .readiness_execution import canonical_sha, file_sha
from .readiness_transport import audit_native_transport_row
from .training_readiness_v2 import APPROVED_STRATEGY_SHA, SHA, Protocol, Record

Level = Literal[10, 11, 12]
LEVELS = (10, 11, 12)
# A bounded representation check across card rarities/types, not another Tier A.
BODY_CHECKS = ("Knight", "Musketeer", "DarkPrince", "Cannon")
SPELL_CHECKS = ("Fireball", "Log", "Zap")
SESSION_SCHEMA = "native-verified-read-session.v1"
SESSION_FREQUENCY = "full-attestation-at-session-enter-and-close"
WAIT_ACTION = 2304
HORIZON_TICKS = 200
INFORMATIVE_MARGIN = 0.01
MAX_RANKING_REGRET = 0.05
# Frozen prospective scalar mixed-level criteria (this module is source-pinned).
SCALAR_MIN_INFORMATIVE_CASES = 2
ANCHORS = {
    (0, 3500, 6500): 0,
    (0, 14500, 6500): 1,
    (0, 9000, 3000): 2,
    (1, 3500, 25500): 0,
    (1, 14500, 25500): 1,
    (1, 9000, 29000): 2,
}


class FilePin(Record):
    path: str
    sha256: SHA

    def read_bytes(self) -> bytes:
        path = Path(self.path)
        # Hash the exact bytes that are parsed, not a separate later read.
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise ValueError(f"level extension artifact changed: {path}")
        return data

    def payload(self) -> Any:
        return json.loads(self.read_bytes())


class NativeLevelPlan(Record):
    card_level: Level
    king_levels: tuple[Level, Level]
    native_scope: Literal["uniform_cards_asymmetric_kings"] = (
        "uniform_cards_asymmetric_kings"
    )

    def tower_levels(self, owner: int) -> tuple[Level, Level, Level]:
        if type(owner) is not int or owner not in (0, 1):
            raise ValueError("owner must be zero or one")
        return self.card_level, self.card_level, self.king_levels[owner]

    def starting_crown_hp(self, owner: int) -> int:
        left, right, king = self.tower_levels(owner)
        return (
            tower_stat("PrincessTower", "hitpoints", left)
            + tower_stat("PrincessTower", "hitpoints", right)
            + tower_stat("KingTower", "hitpoints", king)
        )


def configure_native_levels(
    config: dict[str, Any], plan: NativeLevelPlan
) -> dict[str, Any]:
    """Use only fields documented by the pinned native MatchConfig serializer.

    lvlcap/cardlvlmin affect ordinary cards and Princess support cards. hbd.kt
    changes King stats; avatar.expLevel keeps its displayed level synchronized.
    No unverified per-card `sp.l` or rarity-offset field is introduced.
    """
    result = copy.deepcopy(config)
    battle = result["battle"]
    if battle.get("gamemode") != 72000006:
        raise ValueError("level probes require the exercised default Ladder mode")
    for owner in (0, 1):
        deck = battle[f"deck{owner}"]
        if len(deck["sp"]) != 8 or any(set(card) != {"d"} for card in deck["sp"]):
            raise ValueError("level probes require eight base-form card entries")
        if deck["sc"][0]["d"] != 159000000 or len(deck["sc"]) != 1:
            raise ValueError("only Princess support towers are in scope")
        battle["hbd"][owner]["kt"] = plan.king_levels[owner]
        battle[f"avatar{owner}"]["expLevel"] = plan.king_levels[owner]
    battle["lvlcap"] = plan.card_level
    battle["cardlvlmin"] = plan.card_level
    return result


class LevelFamilyScope(Record):
    """Fixed root-owner HP denominator even when the two seats differ."""

    root_owner: Literal[0, 1]
    levels: NativeLevelPlan

    @property
    def starting_crown_hp(self) -> int:
        return self.levels.starting_crown_hp(self.root_owner)

    def normalized_margin(self, own_remaining: float, enemy_remaining: float) -> float:
        if own_remaining < 0 or enemy_remaining < 0:
            raise ValueError("remaining Crown HP must be nonnegative")
        return (own_remaining - enemy_remaining) / self.starting_crown_hp


PROBE_PLANS = (
    NativeLevelPlan(card_level=10, king_levels=(10, 12)),
    NativeLevelPlan(card_level=10, king_levels=(12, 10)),
    NativeLevelPlan(card_level=12, king_levels=(12, 10)),
    NativeLevelPlan(card_level=12, king_levels=(10, 12)),
)


class LevelProbeDeclaration(Record):
    plan: NativeLevelPlan
    config_sha256: SHA


class LevelExtensionDeclaration(Record):
    schema_version: Literal["readiness-level-extension-plan-v1"] = (
        "readiness-level-extension-plan-v1"
    )
    base_admission_sha256: SHA
    native_attestation_sha256: SHA
    gamedata_sha256: SHA
    probes: tuple[LevelProbeDeclaration, ...]
    strategy_sha256: Literal[
        "2be09f05cfda1a76a2536593df363afde8112377afa70bec55b9489a564da17f"
    ] = APPROVED_STRATEGY_SHA

    @model_validator(mode="after")
    def four_probes(self) -> LevelExtensionDeclaration:
        if tuple(p.plan for p in self.probes) != PROBE_PLANS:
            raise ValueError(
                "four declared uniform-card/asymmetric-King probes required"
            )
        if len({p.config_sha256 for p in self.probes}) != 4:
            raise ValueError("probe configurations must be distinct")
        return self


class NativeLevelProbe(Record):
    config: FilePin
    frames: FilePin
    verified_read_session: FilePin
    # Raw decision and command/receipt rows. Transport is re-audited row by row;
    # a producer "passed" audit is not accepted as evidence.
    transport_decisions: FilePin
    transport_rows: FilePin


class LevelExtensionReceipt(Record):
    """Unverified input. It deliberately exposes no admitted levels or scopes."""

    schema_version: Literal["readiness-level-extension-evidence-v2"] = (
        "readiness-level-extension-evidence-v2"
    )
    declaration: FilePin
    base_admission: FilePin
    nominal_protocol: FilePin
    ranking_checks: FilePin
    gamedata: FilePin
    source_pins: dict[str, SHA] = Field(min_length=1)
    probes: tuple[NativeLevelProbe, ...]
    protocol_decision: FilePin | None = None
    scalar_adaptation: FilePin | None = None
    native_level_scope: Literal["uniform_cards_asymmetric_kings"] = (
        "uniform_cards_asymmetric_kings"
    )


class VerifiedLevelExtension(Record):
    """Scope derived by ``verify_level_extension_receipt`` from recomputed evidence.

    Native measured scope and training-sampling permission are separate fields:
    independent-card training never implies native independent-card parity.
    """

    receipt_sha256: SHA
    declaration: FilePin
    nominal_levels: tuple[Literal[11], ...] = (11,)
    verified_levels: tuple[Level, ...]
    native_level_scope: Literal["uniform_cards_asymmetric_kings"]
    native_measured_card_levels: tuple[Level, ...]
    native_measured_king_levels: tuple[Level, ...]
    native_independent_card_parity: Literal[False] = False
    level_sampling_scope: Literal["uniform_cards", "independent_cards"]
    mixed_level_training_levels: tuple[Level, ...] = ()


def _is_int(value: Any) -> bool:
    return type(value) is int


def _jsonl(pin: FilePin) -> list[Any]:
    data = pin.read_bytes()
    if pin.path.endswith(".gz"):
        data = gzip.decompress(data)
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def _require_session(
    session: dict[str, Any], attestation: str, frame_count: int
) -> None:
    if (
        session.get("schema") != SESSION_SCHEMA
        or session.get("status") != "verified"
        or session.get("failures") != []
        or session.get("verification_frequency") != SESSION_FREQUENCY
        or any(
            session.get(key) != attestation
            for key in (
                "expected_attestation_sha256",
                "start_attestation_sha256",
                "end_attestation_sha256",
            )
        )
        or not isinstance(session.get("session_id"), str)
        or not session["session_id"]
        or not isinstance(session.get("runtime_identity"), dict)
        or not isinstance(session.get("reader_sha256"), str)
        or not _is_int(session.get("reads_completed"))
        or session["reads_completed"] < frame_count
    ):
        raise ValueError("native level probe lacks verified boundary attestation")


def _verify_transport(
    probe: NativeLevelProbe,
    frames_by_tick: dict[int, dict[str, Any]],
    loader: CardDataLoader,
) -> dict[tuple[int, int], int]:
    """Re-audit every retained command row; return first execute tick per play."""
    decisions, rows = _jsonl(probe.transport_decisions), _jsonl(probe.transport_rows)
    accepted: dict[tuple[int, int], int] = {}
    for decision, row in zip_longest(decisions, rows):
        if decision is None or row is None:
            raise ValueError("missing level probe decision or command transport row")
        tick = decision.get("tick")
        frame = frames_by_tick.get(tick) if _is_int(tick) else None
        if frame is None or decision["native_frame"].get("ordinary") != frame:
            raise ValueError("level probe transport is not bound to its pinned frames")
        audit_native_transport_row(row, decision, loader)
        for choice in row["selected"]:
            if choice["action"] == WAIT_ACTION:
                continue
            key = (choice["owner"], loader.get_card(choice["name"])._raw_entry["id"])
            accepted.setdefault(key, row["tick"] + 1)
    if not accepted:
        raise ValueError("level probe has no re-audited accepted command")
    return accepted


_NATIVE_PROJECTILE_KIND = 4
_NATIVE_BODY_KIND = 5


def _spell_damage_attribution(
    event: dict[str, Any], spell_ids: dict[int, str]
) -> tuple[int, int] | None:
    """Return ``(caster_owner, spell_card_id)`` for validated spell HP damage.

    Native telemetry names the attributable object ``source`` and the object
    that delivered the hit ``immediateSource``. Zap (area effect) and the
    rolling Log are their own ``source``. Fireball is thrown from the caster's
    King Tower: ``source`` is that King Tower body (``cardId -1``, kind 5, at the
    owner's King anchor) and the Fireball projectile (kind 4) is
    ``immediateSource``. Only these two shapes count; King Tower arrows carry
    ``immediateSource.cardId -1`` and never do.
    """
    source = event.get("source") or {}
    immediate = event.get("immediateSource") or {}
    target = event.get("target") or {}
    if (
        event.get("kind") != "damage"
        or event.get("pool") != "hitpoints"
        or source.get("validated") is not True
        or target.get("validated") is not True
        or not _is_int(target.get("cardId"))
        or not 26000000 <= target["cardId"] < 28000000
    ):
        return None
    if source.get("cardId") in spell_ids:
        return source.get("owner"), source["cardId"]
    owner, position = immediate.get("owner"), source.get("position")
    if (
        immediate.get("validated") is True
        and immediate.get("objectKind") == _NATIVE_PROJECTILE_KIND
        and immediate.get("cardId") in spell_ids
        and _is_int(owner)
        and owner in (0, 1)
        and source.get("cardId") == -1
        and source.get("objectKind") == _NATIVE_BODY_KIND
        and source.get("owner") == owner
        and isinstance(position, list)
        and len(position) == 2
        and ANCHORS.get((owner, position[0], position[1])) == 2
    ):
        return owner, immediate["cardId"]
    return None


def _verify_probe(
    probe: NativeLevelProbe,
    declared: LevelProbeDeclaration,
    attestation: str,
    loader: CardDataLoader,
) -> set[str]:
    config = probe.config.payload()
    if canonical_sha(config) != declared.config_sha256:
        raise ValueError("native probe configuration differs from its declaration")
    if configure_native_levels(config, declared.plan) != config:
        raise ValueError("native probe does not encode its declared levels")
    frames = _jsonl(probe.frames)
    session = probe.verified_read_session.payload()
    _require_session(session, attestation, len(frames))
    if not frames or frames[0]["ordinary"]["tick"] != 0:
        raise ValueError("level probes require a full tick-zero Crown observation")
    frames_by_tick = {frame["ordinary"]["tick"]: frame["ordinary"] for frame in frames}
    accepted = _verify_transport(probe, frames_by_tick, loader)
    seen: set[str] = set()
    deck_ids = {
        owner: {row["d"] for row in config["battle"][f"deck{owner}"]["sp"]}
        for owner in (0, 1)
    }
    cards = {}
    for name in BODY_CHECKS + SPELL_CHECKS:
        card = loader.get_card(name)
        if card is None:
            raise ValueError(f"required level-check card is missing: {name}")
        cards[name] = card
    body_ids = {cards[name]._raw_entry["id"]: name for name in BODY_CHECKS}
    spell_ids = {cards[name]._raw_entry["id"]: name for name in SPELL_CHECKS}

    def commanded(owner: Any, card_id: int, tick: int) -> None:
        first = accepted.get((owner, card_id))
        if first is None or tick < first:
            raise ValueError("observed card lacks an earlier re-audited command")

    first_crowns = set()
    previous_tick = -1
    previous_read = 0
    for frame in frames:
        ordinary, levels = frame["ordinary"], frame["level_source"]
        if (
            not _is_int(ordinary.get("tick"))
            or ordinary["tick"] <= previous_tick
            or levels["ordinary"] != ordinary
        ):
            raise ValueError("level probe frame ordering or level evidence mismatch")
        previous_tick = ordinary["tick"]
        linkage = levels.get("verified_session", {})
        read_index = linkage.get("read_index")
        if (
            linkage.get("schema") != SESSION_SCHEMA
            or linkage.get("session_id") != session["session_id"]
            or linkage.get("runtime_identity") != session["runtime_identity"]
            or not _is_int(read_index)
            or not previous_read < read_index <= session["reads_completed"]
            or levels.get("reader_sha256") != session["reader_sha256"]
            or canonical_sha({"ok": True, "attestation": levels.get("attestation")})
            != attestation
        ):
            raise ValueError("frame does not belong to the verified read session")
        previous_read = read_index
        for obj in ordinary["objects"]:
            if obj.get("hp") is None:
                continue
            native_level = levels["levels"].get(str(obj["nativeObjectId"]))
            anchor = (obj["owner"], obj["x"], obj["y"])
            if obj["cardId"] == -1 and anchor in ANCHORS:
                slot = ANCHORS[anchor]
                wanted = declared.plan.tower_levels(obj["owner"])[slot]
                hp = tower_stat(
                    "KingTower" if slot == 2 else "PrincessTower", "hitpoints", wanted
                )
                if native_level != wanted or obj["maxHp"] != hp:
                    raise ValueError(
                        "native Crown level or maximum HP differs from declared curve"
                    )
                if ordinary["tick"] == 0:
                    if obj["hp"] != hp:
                        raise ValueError("initial Crown HP is not full starting HP")
                    first_crowns.add(anchor)
                continue
            # Any deviation means the native run was not uniform-card; that
            # evidence can never support the declared uniform measured scope.
            if (
                obj["cardId"] in deck_ids.get(obj["owner"], set())
                and native_level != declared.plan.card_level
            ):
                raise ValueError(
                    "native deck card level differs from the uniform card level"
                )
            if obj["cardId"] in body_ids:
                if obj["cardId"] not in deck_ids[obj["owner"]]:
                    raise ValueError("observed body is not in its declared owner deck")
                commanded(obj["owner"], obj["cardId"], ordinary["tick"])
                name = body_ids[obj["cardId"]]
                card = copy.copy(cards[name])
                card.level = declared.plan.card_level
                if native_level != card.level or obj["maxHp"] != card.scaled_hitpoints:
                    raise ValueError(
                        "native body level or maximum HP differs from scalar scaling"
                    )
                seen.add(name)
        combat = frame.get("rich", {}).get("combatEvents", {})
        for event in combat.get("events") or ():
            attributed = _spell_damage_attribution(event, spell_ids)
            if attributed is None:
                continue
            if (
                combat.get("complete") is not True
                or combat.get("hookSetAttested") is not True
                or event.get("generation") != ordinary["generation"]
                or event.get("stateEpoch") != ordinary["stateEpoch"]
            ):
                raise ValueError(
                    "spell damage telemetry is not complete and epoch-bound"
                )
            spell_owner, spell_id = attributed
            if spell_id not in deck_ids.get(spell_owner, set()):
                raise ValueError(
                    "observed spell source is not in its declared owner deck"
                )
            commanded(spell_owner, spell_id, ordinary["tick"])
            name = spell_ids[spell_id]
            spell = create_spell_from_json(
                cards[name]._raw_entry, level=declared.plan.card_level
            )
            if event.get("requestedAmount") != spell.damage:
                raise ValueError(
                    "native spell damage differs from declared level scaling"
                )
            seen.add(name)
    if first_crowns != set(ANCHORS):
        raise ValueError("both seats need all three full initial Crown observations")
    return seen


def _crown_hp(
    ending: dict[str, Any], max_hp: dict[tuple[int, int, int], int]
) -> list[float]:
    """Sum remaining Crown HP at the six anchors; reject impossible towers."""
    ordinary = ending.get("ordinary", ending)
    hps = [0.0, 0.0]
    anchors = set()
    for obj in ordinary["objects"]:
        if obj.get("cardId") != -1:
            continue
        anchor = (obj.get("owner"), obj.get("x"), obj.get("y"))
        hp = obj.get("hp")
        if (
            anchor not in max_hp
            or anchor in anchors
            or not isinstance(hp, int | float)
            or isinstance(hp, bool)
            or not math.isfinite(hp)
            or not 0 <= hp <= max_hp[anchor]
        ):
            raise ValueError("ending Crown object is unknown, duplicated or impossible")
        anchors.add(anchor)
        hps[anchor[0]] += float(hp)
    return hps


def _plan_max_hp(plan: NativeLevelPlan) -> dict[tuple[int, int, int], int]:
    return {
        anchor: tower_stat(
            "KingTower" if slot == 2 else "PrincessTower",
            "hitpoints",
            plan.tower_levels(anchor[0])[slot],
        )
        for anchor, slot in ANCHORS.items()
    }


def _ending_ordinary(row: dict[str, Any]) -> dict[str, Any]:
    if not _is_int(row.get("root_tick")) or row["root_tick"] < 0:
        raise ValueError("branch root tick is invalid")
    ending = FilePin.model_validate(row["ending_frame"]).payload()
    ordinary = ending.get("ordinary", ending)
    if ordinary.get("tick") != row["root_tick"] + HORIZON_TICKS:
        raise ValueError("level ranking branch did not reach its declared horizon")
    return ordinary


def _verify_rankings(
    pin: FilePin,
    declaration: LevelExtensionDeclaration,
    declaration_sha: str,
    nominal_margin_floor: float,
) -> None:
    """Two public alternatives and two reacting conditions per probe, at10seconds.

    This is bounded transfer evidence. It is not a full-game or independent
    thirty-two-family acceptance result. Scalar ties are scored pessimistically.
    """
    study = pin.payload()
    if (
        study.get("schema") != "readiness-level-rankings-v1"
        or study.get("declaration_sha256") != declaration_sha
        or study.get("horizon_ticks") != HORIZON_TICKS
        or study.get("conditions") != ["balanced/pressure", "defense/balanced"]
    ):
        raise ValueError("level ranking protocol differs from the prospective design")
    expected = {
        (p, c, a, e)
        for p in range(4)
        for c in range(2)
        for a in range(2)
        for e in ("scalar", "reference")
    }
    margins = {}
    for row in study.get("branches", []):
        key = (row["probe"], row["condition"], row["candidate"], row["engine"])
        if (
            not all(_is_int(value) for value in key[:3])
            or key not in expected
            or key in margins
        ):
            raise ValueError("undeclared or duplicate level ranking branch")
        p, _condition, _candidate, _engine = key
        if (
            row.get("config_sha256") != declaration.probes[p].config_sha256
            or row.get("public_legal") is not True
            or row.get("root_owner") != p % 2
        ):
            raise ValueError("level ranking branch scope or public legality mismatch")
        plan = declaration.probes[p].plan
        hps = _crown_hp(_ending_ordinary(row), _plan_max_hp(plan))
        owner = p % 2
        margins[key] = (hps[owner] - hps[1 - owner]) / plan.starting_crown_hp(owner)
    if set(margins) != expected:
        raise ValueError("level ranking branches are missing")
    informative = 0
    for p in range(4):
        reference = [
            sum(margins[p, c, a, "reference"] for c in range(2)) / 2 for a in range(2)
        ]
        scalar = [
            sum(margins[p, c, a, "scalar"] for c in range(2)) / 2 for a in range(2)
        ]
        chosen = [a for a in range(2) if scalar[a] == max(scalar)]
        regret = max(reference) - min(reference[a] for a in chosen)
        if regret > MAX_RANKING_REGRET:
            raise ValueError("material decision ranking regression in a level probe")
        floor = (
            nominal_margin_floor
            * 10928
            / declaration.probes[p].plan.starting_crown_hp(p % 2)
        )
        informative += abs(reference[0] - reference[1]) > max(INFORMATIVE_MARGIN, floor)
    if informative < 2:
        raise ValueError("level probes lack consequential non-wait ranking coverage")


def _scalar_levels(
    case: dict[str, Any], loader: CardDataLoader
) -> list[dict[int, int]]:
    """Validate declared per-seat card levels; return card id -> level per seat."""
    card_levels, tower_levels = case.get("card_levels"), case.get("tower_levels")
    if (
        not isinstance(card_levels, list)
        or len(card_levels) != 2
        or not isinstance(tower_levels, list)
        or len(tower_levels) != 2
        or any(not _is_int(level) or level not in LEVELS for level in tower_levels)
    ):
        raise ValueError("scalar mixed-level case has an invalid level declaration")
    seats = []
    for levels in card_levels:
        if not isinstance(levels, dict) or len(levels) != 8:
            raise ValueError("scalar mixed-level case needs eight levels per seat")
        by_id = {}
        for name, level in levels.items():
            card = loader.get_card(name)
            if card is None or not _is_int(level) or level not in LEVELS:
                raise ValueError("scalar mixed-level card or level is out of scope")
            by_id[card._raw_entry["id"]] = level
        if len(by_id) != 8:
            raise ValueError("scalar mixed-level seat repeats a card")
        seats.append(by_id)
    return seats


def _verify_scalar_adaptation(
    pin: FilePin,
    *,
    base_admission_sha256: str,
    declaration_sha: str,
    gamedata_sha256: str,
    loader: CardDataLoader,
) -> None:
    """Recompute bounded independent-card scalar invariants and rankings.

    Invariants: every observed body HP, Crown HP and spell damage equals the
    scaling curve at that seat's declared card/tower level, with some seat
    holding several levels at once. Adaptation: two alternatives per case,
    Crown-normalized at the actual per-seat tower levels, must separate in at
    least SCALAR_MIN_INFORMATIVE_CASES cases. No producer verdict is read.
    """
    study = pin.payload()
    if (
        study.get("schema") != "readiness-bounded-scalar-adaptation-v2"
        or study.get("base_admission_sha256") != base_admission_sha256
        or study.get("native_declaration_sha256") != declaration_sha
        or study.get("gamedata_sha256") != gamedata_sha256
        or not isinstance(study.get("cases"), list)
        or not study["cases"]
    ):
        raise ValueError("bounded scalar adaptation evidence is missing or mismatched")
    cards = {name: loader.get_card(name) for name in BODY_CHECKS + SPELL_CHECKS}
    ids = {card._raw_entry["id"]: name for name, card in cards.items()}
    covered: set[tuple[str, int]] = set()
    card_levels_seen: set[int] = set()
    asymmetric_towers = False
    informative = 0
    for case in study["cases"]:
        seats = _scalar_levels(case, loader)
        towers = case["tower_levels"]
        asymmetric_towers |= towers[0] != towers[1]
        mixed = [len(set(seat.values())) >= 2 for seat in seats]
        for seat in seats:
            card_levels_seen.update(seat.values())
        observed = FilePin.model_validate(case.get("observation")).payload()
        crowns = [(row.get("owner"), row.get("slot")) for row in observed["towers"]]
        if sorted(crowns) != [(o, s) for o in (0, 1) for s in range(3)] or not all(
            _is_int(o) and _is_int(s) for o, s in crowns
        ):
            raise ValueError("scalar case needs exactly six Crown observations")
        for row in observed["towers"]:
            owner, slot = row["owner"], row["slot"]
            name = "KingTower" if slot == 2 else "PrincessTower"
            if row.get("level") != towers[owner] or row.get("maxHp") != tower_stat(
                name, "hitpoints", towers[owner]
            ):
                raise ValueError("scalar Crown level or HP differs from declared level")
        for kind in ("bodies", "spells"):
            for row in observed.get(kind, ()):
                owner = row.get("owner")
                if not _is_int(owner) or owner not in (0, 1):
                    raise ValueError("scalar observation owner is out of scope")
                card = loader.get_card(row.get("card", ""))
                if card is None or card._raw_entry["id"] not in seats[owner]:
                    raise ValueError("scalar observation card is not in its seat deck")
                level = seats[owner][card._raw_entry["id"]]
                if row.get("level") != level:
                    raise ValueError("scalar observation used an undeclared card level")
                if kind == "bodies":
                    scaled = copy.copy(card)
                    scaled.level = level
                    if row.get("maxHp") != scaled.scaled_hitpoints:
                        raise ValueError("scalar body HP differs from its card level")
                else:
                    spell = create_spell_from_json(card._raw_entry, level=level)
                    if row.get("requestedAmount") != spell.damage:
                        raise ValueError("scalar spell damage differs from card level")
                name = ids.get(card._raw_entry["id"])
                if name is not None and mixed[owner]:
                    covered.add((name, level))
        root_owner = case.get("root_owner")
        if not _is_int(root_owner) or root_owner not in (0, 1):
            raise ValueError("scalar adaptation root owner is invalid")
        max_hp = {
            anchor: tower_stat(
                "KingTower" if slot == 2 else "PrincessTower",
                "hitpoints",
                towers[anchor[0]],
            )
            for anchor, slot in ANCHORS.items()
        }
        denominator = sum(v for (o, _x, _y), v in max_hp.items() if o == root_owner)
        branches = case.get("branches")
        if not isinstance(branches, list) or [b.get("candidate") for b in branches] != [
            0,
            1,
        ]:
            raise ValueError("scalar adaptation case needs exactly two alternatives")
        margins = []
        for branch in branches:
            hps = _crown_hp(_ending_ordinary(branch), max_hp)
            margins.append((hps[root_owner] - hps[1 - root_owner]) / denominator)
        informative += abs(margins[0] - margins[1]) > INFORMATIVE_MARGIN
    required = {(name, level) for name in ids.values() for level in (10, 12)}
    if (
        not required <= covered
        or card_levels_seen != set(LEVELS)
        or not asymmetric_towers
    ):
        raise ValueError("scalar independent-card invariant coverage is incomplete")
    if informative < SCALAR_MIN_INFORMATIVE_CASES:
        raise ValueError("scalar mixed-level adaptation lacks consequential rankings")


def verify_level_extension_receipt(
    path: Path, *, base_admission_sha256: str
) -> VerifiedLevelExtension:
    """Return only artifact-checked native scope and separately authorized training scope."""
    raw = path.read_bytes()
    receipt = LevelExtensionReceipt.model_validate_json(raw)
    declaration = LevelExtensionDeclaration.model_validate_json(
        receipt.declaration.read_bytes()
    )
    if declaration.base_admission_sha256 != base_admission_sha256:
        raise ValueError("level extension belongs to another base admission")
    if receipt.base_admission.sha256 != base_admission_sha256:
        raise ValueError("base admission bytes differ from the extension binding")
    base = receipt.base_admission.payload()
    nominal_protocol = Protocol.model_validate_json(
        receipt.nominal_protocol.read_bytes()
    )
    if (
        nominal_protocol.sha256 != base.get("protocol_sha256")
        or nominal_protocol.floors is None
    ):
        raise ValueError("nominal noise protocol is not bound to the base admission")
    if receipt.gamedata.sha256 != declaration.gamedata_sha256:
        raise ValueError("level extension ruleset differs from declaration")
    receipt.gamedata.read_bytes()
    # stat_scaling reads its multiplier table from the process-wide game data,
    # not from receipt.gamedata; recomputation must use the pinned ruleset.
    if file_sha(gamedata_path()) != declaration.gamedata_sha256:
        raise ValueError("process scaling game data differs from the pinned ruleset")
    package = Path(__file__).resolve().parents[1]
    required_sources = {
        Path(__file__).resolve(),
        package / "tower_scaling.py",
        package / "balance.py",
        package / "stat_scaling.py",
        package / "data.py",
        package / "dynamic_spells.py",
        package / "rl" / "readiness_transport.py",
        package / "rl" / "native_command_checks.py",
    }
    if not required_sources <= {Path(name).resolve() for name in receipt.source_pins}:
        raise ValueError(
            "level extension verifier and scaling source pins are required"
        )
    for filename, digest in receipt.source_pins.items():
        if file_sha(Path(filename)) != digest:
            raise ValueError("level extension source changed")
    if len(receipt.probes) != 4:
        raise ValueError("all four prospective native probes are required")
    loader = CardDataLoader(receipt.gamedata.path)
    seen: dict[int, set[str]] = {10: set(), 12: set()}
    for probe, declared in zip(receipt.probes, declaration.probes, strict=True):
        seen[declared.plan.card_level].update(
            _verify_probe(
                probe, declared, declaration.native_attestation_sha256, loader
            )
        )
    if any(not set(BODY_CHECKS + SPELL_CHECKS) <= names for names in seen.values()):
        raise ValueError("native level/type coverage is incomplete")
    _verify_rankings(
        receipt.ranking_checks,
        declaration,
        receipt.declaration.sha256,
        nominal_protocol.floors.margin,
    )
    if (receipt.protocol_decision is None) != (receipt.scalar_adaptation is None):
        raise ValueError(
            "independent randomization needs both a protocol decision and scalar study"
        )
    sampling: Literal["uniform_cards", "independent_cards"] = "uniform_cards"
    if receipt.protocol_decision is not None and receipt.scalar_adaptation is not None:
        decision = receipt.protocol_decision.payload()
        if (
            decision.get("schema") != "readiness-level-randomization-decision-v1"
            or decision.get("status") != "approved"
            or decision.get("strategy_sha256") != APPROVED_STRATEGY_SHA
            or decision.get("base_admission_sha256") != base_admission_sha256
            or decision.get("native_declaration_sha256") != receipt.declaration.sha256
            or decision.get("level_sampling_scope") != "independent_cards"
            or decision.get("scalar_adaptation_sha256")
            != receipt.scalar_adaptation.sha256
        ):
            raise ValueError(
                "independent-card scope lacks a bound approved protocol decision"
            )
        FilePin.model_validate(decision.get("decision_evidence")).read_bytes()
        _verify_scalar_adaptation(
            receipt.scalar_adaptation,
            base_admission_sha256=base_admission_sha256,
            declaration_sha=receipt.declaration.sha256,
            gamedata_sha256=declaration.gamedata_sha256,
            loader=loader,
        )
        sampling = "independent_cards"
    return VerifiedLevelExtension(
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        declaration=receipt.declaration,
        verified_levels=LEVELS,
        native_level_scope="uniform_cards_asymmetric_kings",
        native_measured_card_levels=tuple(
            sorted({p.plan.card_level for p in declaration.probes})
        ),
        native_measured_king_levels=tuple(
            sorted({k for p in declaration.probes for k in p.plan.king_levels})
        ),
        level_sampling_scope=sampling,
        mixed_level_training_levels=LEVELS if sampling == "independent_cards" else (),
    )
