"""Frozen threshold, spell-routing and isotonic structure checks; never fitting."""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from .decoder_binding import ProofReference
from .loading import ROOT


RUNTIME_SOURCES = ('src/clasher/vision/l1_v4.py', 'src/clasher/live/perception.py',
    'src/clasher/live/perception_adapter.py', 'src/clasher/live/loading.py',
    'src/clasher/live/selection.py', 'src/clasher/live/selection_validation.py',
    'src/clasher/live/selection_trust.py', 'src/clasher/live/decoder_binding.py',
    'src/clasher/data.py', 'src/clasher/card_aliases.py', 'src/clasher/card_types.py',
    'src/clasher/paths.py', 'src/clasher/balance.py', 'src/clasher/gamedata_normalization.py')


def runtime_sources():
    paths = [ROOT/name for name in RUNTIME_SOURCES]
    paths += list((ROOT/'src/clasher/factory').glob('*.py'))
    return {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def runtime_bindings(source_hashes):
    if any(source_hashes.get(path) != digest for path, digest in runtime_sources().items()):
        raise ValueError('Selected runtime/routing sources differ from their sealed bindings')


def threshold(value):
    if (type(value) not in (int, float) or not math.isfinite(value) or
            value not in [i/10 for i in range(1, 10)]):
        raise ValueError('Selected threshold must be numeric, not bool, on the frozen 0.1..0.9 grid')
    return value


def event_thresholds(values, cards):
    if type(values) is not dict or 'default' not in values:
        raise ValueError('Selected event_thresholds requires explicit default')
    if set(values)-set(cards)-{'default'}:
        raise ValueError('Selected event_thresholds has unknown card keys')
    for value in values.values():
        threshold(value)


def spell_routing(cards, spells, source_hashes):
    path = (ROOT/'gamedata.json').resolve()
    if source_hashes.get(str(path)) != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('Spell routing requires the sealed game-data source hash')
    from clasher.data import CardDataLoader
    loader = CardDataLoader(path)
    rows = {card: loader.get_card(card) for card in cards}
    if any(row is None or type(row._raw_entry.get('id')) is not int for row in rows.values()):
        raise ValueError('Card vocabulary outside sealed public metadata')
    # Same fixed 28 namespace routing as frozen validation_replay_v4.
    expected = tuple(card for card in cards if rows[card]._raw_entry['id']//1000000 == 28)
    if tuple(spells) != expected:
        raise ValueError('Spell subset/order differs from sealed public metadata')


@dataclass(frozen=True)
class CalibrationBinding:
    proof: ProofReference
    minimum_per_card_support: int = 20
    raw_fallback_authorized: bool = False


def calibration(values, cards, binding):
    if (type(binding) is not CalibrationBinding or type(binding.proof) is not ProofReference
            or type(binding.minimum_per_card_support) is not int or binding.minimum_per_card_support != 20
            or type(binding.raw_fallback_authorized) is not bool):
        raise ValueError('Measured calibration/support/fallback binding required')
    if type(values) is not dict or set(values)-set(cards)-{'default'}:
        raise ValueError('Selected calibration must map known cards/default to knots')
    if ('default' not in values or not values['default']) and not binding.raw_fallback_authorized:
        raise ValueError('Missing pooled calibration requires authenticated measured raw-fallback policy')
    for knots in values.values():
        if type(knots) not in (list, tuple) or (not knots and not binding.raw_fallback_authorized):
            raise ValueError('Calibration knots require measured fallback or supported pairs')
        previous = None
        for pair in knots:
            if (type(pair) not in (list, tuple) or len(pair) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in pair)):
                raise ValueError('Calibration knots require finite numeric [0,1] pairs')
            x, y = pair
            if previous is not None and (x <= previous[0] or y < previous[1]):
                raise ValueError('Calibration knots must have increasing x and nondecreasing y')
            previous = pair


def bound_proof(proof, source_hashes):
    if (type(proof) is not ProofReference or
            source_hashes.get(str(Path(proof.path).resolve())) != proof.sha256):
        raise ValueError('Proof reference must be bound by selected source hashes')
