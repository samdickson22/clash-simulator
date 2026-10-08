"""Small cycle/phase tests; run on a fleet node, not the command center."""
import unittest
from derived_d1 import DerivedD1, PublicEvent
from own_cycle import OwnCycle


class DerivationTests(unittest.TestCase):
    def test_queue_pending_and_own_slots(self):
        cards = list('abcdefgh')
        d = DerivedD1(dict.fromkeys(cards, 1))
        own = OwnCycle(cards)
        for i, name in enumerate(cards + cards[:3]):
            tick = i * 30
            d.accept(PublicEvent(tick, 'card', name))
            own.play(tick, name)
            self.assertEqual(len(d.queue), 5)
            for t in range(tick, tick + 26):
                d.advance(t); own.advance(t)
                for a, b in zip(d.queue, own.queue):
                    if a is not None:
                        self.assertEqual(a, b)
                self.assertTrue(set(filter(None, d.derived()['hand_known'])) <= set(own.hand))
                self.assertEqual(d.refill, own.refill)
        self.assertEqual(tuple(d.queue), tuple(own.queue))

    def test_multiple_empty_slots(self):
        d = DerivedD1(dict.fromkeys('abcdefgh', 1))
        for name in 'abcd':
            d.accept(PublicEvent(0, 'card', name))
        self.assertEqual(len(d.queue), 8)
        self.assertEqual(d.derived()['hand_known'], (None,) * 4)
        d.advance(61)
        self.assertEqual(tuple(d.queue), tuple('abcd'))
        self.assertEqual(d.derived()['next_card'], 'a')

    def test_integer_regeneration_phase_edges(self):
        d = DerivedD1({'a': 3})
        d.advance(2400); d.accept(PublicEvent(2400, 'card', 'a'))
        d.advance(2401)
        self.assertEqual(d.elixir_units, 70357)
        d.advance(4800); d.accept(PublicEvent(4800, 'ability', amount=3))
        d.advance(4801)
        self.assertEqual(d.elixir_units, 70537)

    def test_mirror_collector_and_ability(self):
        d = DerivedD1({'a': 2, 'Mirror': 0})
        d.accept(PublicEvent(0, 'card', 'a'))
        d.accept(PublicEvent(0, 'card', 'Mirror'))
        self.assertEqual(d.elixir, 1.)
        d.accept(PublicEvent(0, 'collector', amount=2))
        d.accept(PublicEvent(0, 'ability', amount=1))
        self.assertEqual(d.elixir, 2.)
        self.assertEqual(len(d.queue), 6)

    def test_impossible_and_mutated_streams_fail(self):
        d = DerivedD1({'a': 1})
        d.accept(PublicEvent(0, 'card', 'a'))
        with self.assertRaises(ValueError):
            d.accept(PublicEvent(5, 'card', 'a'))
        with self.assertRaises(ValueError):
            d.update(6, [])


if __name__ == '__main__':
    unittest.main()
