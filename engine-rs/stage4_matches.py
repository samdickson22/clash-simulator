"""Resumable bundle interaction games with read-only Python C56 controllers.

R uses a deterministic engine fixture schedule because these repairs are outside
the C56 actor vocabulary. Other bundles use Python C56 controllers.

These constructed decks test mechanic interactions, not the final human-deck
C56 admission. Native controller action qualification is a separate gate.
"""

import argparse
from collections import deque
import json
from pathlib import Path
import random
import time

import clasher_core
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.public_action_mask import PublicActionMaskInput
from diagnostics import detail, phase_step
from differential import BattleState, Position, battle_digest, config, snapshot
from stage2 import fingerprint
from stage2_matches import PILOT, STYLES

BUNDLES = {
    "C": ("ArcherQueen", "MightyMiner", "Goblinstein"),
    "S": ("FirespiritHut", "GoblinHut"),
    "R": (
        "Vines",
        "DarkMagic",
        "GoblinCurse",
        "Heal",
        "Elixir Collector",
        "GoblinDrill",
    ),
    "B1": (
        "BarbLog",
        "Arrows",
        "Tornado",
        "ElectroSpirit",
        "Lightning",
        "Poison",
        "Rocket",
        "Earthquake",
        "RoyalDelivery",
    ),
    "B2": (
        "BabyDragon",
        "Minions",
        "Bats",
        "MinionHorde",
        "Balloon",
        "Wizard",
        "Valkyrie",
        "Princess",
        "Firecracker",
        "BlowdartGoblin",
    ),
    "B3": (
        "AngryBarbarians",
        "Berserker",
        "MiniPekka",
        "SkeletonArmy",
        "GoblinGang",
        "Rascals",
        "Golem",
        "RoyalHogs",
        "Wallbreakers",
        "FireSpirits",
        "Ghost",
    ),
    "B4": ("InfernoTower", "Xbow", "BombTower", "Miner", "GoblinBarrel"),
}


