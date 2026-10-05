"""Scenario 1b: sweep the Zap time across the King wake-up (native vs scalar models).

Same setup as s1_king_wakeup_stun.py (Hog at 250, Fireball on the owner-0 King at
250, King activation at tick ~293). One Zap on the King per run at a swept cast
tick. Records the King first-shot tick on native and on three scalar models:
  current  main source as is
  T1       triage proposal: both activation clocks keep running while stunned;
           completion during the stun arms the shot for the first legal frame
  T2       only the 3.3 s activation delay keeps running while stunned; the
           0.7 s first-hit remainder stays paused like an ordinary loaded attack
Usage: s1b_zap_sweep.py <emulator-serial> [model-only]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402
import s1_king_wakeup_stun as S  # noqa: E402
from clasher.entities import Building  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"
PORT = L.PORTS[SERIAL]
MODEL_ONLY = "model-only" in sys.argv
ZAP_TICKS = [None] + list(range(286, 378, 3))
ORIGINAL = Building._update_active_combat


def make_patch(mode):
    def patched(self, dt, battle_state):
        if (self._freeze_target_pause_remaining > 0 and getattr(self, "_is_king_tower", False)
                and getattr(self, "_tower_active", False)
                and (self.activation_delay_remaining > 0 or self.activation_first_hit_delay_remaining > 0)):
            if self.activation_delay_remaining > 0:
                work = min(dt, self.activation_delay_remaining)
                self.activation_delay_remaining = max(0.0, self.activation_delay_remaining - work)
                if self.activation_delay_remaining <= 1e-9:
                    self.activation_delay_remaining = 0.0
                dt -= work
            if mode == "T1" and dt > 1e-9 and self.activation_first_hit_delay_remaining > 0:
                work = min(dt, self.activation_first_hit_delay_remaining)
                self.activation_first_hit_delay_remaining -= work
                if self.activation_first_hit_delay_remaining <= 1e-9:
                    self.activation_first_hit_delay_remaining = 0.0
                    self.attack_cooldown = 0.0
                    self._attack_preload_blocked = False
            return
        return ORIGINAL(self, dt, battle_state)
    return patched


def main():
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(PORT, S.D0, S.D1, need1=("HogRider", "Fireball", "Zap"))
    rows = []
    for zap in ZAP_TICKS:
        cmds = S.BASE + ([{"tick": zap, "owner": 1, "card": "Zap", "xy": (9.0, 3.0)}] if zap else [])
        row = {"zap_cast_tick": zap}
        for model in ("current", "T1", "T2"):
            Building._update_active_combat = ORIGINAL if model == "current" else make_patch(model)
            try:
                sc = L.run_scalar(initial, config, [S.D0, S.D1], cmds, 470)
            finally:
                Building._update_active_combat = ORIGINAL
            ev = S.king_events(sc["frames"], "scalar")
            row[model] = {"activation": ev["activation_tick"], "first_shot": ev["first_shot_tick"],
                          "rejected": sc["rejected"]}
        if not MODEL_ONLY:
            na = L.run_native(PORT, config, cmds, 470, rich=True)
            ev = S.king_events(na["frames"], "native")
            king = []
            for f in na["frames"]:
                if 350 <= f["tick"] <= 400:
                    k = next(o for o in f["objects"] if o["id"] == 5000000)
                    king.append([f["tick"], k.get("target"), k.get("timeline"), k.get("load"), k["hp"]])
            row["native"] = {"activation": ev["activation_tick"], "first_shot": ev["first_shot_tick"],
                             "king_rich_350_400": king}
        rows.append(row)
        print(zap, {m: row[m]["first_shot"] for m in ("native", "current", "T1", "T2") if m in row}, flush=True)
    out = {"scenario": "king_wakeup_zap_sweep", "serial": SERIAL, "seed": seed, "config": config,
           "base_commands": S.BASE, "rows": rows, "provenance": L.provenance()}
    L.dump("s1b_zap_sweep.json" if not MODEL_ONLY else "s1b_zap_sweep_models_only.json", out)


if __name__ == "__main__":
    main()
