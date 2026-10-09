"""CPU regressions for the pending final-joint authentication handoff."""
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from clasher.live.selection import (AuthenticatedSelection, SelectionClaims, authenticate_selection,
                                    load_authenticated_selection, require_selection, sha256)
from selection_fixtures import selection_fixture


class SelectionTests(unittest.TestCase):
    def test_json_calibration_and_config_cannot_supply_authority(self):
        for config in ({}, {'body_threshold': .7}, {'authenticated_selection': {'final_joint': True}},
                       {'selection_provenance': {'body_threshold': .7}}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                require_selection(config)
        with self.assertRaises(ValueError):
            load_authenticated_selection('selection-freeze.json', None)
        with self.assertRaises(ValueError):
            AuthenticatedSelection(None, None, None)

    def test_separate_verifier_required_and_t7_only_claims_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            selection, checkpoint = selection_fixture(directory)
            claims = SelectionClaims(False, sha256(checkpoint), selection.cards, selection.bodies,
                selection.spells, .7, {'default': .1}, {}, selection.selection_sha256,
                dict(selection.source_hashes))
            def t7_verifier(source):
                return claims
            with self.assertRaisesRegex(ValueError, 'T7-only'):
                authenticate_selection(selection.selection_path, t7_verifier)
            def json_verifier(source):
                return {'authenticated': True, 'final_joint': True, 'body_threshold': .7}
            with self.assertRaises(ValueError):
                authenticate_selection(selection.selection_path, json_verifier)

    def test_checkpoint_vocabulary_and_source_bindings_and_spawn_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            selection, checkpoint = selection_fixture(directory)
            # multiprocessing spawn uses this same serialization boundary.
            received = pickle.loads(pickle.dumps(selection))
            self.assertEqual(require_selection({'authenticated_selection': received}), selection)
            state = {'cards': ['Knight', 'Zap'], 'bodies': ['Knight']}
            received.bind_checkpoint(checkpoint.read_bytes(), state)
            with self.assertRaisesRegex(ValueError, 'checkpoint SHA'):
                received.bind_checkpoint(b'wrong', state)
            with self.assertRaisesRegex(ValueError, 'vocabulary'):
                received.bind_checkpoint(checkpoint.read_bytes(), dict(state, cards=['Zap', 'Knight']))
            receipt = json.loads(json.dumps(received.provenance()))
            with self.assertRaises(ValueError):
                require_selection({'authenticated_selection': receipt})
            Path(received.source_hashes[0][0]).write_text('changed')
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                require_selection({'authenticated_selection': received})

    def test_selection_content_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            selection, _ = selection_fixture(directory)
            Path(selection.selection_path).write_text('{"body_threshold": 0.5}')
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                selection.check_sources()

    def test_unadmitted_vectorized_formal_path_refuses_before_model_load(self):
        from clasher.live.perception import V4Perception
        with tempfile.TemporaryDirectory() as directory:
            selection, checkpoint = selection_fixture(directory)
            with patch('torch.load') as load:
                with self.assertRaisesRegex(ValueError, 'unadmitted'):
                    V4Perception(dict(checkpoint=str(checkpoint), authenticated_selection=selection,
                                      vectorized_decoder=True))
                load.assert_not_called()

    def test_checkpoint_hash_checked_before_torch_deserialization(self):
        from clasher.live.perception import V4Perception
        with tempfile.TemporaryDirectory() as directory:
            selection, checkpoint = selection_fixture(directory)
            checkpoint.write_bytes(b'changed')
            with patch('torch.load') as load:
                with self.assertRaisesRegex(ValueError, 'checkpoint SHA'):
                    V4Perception(dict(checkpoint=str(checkpoint), authenticated_selection=selection))
                load.assert_not_called()

    def test_runtime_refuses_real_taps_for_unadmitted_diagnostic(self):
        from clasher.live.runtime import run
        from test_runtime import config
        with tempfile.TemporaryDirectory() as directory:
            selection, checkpoint = selection_fixture(directory)
            cfg = config(directory, frames=2)
            cfg['perception'] = dict(kind='v4', checkpoint=str(checkpoint), authenticated_selection=selection,
                                     vectorized_decoder=True, decoder_diagnostic=True)
            cfg['actuator']['kind'] = 'grpc'
            output = Path(directory)/'result'
            with self.assertRaisesRegex(ValueError, 'mock input'):
                run(cfg, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
