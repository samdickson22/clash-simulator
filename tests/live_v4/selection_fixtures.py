"""Synthetic selection handoff fixtures; never formal seal authentication."""
from pathlib import Path
from clasher.live.selection import SelectionClaims, authenticate_selection, sha256


def selection_fixture(directory, cards=('Knight', 'Zap'), bodies=('Knight',), **overrides):
    directory = Path(directory)
    checkpoint = directory/'synthetic-checkpoint.bin'
    checkpoint.write_bytes(b'synthetic checkpoint; no model or formal evidence')
    source = directory/'synthetic-selection.json'
    source.write_text('{"fixture_only": true}')
    evidence = directory/'synthetic-source.json'
    evidence.write_text('{"synthetic": true}')
    claims = SelectionClaims(final_joint=True, checkpoint_sha256=sha256(checkpoint), cards=tuple(cards),
        bodies=tuple(bodies), spells=('Zap',), body_threshold=.7, event_thresholds={'default': .1},
        calibration={}, selection_sha256=sha256(source), source_hashes={str(evidence): sha256(evidence)},
        **overrides)
    def fixture_verifier(path):
        if path != source:
            raise ValueError('Wrong synthetic fixture')
        return claims
    return authenticate_selection(source, fixture_verifier), checkpoint
