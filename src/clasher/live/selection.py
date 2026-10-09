"""Live selection handoff from an independently trusted owner authenticator.

This module does not interpret or authenticate a final joint seal: that format
is owned elsewhere and still pending. JSON, calibration and flags cannot mint
authority. A trusted code-level verifier must authenticate the final evidence
and return normalized claims; this boundary then checks the artifact bindings.
"""
from dataclasses import dataclass
import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path


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

    def __init__(self, claims, source, verifier_path, token=None):
        if token is not _AUTHENTICATED:
            raise ValueError('Selection requires separate final joint authentication')
        values = dict(checkpoint_sha256=claims.checkpoint_sha256,
                      cards=tuple(claims.cards), bodies=tuple(claims.bodies), spells=tuple(claims.spells),
                      body_threshold=body_threshold(claims.body_threshold),
                      event_thresholds_json=json.dumps(claims.event_thresholds, sort_keys=True, allow_nan=False),
                      calibration_json=json.dumps(claims.calibration, sort_keys=True, allow_nan=False),
                      selection_path=str(Path(source).resolve()), selection_sha256=claims.selection_sha256,
                      source_hashes=tuple(sorted((str(Path(p).resolve()), h) for p, h in claims.source_hashes.items())),
                      verifier_path=str(Path(verifier_path).resolve()), verifier_sha256=sha256(verifier_path),
                      decoder_admitted=claims.decoder_admitted)
        for key, value in values.items():
            object.__setattr__(self, key, value)
        self.check_sources()

    def check_sources(self):
        for path, expected in ((self.selection_path, self.selection_sha256),
                               (self.verifier_path, self.verifier_sha256), *self.source_hashes):
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
                    verifier_sha256=self.verifier_sha256, decoder_admitted=self.decoder_admitted)


def authenticate_selection(source, verifier):
    """Call trusted owner code, then freeze its normalized, artifact-bound view.

The verifier must independently establish final joint authority, threshold and
decoder admission from actual evidence. Its output declarations alone are not
an authentication algorithm. No built-in verifier or JSON fallback exists.
"""
    claims = verifier(Path(source))
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
    verifier_path = inspect.getsourcefile(verifier)
    if not verifier_path:
        raise ValueError('Owner authenticator source must be hashable')
    return AuthenticatedSelection(claims, source, verifier_path, _AUTHENTICATED)


def load_authenticated_selection(source, authenticator):
    """Explicit trusted module:function hook; pending owner code means refusal."""
    if not source or not authenticator:
        raise ValueError('V4 requires a separately authenticated final joint selection')
    name, attribute = authenticator.rsplit(':', 1)
    return authenticate_selection(source, getattr(importlib.import_module(name), attribute))


def require_selection(config):
    selection = config.get('authenticated_selection')
    if type(selection) is not AuthenticatedSelection:
        raise ValueError('V4 requires a separately authenticated final joint selection')
    selection.check_sources()
    return selection
