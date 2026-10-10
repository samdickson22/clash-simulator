"""05-safe tests of ownership and final-publication barriers; synthetic JSON only."""
import copy
import unittest
from audit_vacancy import classify_gpu_pids
from finalize_metadata import validate_final


class MetadataBarriers(unittest.TestCase):
    def fixture(self):
        meter = dict(sha256='one', cpu_seconds=1, gpu_wall_seconds=2)
        cost = dict(final=True, scientific_complete=True, vacancy_complete=True,
                    meters=[meter], cpu_seconds=1, gpu_wall_seconds=2)
        stage1 = {a: dict(stage1_complete=True, survives=False,
                         regret_game_proofs=[dict(index=i) for i in range(64)])
                  for a in ('R3c', 'R3d', 'R3e')}
        desc = dict(paired_seeds=600, never_adoptable=True, live_adoption=False,
                    arms=dict(R3a=dict(survives=False)), block_proofs=[{}]*600)
        vacancy = dict(all_recorded_groups_absent=True, observer_independently_absent=True, gpu_owned_pids=[])
        return [cost, copy.deepcopy(cost), stage1, desc, None, [copy.deepcopy(vacancy) for _ in range(5)]]

    def test_gpu_ownership(self):
        self.assertEqual(classify_gpu_pids('', {12}), ([], []))
        self.assertEqual(classify_gpu_pids('98\n99\n', {12}), ([98, 99], []))
        self.assertEqual(classify_gpu_pids('12\n99\n', {12}), ([12, 99], [12]))

    def test_complete_kill_allows_skipped_stage2(self):
        validate_final(*self.fixture())

    def test_survivor_requires_stage2(self):
        v = self.fixture(); v[2]['R3c']['survives'] = True
        with self.assertRaises(AssertionError): validate_final(*v)

    def test_incomplete_or_duplicate_cost_rejected(self):
        v = self.fixture(); v[0]['final'] = False
        with self.assertRaises(AssertionError): validate_final(*v)
        v = self.fixture(); v[1]['meters'] *= 2
        with self.assertRaisesRegex(AssertionError, 'Duplicate'): validate_final(*v)

    def test_unadmitted_live_adoption_rejected(self):
        v = self.fixture(); v[3]['live_adoption'] = True
        with self.assertRaises(AssertionError): validate_final(*v)

    def test_live_gpu_or_unconfirmed_observer_rejected(self):
        v = self.fixture(); v[5][0]['gpu_owned_pids'] = [12]
        with self.assertRaises(AssertionError): validate_final(*v)
        v = self.fixture(); v[5][0]['observer_independently_absent'] = False
        with self.assertRaises(AssertionError): validate_final(*v)


if __name__ == '__main__':
    unittest.main()
