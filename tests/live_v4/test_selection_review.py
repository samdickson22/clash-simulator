"""Synthetic owner-review regressions; no final authority, model or device run."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from clasher.live.decoder_binding import (DecoderBinding, ProofReference, IMPLEMENTATION,
    closure_hash, current_scope, qualify, source_hashes)
from clasher.live.loading import ROOT
from clasher.live.selection import authenticate_selection, load_authenticated_selection, sha256
from clasher.live.selection_trust import ModulePin, VerifierTrustPolicy
from selection_fixtures import claims_fixture, trust_policy_for


def authenticate(claims, source):
    def fixture_verifier(path):
        return claims
    return authenticate_selection(source, fixture_verifier, trust_policy=trust_policy_for(fixture_verifier))


def decoder_fixture(directory):
    claims, checkpoint, source = claims_fixture(directory)
    equality = Path(directory)/'synthetic-equality.json'
    timing = Path(directory)/'synthetic-timing.json'
    equality.write_text('{"fixture_only": true, "equality": true}')
    timing.write_text('{"fixture_only": true, "timing": true}')
    hashes = source_hashes()
    binding = DecoderBinding(IMPLEMENTATION, hashes, closure_hash(hashes),
        ProofReference(str(equality), sha256(equality)), ProofReference(str(timing), sha256(timing)),
        (current_scope('cpu'),))
    pins = dict(claims.source_hashes)
    pins.update({str((ROOT/name).resolve()): value for name, value in hashes})
    pins.update({str(equality): sha256(equality), str(timing): sha256(timing)})
    return replace(claims, decoder_admitted=True, decoder_binding=binding, source_hashes=pins), checkpoint, source


class ReviewValidationTests(unittest.TestCase):
    def test_event_thresholds_refuse_default_key_and_grid_failures(self):
        invalid = [{}, None, {'Knight': .3}, {'default': .3, 'Unknown': .5},
            {'default': .3, ' Knight': .5}]
        for value in (True, False, float('nan'), float('inf'), .55, 0., 1., '.5'):
            invalid += [{'default': value}, {'default': .3, 'Knight': value}]
        with tempfile.TemporaryDirectory() as directory:
            for thresholds in invalid:
                with self.subTest(thresholds=thresholds):
                    claims, _, source = claims_fixture(directory, event_thresholds=thresholds)
                    with self.assertRaises(ValueError):
                        authenticate(claims, source)

    def test_selected_event_map_and_calibration_preserved_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            values = {'default': [[.1, 0.], [.5, .2], [1., 1.]], 'Knight': [[.2, .3], [.8, .7]]}
            thresholds = {'default': .3, 'Knight': .9}
            claims, _, source = claims_fixture(directory, event_thresholds=thresholds, calibration=values)
            selection = authenticate(claims, source)
            self.assertEqual(json.loads(selection.event_thresholds_json), thresholds)
            self.assertEqual(json.loads(selection.calibration_json), values)
            values['default'][0][1] = .9
            self.assertEqual(json.loads(selection.calibration_json)['default'][0], [.1, 0.])

    def test_spell_subset_metadata_and_order_refuse_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            for spells in ((), ('Knight',), ('Zap', 'Zap'), ('Unknown',)):
                with self.subTest(spells=spells):
                    claims, _, source = claims_fixture(directory, spells=spells)
                    with self.assertRaises(ValueError):
                        authenticate(claims, source)
            claims, _, source = claims_fixture(directory, cards=('Knight', 'Fireball', 'Zap'),
                                               spells=('Zap', 'Fireball'))
            with self.assertRaisesRegex(ValueError, 'Spell subset/order'):
                authenticate(claims, source)
            claims, _, source = claims_fixture(directory)
            pins = dict(claims.source_hashes)
            pins.pop(str((ROOT/'gamedata.json').resolve()))
            with self.assertRaisesRegex(ValueError, 'game-data source hash'):
                authenticate(replace(claims, source_hashes=pins), source)

    def test_calibration_refuses_malformed_or_unjustified_raw_operation(self):
        invalid = [None, {}, {'Unknown': [[0., 0.]]}, {'Knight': [[0., 0.]]}]
        invalid += [{'default': knots} for knots in ([], None, True, [[.2]], [[.1, .2, .3]],
            [[True, .2]], [[.2, float('nan')]], [[-.1, .2]], [[.2, 1.1]],
            [[.2, .3], [.1, .4]], [[.2, .3], [.2, .4]], [[.2, .3], [.8, .2]])]
        with tempfile.TemporaryDirectory() as directory:
            for values in invalid:
                with self.subTest(calibration=values):
                    claims, _, source = claims_fixture(directory, calibration=values)
                    with self.assertRaises(ValueError):
                        authenticate(claims, source)
            claims, _, source = claims_fixture(directory)
            with self.assertRaises(ValueError):
                authenticate(replace(claims, calibration_binding=None), source)
            with self.assertRaises(ValueError):
                authenticate(replace(claims, calibration_binding=replace(claims.calibration_binding,
                                                                          minimum_per_card_support=10)), source)
            with self.assertRaises(ValueError):
                authenticate(replace(claims, calibration_binding=replace(claims.calibration_binding,
                    proof=ProofReference('unbound-proof', '0'*64))), source)

    def test_empty_calibration_requires_explicit_bound_measured_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            claims, _, source = claims_fixture(directory, calibration={})
            claims = replace(claims, calibration_binding=replace(claims.calibration_binding,
                                                                 raw_fallback_authorized=True))
            selection = authenticate(claims, source)
            self.assertEqual(json.loads(selection.calibration_json), {})
            self.assertTrue(selection.provenance()['calibration_binding']['raw_fallback_authorized'])


class DecoderBindingTests(unittest.TestCase):
    def test_bare_boolean_and_wrong_source_identity_or_proof_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            claims, _, source = claims_fixture(directory, decoder_admitted=True)
            with self.assertRaisesRegex(ValueError, 'Bare decoder_admitted'):
                authenticate(claims, source)
            claims, _, source = decoder_fixture(directory)
            binding = claims.decoder_binding
            for bad in (replace(binding, implementation='other-decoder'),
                        replace(binding, source_closure_sha256='0'*64),
                        replace(binding, source_hashes=binding.source_hashes[:-1]),
                        replace(binding, scopes=()),
                        replace(binding, equality_proof=ProofReference('unbound', '0'*64)),
                        replace(binding, timing_proof=ProofReference('unbound', '0'*64))):
                with self.subTest(binding=bad), self.assertRaises(ValueError):
                    authenticate(replace(claims, decoder_binding=bad), source)

    def test_scope_covers_only_exact_device_platform_backend_and_torch(self):
        with tempfile.TemporaryDirectory() as directory:
            claims, _, source = decoder_fixture(directory)
            selection = authenticate(claims, source)
            self.assertTrue(qualify(selection, {'vectorized_decoder': True, 'device': 'cpu'})['decoder_admitted'])
            for device in ('mps', 'cuda'):
                with self.subTest(device=device), self.assertRaisesRegex(ValueError, 'scope'):
                    qualify(selection, {'vectorized_decoder': True, 'device': device})
            scope = claims.decoder_binding.scopes[0]
            for bad in (replace(scope, platform='darwin/arm64'), replace(scope, backend='other-backend'),
                        replace(scope, torch_version='other-version')):
                binding = replace(claims.decoder_binding, scopes=(bad,))
                changed = authenticate(replace(claims, decoder_binding=binding), source)
                with self.assertRaisesRegex(ValueError, 'scope'):
                    qualify(changed, {'vectorized_decoder': True, 'device': 'cpu'})

    def test_diagnostic_label_and_closure_do_not_claim_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            claims, _, source = claims_fixture(directory)
            result = qualify(authenticate(claims, source), dict(vectorized_decoder=True,
                             decoder_diagnostic=True, device='cpu'))
            self.assertEqual(result['scope'], 'unadmitted-decoder-diagnostic-qualification')
            self.assertFalse(result['decoder_admitted'])
            self.assertEqual(result['source_closure_sha256'], closure_hash(source_hashes()))

    def test_direct_pixel_wrapper_keeps_diagnostic_label(self):
        from clasher.live.perception import V4Perception
        with tempfile.TemporaryDirectory() as directory:
            claims, checkpoint, source = claims_fixture(directory)
            selection = authenticate(claims, source)
            runtime = SimpleNamespace(PixelPerception=MagicMock())
            with patch('torch.load', return_value={'cards': list(claims.cards),
                    'bodies': list(claims.bodies), 'model': {}}), \
                 patch('clasher.vision.l1_v4.PerceptionV4', return_value=MagicMock()), \
                 patch('clasher.live.perception_adapter.vectorized_runtime', return_value=(runtime, object())):
                sensor = V4Perception(dict(checkpoint=str(checkpoint), authenticated_selection=selection,
                                          vectorized_decoder=True, decoder_diagnostic=True, device='cpu'))
            self.assertEqual(sensor.qualification, 'unadmitted-decoder-diagnostic-qualification')
            self.assertFalse(sensor.decoder_provenance['decoder_admitted'])


class ExternalTrustTests(unittest.TestCase):
    def test_unset_policy_and_changed_external_pin_refuse_before_callback(self):
        called = []
        def verifier(source):
            called.append(source)
            return {'claimed_policy': 'trusted'}
        with self.assertRaisesRegex(ValueError, 'Externally pinned'):
            authenticate_selection('arbitrary-seal', verifier)
        policy = trust_policy_for(verifier)
        pin = next(p for p in policy.modules if p.name == verifier.__module__)
        bad = replace(policy, modules=tuple(replace(p, sha256='0'*64) if p == pin else p for p in policy.modules))
        with self.assertRaisesRegex(ValueError, 'before invocation'):
            authenticate_selection('arbitrary-seal', verifier, trust_policy=bad)
        self.assertEqual(called, [])

    def test_policy_rejects_different_entrypoint_before_import(self):
        def verifier(source):
            raise AssertionError('not called')
        with self.assertRaisesRegex(ValueError, 'externally pinned'):
            load_authenticated_selection('seal', 'untrusted_module:verify', trust_policy=trust_policy_for(verifier))
        self.assertNotIn('untrusted_module', sys.modules)

    def test_changed_import_closure_is_checked_before_verifier_module_executes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root/'imported'
            owner = root/'synthetic_owner_verifier.py'
            dependency = root/'synthetic_owner_dependency.py'
            owner.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n'
                             'def verify(source): return None\n')
            dependency.write_text('VALUE = 1\n')
            policy = VerifierTrustPolicy('synthetic_owner_verifier:verify', (
                ModulePin('synthetic_owner_verifier', str(owner), sha256(owner)),
                ModulePin('synthetic_owner_dependency', str(dependency), sha256(dependency))))
            dependency.write_text('VALUE = 2\n')
            with patch.object(sys, 'path', [directory, *sys.path]), self.assertRaisesRegex(ValueError, 'before invocation'):
                load_authenticated_selection('seal', policy.entrypoint, trust_policy=policy)
            self.assertFalse(marker.exists())
            self.assertNotIn('synthetic_owner_verifier', sys.modules)

    def test_loaded_namespace_redirection_is_rejected(self):
        import clasher.mechanics as namespace
        def verifier(source):
            raise AssertionError('not called')
        policy = trust_policy_for(verifier)
        with patch.object(namespace, '__path__', ['/untrusted-namespace']), \
             self.assertRaisesRegex(ValueError, 'namespace'):
            authenticate_selection('seal', verifier, trust_policy=policy)


if __name__ == '__main__':
    unittest.main()
