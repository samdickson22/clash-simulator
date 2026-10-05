"""Candidate scalar models for scenario 7 (episode-24 route resume; opened development evidence).

Both models share the gate of review variant H
(readiness/tier-a-fresh-v6/review/episode-24-mechanism.md): a troop that stopped
in range of its navigation target (a building) is frozen, re-acquires that same
target while standing in range, and later restarts toward it. They differ only in
the route used at the restart:

  H1 ("retain"): the unconsumed walking route held at the stop (review patch
      /tmp/ep24v6/patch_reacq.py, sha256 cbab1795...58642).
  H2 ("rebuild at re-acquire"): a route rebuilt from the re-acquisition position
      at the re-acquisition tick, with its first node consumed there if the
      advance reached test (< 1001 units) passes without travel.

Refinements added after the first native run (displacement while stopped):
  H9: H1, but at the re-acquisition the retained head node gets the advance
      reached test (projected on its recorded direction, < 1001) from the
      current position; a reached head is consumed, an emptied route rebuilds.
  H11: H1, but only if the troop is still in its stop cell at re-acquisition.
Added after the second native run:
  H12: H1, but only if the troop is still in its stop cell at re-acquisition
      AND the retained head does not pass the reached test there (H9 and H11
      both resume); otherwise the current rebuild-at-restart behaviour.

``install(name)`` patches ``Troop.update_movement_component``; ``uninstall()``
restores it.
"""

import copy

from clasher.entities import Building, Troop
from clasher.kinematics import normalized_vector_logic_units, tiles_to_logic_units, trunc_div
from clasher.pathfinding import _cell_center, _set_native_route_direction, ground_path_waypoint

ORIGINAL = Troop.update_movement_component
LOG = []
_KEEP = ("_native_ground_route_cells", "_ground_path_cache_key", "_native_friendly_building_signature",
         "_native_ground_route_direction", "_ground_path_backwards", "_ground_path_cache_backwards")


def _rebuilt_at_reacquire(unit, battle, target):
    keep = {k: copy.copy(getattr(unit, k, None)) for k in _KEEP}
    unit._native_ground_route_cells = []
    unit._ground_path_cache_key = None
    ground_path_waypoint(battle, unit, target.position, target_entity=target,
                         backwards_reference=target.position)
    route = list(unit._native_ground_route_cells or [])
    if route:
        w = _cell_center(route[0])
        dx = tiles_to_logic_units(w.x - unit.position.x)
        dy = tiles_to_logic_units(w.y - unit.position.y)
        ux, uy = normalized_vector_logic_units(dx, dy, 256)
        if trunc_div(ux * dx, 256) + trunc_div(uy * dy, 256) < 1001:
            route = route[1:]
    unit._native_ground_route_cells = route
    _set_native_route_direction(unit, route[0] if route else None)
    out = {k: copy.copy(getattr(unit, k, None)) for k in _KEEP}
    for k, v in keep.items():
        setattr(unit, k, v)
    return out


