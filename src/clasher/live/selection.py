"""Live selection handoff from an independently trusted owner authenticator.

This module does not interpret or authenticate a final joint seal: that format
is owned elsewhere and still pending. JSON, calibration and flags cannot mint
authority. A trusted code-level verifier must authenticate the final evidence
and return normalized claims; this boundary then checks the artifact bindings.
"""
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
import math
from pathlib import Path
from .decoder_binding import DecoderBinding, validate_binding
from .loading import ROOT
from .selection_trust import require_policy
from .selection_validation import (CalibrationBinding, bound_proof, calibration,
                                   event_thresholds, runtime_bindings, spell_routing)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_threshold(value):
    if (type(value) not in (int, float) or not math.isfinite(value) or
            value not in [i/10 for i in range(1, 10)]):
        raise ValueError('Selected body_threshold must be numeric, not bool, on the registered 0.1..0.9 grid')
    return value


@dataclass(frozen=True)
class SelectionClaims:
    """Owner verifier's normalized output, never itself live authority."""
    final_joint: bool
    checkpoint_sha256: str
    cards: tuple
    bodies: tuple
    spells: tuple
    body_threshold: float
    event_thresholds: dict
    calibration: dict
    selection_sha256: str
    source_hashes: dict
    decoder_admitted: bool = False
    decoder_binding: DecoderBinding | None = None
    calibration_binding: CalibrationBinding | None = None


_AUTHENTICATED = object()


@dataclass(frozen=True, init=False)
class AuthenticatedSelection:
    checkpoint_sha256: str
    cards: tuple
    bodies: tuple
    spells: tuple
    body_threshold: float
    event_thresholds_json: str
    calibration_json: str
    selection_path: str
    selection_sha256: str
    source_hashes: tuple
    verifier_path: str
    verifier_sha256: str
    decoder_admitted: bool
    decoder_binding: DecoderBinding | None
    calibration_binding: CalibrationBinding
    verifier_import_hashes: tuple
    verifier_namespace_paths: tuple

    def __init__(self, claims, source, policy, token=None):
        if token is not _AUTHENTICATED:
            raise ValueError('Selection requires separate final joint authentication')
        values = dict(checkpoint_sha256=claims.checkpoint_sha256,
                      cards=tuple(claims.cards), bodies=tuple(claims.bodies), spells=tuple(claims.spells),
                      body_threshold=body_threshold(claims.body_threshold),
                      event_thresholds_json=json.dumps(claims.event_thresholds, sort_keys=True, allow_nan=False),
                      calibration_json=json.dumps(claims.calibration, sort_keys=True, allow_nan=False),
                      selection_path=str(Path(source).resolve()), selection_sha256=claims.selection_sha256,
                      source_hashes=tuple(sorted((str(Path(p).resolve()), h) for p, h in claims.source_hashes.items())),
                      verifier_path=str(Path(next(p.path for p in policy.modules
                          if p.name == policy.entrypoint.split(':')[0])).resolve()),
                      verifier_sha256=next(p.sha256 for p in policy.modules
                          if p.name == policy.entrypoint.split(':')[0]),
                      decoder_admitted=claims.decoder_admitted, decoder_binding=claims.decoder_binding,
                      calibration_binding=claims.calibration_binding, verifier_import_hashes=policy.hashes(),
                      verifier_namespace_paths=policy.namespaces())
        for key, value in values.items():
            object.__setattr__(self, key, value)
        self.check_sources()

    def check_sources(self):
        for path, expected in ((self.selection_path, self.selection_sha256),
                               *self.verifier_import_hashes, *self.source_hashes):
            if sha256(path) != expected:
                raise ValueError('Authenticated selection/source hash changed: '+path)

    def bind_checkpoint(self, checkpoint_bytes, state):
        self.check_sources()
        if hashlib.sha256(checkpoint_bytes).hexdigest() != self.checkpoint_sha256:
            raise ValueError('Authenticated selection checkpoint SHA mismatch')
        if tuple(state['cards']) != self.cards or tuple(state['bodies']) != self.bodies:
            raise ValueError('Authenticated selection vocabulary mismatch')

    def provenance(self):
        return dict(schema='clasher.live.authenticated-selection-handoff.v1',
                    checkpoint_sha256=self.checkpoint_sha256, cards=self.cards, bodies=self.bodies,
                    spells=self.spells, body_threshold=self.body_threshold,
                    event_thresholds=json.loads(self.event_thresholds_json),
                    calibration=json.loads(self.calibration_json),
                    selection_path=self.selection_path, selection_sha256=self.selection_sha256,
                    source_hashes=dict(self.source_hashes), verifier_path=self.verifier_path,
                    verifier_sha256=self.verifier_sha256, verifier_import_hashes=dict(self.verifier_import_hashes),
                    verifier_namespace_paths=dict(self.verifier_namespace_paths),
                    calibration_binding=asdict(self.calibration_binding), decoder_admitted=self.decoder_admitted,
                    decoder_binding=asdict(self.decoder_binding) if self.decoder_binding else None)


