"""Bandit anticipation, speed-based travel, hit and immunity regressions."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class Dash(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation
    def test_both_bandits_seats_windup_travel_zap_and_live_import(self):
        for card in ('Assassin','BossBandit'):
            cards=(card,'Cannon','Zap','Fireball');cfg=config(cards)
            for seat in (0,1):
                for zap_tick in (None,26,42):
                    with self.subTest(card=card,seat=seat,zap_tick=zap_tick):
                        b=initial(669530,cards=cards)
                        for owner,name,y in ((seat,card,13.5 if seat==0 else 18.5),(1-seat,'Cannon',19.5 if seat==0 else 12.5)):
                            b.players[owner].elixir=10
                            self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
                        actor=next(e for e in b.entities.values() if getattr(e.card_stats,'name',None)==card)
                        r=clasher_core.BattleState(snapshot(b,cfg));seen=set()
                        for _ in range(200):
                            if b.tick==zap_tick and actor.is_alive:
                                b.players[1-seat].elixir=10;r=clasher_core.BattleState(snapshot(b,cfg))
                                pos=Position(actor.position.x,actor.position.y)
                                self.assertTrue(b.deploy_card(1-seat,'Zap',pos))
                                self.assertTrue(r.apply_action(1-seat,'Zap',pos.x,pos.y))
                            b.step();r.step();self.same(b,r)
                            phase='travel' if actor._bandit_dashing else 'charging' if actor._bandit_charging else 'idle'
                            if phase not in seen:
                                seen.add(phase);self.continuation(b,cfg,100)
                        self.assertIn('charging',seen)
                        if zap_tick is None:self.assertIn('travel',seen)

    def test_lethal_dash_preserves_preload_when_cleanup_publishes_clock(self):
        import cloudpickle,hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parent/'dash-clock-r28-root802.pkl'
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,old,_=cloudpickle.loads(root.read_bytes());cfg=config(tuple(old['cards']))
        r=clasher_core.BattleState(snapshot(b,cfg));b.step();r.step();self.same(b,r)
        actor=b.entities[79];row=next(e for e in json.loads(r.snapshot())['entities'] if e['id']==79)
        self.assertEqual(actor._ordinary_clock.load_remaining_ms,100)
        self.assertEqual(row['clock']['remaining'],100)
        self.continuation(b,cfg,180)

    def test_cancelled_windup_retains_new_out_of_band_crown_target(self):
        import cloudpickle,hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parent/'dash-r29-root1557.pkl'
        pins=json.loads(root.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(root.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root.parent.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,old,_=cloudpickle.loads(root.read_bytes());cfg=config(tuple(old['cards']))
        r=clasher_core.BattleState(snapshot(b,cfg));b.step();r.step();self.same(b,r)
        self.assertEqual(b.entities[158].target_id,5)
        self.continuation(b,cfg,180)

if __name__=='__main__':unittest.main()
