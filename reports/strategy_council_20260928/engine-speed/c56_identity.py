"""C56 scripted match/branch digests, recorded before Stage 0 engine edits."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import random
import sys
from pathlib import Path

ES = Path(__file__).resolve().parent
ROOT = ES.parents[2]
spec = importlib.util.spec_from_file_location("p16_identity", ES.parent / "c56/engine/tools/p16_identity.py")
p16 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p16)
from clasher.rl.c56_scripted import C56_ADDED_CARDS
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent, SUPPORTED_CARDS


def run_all():
    builder = ContractV5ObservationBuilder()
    cards = sorted(SUPPORTED_CARDS | C56_ADDED_CARDS)
    assert len(cards) == 56
    rng = random.Random(20261003)
    rng.shuffle(cards)
    decks = [cards[i:i + 8] for i in range(0, len(cards), 8)]
    res = builder.loader, builder, None, p16.DiscreteTileActionSpace()
    results = {}
    for i, deck in enumerate(decks):
        ep = {"id": f"c56-{i:02d}", "seed": 20261003 + i,
              "decks": [deck, decks[(i + 3) % len(decks)]],
              "styles": [p16.STYLES[i % 3], p16.STYLES[(i + 1) % 3]]}
        with contextlib.redirect_stdout(io.StringIO()):
            battle = p16.new_battle(ep, builder.loader)
            bots = [PublicScriptedOpponent(builder, style=s, card_scope="c56") for s in ep["styles"]]
            trace = []
            play(battle, res, bots, 600, trace)
            root = battle.clone()
            play(battle, res, bots, 1800, trace)
            branches = {}
            view = builder.build_public(root, 0)
            picks = {2304}
            per_slot = {}
            for decision in bots[0].ranked_plays(view):
                per_slot.setdefault(decision.action_id // 576, decision.action_id)
            picks.update(per_slot.values())
            for action in sorted(picks):
                branch = root.clone()
                branch_trace = []
                play(branch, res, bots, root.tick + 200, branch_trace, forced=action)
                branches[str(action)] = branch_trace
            results[ep["id"]] = {"episode": ep, "trace": trace, "branches": branches}
        print(f"{ep['id']} ticks={battle.tick} branches={len(branches)}", file=sys.stderr, flush=True)
    return results


def play(battle, res, bots, until, trace, forced=None):
    _, builder, _, space = res
    while battle.tick < 90 and not battle.game_over:
        battle.step()
    while battle.tick < until and not battle.game_over:
        views = [builder.build_public(battle, seat) for seat in (0, 1)]
        actions = [int(bot.select_action(view)) for bot, view in zip(bots, views)]
        if forced is not None:
            actions[0], forced = forced, None
        trace.append([battle.tick, actions, [p16.packet_sha(v) for v in views], p16.state_digest(battle)])
        accepted = []
        for seat, action in enumerate(actions):
            mask = bots[seat].mask_builder.build(p16.PublicActionMaskInput.from_confidence_observation(views[seat]))
            assert mask[action], (seat, action, battle.tick)
            choice = space.decode_action(action, seat)
            if not choice.is_no_op:
                name = builder.card_name_for_token_id(int(views[seat].observation.hand_ids[choice.slot]))
                accepted.append(bool(battle.deploy_card(seat, name, choice.position)))
            else:
                accepted.append(True)
        trace[-1].append(accepted)
        for _ in range(5):
            if not battle.game_over:
                battle.step()
    trace.append([battle.tick, None, None, p16.state_digest(battle)])


def main():
    mode, filename = sys.argv[1:3]
    path = Path(filename)
    results = run_all()
    # Normalize tuples and numpy-independent JSON values before comparison.
    results = json.loads(json.dumps(results))
    boundaries = sum(len(r["trace"]) + sum(map(len, r["branches"].values())) for r in results.values())
    if mode == "record":
        if path.exists():
            raise FileExistsError(path)
        path.write_text(json.dumps(results, separators=(",", ":")))
        mismatches = []
    elif mode == "check":
        baseline = json.loads(path.read_text())
        mismatches = [key for key in sorted(results.keys() | baseline.keys()) if results.get(key) != baseline.get(key)]
    else:
        raise ValueError(mode)
    print(json.dumps({"mode": mode, "episodes": len(results), "digest_boundaries": boundaries,
                      "mismatches": mismatches, "baseline_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
