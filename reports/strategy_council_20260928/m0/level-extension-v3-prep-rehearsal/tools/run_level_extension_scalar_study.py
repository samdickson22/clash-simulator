"""Scalar side of the level extension: ranking branches and the mixed-level study.

``rankings`` replays each native probe's frozen ranking root in the scalar
engine (same levels, prefix, alternatives and reacting conditions) and records
Crown-only ending frames at root + 200 ticks.

``adaptation`` runs the prospective, bounded independent-card scalar study:
per case, engine-reported Crown/body HP and spell damage at each declared
seat/card level, plus two public alternatives from a controller-played root.
The pinned verifier recomputes every scaling value and ranking margin; this
runner writes no verdict. No emulator, adb or ledger is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parent))
import level_extension_common as common  # noqa: E402

common.prefer_runtime_scripts()

import argparse  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402

from clasher.arena import Position  # noqa: E402
from clasher.data import CardDataLoader  # noqa: E402
from clasher.rl.native_public_observation import (  # noqa: E402
    NativeProjectileCatalog,
    public_reference_builder,
)
from clasher.rl.public_action_mask import (  # noqa: E402
    PublicActionMaskBuilder,
    PublicActionMaskInput,
)
from clasher.rl.public_observation import reference_public_observation  # noqa: E402
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent  # noqa: E402
from clasher.rl.readiness_execution import condition_styles, packet_sha  # noqa: E402
from clasher.rl.readiness_level_extension import (  # noqa: E402
    BODY_CHECKS,
    SPELL_CHECKS,
    LevelExtensionDeclaration,
)
from clasher.tower_scaling import tower_stat  # noqa: E402

DECK = list(common.DECK)


def mixed(bodies: int, spells: int, hog: int) -> dict[str, int]:
    return {**{n: bodies for n in BODY_CHECKS}, **{n: spells for n in SPELL_CHECKS}, "HogRider": hog}


def uniform(level: int) -> dict[str, int]:
    return {n: level for n in DECK}


# Frozen prospective design (declared before the admitted run). Every case
# gives at least one seat several card levels at once; Crown levels are per
# seat. Seat 0 is mixed in cases 0/1/4/5, seat 1 in cases 2-5, so each check
# card appears at 10 and 12 in a mixed seat, levels 10/11/12 all appear and
# Crown levels are asymmetric. Hands come from the declared seeds.
CASES = (
    {"card_levels": (mixed(10, 12, 11), uniform(11)), "tower_levels": (10, 12), "root_owner": 0, "seed": 2609291},
    {"card_levels": (mixed(12, 10, 11), uniform(11)), "tower_levels": (12, 11), "root_owner": 0, "seed": 2609292},
    {"card_levels": (uniform(12), mixed(10, 12, 11)), "tower_levels": (11, 10), "root_owner": 1, "seed": 2609293},
    {"card_levels": (uniform(10), mixed(12, 10, 11)), "tower_levels": (12, 10), "root_owner": 1, "seed": 2609294},
    {"card_levels": (mixed(12, 10, 11), mixed(10, 12, 11)), "tower_levels": (10, 12), "root_owner": 0, "seed": 2609295},
    {"card_levels": (mixed(10, 12, 12), mixed(12, 10, 10)), "tower_levels": (12, 10), "root_owner": 1, "seed": 2609296},
)
# Both seats follow the balanced controller from tick 90; the root is the
# first five-tick boundary at/after ROOT_MIN_TICK where the declared
# attack-versus-defense alternatives exist (common.ranking_candidates).
ROOT_MIN_TICK = 90
ROOT_SEARCH_TICKS = 1500
ADAPTATION_CONDITION = "balanced/pressure"


def case_levels(case) -> tuple[dict[str, int], dict[str, int]]:
    return dict(case["card_levels"][0]), dict(case["card_levels"][1])


class Scalar:
    def __init__(self, loader, catalog):
        self.loader = loader
        self.builder = public_reference_builder(loader, catalog, card_semantics_version=4,
                                                public_contract_version=4)
        self.masks = PublicActionMaskBuilder(self.builder)
        self.space = common.DiscreteTileActionSpace()

    def views(self, battle):
        return [reference_public_observation(self.builder.build_actor(battle, owner)) for owner in (0, 1)]

    def legal(self, view, action):
        return bool(self.masks.build(PublicActionMaskInput.from_confidence_observation(view))[action])

    @staticmethod
    def advance(battle, target):
        while battle.tick < target and not battle.game_over:
            battle.step()

    def act(self, battle, view, owner, action):
        """Deploy a public-legal action exactly as the Tier A scalar runner does."""
        choice = self.space.decode_action(action, owner)
        if choice.is_no_op:
            return None
        name = self.builder.card_name_for_token_id(int(view.observation.hand_ids[choice.slot]))
        if name is None or not battle.deploy_card(owner, name, Position(choice.position.x, choice.position.y)):
            raise ValueError("scalar rejected a declared public-legal action")
        return name

    def branch(self, battle, root_tick, root_owner, candidate, condition, decisions_path):
        """Run one alternative for HORIZON_TICKS under a condition; return ending frame."""
        styles = condition_styles(condition, root_owner)
        controllers = [PublicScriptedOpponent(self.builder, style=style) for style in styles]
        with common.JsonlWriter(decisions_path) as stream:
            for boundary in range(root_tick, root_tick + common.HORIZON_TICKS, 5):
                self.advance(battle, boundary)
                if battle.game_over or battle.tick != boundary:
                    raise ValueError("scalar ranking branch ended or skipped an interval")
                views = self.views(battle)
                actions = []
                for owner, view in enumerate(views):
                    if boundary == root_tick and owner == root_owner:
                        action = candidate["action_id"]
                        slot = action // 576
                        if action != 2304 and int(view.observation.hand_ids[slot]) != candidate["card_token"]:
                            raise ValueError("scalar root hand slot differs from the frozen candidate")
                    else:
                        action = controllers[owner].select_action(view)
                    if not self.legal(view, action):
                        raise ValueError("declared scalar action is not public-legal")
                    actions.append(action)
                stream.write({"tick": boundary, "actions": actions,
                              "public_sha256": [packet_sha(v) for v in views]})
                for owner, (view, action) in enumerate(zip(views, actions)):
                    self.act(battle, view, owner, action)
                self.advance(battle, boundary + 1)
        self.advance(battle, root_tick + common.HORIZON_TICKS)
        if battle.tick != root_tick + common.HORIZON_TICKS:
            raise ValueError("scalar ranking branch did not reach its horizon")
        return common.scalar_crown_frame(battle)


# ----------------------------------------------------------------- rankings


def run_rankings(args, catalog) -> dict:
    declaration = LevelExtensionDeclaration.model_validate_json(args.declaration.read_text())
    if common.file_sha(args.gamedata) != declaration.gamedata_sha256:
        raise ValueError("gamedata differs from the declaration")
    native = json.loads((args.native_run / "collection-result.json").read_text())
    if native["declaration"]["sha256"] != common.file_sha(args.declaration):
        raise ValueError("native collection belongs to another declaration")
    loader = CardDataLoader(args.gamedata)
    scalar = Scalar(loader, catalog)
    args.output.mkdir(parents=True, exist_ok=False)
    rows, failures = [], []
    for record, declared in zip(native["probes"], declaration.probes, strict=True):
        index = record["probe"]
        plan = declared.plan
        root_pin = record.get("ranking_root")
        if record.get("status") == "failed" or root_pin is None:
            failures.append({"probe": index, "failure": "native probe has no frozen ranking root"})
            continue
        root = json.loads(Path(root_pin["path"]).read_bytes())
        if common.file_sha(Path(root_pin["path"])) != root_pin["sha256"] or not root.get("candidates"):
            failures.append({"probe": index, "failure": "ranking root changed or is ineligible"})
            continue
        probe_dir = Path(record["output"])
        initial = json.loads((probe_dir / "initial.json").read_text())
        config = json.loads(Path(record["config"]["path"]).read_text())
        if common.canonical_sha(config) != declared.config_sha256:
            raise ValueError("probe config differs from the declaration")
        out = args.output / f"probe-{index}"
        out.mkdir()
        levels = {name: plan.card_level for name in DECK}
        for condition_index, condition in enumerate(common.RANKING_CONDITIONS):
            for candidate in root["candidates"]:
                name = f"ranking-c{condition_index}-a{candidate['candidate']}"
                try:
                    battle = common.scalar_battle_from_native_initial(
                        initial, config, loader, card_levels=(levels, levels),
                        princess_levels=(plan.card_level, plan.card_level), king_levels=plan.king_levels,
                    )
                    for crown in common.scalar_crowns(battle):
                        level = plan.tower_levels(crown["owner"])[crown["slot"]]
                        kind = "KingTower" if crown["slot"] == 2 else "PrincessTower"
                        if crown["level"] != level or crown["maxHp"] != tower_stat(kind, "hitpoints", level):
                            raise ValueError("scalar Crown levels differ from the declared plan")
                    for command in root["prefix_commands"]:
                        scalar.advance(battle, command["submitted_tick"])
                        if not battle.deploy_card(command["owner"], command["name"], Position(*command["xy"])):
                            raise ValueError("scalar rejected a recorded native prefix command")
                    scalar.advance(battle, root["root_tick"])
                    ending = scalar.branch(battle, root["root_tick"], root["root_owner"], candidate,
                                           condition, out / f"{name}-decisions.jsonl.gz")
                except Exception as error:
                    failures.append({"probe": index, "condition": condition_index,
                                     "candidate": candidate["candidate"],
                                     "failure": f"{type(error).__name__}: {error}",
                                     "traceback": traceback.format_exc()})
                    continue
                ending_pin = common.write_new(out / f"{name}-ending-frame.json", ending)
                rows.append({
                    "probe": index, "condition": condition_index, "candidate": candidate["candidate"],
                    "engine": "scalar", "root_tick": root["root_tick"], "root_owner": root["root_owner"],
                    "public_legal": True, "config_sha256": declared.config_sha256,
                    "role": candidate["role"], "action_id": candidate["action_id"],
                    "ending_frame": ending_pin,
                    "artifacts": {"decisions.jsonl.gz": common.pin(out / f"{name}-decisions.jsonl.gz")},
                })
    tool_files = [Path(__file__).resolve(), Path(common.__file__).resolve()]
    result = {
        "schema": "readiness-level-scalar-rankings-v1",
        "declaration_sha256": common.file_sha(args.declaration),
        "native_collection": common.pin(args.native_run / "collection-result.json"),
        "gamedata": common.pin(args.gamedata),
        "horizon_ticks": common.HORIZON_TICKS,
        "conditions": list(common.RANKING_CONDITIONS),
        "runtime": common.runtime_identity(),
        "source_pins": common.source_pins(common.runtime_source_files(tool_files)),
        "branches": rows,
        "failures": failures,
    }
    common.write_new(args.output / "scalar-rankings.json", result)
    return result


# --------------------------------------------------------------- adaptation


def _first(battle, owner, name, exclude=()):
    for entity in battle.entities.values():
        stats = getattr(entity, "card_stats", None)
        if (entity.player_id == owner and stats is not None and stats.name == name
                and entity.is_alive and entity.id not in exclude):
            return entity
    return None


def _force_play(battle, owner, name, position):
    """Stat probe only: guarantee the card and elixir, then use the real deploy path."""
    player = battle.players[owner]
    player.elixir = player.max_elixir
    if name not in player.hand:
        player.hand[0] = name
    if not battle.deploy_card(owner, name, position):
        raise ValueError(f"scalar stat probe could not deploy {name}")


def _mirror(point, owner):
    return point if owner == 0 else (18.0 - point[0], 32.0 - point[1])


def observe_case(base, loader) -> dict:
    """Engine-reported Crown, body and spell values at the case's declared levels."""
    towers = [{k: r[k] for k in ("owner", "slot", "level", "maxHp")} for r in common.scalar_crowns(base)]
    bodies, spells = [], []
    for owner in (0, 1):
        for name in (*BODY_CHECKS, "HogRider"):
            battle = base.clone()
            point = (9.5, 9.5) if name == "Cannon" else (3.5, 10.5)
            _force_play(battle, owner, name, Position(*_mirror(point, owner)))
            Scalar.advance(battle, battle.tick + 30)
            entity = _first(battle, owner, name)
            if entity is None:
                raise ValueError(f"scalar stat probe did not spawn {name}")
            bodies.append({"owner": owner, "card": name, "level": int(entity.card_stats.level),
                           "maxHp": int(round(entity.max_hitpoints)), "engine_entity": entity.card_stats.name})
        for name in SPELL_CHECKS:
            battle = base.clone()
            enemy = 1 - owner
            _force_play(battle, enemy, "Knight", Position(*_mirror((9.5, 17.5), owner)))
            target = None
            for _ in range(400):
                battle.step()
                target = _first(battle, enemy, "Knight")
                if target is not None and (target.position.y < 14.0 if owner == 0 else target.position.y > 18.0):
                    break
            if target is None:
                raise ValueError("spell target never reached the caster's half")
            resolved = battle.resolve_card_play(owner, name)
            spell_level = int(resolved[2].level)
            x, y = target.position.x, target.position.y
            if name == "Log":
                y += -1.0 if owner == 0 else 1.0
            with common.DamageRecorder() as recorder:
                _force_play(battle, owner, name, Position(round(x - 0.5) + 0.5, round(y - 0.5) + 0.5))
                Scalar.advance(battle, battle.tick + 80)
            hits = [c for c in recorder.calls if c["source_kind"] == name and c["entity_id"] == target.id]
            if not hits:
                raise ValueError(f"scalar {name} never damaged its stat-probe target")
            spells.append({"owner": owner, "card": name, "level": spell_level,
                           "requestedAmount": hits[0]["amount"], "target": hits[0]["target"],
                           "target_owner": hits[0]["target_owner"]})
    return {"towers": towers, "bodies": bodies, "spells": spells}


