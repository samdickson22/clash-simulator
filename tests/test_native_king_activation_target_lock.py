"""Native King first-target lock during the activation first-hit phase (15.535.86).

Fixture: opened development evidence from tier-a-fresh-v3 episode-05 (native
job-00161, scalar job-00160), built by
reports/strategy_council_20260928/m0/native-mechanics-20260928/build_king_target_lock_fixture.py.
Native facts pinned here:
  * the King acquires and locks its first target inside the 700 ms first-hit
    phase (target set by tick 2360, phase ends 2369);
  * a unit that becomes nearer before the shot (order flips at 2363) does not
    steal the lock, and the first shot at 2369 goes to the locked unit.
"""

import gzip
import hashlib
import json
import random
from collections import deque
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Projectile
from clasher.player import PlayerState

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[1]
REFERENCE = json.loads(
    (FIXTURES / "native_king_activation_target_lock_15_535_86.json").read_text()
)
FRAMES = {int(tick): frame for tick, frame in REFERENCE["frames"].items()}
LOCKED = str(REFERENCE["locked_goblin"])
NEARER = str(REFERENCE["nearer_goblin"])
ACTIVATION_END = REFERENCE["activation_delay_end_tick"]
FIRST_SHOT = REFERENCE["first_shot_tick"]
KING_XY = tuple(v / 1000 for v in REFERENCE["king_xy"])


@pytest.fixture(scope="module")
def loader(tmp_path_factory):
    path = tmp_path_factory.mktemp("gamedata") / "gamedata.json"
    path.write_bytes(
        gzip.decompress((FIXTURES / "native_gamedata_15_535_86_daa58b28.json.gz").read_bytes())
    )
    return CardDataLoader(path)


def _king(battle):
    return next(
        e for e in battle.entities.values()
        if e.player_id == REFERENCE["king_owner"] and e.card_stats.name == "KingTower"
    )


def _native_xy(goblin, tick):
    """Native Goblin position, linear between the recorded 5-tick frames."""
    low = tick - (tick - 2350) % 5
    a = FRAMES[low]["goblins"][goblin]["xy"]
    if tick == low:
        return a[0] / 1000, a[1] / 1000
    b = FRAMES[low + 5]["goblins"][goblin]["xy"]
    w = (tick - low) / 5
    return (a[0] + (b[0] - a[0]) * w) / 1000, (a[1] + (b[1] - a[1]) * w) / 1000


def _distance(xy):
    return ((xy[0] - KING_XY[0]) ** 2 + (xy[1] - KING_XY[1]) ** 2) ** 0.5


def test_fixture_nearest_order_swaps_during_first_hit_phase():
    assert FRAMES[2360]["king"]["target"] == int(LOCKED)
    assert FRAMES[2365]["king"]["target"] == int(LOCKED)
    assert [p["target"] for p in FRAMES[2370]["king_projectiles"]] == [int(LOCKED)]
    assert _distance(_native_xy(LOCKED, 2360)) < _distance(_native_xy(NEARER, 2360))
    assert _distance(_native_xy(NEARER, 2365)) < _distance(_native_xy(LOCKED, 2365))
    assert _distance(_native_xy(NEARER, FIRST_SHOT)) < _distance(_native_xy(LOCKED, FIRST_SHOT))


@pytest.mark.parametrize("fast_path", [False, True])
def test_king_first_shot_hits_unit_locked_during_first_hit_phase(fast_path, loader):
    battle = BattleState(fast_path=fast_path, card_loader=loader)
    king = _king(battle)
    goblins = {}
    for name in (LOCKED, NEARER):
        battle._spawn_unit_at_position(
            Position(*_native_xy(name, ACTIVATION_END)), 0,
            battle.card_loader.get_card("Goblins"),
            deploy_delay_override=0, snap_to_valid=False,
        )
        goblins[name] = battle.entities[max(battle.entities)]
        goblins[name].hitpoints = FRAMES[ACTIVATION_END]["goblins"][name]["hp"]
    by_id = {g.id: name for name, g in goblins.items()}
    king.activate()
    # The 3.3 s activation delay ends on tick 2355, as in both engines.
    king.activation_delay_remaining = battle.dt
    targets, shots = {}, []
    for tick in range(ACTIVATION_END, FIRST_SHOT + 2):
        for name, goblin in goblins.items():
            goblin.position = Position(*_native_xy(name, tick))
        if fast_path:
            battle._refresh_fast_path_caches()
        before = set(battle.entities)
        king.update_combat_component(battle.dt, battle)
        targets[tick] = by_id.get(king.target_id)
        for identity in set(battle.entities) - before:
            entity = battle.entities[identity]
            if isinstance(entity, Projectile):
                shots.append((tick, by_id.get(getattr(entity.primary_target, "id", None))))
    # Timing is unchanged: the first shot still launches when the phase ends.
    assert shots[0] == (FIRST_SHOT, LOCKED)
    # The lock is taken inside the phase and survives the nearest-order flip.
    assert targets[2360] == LOCKED
    assert targets[2365] == LOCKED