def match(bundle, case, cfg, builder, ticks=6001, trace_tick=None):
    rng = random.Random(5604100 + case)
    focal = BUNDLES[bundle]
    decks = []
    for seat in (0, 1):
        start = (case * 3 + seat) % len(focal)
        deck = [focal[(start + k) % len(focal)] for k in range(min(3, len(focal)))]
        if bundle == "C":
            deck = [
                focal[(case + seat) % 3],
                BUNDLES["B1"][(case + seat) % 9],
                BUNDLES["B2"][(case + seat + 4) % 10],
                BUNDLES["B3"][(case * 2 + seat) % 11],
                BUNDLES["B4"][(case + seat) % 5],
                BUNDLES["S"][(case + seat) % 2],
                "Knight",
                "Zap",
            ]
        elif bundle == "S":
            deck += [
                BUNDLES["B1"][(case + seat) % 9],
                BUNDLES["B2"][(case + seat + 4) % 10],
                BUNDLES["B3"][(case * 2 + seat) % 11],
                BUNDLES["B4"][(case + seat) % 5],
                "Knight",
                "Musketeer",
            ]
        elif bundle == "R":
            deck += [
                BUNDLES["B1"][(case + seat) % 9],
                BUNDLES["B2"][(case + seat + 4) % 10],
                BUNDLES["B3"][(case * 2 + seat) % 11],
                BUNDLES["B4"][(case + seat) % 5],
                "Knight",
            ]
        elif bundle == "B1":
            deck += [
                "Knight",
                "Archers",
                "Giant",
                "Musketeer",
                ("Cannon", "Tesla")[(seat + case) % 2],
            ]
        else:
            deck += [
                BUNDLES["B1"][(case + seat) % 9],
                (
                    BUNDLES["B2"][(case + seat + 4) % 10]
                    if bundle in ("B3", "B4")
                    else BUNDLES["B1"][(case + seat + 4) % 9]
                ),
                "Knight",
                "Musketeer",
                (
                    BUNDLES["B3"][(case + seat) % 11]
                    if bundle == "B4"
                    else ("Cannon", "Tesla")[(seat + case) % 2]
                ),
            ]
        rng.shuffle(deck)
        decks.append(deck)
    b = BattleState(
        players=[
            PlayerState(seat, deck=deck, hand=deck[:4], cycle_queue=deque(deck[4:]))
            for seat, deck in enumerate(decks)
        ],
        rng=random.Random(5604200 + case),
    )
    r = clasher_core.BattleState(snapshot(b, cfg))
    styles = [STYLES[case % 3], STYLES[(case // 3 + 1) % 3]]
    if bundle == "R":
        styles = ["fixture_schedule"] * 2
        bots = [None, None]
    else:
        bots = [
            PublicScriptedOpponent(builder, style=s, card_scope="c56") for s in styles
        ]
    space = DiscreteTileActionSpace()
    actions = []
    abilities = []
    pcpu = rcpu = 0.0
    imports = 0
    clone_us = []

    def same(p, native):
        words, index = native.rng_state()
        return battle_digest(p) == native.digest() and p.rng.getstate()[1] == tuple(
            words
        ) + (index,)

    for t in range(trace_tick or ticks):
        if b.game_over:
            break
        if t >= 90 and t % 5 == 0:
            for seat, bot in enumerate(bots):
                if bundle == "R":
                    if t % 40:
                        continue
                    card = b.players[seat].hand[(t // 40 + seat + case) % 4]
                    if card is None:
                        continue
                    meta = cfg["cards"][card]
                    if meta.get("spell") is not None:
                        enemies = [
                            e
                            for e in b.entities.values()
                            if e.is_alive
                            and e.player_id != seat
                            and type(e).__name__ == "Troop"
                        ]
                        if not enemies:
                            enemies = [
                                e
                                for e in b.entities.values()
                                if e.is_alive
                                and e.player_id != seat
                                and type(e).__name__ == "Building"
                            ]
                        target = max(enemies, key=lambda e: (e.hitpoints, -e.id))
                        pos = Position(
                            min(17.5, max(0.5, int(target.position.x) + 0.5)),
                            min(31.5, max(0.5, int(target.position.y) + 0.5)),
                        )
                    else:
                        x = (4.5, 9.5, 13.5)[(t // 40 + seat + case) % 3]
                        y = (
                            (21.5 if seat == 0 else 10.5)
                            if meta.get("anywhere")
                            else (13.5 if seat == 0 else 18.5)
                        )
                        pos = Position(x, y)
                else:
                    packet = builder.build_public(b, seat)
                    action = bot.select_action(packet)
                    assert bot.mask_builder.build(
                        PublicActionMaskInput.from_confidence_observation(packet)
                    )[action]
                    decoded = space.decode_action(action, seat)
                    if decoded.is_no_op:
                        continue
                    card = builder.card_name_for_token_id(
                        int(packet.observation.hand_ids[decoded.slot])
                    )
                    pos = decoded.position
                pa = b.deploy_card(seat, card, pos)
                ra = r.apply_action(seat, card, pos.x, pos.y)
                actions.append([t, seat, card, pos.x, pos.y, pa, ra])
                if pa != ra or not same(b, r):
                    return dict(
                        ok=False, kind="action", tick=t, actions=actions, **detail(b, r)
                    )
        if bundle == "C" and t >= 100 and t % 20 == 0:
            for seat in (0, 1):
                ready = b.can_activate_champion_ability(seat)
                if ready != r.can_activate_champion_ability(seat):
                    return dict(
                        ok=False,
                        kind="ability_ready",
                        tick=t,
                        actions=actions,
                        abilities=abilities,
                        **detail(b, r),
                    )
                if ready:
                    pa = b.activate_champion_ability(seat)
                    ra = r.activate_champion_ability(seat)
                    abilities.append(
                        [
                            t,
                            seat,
                            next(c for c in decks[seat] if c in BUNDLES["C"]),
                            pa,
                            ra,
                        ]
                    )
                    if pa != ra or not same(b, r):
                        return dict(
                            ok=False,
                            kind="ability_action",
                            tick=t,
                            actions=actions,
                            abilities=abilities,
                            **detail(b, r),
                        )
        if trace_tick and t == trace_tick - 1:
            return phase_step(b, r)
        start = time.process_time()
        b.step()
        pcpu += time.process_time() - start
        start = time.process_time()
        r.step()
        rcpu += time.process_time() - start
        if not same(b, r):
            return dict(
                ok=False, kind="tick", tick=b.tick, actions=actions, **detail(b, r)
            )
        if b.tick % 400 == 0 and not b.game_over:
            copy = b.clone()
            imported = clasher_core.BattleState(snapshot(b, cfg))
            start = time.process_time()
            for _ in range(100):
                child = imported.clone()
            clone_us.append((time.process_time() - start) * 1e4)
            before = imported.digest()
            for _ in range(80):
                copy.step()
                child.step()
                if not same(copy, child):
                    return dict(
                        ok=False,
                        kind="import",
                        root_tick=b.tick,
                        tick=copy.tick,
                        actions=actions,
                        **detail(copy, child),
                    )
            assert imported.digest() == before and same(b, r)
            imports += 1
    return dict(
        ok=True,
        ticks=b.tick,
        terminal=b.game_over,
        decks=decks,
        styles=styles,
        actions=len(actions),
        accepted=sum(a[-1] for a in actions),
        accepted_abilities={
            c: sum(a[-1] for a in abilities if a[2] == c) for c in BUNDLES["C"]
        },
        accepted_by_card={
            name: sum(a[-1] for a in actions if a[2] == name)
            for name in sorted({a[2] for a in actions})
        },
        imports=imports,
        python_cpu=pcpu,
        rust_cpu=rcpu,
        clone_us=clone_us,
        digest=battle_digest(b),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", choices=BUNDLES, required=True)
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--case", type=int)
    parser.add_argument("--ticks", type=int, default=6001)
    parser.add_argument("--trace-tick", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = fingerprint()
    out = dict(
        fingerprint=identity,
        bundle=args.bundle,
        games=args.games,
        ticks=args.ticks,
        results={},
    )
    if args.output.exists():
        old = json.loads(args.output.read_text())
        if all(
            old.get(k) == out[k] for k in ("fingerprint", "bundle", "games", "ticks")
        ):
            out = old
    earlier = (
        (BUNDLES["B2"] + (BUNDLES["B3"] if args.bundle == "B4" else ()))
        if args.bundle in ("B3", "B4")
        else ()
    )
    if args.bundle in ("R", "S", "C"):
        earlier = (
            BUNDLES["B2"]
            + BUNDLES["B3"]
            + BUNDLES["B4"]
            + (BUNDLES["S"] if args.bundle == "C" else ())
        )
    cfg = config(
        tuple(dict.fromkeys((*PILOT, *BUNDLES["B1"], *earlier, *BUNDLES[args.bundle])))
    )
    builder = ContractV5ObservationBuilder()
    for case in [args.case] if args.case is not None else range(args.games):
        key = str(case)
        if out["results"].get(key, {}).get("ok") and not args.trace_tick:
            continue
        result = match(args.bundle, case, cfg, builder, args.ticks, args.trace_tick)
        assert fingerprint() == identity, "source drift during bundle gate"
        out["results"][key] = result
        tmp = args.output.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=2) + "\n")
        tmp.replace(args.output)
        print(
            case,
            {k: v["field_diff"] for k, v in result.items()}
            if args.trace_tick
            else {
                k: v
                for k, v in result.items()
                if k not in ("python", "rust", "field_diff", "actions")
            },
            flush=True,
        )
        if not result.get("ok"):
            raise SystemExit(1)
    print("PASS", len(out["results"]), "bundle interaction games", flush=True)


if __name__ == "__main__":
    main()
