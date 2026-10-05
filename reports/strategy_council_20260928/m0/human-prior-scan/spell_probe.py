"""Targeted probes for spells/special cards whose smoke effect was masked."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from card_map import SLUG_TO_GAMEDATA
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop, Building
from clasher.rl.deck_pool import apply_ordered_deck_to_player

def fresh(card):
    b = BattleState()
    deck = [card] + [c for c in ["Knight","Archers","Giant","Minions","Musketeer","Zap","Cannon","Skeletons"] if c != card]
    apply_ordered_deck_to_player(b.players[0], deck[:8])
    b.players[0].elixir = 10.0
    return b

def tower_hp(b, pid):
    return sum(max(0, e.hitpoints) for e in b.entities.values() if e.player_id == pid and isinstance(e, Building) and getattr(e.card_stats,'name','') in ('Tower','KingTower'))

def enemy_units(b):
    return [e for e in b.entities.values() if e.player_id == 1 and isinstance(e, Troop) and e.is_alive]

out = {}
# 1. Spell on enemy left princess tower: tower damage within 10 s.
spells = [s for s, n in SLUG_TO_GAMEDATA.items() if n in ("Arrows","Zap","Fireball","Rocket","Lightning","Poison","Earthquake","Freeze","Tornado","Vines","DarkMagic","GoblinCurse","GiantSnowball","Rage","Heal","Clone","MergeMaiden","Graveyard","GoblinBarrel")]
for slug in sorted(spells):
    card = SLUG_TO_GAMEDATA[slug]
    b = fresh(card)
    for _ in range(20): b.step()
    t0 = tower_hp(b, 1)
    ok = b.deploy_card(0, card, Position(3.5, 25.5))
    for _ in range(200): b.step()
    out[f"tower_spell:{slug}"] = {"accepted": ok, "enemy_tower_hp_removed_10s": round(t0 - tower_hp(b, 1), 1)}
# 2. Spell on a stationary enemy Knight group (Vines/Void/Curse/Freeze single-target checks).
for slug in ["vines","void","goblin-curse","freeze","tornado","zap","poison","spirit-empress"]:
    card = SLUG_TO_GAMEDATA[slug]
    b = fresh(card)
    apply_ordered_deck_to_player(b.players[1], ["Knight","Archers","Giant","Minions","Musketeer","Zap","Cannon","Skeletons"])
    b.players[1].elixir = 10
    b.deploy_card(1, "Knight", Position(9.5, 20.5))
    for _ in range(30): b.step()
    ks = enemy_units(b); hp0 = sum(e.hitpoints for e in ks); pos = ks[0].position
    ok = b.deploy_card(0, card, Position(pos.x, pos.y))
    for _ in range(60): b.step()
    ks2 = [e for e in b.entities.values() if e.player_id == 1 and isinstance(e, Troop)]
    out[f"unit_spell:{slug}"] = {"accepted": ok, "knight_hp_removed_3s": round(hp0 - sum(max(0,e.hitpoints) for e in ks2), 1),
                                 "own_new": sorted({getattr(e.card_stats,'name','?') for e in b.entities.values() if e.player_id==0 and isinstance(e,(Troop,Building)) and getattr(e.card_stats,'name','') not in ('Tower','KingTower')})}
# 3. Own-buff spells on own Knight: Clone/Rage/Heal.
for slug in ["clone","rage","heal-spirit"]:
    card = SLUG_TO_GAMEDATA[slug]
    b = fresh(card)
    b.deploy_card(0, "Knight", Position(9.5, 10.5))
    for _ in range(30): b.step()
    k = [e for e in b.entities.values() if e.player_id==0 and isinstance(e,Troop)][0]
    k.hitpoints = k.hitpoints * 0.5; hp_half = k.hitpoints
    b.players[0].elixir = 10
    ok = b.deploy_card(0, card, Position(k.position.x, k.position.y))
    sp0 = k.position.y
    for _ in range(40): b.step()
    troops = [e for e in b.entities.values() if e.player_id==0 and isinstance(e,Troop)]
    out[f"own_spell:{slug}"] = {"accepted": ok, "own_troops_after": len(troops), "knight_hp_gain": round(k.hitpoints - hp_half,1), "knight_dy_2s": round(k.position.y - sp0, 2)}
# 4. Elixir Collector generation; Goblin Drill spawn on enemy side.
for card, pos in [("Elixir Collector", Position(9.0, 5.0)), (None, None)]:
    b = fresh(card or "Knight")
    if card: b.deploy_card(0, card, pos)
    b.players[0].elixir = 0.0
    for _ in range(600): b.step()
    out[f"elixir_after_30s:{card}"] = round(b.players[0].elixir, 2)
b = fresh("GoblinDrill")
ok = b.deploy_card(0, "GoblinDrill", Position(5.5, 22.5))
for _ in range(200): b.step()
out["goblin_drill_enemy_side"] = {"accepted": ok, "own_entities": sorted({f"{type(e).__name__}:{getattr(e.card_stats,'name','?')}" for e in b.entities.values() if e.player_id==0 and getattr(e.card_stats,'name','') not in ('Tower','KingTower')}), "enemy_tower_hp_removed": round(2*3052+4824 - tower_hp(b,1),1)}
# 5. Spirit Empress alternative entries.
for card in ["MergeMaiden_Normal", "MergeMaiden_Mounted"]:
    b = fresh(card)
    try:
        ok = b.deploy_card(0, card, Position(9.5, 12.5))
        for _ in range(300): b.step()
        out[f"spirit_empress_alt:{card}"] = {"accepted": ok, "own": sorted({getattr(e.card_stats,'name','?') for e in b.entities.values() if e.player_id==0 and isinstance(e,Troop)}), "enemy_tower_hp_removed": round(2*3052+4824 - tower_hp(b,1),1)}
    except Exception as exc:
        out[f"spirit_empress_alt:{card}"] = f"{type(exc).__name__}: {exc}"
(HERE / "spell_probe.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out, indent=1))
