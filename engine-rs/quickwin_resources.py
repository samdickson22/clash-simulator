"""Opt-in Stage 5 Resources startup caching, without patching shared modules.

Use with engine-rs and engine-speed/stage5 on PYTHONPATH. No disk cache is used.
The sealed Resources initializer and exporter functions execute unchanged,
with private global/import namespaces pointing to the cached battle/arena.
"""
from __future__ import annotations

import builtins
import copy
from functools import lru_cache
import importlib
from pathlib import Path
from types import FunctionType, ModuleType

import differential
import fair_player
from clasher.arena import TileGrid
from clasher.battle import BattleState
from clasher.kinematics import tiles_to_logic_units
from clasher.native_tilemap import nearest_native_path_id


@lru_cache(maxsize=65536)
def cached_path_id(x_units: int, y_units: int, other_x_units: int = -1) -> int:
    return nearest_native_path_id(x_units, y_units, other_x_units)


@lru_cache(maxsize=16)
def _tower_data(path: str, mtime_ns: int, size: int, inode: int) -> dict:
    # Delegate parsing and validation to the unchanged loader. A private holder
    # is enough because it only reads self.card_loader.data_file.
    from types import SimpleNamespace
    holder = SimpleNamespace(card_loader=SimpleNamespace(data_file=path))
    return BattleState._load_princess_tower_character_data(holder)


class CachedTileGrid(TileGrid):
    def native_path_id_at(self, pos, other_x=None):
        return cached_path_id(
            tiles_to_logic_units(pos.x), tiles_to_logic_units(pos.y),
            -1 if other_x is None else tiles_to_logic_units(other_x),
        )


class CachedBattleState(BattleState):
    def __init__(self, *args, **kwargs):
        # The private exporters construct battles by keyword only.
        if not args:
            kwargs.setdefault("arena", CachedTileGrid())
        super().__init__(*args, **kwargs)

    def _load_princess_tower_character_data(self):
        path = Path(self.card_loader.data_file).resolve()
        stat = path.stat()
        # Return independent mutable data, just as the uncached JSON loader does.
        return copy.deepcopy(_tower_data(str(path), stat.st_mtime_ns, stat.st_size, stat.st_ino))


def _bind(function, namespace):
    bound = FunctionType(function.__code__, namespace, function.__name__,
                         function.__defaults__, function.__closure__)
    bound.__kwdefaults__ = function.__kwdefaults__
    bound.__annotations__ = function.__annotations__
    bound.__doc__ = function.__doc__
    return bound


def _private_exporters():
    # These helpers import differential.initial/config recursively (Mirror,
    # Clone, death effects). Give all four private namespaces the same import
    # map, leaving sys.modules and every original function untouched.
    names = ("differential", "mirror_snapshot", "clone_snapshot", "death_area_snapshot")
    originals = {name: importlib.import_module(name) for name in names}
    private = {name: ModuleType(name) for name in names}
    tilemap = ModuleType("clasher.native_tilemap")
    tilemap.__dict__.update(importlib.import_module(tilemap.__name__).__dict__)
    tilemap.nearest_native_path_id = cached_path_id

    def private_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and fromlist:
            if name in private:
                return private[name]
            if name == tilemap.__name__:
                return tilemap
        return builtins.__import__(name, globals, locals, fromlist, level)

    replacements = {id(BattleState): CachedBattleState}
    for name, original in originals.items():
        namespace = private[name].__dict__
        namespace.update(original.__dict__)
        namespace["__builtins__"] = dict(vars(builtins), __import__=private_import)
        for key, value in original.__dict__.items():
            if isinstance(value, FunctionType) and value.__module__ == name:
                namespace[key] = _bind(value, namespace)
                replacements[id(value)] = namespace[key]
    for module in private.values():
        for key, value in list(module.__dict__.items()):
            if id(value) in replacements:
                module.__dict__[key] = replacements[id(value)]
    return private["differential"]


_exporters = _private_exporters()


def cached_resources(base_class):
    """Adapt a separately loaded sealed fair class before other wrappers."""
    class CachedResources(base_class):
        __init__ = _bind(base_class.__init__, dict(
            base_class.__init__.__globals__,
            config=_exporters.config, initial=_exporters.initial,
        ))
    return CachedResources


class Resources(cached_resources(fair_player.Resources)):
    """Same outputs/root behavior as sealed Resources; cached startup only."""


def clear_startup_caches():
    """Explicit invalidation for a caller that changes game data in-process."""
    _tower_data.cache_clear()
    cached_path_id.cache_clear()
