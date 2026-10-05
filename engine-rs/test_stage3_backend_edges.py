"""Backend boundary checks and non-default public styles/scheduling."""

import builtins
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import cloudpickle
import numpy as np
from differential import ES
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from test_stage3_backend import reference

sys.path.insert(0, str(ES / "srp_reference"))
from oq_lib import Context


class BackendEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = Context()
        cls.env = cls.ctx.envs("holdout", 0)[0]
        cls.root = cloudpickle.loads(
            (
                Path.home() / ".cache/clasher-engine-speed/stage0-srp-snapshots.pkl"
            ).read_bytes()
        )[0]
        cls.env.battle = cls.root
        cls.bot = cls.ctx.bot("balanced")

    def test_default_does_not_import_native_backend(self):
        original = builtins.__import__

        def guarded(name, *args, **kwargs):
            if name in ("clasher_core", "differential"):
                raise AssertionError("default attempted native import")
            return original(name, *args, **kwargs)

        legal = np.flatnonzero(
            self.env.get_action_mask(0)
            & self.env.action_space.legal_action_mask(self.root, 0)
        )
        with patch("builtins.__import__", guarded):
            planner = ScriptRolloutPlanner(
                self.env, self.bot, horizon=10, samples=0, script_top=0, seed=4
            )
            self.assertIn(planner.select_action(self.root, 0, legal), legal)

    def test_styles_same_script_opponent_and_overshooting_interval(self):
        for style in ("balanced", "pressure", "defense"):
            bot = PublicScriptedOpponent(self.env.structured_obs_builder, style=style)
            kwargs = dict(
                horizon=21, rollout_interval=10, samples=0, script_top=0, seed=4
            )
            py = reference.ScriptRolloutPlanner(self.env, bot, **kwargs)
            native = ScriptRolloutPlanner(self.env, bot, backend="native", **kwargs)
            for seat in (0, 1):
                self.assertEqual(
                    py._rollout(self.root, seat, 2304, 2304).hex(),
                    native._rollout(self.root, seat, 2304, 2304).hex(),
                )
            self.assertEqual(py.rollout_ticks, 60)
            for key in ("rollout_ticks", "script_calls", "observation_skips"):
                self.assertEqual(getattr(py, key), getattr(native, key))

    def test_native_rejects_unqualified_typed_vocabulary(self):
        with patch.object(self.bot.builder, "_uses_typed_tokens", True):
            with self.assertRaises(ValueError):
                ScriptRolloutPlanner(self.env, self.bot, backend="native")

    def test_terminal_scores(self):
        native = ScriptRolloutPlanner(self.env, self.bot, backend="native")
        root = self.root.clone()
        root.game_over = True
        for winner in (None, 0, 1):
            root.winner = winner
            for seat in (0, 1):
                expected = 0.0 if winner is None else 2.0 if winner == seat else -2.0
                self.assertEqual(native._rollout(root, seat, 2304, 2304), expected)
        self.assertEqual(native.rollout_ticks, 0)

    def test_native_rejects_unported_profile_and_custom_rules(self):
        with self.assertRaises(ValueError):
            ScriptRolloutPlanner(
                self.env, self.bot, profile="objective-v1", backend="native"
            )
        native = ScriptRolloutPlanner(self.env, self.bot, backend="native")
        root = self.root.clone()
        root.players[0].max_elixir = 20
        with self.assertRaises(ValueError):
            native._rollout(root, 0, 2304, 2304)


if __name__ == "__main__":
    unittest.main()
