"""Synthetic selection handoff fixtures; never formal seal authentication."""
from pathlib import Path
import sys
from clasher.live.decoder_binding import ProofReference
from clasher.live.loading import ROOT
from clasher.live.selection import SelectionClaims, authenticate_selection, sha256
from clasher.live.selection_trust import ModulePin, VerifierTrustPolicy
from clasher.live.selection_validation import CalibrationBinding, runtime_sources


def trust_policy_for(verifier):
    names = [name for name in sys.modules if name == verifier.__module__ or
             name == 'selection_fixtures' or name == 'clasher' or name.startswith('clasher.')]
    pins = tuple(ModulePin(name, str(Path(sys.modules[name].__file__).resolve()),
                           sha256(sys.modules[name].__file__)) for name in sorted(names)
                 if getattr(sys.modules[name], '__file__', None) and str(sys.modules[name].__file__).endswith('.py'))
    pins += tuple(ModulePin(name, str(Path(next(iter(sys.modules[name].__path__))).resolve()), None)
                  for name in sorted(names) if getattr(sys.modules[name], '__file__', None) is None
                  and getattr(sys.modules[name], '__path__', None))
    return VerifierTrustPolicy(verifier.__module__+':'+verifier.__qualname__, pins)


def claims_fixture(directory, cards=('Knight', 'Zap'), bodies=('Knight',), **overrides):
    directory = Path(directory)
    checkpoint = directory/'synthetic-checkpoint.bin'
    checkpoint.write_bytes(b'synthetic checkpoint; no model or formal evidence')
    source = directory/'synthetic-selection.json'
    source.write_text('{"fixture_only": true}')
    evidence = directory/'synthetic-source.json'
    evidence.write_text('{"synthetic": true}')
    from clasher.data import CardDataLoader
    loader = CardDataLoader(ROOT/'gamedata.json')
    values = dict(final_joint=True, checkpoint_sha256=sha256(checkpoint), cards=tuple(cards),
        bodies=tuple(bodies), spells=tuple(c for c in cards if loader.get_card(c)._raw_entry['id']//1000000 == 28),
        body_threshold=.7, event_thresholds={'default': .1}, calibration={'default': [[0., 0.], [1., 1.]]},
        selection_sha256=sha256(source), source_hashes={**runtime_sources(), str(evidence): sha256(evidence),
            str((ROOT/'gamedata.json').resolve()): sha256(ROOT/'gamedata.json')},
        calibration_binding=CalibrationBinding(ProofReference(str(evidence), sha256(evidence))))
    values.update(overrides)
    return SelectionClaims(**values), checkpoint, source


def selection_fixture(directory, cards=('Knight', 'Zap'), bodies=('Knight',), **overrides):
    claims, checkpoint, source = claims_fixture(directory, cards, bodies, **overrides)
    def fixture_verifier(path):
        if path != source:
            raise ValueError('Wrong synthetic fixture')
        return claims
    return authenticate_selection(source, fixture_verifier, trust_policy=trust_policy_for(fixture_verifier)), checkpoint
