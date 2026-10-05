"""Instrumented re-simulation of C56 perspectives on the tower-gap runtime COPY.

Runs the unmodified ``reconstruct_perspective_v5`` with monkeypatches applied
only inside this process:
  * sim-kill contradictions are recorded (same rule as the extractor) but do not
    stop the replay ("nocut"), so post-cut tower damage can be compared with the
    real final tower HP; every other hard cut still stops the replay;
  * every damage event on a crown tower is attributed to the source unit/spell
    (stack walk to the damaging object);
  * variants change card levels / tower levels.

Variants (``--variant``):
  base        nominal L11 cards and towers (extraction setting)
  rel         real per-card and tower levels shifted by -5 (L16 -> L11), i.e. level differences preserved
  tower_real  nominal L11 cards, towers at the real tower level
  evo2        nominal L11, evo/hero-slot cards +2 levels (crude stand-in for evo/hero power)
  rel_evo2    rel plus evo/hero-slot cards +2 levels
  spell_ctd   nominal; spells deal 0 damage to crown towers (bound on the spell contribution)
  clamp       nominal; a crown tower whose death would contradict the recording is held at 1 HP and the
              overshoot (excess damage) is booked per tower -> retention for any excess threshold

Output: one JSON line per perspective in --out (resumable: skips done keys).
Run with CLASHER_ROOT=<tower-gap>/runtime PYTHONPATH=<tower-gap>/runtime/src.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TG = HERE.parent
RT = TG / "runtime"
COUNCIL = TG.parent
PAYLOADS = COUNCIL / "c56/data/payloads"
SCAN = COUNCIL / "m0/human-prior-scan"
assert os.environ.get("CLASHER_ROOT") == str(RT), "set CLASHER_ROOT to the tower-gap runtime copy"
sys.path.insert(0, str(RT / "src"))
sys.path.insert(0, str(SCAN))

import clasher  # noqa: E402
assert Path(clasher.__file__).resolve().parents[2] == RT.resolve(), clasher.__file__
from clasher import entities as E  # noqa: E402
from clasher.battle import BattleState  # noqa: E402
from clasher.player import PlayerState  # noqa: E402
from clasher.rl import human_replay_demonstrations as hrd  # noqa: E402
from clasher.rl import human_replay_v5 as v5r  # noqa: E402
from clasher.rl.contract_v5 import CachedContractV5ActionMask, ContractV5ObservationBuilder  # noqa: E402
from card_map import SLUG_TO_GAMEDATA  # noqa: E402

CTX: dict = {}
_ORIG_PDA = hrd.RecordedMatch.princess_down_allowed
_ORIG_KDA = hrd.RecordedMatch.king_down_allowed
_ORIG_TOWERS = v5r._towers
_ORIG_APPLY = v5r.apply_ordered_deck_to_player
_ORIG_TAKE = E.Entity.take_damage


def _identify(tower):
    frame = sys._getframe(2)
    depth = 0
    while frame is not None and depth < 12:
        obj = frame.f_locals.get("self")
        if obj is not None and obj is not tower and not isinstance(obj, BattleState):
            name = getattr(obj, "spell_name", None) or getattr(obj, "source_name", None)
            if not name or name == "Unknown":
                stats = getattr(obj, "card_stats", None)
                name = getattr(stats, "name", None) if stats is not None else None
            if not name:
                name = getattr(obj, "name", None)
            kind = type(obj).__name__
            return str(name or kind), kind, getattr(obj, "player_id", None)
        frame = frame.f_back
        depth += 1
    return "?", "?", None


def _take_damage(self, amount, *, source_kind=None, affects_hidden=False):
    slot = getattr(self, "_crown_tower_slot", None)
    if slot is None or CTX.get("battle") is None:
        return _ORIG_TAKE(self, amount, source_kind=source_kind, affects_hidden=affects_hidden)
    name, kind, owner = _identify(self)
    if name == "?" and source_kind:
        name = str(source_kind)
    if CTX.get("no_spell_tower") and name in CTX["spell_names"]:
        return None
    before = float(self.hitpoints)
    if CTX.get("clamp") and self.is_alive and before - float(amount) <= 0 and _would_contradict(self.player_id, slot):
        # keep a tower the recording proves standing alive at 1 HP; book the overshoot
        excess = float(amount) - (before - 1.0)
        key = f"{self.player_id}:{slot}"
        CTX["excess"][key] = CTX["excess"].get(key, 0.0) + excess
        CTX["excess_events"].append((CTX["battle"].tick, self.player_id, slot, round(CTX["excess"][key], 1),
                                     round(float(CTX["max_hp"].get(key, 1.0)), 1)))
        amount = before - 1.0
        if amount <= 0:
            CTX["damage"].append((CTX["battle"].tick, self.player_id, slot, 0.0, name, kind, owner, source_kind))
            return None
    _ORIG_TAKE(self, amount, source_kind=source_kind, affects_hidden=affects_hidden)
    dealt = before - float(self.hitpoints)
    if dealt > 0:
        CTX["damage"].append((CTX["battle"].tick, self.player_id, slot, round(dealt, 1), name, kind, owner,
                              source_kind))
    return None


def _would_contradict(pid, slot):
    battle = CTX["battle"]
    match = CTX["match"]
    tick = battle.tick
    if slot == "king":
        return not _ORIG_KDA(match, pid, tick)
    state = _ORIG_TOWERS(battle)
    state[(pid, slot)] = False
    other = "right" if slot == "left" else "left"
    sim_down = sum(not state[(pid, lane)] for lane in hrd.LANES)
    if CTX.get("down_lanes") is None:
        CTX["down_lanes"] = hrd.proven_down_lanes(match, battle)
    return (sim_down > _ORIG_PDA(match, pid, tick)
            or (match.princess_down[pid] == 1 and CTX["down_lanes"][pid] == frozenset({other})))


def _battle_factory(**kwargs):
    levels = CTX["tower_levels"]
    battle = BattleState(players=[PlayerState(0, tower_level=levels[0]), PlayerState(1, tower_level=levels[1])],
                         **kwargs)
    CTX["battle"] = battle
    CTX["max_hp"] = {f"{pid}:{slot}": float(battle._starting_tower_hps[pid][slot]) for pid in (0, 1)
                     for slot in ("left", "right", "king")}
    return battle


def _apply(player, deck, *, card_levels=None):
    _ORIG_APPLY(player, deck, card_levels=card_levels)
    wanted = CTX["card_levels"][player.player_id]
    if wanted:
        player.set_card_levels(wanted)


def _towers(battle):
    after = _ORIG_TOWERS(battle)
    before = CTX.get("tower_state")
    CTX["tower_state"] = after
    tick = battle.tick
    if tick % 20 == 0:
        hp = []
        for pid in (0, 1):
            p = battle.players[pid]
            hp.append([round(float(p.left_tower_hp)), round(float(p.right_tower_hp)), round(float(p.king_tower_hp))])
        CTX["hp"].append((tick, hp))
    for entity in battle.entities.values():
        if getattr(entity, "_crown_tower_slot", None) == "king" and getattr(entity, "_tower_active", True):
            CTX["king_active"].setdefault(entity.player_id, tick)
    if before is None:
        return after
    match = CTX["match"]
    for (pid, slot), alive in after.items():
        if alive or not before[(pid, slot)]:
            continue
        CTX["sim_kills"].append((tick, pid, slot))
        if slot == "king":
            contradicted = not _ORIG_KDA(match, pid, tick)
        else:
            if CTX.get("down_lanes") is None:
                CTX["down_lanes"] = hrd.proven_down_lanes(match, battle)
            other = "right" if slot == "left" else "left"
            sim_down = sum(not after[(pid, lane)] for lane in hrd.LANES)
            contradicted = (sim_down > _ORIG_PDA(match, pid, tick)
                            or (match.princess_down[pid] == 1 and CTX["down_lanes"][pid] == frozenset({other})))
        if contradicted and CTX.get("contradiction") is None:
            CTX["contradiction"] = (tick, pid, slot)
    return after


def install():
    E.Entity.take_damage = _take_damage
    v5r.BattleState = _battle_factory
    v5r.apply_ordered_deck_to_player = _apply
    v5r._towers = _towers
    hrd.RecordedMatch.princess_down_allowed = lambda self, player, tick: 2
    hrd.RecordedMatch.king_down_allowed = lambda self, player, tick: True


LEVEL_OK: dict = {}


def _level_ok(name, level):
    """Spells whose crown-tower override is only reconciled at L11 stay at L11 (recorded as pinned)."""
    key = (name, level)
    if key not in LEVEL_OK:
        from clasher.battle import SPELL_REGISTRY
        from clasher.dynamic_spells import create_spell_from_json
        spell = SPELL_REGISTRY.get(name)
        ok = True
        if spell is not None and level != 11:
            try:
                stats = CTX["battle_loader"].get_card(name)
                create_spell_from_json(stats._raw_entry, level=level)
            except Exception:  # noqa: BLE001
                ok = False
        LEVEL_OK[key] = ok
    return LEVEL_OK[key]


def levels_for(match, variant):
    """Return per-player {card: level} and (tower level, tower level).

    rel: level differences preserved relative to the match's top level M (card' = 11 + real - M, tower' = 11 + tower - M).
    Uniform L16 equals uniform L11 up to rounding (cards x1.598, towers x1.592), so only relative
    levels can matter; absolute L16 is not supported for Earthquake/Poison crown damage.
    """
    deck_levels = match.info["deck_levels"]
    slugs = match.info["deck_slugs"]
    towers = CTX["tower_card_levels"]
    evo_slot = [{name: ("-ev" in s or "-hero" in s) for name, s in zip(match.decks[pid], slugs[pid])} for pid in (0, 1)]
    tower_real = [max(1, min(16, towers[pid] or 16)) for pid in (0, 1)]
    top = max(max(tower_real), max(max(deck_levels[0]), max(deck_levels[1])))
    rel_cards = [{n: 11 + lv - top for n, lv in zip(match.decks[pid], deck_levels[pid])} for pid in (0, 1)]
    rel_tower = tuple(11 + t - top for t in tower_real)
    nominal = [{n: 11 for n in match.decks[pid]} for pid in (0, 1)]
    if variant in ("base", "spell_ctd", "clamp"):
        cards, tw = nominal, (11, 11)
    elif variant == "rel":
        cards, tw = rel_cards, rel_tower
    elif variant == "tower_real":
        cards, tw = nominal, tuple(tower_real)
    elif variant == "evo2":
        cards, tw = [{n: 11 + 2 * evo_slot[pid][n] for n in match.decks[pid]} for pid in (0, 1)], (11, 11)
    elif variant == "rel_evo2":
        cards, tw = [{n: rel_cards[pid][n] + 2 * evo_slot[pid][n] for n in match.decks[pid]} for pid in (0, 1)], rel_tower
    else:
        raise ValueError(variant)
    pinned = []
    out = []
    for pid in (0, 1):
        d = {}
        for n, lv in cards[pid].items():
            lv = max(1, min(20, lv))
            if not _level_ok(n, lv):
                pinned.append((pid, n, lv))
                lv = 11
            d[n] = lv
        out.append(d)
    CTX["pinned"] = pinned
    return out, tw


def run_one(record, side, variant, builder, mask_builder):
    match = hrd.parse_il_replay_record(record, SLUG_TO_GAMEDATA)
    seat = ("team", "opponent").index(side)
    b = record["payload"]["battle"]
    CTX.clear()
    CTX["tower_card_levels"] = [((b[s]["players"][0].get("tower_card") or {}).get("level")) for s in ("team", "opponent")]
    CTX["battle_loader"] = LOADER
    card_levels, tower_levels = levels_for(match, variant)
    CTX.update(match=match, card_levels=card_levels, tower_levels=tower_levels, damage=[], hp=[], sim_kills=[],
               king_active={}, contradiction=None, down_lanes=None, tower_state=None, rows=[],
               no_spell_tower=variant == "spell_ctd", spell_names=SPELL_NAMES,
               clamp=variant == "clamp", excess={}, excess_events=[])

    def observer(battle, learner, label):
        CTX["rows"].append(battle.tick)

    started = time.time()
    demo = v5r.reconstruct_perspective_v5(match, seat, builder, mask_builder=mask_builder, row_observer=observer)
    s = demo.summary
    valid = demo.controls["expert_action_supervision_valid"]
    ticks = demo.execution["submitted_ticks"]
    contradiction = CTX["contradiction"]
    cut_tick = contradiction[0] if contradiction else None
    # retention if the sim-kill contradiction had cut (rows strictly before the contradiction tick)
    sup_cut = int(valid[ticks < cut_tick].sum()) if cut_tick is not None else int(valid.sum())
    return {
        "match_id": match.match_id, "side": side, "seat": seat, "variant": variant,
        "card_levels": [sorted(set(d.values())) for d in card_levels], "tower_levels": list(tower_levels),
        "pinned": CTX.get("pinned", []),
        "other_cut": s["cut_reason"], "other_cut_tick": s["cut_tick"], "rows": int(len(valid)),
        "supervised_nocut": int(valid.sum()), "supervised_cut": sup_cut,
        "possible": int(-(-match.playable_end_tick // 5)), "playable_end_tick": int(match.playable_end_tick),
        "contradiction": contradiction, "sim_kills": CTX["sim_kills"], "king_active": CTX["king_active"],
        "damage": CTX["damage"], "excess_events": CTX["excess_events"], "row_ticks_valid": ticks[valid].tolist() if variant == "clamp" else None, "hp": CTX["hp"][::5], "hp_end": CTX["hp"][-1] if CTX["hp"] else None,
        "seconds": round(time.time() - started, 2),
    }


SPELL_NAMES: set = set()
LOADER = None


def _uniform_levels(record):
    b = record["payload"]["battle"]
    levels = set()
    for side in ("team", "opponent"):
        pl = b[side]["players"][0]
        levels.update(int(c["level"]) for c in pl["deck"])
        levels.add(int((pl.get("tower_card") or {}).get("level") or 16))
    return len(levels) == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True, help="jsonl of {tag, shard, index, side}")
    parser.add_argument("--variants", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    install()
    builder = ContractV5ObservationBuilder()
    global SPELL_NAMES
    global LOADER
    loader = LOADER = BattleState().card_loader
    SPELL_NAMES = {name for name, d in loader.load_card_definitions().items() if getattr(d, "kind", None) == "spell"}
    sample = [json.loads(line) for line in Path(args.sample).read_text().splitlines() if line.strip()]
    sample = sample[args.worker::args.workers]
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["match_id"], r["side"], r["variant"]))
    by_shard: dict[int, list] = {}
    for item in sample:
        by_shard.setdefault(item["shard"], []).append(item)
    with out.open("a") as sink:
        for shard, items in sorted(by_shard.items()):
            wanted = {item["index"]: item for item in items}
            with gzip.open(PAYLOADS / f"shard-{shard:03d}.jsonl.gz", "rt") as stream:
                for index, line in enumerate(stream):
                    if index not in wanted:
                        continue
                    record = json.loads(line)
                    item = wanted[index]
                    base_result = None
                    for variant in args.variants:
                        if (record["tag"], item["side"], variant) in done:
                            continue
                        if variant == "rel" and _uniform_levels(record) and "base" in args.variants:
                            # rel == base exactly when every card and both towers share one level
                            sink.write(json.dumps({"match_id": record["tag"], "side": item["side"], "variant": "rel",
                                                   "same_as_base": True}) + "\n")
                            sink.flush()
                            continue
                        mask_builder = CachedContractV5ActionMask(builder)
                        try:
                            result = run_one(record, item["side"], variant, builder, mask_builder)
                        except Exception as error:  # noqa: BLE001
                            result = {"match_id": record["tag"], "side": item["side"], "variant": variant,
                                      "error": repr(error)[:500]}
                        sink.write(json.dumps(result) + "\n")
                        sink.flush()


if __name__ == "__main__":
    main()
