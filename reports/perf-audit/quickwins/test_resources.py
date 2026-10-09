"""Cache invalidation/mutation and path tie regressions; CPU host only."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import quickwin_resources as cache
from clasher.native_tilemap import nearest_native_path_id


class StartupCacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear_startup_caches()

    def test_tower_data_is_independent_and_file_change_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"gamedata.json"
            def write(value):
                path.write_text(json.dumps({"items": {"spells": [{
                    "name": "King_PrincessTowers", "statCharacterData": {"projectileData": {"speed": value}}
                }]}}))
            write(600)
            battle = object.__new__(cache.CachedBattleState)
            battle.card_loader = SimpleNamespace(data_file=path)
            first = battle._load_princess_tower_character_data()
            first["projectileData"]["speed"] = -1
            self.assertEqual(battle._load_princess_tower_character_data()["projectileData"]["speed"], 600)
            stamp = path.stat().st_mtime_ns
            write(700)
            os.utime(path, ns=(stamp+1000000, stamp+1000000))
            self.assertEqual(battle._load_princess_tower_character_data()["projectileData"]["speed"], 700)
            self.assertEqual(cache._tower_data.cache_info().misses, 2)

    def test_path_ties_defaults_and_boundaries_are_exact(self):
        for x in (-501, -1, 0, 250, 4500, 8995, 9000, 9005, 13500, 18000):
            for y in (-1, 0, 250, 15000, 16000, 17000, 31750, 32000):
                for other in (-1, 4500, 9000, 13500):
                    args = (x, y, other)
                    self.assertEqual(cache.cached_path_id(*args), nearest_native_path_id(*args))
                    self.assertEqual(cache.cached_path_id(*args), nearest_native_path_id(*args))
        self.assertEqual(cache.cached_path_id(9000, 16000), cache.cached_path_id(9000, 16000, -1))


if __name__ == "__main__":
    unittest.main()
