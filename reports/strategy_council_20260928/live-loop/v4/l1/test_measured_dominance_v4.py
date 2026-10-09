import itertools
import unittest
from copy import deepcopy
from measured_dominance_v4 import optimistic_counts, next_step, rank, verify_certificate, GRID


def pred(stamp, **kw):
    return dict(episode_id='v', card='X', side=0, kind='card_play', production_timestamp_ms=stamp, **kw)


def truth(stamp):
    return dict(episode_id='v', card='X', side=0, kind='troop', execution_timestamp_ms=stamp)


def grid(m=1):
    return [dict(epoch=e, threshold=t, opponent=dict(truth=1, predictions=1, matched=m),
        measured=False, evidence_kind='zero-service upper bound') for e in range(1,25) for t in GRID]


def measure(row, m):
    out=deepcopy(row);out.update(measured=True, evidence_kind='measured completion+FIFO')
    out['opponent']['matched']=m;return out


class DominanceTests(unittest.TestCase):
    def test_premature_prediction_remains_possible(self):
        # Production0 < execution100: zero-service scoring would miss this.
        self.assertEqual(optimistic_counts([pred(0)], [truth(100)], episodes=['v'])['matched'],1)

    def test_nested_matching_exhaustive(self):
        for ps in itertools.product((-600,0,700), repeat=3):
            for ts in itertools.product((0,600), repeat=2):
                best=0
                for n in range(3):
                    for pi in itertools.combinations(range(3),n):
                        for ti in itertools.permutations(range(2),n):
                            if all(ps[p]<=ts[t]+500 for p,t in zip(pi,ti)):best=max(best,n)
                self.assertEqual(optimistic_counts([pred(x) for x in ps],[truth(x) for x in ts],episodes=['v'])['matched'],best)

    def test_measured_edges_subset_for_delayed_predictions(self):
        ps=[-100,40,700];ts=[0,500]
        ub=optimistic_counts([pred(x) for x in ps],[truth(x) for x in ts],episodes=['v'])['matched']
        for delays in itertools.product((0,100,1000),repeat=3):
            best=0
            for n in range(3):
                for pi in itertools.combinations(range(3),n):
                    for ti in itertools.permutations(range(2),n):
                        if all(ts[t]<=ps[p]+delays[p]<=ts[t]+500 for p,t in zip(pi,ti)):best=max(best,n)
            self.assertLessEqual(best,ub)

    def test_reject_clock_fields(self):
        with self.assertRaises(ValueError):optimistic_counts([pred(0,available_timestamp_ms=0)],[truth(0)],episodes=['v'])

    def test_key_kind_and_side_separation(self):
        p=pred(0);p['side']=1
        self.assertEqual(optimistic_counts([p],[truth(0)],episodes=['v']),dict(truth=1,predictions=0,matched=0))
        p=pred(0);p['kind']='champion_ability'
        self.assertEqual(optimistic_counts([p],[truth(0)],episodes=['v'])['predictions'],0)

    def test_ties_earlier_epoch_higher_threshold(self):
        rows=grid();n=next_step(rows,[])['next_cell'];self.assertEqual((n['epoch'],n['threshold']),(1,.9))
        lower=measure(rows[0],1) # e1 .1 is not enough to eliminate equal-metric .9
        self.assertFalse(next_step(rows,[lower])['closed'])
        self.assertEqual(next_step(rows,[lower])['next_cell']['threshold'],.9)
        self.assertEqual(rank(lower),rank(deepcopy(lower)))

    def test_equal_metrics_worse_tiebreak_eliminated(self):
        rows=grid();incumbent=measure(next_step(rows,[])["next_cell"],1)
        state=next_step(rows,[incumbent])
        self.assertIn([2,.9],state["eliminated"]) # later epoch
        self.assertIn([1,.8],state["eliminated"]) # lower threshold
        self.assertTrue(state["closed"])

    def test_termination_and_tamper(self):
        rows=grid();first=next_step(rows,[])['next_cell'];measured=[measure(first,1)]
        certificate=next_step(rows,measured);self.assertTrue(certificate['closed'])
        verify_certificate(certificate,recompute_bounds=lambda:rows,recompute_measured=lambda:measured)
        bad=deepcopy(certificate);bad['measured_cells']=2
        with self.assertRaises(ValueError):verify_certificate(bad,recompute_bounds=lambda:rows,recompute_measured=lambda:measured)

    def test_unclosed_and_budget_not_a_winner(self):
        rows=grid();measured=[]
        for _ in range(30):measured.append(measure(next_step(rows,measured)['next_cell'],0))
        state=next_step(rows,measured);self.assertFalse(state['closed']);self.assertTrue(state['budget_checkpoint'])
        with self.assertRaises(ValueError):verify_certificate(state,recompute_bounds=lambda:rows,recompute_measured=lambda:measured)

    def test_bound_tamper_and_changed_counts(self):
        rows=grid(0);m=measure(next_step(rows,[])['next_cell'],1)
        with self.assertRaises(ValueError):next_step(rows,[m])
        rows=grid();m=measure(rows[0],1);m['opponent']['predictions']=2
        with self.assertRaises(ValueError):next_step(rows,[m])

    def test_missing_duplicate_and_order(self):
        rows=grid()
        for bad in (rows[:-1],rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError):next_step(bad,[])
        # A valid closed mathematical certificate still needs the frozen order.
        measured=[measure(rows[0],0),measure(next_step(rows,[])['next_cell'],1)]
        with self.assertRaises(ValueError):verify_certificate(next_step(rows,measured),recompute_bounds=lambda:rows,recompute_measured=lambda:measured)


if __name__=='__main__':unittest.main()
