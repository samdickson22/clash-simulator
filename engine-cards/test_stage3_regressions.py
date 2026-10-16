"""Reduced regressions discovered by native script trajectories."""

import unittest
import clasher_core
from clasher.arena import Position
from differential import initial, config, snapshot, battle_digest


class Stage3Regressions(unittest.TestCase):
    def test_leaf_danger_uses_current_charge_speed(self):
        import cloudpickle, json
        from pathlib import Path
        from dataclasses import astuple
        from test_stage3 import resources, metadata
        from stage2_matches import PILOT
        from clasher.rl.reward_model import potential_breakdown_p0

        b = cloudpickle.loads(
            Path("engine-rs/evidence-stage3/leaf_failure.pkl").read_bytes()
        )
        r = clasher_core.BattleState(snapshot(b, config(PILOT)))
        r.set_public_movement_speeds(
            [
                (
                    e.id,
                    float(
                        e.original_speed if e.original_speed is not None else e.speed
                    ),
                )
                for e in b.entities.values()
                if type(e).__name__ == "Troop"
            ]
        )
        scripts = clasher_core.NativeScripts(json.dumps(metadata(resources()[1])))
        self.assertEqual(
            scripts.evaluation_parts(r), list(astuple(potential_breakdown_p0(b)))
        )

    def test_targetless_direct_shot_hits_body_at_endpoint(self):
        from clasher.entities import Projectile

        b = initial(cards=("Knight", "Archers", "Giant", "Musketeer"))
        self.assertTrue(b.deploy_card(1, "Knight", Position(3.5, 18.5)))
        knight = next(e for e in b.entities.values() if e.card_stats.name == "Knight")
        shot = Projectile(
            id=b.next_entity_id,
            position=Position(3.5, 18.3),
            player_id=0,
            card_stats=b.card_loader.get_card("Archers"),
            hitpoints=1,
            max_hitpoints=1,
            damage=112,
            range=0,
            sight_range=0,
            target_position=Position(3.5, 18.5),
            travel_speed=12.0,
            splash_radius=0.0,
            source_name="Archer",
            primary_target=None,
        )
        b.entities[shot.id] = shot
        b.next_entity_id += 1
        r = clasher_core.BattleState(snapshot(b, config()))
        b.step()
        r.step()
        self.assertEqual(knight.hitpoints, 1654.0)
        self.assertEqual(battle_digest(b), r.digest())

    def test_removed_crown_projectile_does_not_block_public_pocket(self):
        import cloudpickle, json
        from pathlib import Path
        from test_stage3 import resources, metadata, verify_view

        b = cloudpickle.loads(
            Path("engine-rs/evidence-stage3/action_failure.pkl").read_bytes()
        )
        r = clasher_core.BattleState(
            Path("engine-rs/evidence-stage3/action_failure_native.json").read_text()
        )
        _, builder, mask_builder, _ = resources()
        scripts = clasher_core.NativeScripts(json.dumps(metadata(builder)))
        verify_view(b, r, scripts, builder, mask_builder, actions=True)
        self.assertEqual(scripts.select_action(r, 0, "pressure"), 923)

    def test_equal_character_distance_uses_spatial_bucket_order(self):
        b = initial(cards=("Cannon", "Skeletons", "Knight", "Giant"))
        b.players[1].elixir = 10
        self.assertTrue(b.deploy_card(1, "Cannon", Position(14.5, 18.5)))
        self.assertTrue(b.deploy_card(0, "Skeletons", Position(14.5, 13.5)))
        cannon = next(e for e in b.entities.values() if e.card_stats.name == "Cannon")
        skeletons = [e for e in b.entities.values() if e.card_stats.name == "Skeletons"]
        del b.entities[skeletons[0].id]
        for e, x in zip(skeletons[1:], (15.199, 13.801)):
            e.position = Position(x, 13.097)
            e.deploy_delay_remaining = 0.5
            e.spawn_stagger_remaining = 0
        cannon.deploy_delay_remaining = 0
        cannon.spawn_stagger_remaining = 0
        r = clasher_core.BattleState(
            snapshot(b, config(("Cannon", "Skeletons", "Knight", "Giant")))
        )
        b.step()
        r.step()
        self.assertEqual(cannon.target_id, skeletons[2].id)
        self.assertEqual(battle_digest(b), r.digest())


if __name__ == "__main__":
    unittest.main()
