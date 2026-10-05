"""Compare engine level-11 character stats with the native decoded-logic catalog for C56 cards.

Usage: .venv/bin/python reports/strategy_council_20260928/c56/engine/audit/tools/stat_diff.py [OUT.json]
Read-only. Native values are level-1 base values; HP/damage are scaled with the
engine's scale_stat(.., 11). Prints rows that differ.
"""
import json, sys, tomllib, re
from pathlib import Path
from clasher.battle import BattleState
from clasher.stat_scaling import scale_stat
from clasher.unit_traits import unit_mass

NATIVE = Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767"
C56_NEW = ["BarbarianBarrel","AngryBarbarians","Berserker","Arrows","Tornado","ElectroSpirit","Ghost","Lightning","Balloon","BabyDragon","Wizard","Minions","Valkyrie","Golem","SkeletonArmy","Miner","MiniPekka","FirespiritHut","RoyalHogs","Princess","BlowdartGoblin","Poison","GoblinGang","GoblinBarrel","Bats","Rocket","Wallbreakers","BombTower","Firecracker","MinionHorde","GoblinHut","Goblinstein","Rascals","MightyMiner","Earthquake","FireSpirits","InfernoTower","Xbow","RoyalDelivery","ArcherQueen"]

def native_tables():
    out = {}
    files = list((NATIVE / "characters").glob("*.toml")) + [NATIVE / "buildings.toml", NATIVE / "characters.toml", NATIVE / "projectiles.toml"]
    for path in files:
        try:
            data = tomllib.loads(path.read_text())
        except Exception:
            continue
        for kind in ("CHARACTER", "BUILDING", "PROJECTILE"):
            for name, table in (data.get(kind) or {}).items():
                if isinstance(table, dict):
                    out.setdefault((kind, name.casefold()), table)
        for name, table in data.items():
            if isinstance(table, dict) and name not in ("CHARACTER","BUILDING","PROJECTILE","AEO","BUFF","ACTION","STATS","EXT","SHAPE"):
                out.setdefault(("ANY", name.casefold()), table)
    return out

def main():
    nat = native_tables()
    b = BattleState()
    rows = []
    for card in C56_NEW:
        stats = b.card_loader.get_card(card)
        if stats is None:
            rows.append({"card": card, "error": "no engine card"}); continue
        raw = stats._raw_entry
        chars = []
        c = raw.get("summonCharacterData") or {}
        if c: chars.append(c)
        for key in ("summonCharacterSecondData",):
            if raw.get(key): chars.append(raw[key])
        for ch in chars:
            nm = str(ch.get("name", ""))
            t = nat.get(("CHARACTER", nm.casefold())) or nat.get(("BUILDING", nm.casefold())) or nat.get(("ANY", nm.casefold()))
            if t is None:
                rows.append({"card": card, "char": nm, "error": "no native table"}); continue
            diffs = {}
            for nf, ef, scaled in (("Hitpoints","hitpoints",True),("Damage","damage",True),("HitSpeed","hitSpeed",False),("LoadTime","loadTime",False),("Range","range",False),("Speed","speed",False),("CollisionRadius","collisionRadius",False),("DeployTime","deployTime",False),("SightRange","sightRange",False),("LifeTime","lifeTime",False),("SpawnPauseTime","spawnPauseTime",False),("SpawnNumber","spawnNumber",False),("DeathDamage","deathDamage",True)):
                nv = t.get(nf); ev = ch.get(ef)
                if nv is None and ev is None: continue
                if nv != ev:
                    diffs[nf] = {"native": nv, "engine_raw": ev}
            nm_mass = t.get("Mass")
            if nm_mass is not None:
                class S: pass
                s = S(); s._raw_entry = {"summonCharacterData": ch}; s.name = nm; s.summon_character_data = ch
                try:
                    em = unit_mass(s)
                except Exception as exc:
                    em = repr(exc)
                if em != float(nm_mass):
                    diffs["Mass"] = {"native": nm_mass, "engine": em}
            if t.get("IgnorePushback") and not ch.get("ignorePushback"):
                diffs["IgnorePushback"] = {"native": True, "engine_raw": ch.get("ignorePushback")}
            rows.append({"card": card, "char": nm, "diffs": diffs})
    text = json.dumps(rows, indent=1)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    for r in rows:
        if r.get("error") or r.get("diffs"):
            print(json.dumps(r))

main()