def authenticate_selection(source, verifier, *, trust_policy=None):
    """Call trusted owner code, then freeze its normalized, artifact-bound view.

The verifier must independently establish final joint authority, threshold and
decoder admission from actual evidence. Its output declarations alone are not
an authentication algorithm. No built-in verifier or JSON fallback exists.
"""
    policy = require_policy(trust_policy)
    policy.check_callable(verifier)  # Trust pins are external; checked BEFORE invocation.
    claims = verifier(Path(source))
    policy.check_callable(verifier)
    if type(claims) is not SelectionClaims or claims.final_joint is not True:
        raise ValueError('Authenticated final joint selection required; T7-only receipts are insufficient')
    if type(claims.decoder_admitted) is not bool or not claims.source_hashes:
        raise ValueError('Selection must bind source hashes and decoder admission')
    digests = (claims.checkpoint_sha256, claims.selection_sha256, *claims.source_hashes.values())
    if any(type(h) is not str or len(h) != 64 or any(c not in '0123456789abcdef' for c in h) for h in digests):
        raise ValueError('Selection requires complete SHA256 bindings')
    for vocabulary in (claims.cards, claims.bodies, claims.spells):
        if any(type(v) is not str or not v for v in vocabulary) or len(set(vocabulary)) != len(vocabulary):
            raise ValueError('Selection requires exact ordered vocabulary')
    if not claims.cards or not claims.bodies or type(claims.event_thresholds) is not dict or type(claims.calibration) is not dict:
        raise ValueError('Selection is incomplete')
    source_hashes = {str(Path(path).resolve()): h for path, h in claims.source_hashes.items()}
    runtime_bindings(source_hashes)
    event_thresholds(claims.event_thresholds, claims.cards)
    spell_routing(claims.cards, claims.spells, source_hashes)
    calibration(claims.calibration, claims.cards, claims.calibration_binding)
    bound_proof(claims.calibration_binding.proof, source_hashes)
    if claims.decoder_admitted != (claims.decoder_binding is not None):
        raise ValueError('Bare decoder_admitted boolean cannot establish admission')
    if claims.decoder_binding is not None:
        validate_binding(claims.decoder_binding)
        for name, digest in claims.decoder_binding.source_hashes:
            if source_hashes.get(str((ROOT/name).resolve())) != digest:
                raise ValueError('Decoder implementation sources must be bound by the selection')
        bound_proof(claims.decoder_binding.equality_proof, source_hashes)
        bound_proof(claims.decoder_binding.timing_proof, source_hashes)
    return AuthenticatedSelection(claims, source, policy, _AUTHENTICATED)


def load_authenticated_selection(source, authenticator, *, trust_policy=None):
    """Explicit trusted module:function hook; pending owner code means refusal."""
    if not source or not authenticator:
        raise ValueError('V4 requires a separately authenticated final joint selection')
    policy = require_policy(trust_policy)
    policy.check(authenticator)  # Check closure/hash/resolution before importing owner code.
    name, attribute = authenticator.rsplit(':', 1)
    return authenticate_selection(source, getattr(importlib.import_module(name), attribute), trust_policy=policy)


def require_selection(config):
    selection = config.get('authenticated_selection')
    if type(selection) is not AuthenticatedSelection:
        raise ValueError('V4 requires a separately authenticated final joint selection')
    selection.check_sources()
    return selection