def _make(model):
    def update_movement_component(self, dt, bs):
        route = getattr(self, "_native_ground_route_cells", None)
        active = self._native_natural_movement_active
        if active and route and not self.is_charging and self._movement_target_id is None and not self.is_stunned():
            nav = getattr(self, "_native_navigation_target_id", None)
            tgt = bs.entities.get(nav) if nav is not None else None
            if nav is not None and self.target_id == nav and isinstance(tgt, Building):
                self._s7_saved = (list(route), self._ground_path_cache_key)
                self._s7_stop = (self.position.x, self.position.y, getattr(self, "_native_ground_route_direction", None))
                self._s7_frozen = False
                self._s7_nav = nav
                self._s7_h2 = None
        saved = getattr(self, "_s7_saved", None)
        if saved is not None and self.is_stunned():
            self._s7_frozen = True
            self._s7_reacq = False
            self._s7_h2 = None
        elif (saved is not None and getattr(self, "_s7_frozen", False)
              and self.target_id == getattr(self, "_s7_nav", None) and self._movement_target_id is None):
            if not getattr(self, "_s7_reacq", False):
                self._s7_h2 = _rebuilt_at_reacquire(self, bs, bs.entities.get(self._s7_nav))
                sx, sy, direction = self._s7_stop
                head = _cell_center(saved[0][0])
                if direction is None:
                    direction = normalized_vector_logic_units(tiles_to_logic_units(head.x - sx),
                                                              tiles_to_logic_units(head.y - sy), 256)
                remaining = (trunc_div(direction[0] * tiles_to_logic_units(head.x - self.position.x), 256)
                             + trunc_div(direction[1] * tiles_to_logic_units(head.y - self.position.y), 256))
                self._s7_reached = remaining < 1001
                self._s7_cell_changed = (int(sx * 2), int(sy * 2)) != (int(self.position.x * 2), int(self.position.y * 2))
                if model == "H9" and self._s7_reached:
                    saved[0].pop(0)
                    self._s7_dir = None
                    if saved[0]:
                        self._s7_dir = normalized_vector_logic_units(
                            tiles_to_logic_units(_cell_center(saved[0][0]).x - self.position.x),
                            tiles_to_logic_units(_cell_center(saved[0][0]).y - self.position.y), 256)
                LOG.append({"model": model, "tick": bs.tick, "id": self.id,
                            "pos": [round(self.position.x * 1000), round(self.position.y * 1000)],
                            "stop_route": [list(c) for c in saved[0]],
                            "reacquire_route": [list(c) for c in self._s7_h2["_native_ground_route_cells"]],
                            "stop_pos": [round(sx * 1000), round(sy * 1000)], "head_remaining": remaining,
                            "cell_changed": self._s7_cell_changed})
            self._s7_reacq = True
        if (not active and saved is not None and getattr(self, "_s7_frozen", False)
                and getattr(self, "_s7_reacq", False) and self._movement_target_id is not None
                and self._movement_target_id == getattr(self, "_s7_nav", None)
                and not self._native_ground_route_cells and self.deploy_delay_remaining <= 0
                and not self.is_stunned() and self._knockback_target is None):
            if (model == "H1" or (model == "H9" and saved[0]) or (model == "H11" and not self._s7_cell_changed)
                    or (model == "H12" and not self._s7_cell_changed and not self._s7_reached)):
                self._native_ground_route_cells, self._ground_path_cache_key = list(saved[0]), saved[1]
                if model == "H9" and getattr(self, "_s7_dir", None) is not None and self._s7_reached:
                    self._native_ground_route_direction = self._s7_dir
            elif model in ("H9", "H11", "H12"):
                pass
            elif model == "H2" and self._s7_h2 and self._s7_h2["_native_ground_route_cells"]:
                for k, v in self._s7_h2.items():
                    setattr(self, k, copy.copy(v))
            LOG.append({"model": model, "tick": bs.tick, "id": self.id, "restart": True,
                        "pos": [round(self.position.x * 1000), round(self.position.y * 1000)],
                        "installed": [list(c) for c in self._native_ground_route_cells]})
            self._s7_saved = None
        ORIGINAL(self, dt, bs)
        if self._native_natural_movement_active:
            self._s7_saved = None
    return update_movement_component


_LANDED_STASH = getattr(Troop, "_stash_native_frozen_stop_route", None)


def _disable_landed_rule():
    # The rule landed in main (H12) is switched off for "revert" and for every
    # candidate, so each candidate wraps the pre-fix movement component.
    if _LANDED_STASH is not None:
        Troop._stash_native_frozen_stop_route = lambda self, battle_state: None


def install(name):
    """"main": current source (with the landed H12 rule); "revert": main with the
    landed rule disabled in memory (the pre-fix behaviour, formerly "base")."""
    uninstall()
    if name == "main":
        return
    _disable_landed_rule()
    if name not in ("revert", "base"):
        Troop.update_movement_component = _make(name)


def uninstall():
    Troop.update_movement_component = ORIGINAL
    if _LANDED_STASH is not None:
        Troop._stash_native_frozen_stop_route = _LANDED_STASH
