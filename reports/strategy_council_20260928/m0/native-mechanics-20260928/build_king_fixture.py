"""Build tests/fixtures/native_king_wakeup_stun_15_535_86.json from recorded native runs.

Inputs are the pre-repair native records in this directory (native columns only):
s1b_zap_sweep_pre_repair.json and s1c_icespirit_freeze_pre_repair.json. The native
initial deck/hand/cycle/elixir for each seed is re-read with configure+observe.
Usage: build_king_fixture.py <emulator-serial>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402
import s1_king_wakeup_stun as S  # noqa: E402
import s5_lane_after_tower as F  # noqa: E402

PORT = L.PORTS[sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"]
FIXTURE = L.ROOT / "tests/fixtures/native_king_wakeup_stun_15_535_86.json"


def initial_state(seed, d0, d1):
    config = L.make_config(d0, d1, seed)
    L.configure_single(PORT, config)
    initial = L.single(PORT, "observe")
    assert initial["tick"] == 0
    names = {L.card_id(n): n for n in d0 + d1}
    out = {}
    for p in initial["players"]:
        out[str(p["owner"])] = {
            "deck": [names[c["cardId"]] for c in p["deck"]],
            "hand": [names[c["cardId"]] for c in sorted(p["hand"], key=lambda c: c["handIndex"])],
            "cycle": [names[c["cardId"]] for c in sorted(p["cycle"], key=lambda c: c["cycleIndex"])],
            "elixir": p["elixir"],
        }
    return out


def main():
    here = Path(__file__).resolve().parent
    sweep_path = here / "s1b_zap_sweep_pre_repair.json"
    ice_path = here / "s1c_icespirit_freeze_pre_repair.json"
    sweep = json.loads(sweep_path.read_text())
    ice = json.loads(ice_path.read_text())
    fixture = {
        "role": "development",
        "scope": "Opened native 15.535.86 development controls; King wake-up under Zap stun and "
                 "Ice Spirit freeze. First King shot = tick a projectile sourced by the King first exists.",
        "gamedata_sha256": L.sha(L.GAMEDATA),
        "sources": {str(p.relative_to(L.ROOT)): L.sha(p) for p in (sweep_path, ice_path)},
        "zap_sweep": {
            "seed": sweep["seed"], "decks": [S.D0, S.D1],
            "initial": initial_state(sweep["seed"], S.D0, S.D1),
            "base_commands": sweep["base_commands"],
            "zap_target": [9.0, 3.0],
            "rows": [{"zap_cast_tick": r["zap_cast_tick"],
                      "native_activation_tick": r["native"]["activation"],
                      "native_first_shot_tick": r["native"]["first_shot"]} for r in sweep["rows"]],
        },
        "ice_spirit": {
            "seed": ice["seed"], "decks": [F.D0, F.D1],
            "initial": initial_state(ice["seed"], F.D0, F.D1),
            "prefix": ice["prefix"],
            "cases": {name: {"test": v["test"], "native_fall_tick": v["native"]["fall"],
                             "native_king_first_hp_loss": v["native"]["king_first_hp_loss"],
                             "native_first_shot_tick": v["native"]["first_shot"]["tick"]}
                      for name, v in ice["variants"].items() if name in ("none", "ice_f1_x6.5")},
        },
    }
    FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")
    print("wrote", FIXTURE, FIXTURE.stat().st_size)


if __name__ == "__main__":
    main()
