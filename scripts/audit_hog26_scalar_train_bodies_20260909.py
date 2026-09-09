"""Exercise declared training-card body births and forced-death descendants."""

import argparse
import hashlib
import json
import random
from pathlib import Path

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.entities import Building, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.rl.structured_obs import StructuredObservationBuilder
from scripts.hog26_scalar_actor_projection import scalar_body_token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "training_decks/hog26_procedural_supported_seed1278401.json"
    manifest = json.loads(manifest_path.read_text())
    decks = [d for d in manifest["decks"] if d["split"] in {"train", "learner"}]
    cards = sorted({card for deck in decks for card in deck["cards"]})
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(token_names=vocabulary.token_names,
                                           card_semantics_version=3, max_entities=128,
                                           canonical_lane_globals=True)
    rows = []
    for card in cards:
        name = resolve_card_name(card, definitions)
        battle = BattleState(card_loader=loader, rng=random.Random(1279051))
        initial = set(battle.entities)
        battle.players[0].hand = [name, None, None, None]
        battle.players[0].elixir = 10
        accepted = battle.deploy_card(0, name, Position(3.5, 10.5))
        bodies, unresolved, root_ids, effect_types = {}, {}, set(), set()
        for tick in range(201):
            for key, entity in tuple(battle.entities.items()):
                if key in initial:
                    continue
                if not isinstance(entity, (Troop, Building)):
                    source = getattr(entity, "source_entity", None)
                    if entity.is_alive and getattr(source, "id", None) not in initial:
                        effect_types.add((type(entity).__name__,
                                          getattr(getattr(entity, "card_stats", None), "name", "") or "",
                                          getattr(entity, "spell_name", "") or "",
                                          getattr(entity, "source_name", "") or ""))
                    continue
                if tick <= 20:
                    root_ids.add(key)
                if not entity.is_alive or not any(entity.is_visible_to(seat) for seat in (0, 1)):
                    continue
                label = (type(entity).__name__, entity.card_stats.name)
                try:
                    token = scalar_body_token(entity, builder)
                    bodies[label] = vocabulary.token_names[token]
                except ValueError as exc:
                    unresolved[label] = str(exc)
            if tick == 100:
                # Synthetic mechanism probe only, never an outcome trajectory.
                for key in root_ids:
                    entity = battle.entities.get(key)
                    if entity is not None and entity.is_alive:
                        entity.take_damage(1e9, source_kind="diagnostic")
                        if entity.is_alive:
                            entity.take_damage(1e9, source_kind="diagnostic")
            if tick < 200:
                battle.step()
        row = {"card": card, "canonical_card": name, "deployment_accepted": accepted,
               "bodies": [{"class": k[0], "stats_name": k[1], "token": v}
                          for k, v in sorted(bodies.items())],
               "unresolved": [{"class": k[0], "stats_name": k[1], "reason": v}
                              for k, v in sorted(unresolved.items())],
               "diagnostic_effect_types": [{"class": k[0], "stats_name": k[1],
                                            "spell_name": k[2], "source_name": k[3]}
                                           for k in sorted(effect_types)]}
        rows.append(row)
        print(json.dumps({"card": card, "accepted": accepted, "body_types": len(bodies),
                          "unresolved": row["unresolved"]}), flush=True)
    sources = [Path(__file__).relative_to(root).as_posix(), "scripts/hog26_scalar_actor_projection.py",
               "src/clasher/battle.py", "src/clasher/entities.py"]
    report = {"scope": "Training/learner manifest cards only. One seat, 200 real ticks plus "
                       "synthetic forced parent deaths. Not complete-game coverage or actor-view acceptance. "
                       "Effect source/spell names are diagnostic provenance, not authorized actor identities.",
              "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources},
              "cards": rows}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
