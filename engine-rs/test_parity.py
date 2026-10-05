"""Regression trajectories reduced to the first affected semantic boundary."""
import json
import unittest
import clasher_core
from differential import config, initial, snapshot, scripted_actions, battle_digest


class Parity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config()

    def replay(self, case, ticks):
        b = initial(9700 + case)
        native = clasher_core.BattleState(snapshot(b, self.cfg))
        for t in range(ticks):
            _, errors = scripted_actions(b, native, self.cfg, case, t)
            self.assertEqual(errors, 0)
            b.step(); native.step()
            self.assertEqual(battle_digest(b), native.digest(), f'case {case} tick {t+1}')
        return b, json.loads(native.snapshot())

    def test_pending_lethal_removal_reacquires_without_finish(self):
        b, state = self.replay(0, 438)
        for eid in (1, 5):
            e = next(e for e in state['entities'] if e['id'] == eid)
            self.assertEqual(e['clock']['finish'], 0)
            self.assertEqual(e['target'], b.entities[eid].target_id)
            self.assertIsNotNone(e['target'])

    def test_multiple_body_pressure_is_averaged(self):
        self.replay(2, 568)

    def test_staggered_archer_is_not_a_combat_candidate(self):
        self.replay(1, 1201)

    def test_melee_keep_range_does_not_use_projectile_extension(self):
        self.replay(5, 641)

    def test_started_melee_hit_continues_outside_engagement(self):
        self.replay(5, 710)

    def test_crown_fallback_skips_live_pending_lethal_king(self):
        self.replay(2, 851)

    def test_depleted_eligible_archer_emits_live_projectile(self):
        self.replay(8, 1232)

    def test_simultaneous_king_deaths_draw(self):
        b, state = self.replay(2, 852)
        self.assertTrue(state['game_over'])
        self.assertIsNone(state['winner'])

    def test_tower_acquisition_consumes_passive_and_active_load(self):
        self.replay(9, 1259)

    def test_live_crown_footprint_rejects_without_payment(self):
        from differential import CARDS, Position
        for card in CARDS:
            for seat, x, y in [(0,13.5,7.5),(1,4.5,24.5),(0,9,3)]:
                b = initial(7)
                native = clasher_core.BattleState(snapshot(b, self.cfg))
                before = native.digest()
                self.assertFalse(b.deploy_card(seat,card,Position(x,y)))
                self.assertFalse(native.apply_action(seat,card,x,y))
                self.assertEqual(before, native.digest())
                self.assertEqual(battle_digest(b), native.digest())

    def test_debug_phase_replay_uses_same_tick(self):
        from diagnostics import phase_step
        b = initial(11)
        r = clasher_core.BattleState(snapshot(b,self.cfg))
        reference = r.clone()
        reference.step()
        phases = phase_step(b,r)
        self.assertEqual(list(phases), ['before','start','combat','movement','objects','cleanup','complete'])
        self.assertEqual(r.snapshot(),reference.snapshot())
        self.assertEqual(r.digest(),battle_digest(b))

    def test_king_projectiles_do_not_keep_destroyed_kings_alive(self):
        b, state = self.replay(13, 1458)
        self.assertTrue(state['game_over'])
        self.assertIsNone(state['winner'])

    def test_depleted_crown_remains_navigation_goal_until_cleanup(self):
        self.replay(2, 536)


if __name__ == '__main__':
    unittest.main()