def test_torch_combat_locks_king_target_during_first_hit_phase(loader):
    torch = pytest.importorskip("torch")
    from clasher.kinematics import tiles_to_logic_units
    from clasher.torch_sim.catalog import TensorCardCatalog
    from clasher.torch_sim.combat import step_stationary_combat_
    from clasher.torch_sim.combat_adapter import project_stationary_combat

    battle = BattleState(card_loader=loader)
    king = _king(battle)
    goblins = {}
    for name in (LOCKED, NEARER):
        battle._spawn_unit_at_position(
            Position(*_native_xy(name, ACTIVATION_END)), 0,
            battle.card_loader.get_card("Goblins"),
            deploy_delay_override=0, snap_to_valid=False,
        )
        goblins[name] = battle.entities[max(battle.entities)]
    king.activate()
    king.activation_delay_remaining = battle.dt
    state = project_stationary_combat(
        [battle], TensorCardCatalog.compile(loader, ["Goblins"])
    ).state
    slots = {entity.id: slot for slot, entity in enumerate(battle.entities.values())}
    king_slot = slots[king.id]
    names = {slots[g.id]: name for name, g in goblins.items()}
    # The runtime adapter keeps an in-progress activation fail-closed; drive
    # the kernel directly with only the King's combat component enabled.
    state.ordinary_combat_supported[:] = True
    state.combat_enabled[:] = False
    state.combat_enabled[0, king_slot] = True
    targets, shots = {}, []
    for tick in range(ACTIVATION_END, FIRST_SHOT + 2):
        for name, goblin in goblins.items():
            x, y = _native_xy(name, tick)
            state.x_units[0, slots[goblin.id]] = tiles_to_logic_units(x)
            state.y_units[0, slots[goblin.id]] = tiles_to_logic_units(y)
        result = step_stationary_combat_(state, battle.dt)
        targets[tick] = names.get(int(state.target_slot[0, king_slot]))
        if bool(result.projectile_launched[0, king_slot]):
            shots.append((tick, targets[tick]))
    assert shots[0] == (FIRST_SHOT, LOCKED)
    assert targets[2360] == LOCKED
    assert targets[2365] == LOCKED


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_episode_05_scalar_replay_king_first_target_and_hp_match_native():
    setup = REFERENCE["episode_05_replay"]
    capture = REPO / setup["capture"]
    actions = REPO / setup["actions"]
    if not capture.is_dir() or not actions.is_file():
        pytest.skip("tier-a-fresh-v3 episode-05 capture is not present")
    for name, digest in setup["capture_sha256"].items():
        assert _sha(capture / name) == digest, name
    assert _sha(actions) == REFERENCE["sources"][setup["actions"]]

    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS

    loader = CardDataLoader(capture / "gamedata.json")
    initial = json.loads((capture / "initial.json").read_text())
    config = json.loads((capture / "plan.json").read_text())["config"]
    prefix = json.loads((capture / "result.json").read_text())["commands"]
    names = {loader.get_card(n)._raw_entry["id"]: n for n in PUBLIC_REFERENCE_CARDS}
    players = []
    for owner in (0, 1):
        state = next(p for p in initial["players"] if p["owner"] == owner)
        players.append(PlayerState(
            owner,
            deck=[names[c["cardId"]] for c in state["deck"]],
            hand=[names[c["cardId"]] for c in sorted(state["hand"], key=lambda c: c["handIndex"])],
            cycle_queue=deque(
                names[c["cardId"]] for c in sorted(state["cycle"], key=lambda c: c["cycleIndex"])
            ),
            elixir=state["elixir"],
        ))
    battle = BattleState(
        players=players, rng=random.Random(config["rndSeed"]), card_loader=loader
    )
    king = _king(battle)
    seen = set(battle.entities)
    observed = {"shots": [], "target_2360": None, "goblins_2360": {}}

    def advance(tick):
        while battle.tick < tick and not battle.game_over:
            battle.step()
            for identity, entity in battle.entities.items():
                if identity in seen:
                    continue
                seen.add(identity)
                if isinstance(entity, Projectile) and entity.source_entity is king:
                    observed["shots"].append((battle.tick, entity.primary_target))
            if battle.tick == 2360:
                observed["target_2360"] = king.target_id
                observed["goblins_2360"] = {
                    e.id: (e.position.x, e.position.y) for e in battle.entities.values()
                    if e.player_id == 0 and e.is_alive and e.card_stats.name == "Goblins"
                }

    for command in (c for c in prefix if c["submitted_tick"] < setup["root_tick"]):
        advance(command["submitted_tick"])
        assert battle.deploy_card(command["owner"], command["name"], Position(*command["xy"]))
    advance(setup["root_tick"])
    # The recorded scalar actions equal native job-00161's through tick 2555.
    space = DiscreteTileActionSpace()
    for line in gzip.open(actions, "rt"):
        record = json.loads(line)
        if record["tick"] > 2375:
            break
        advance(record["tick"])
        for owner, action in enumerate(record["actions"]):
            choice = space.decode_action(action, owner)
            if choice.is_no_op:
                continue
            card = battle.players[owner].hand[choice.slot]
            assert battle.deploy_card(owner, card, Position(choice.position.x, choice.position.y))
        advance(record["tick"] + 1)
    advance(2375)

    native_locked = tuple(v / 1000 for v in FRAMES[2360]["goblins"][LOCKED]["xy"])
    locked = next(
        identity for identity, (x, y) in observed["goblins_2360"].items()
        if abs(x - native_locked[0]) < 0.05 and abs(y - native_locked[1]) < 0.05
    )
    first_tick, first_target = observed["shots"][0]
    assert (first_tick, first_target.id) == (FIRST_SHOT, locked)
    assert king.hitpoints == setup["native_king_hp_2375"] == 4199
    assert observed["target_2360"] == locked