def controller_root(scalar, battle, root_owner):
    """Balanced controllers from tick 90; first eligible root at/after ROOT_MIN_TICK."""
    controllers = [PublicScriptedOpponent(scalar.builder, style="balanced") for _ in (0, 1)]
    prefix = []
    boundary = 90
    while boundary <= ROOT_MIN_TICK + ROOT_SEARCH_TICKS:
        Scalar.advance(battle, boundary)
        views = scalar.views(battle)
        if boundary >= ROOT_MIN_TICK:
            try:
                candidates = common.ranking_candidates(scalar.builder, views[root_owner])
            except ValueError:
                candidates = None
            if candidates is not None:
                return boundary, candidates, prefix, packet_sha(views[root_owner])
        for owner, view in enumerate(views):
            action = controllers[owner].select_action(view)
            name = scalar.act(battle, view, owner, action)
            if name is not None:
                prefix.append({"owner": owner, "tick": boundary, "action": action, "name": name})
        Scalar.advance(battle, boundary + 1)
        boundary += 5
    raise ValueError("no eligible scalar adaptation root inside the declared window")


def run_adaptation(args, catalog) -> dict:
    declaration = LevelExtensionDeclaration.model_validate_json(args.declaration.read_text())
    gamedata_sha = common.file_sha(args.gamedata)
    if gamedata_sha != declaration.gamedata_sha256:
        raise ValueError("gamedata differs from the declaration")
    base_sha = common.file_sha(args.base_admission)
    if declaration.base_admission_sha256 != base_sha:
        raise ValueError("declaration belongs to another base admission")
    loader = CardDataLoader(args.gamedata)
    scalar = Scalar(loader, catalog)
    args.output.mkdir(parents=True, exist_ok=False)
    cases, design = [], []
    for index, case in enumerate(CASES):
        levels = case_levels(case)
        design.append({**case, "card_levels": list(levels), "tower_levels": list(case["tower_levels"])})
        base = common.scalar_battle_for_case((DECK, DECK), levels, case["tower_levels"], loader, case["seed"])
        observation = observe_case(base, loader)
        observation_pin = common.write_new(args.output / f"case-{index}-observation.json", observation)
        root_battle = base.clone()
        root_tick, candidates, prefix, root_packet = controller_root(scalar, root_battle, case["root_owner"])
        branches = []
        for candidate in candidates:
            battle = root_battle.clone()
            ending = scalar.branch(battle, root_tick, case["root_owner"], candidate, ADAPTATION_CONDITION,
                                   args.output / f"case-{index}-a{candidate['candidate']}-decisions.jsonl.gz")
            ending_pin = common.write_new(args.output / f"case-{index}-a{candidate['candidate']}-ending-frame.json",
                                          ending)
            branches.append({"candidate": candidate["candidate"], "role": candidate["role"],
                             "action_id": candidate["action_id"], "root_tick": root_tick,
                             "ending_frame": ending_pin})
        cases.append({
            "case": index,
            "card_levels": [dict(levels[0]), dict(levels[1])],
            "tower_levels": list(case["tower_levels"]),
            "root_owner": case["root_owner"],
            "seed": case["seed"],
            "condition": ADAPTATION_CONDITION,
            "root_public_packet_sha256": root_packet,
            "prefix_plays": prefix,
            "observation": observation_pin,
            "branches": branches,
        })
    tool_files = [Path(__file__).resolve(), Path(common.__file__).resolve()]
    study = {
        "schema": "readiness-bounded-scalar-adaptation-v2",
        "base_admission_sha256": base_sha,
        "native_declaration_sha256": common.file_sha(args.declaration),
        "gamedata_sha256": gamedata_sha,
        "design": {"cases": design, "root_min_tick": ROOT_MIN_TICK, "root_search_ticks": ROOT_SEARCH_TICKS,
                   "roles": list(common.RANKING_ROLES), "condition": ADAPTATION_CONDITION,
                   "horizon_ticks": common.HORIZON_TICKS},
        "runtime": common.runtime_identity(),
        "source_pins": common.source_pins(common.runtime_source_files(tool_files)),
        "created_at": time.time(),
        "cases": cases,
    }
    common.write_new(args.output / "scalar-adaptation.json", study)
    return study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("rankings", "adaptation"):
        command = sub.add_parser(name)
        command.add_argument("--declaration", type=Path, required=True)
        command.add_argument("--gamedata", type=Path, required=True)
        command.add_argument("--catalog", type=Path, required=True)
        command.add_argument("--catalog-sha256", required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--allow-workspace-runtime", action="store_true")
    sub.choices["rankings"].add_argument("--native-run", type=Path, required=True)
    sub.choices["adaptation"].add_argument("--base-admission", type=Path, required=True)
    args = parser.parse_args()
    common.require_runtime_root(args.allow_workspace_runtime)
    catalog = NativeProjectileCatalog.from_csv(args.catalog, expected_sha256=args.catalog_sha256)
    if args.command == "rankings":
        result = run_rankings(args, catalog)
        print(json.dumps({"branches": len(result["branches"]), "failures": len(result["failures"])}))
        raise SystemExit(0 if not result["failures"] else 1)
    study = run_adaptation(args, catalog)
    print(json.dumps({"cases": len(study["cases"])}))


if __name__ == "__main__":
    main()
