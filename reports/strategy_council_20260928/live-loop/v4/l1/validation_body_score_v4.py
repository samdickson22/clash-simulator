"""Score authenticated full-validation body tracks; no threshold seal or heldout.

Event replay admission authenticates the producer, complete formal fit, every
validation episode and measured FIFO completion. Body labels are private scorer
inputs only; inference has already finished and its files are immutable.
"""
import argparse
import json
from pathlib import Path

from body_scoring_v4 import BodyTruth, POLICY, score_frame, summarize
from validation_admission_v4 import read, sha
from validation_score_v4 import load_replay, rows


def score_run(args):
    loaded = load_replay(args)  # First: fail closed before opening body payloads.
    from labels_v4 import BodyLabels, read_objects
    code = Path(__file__).resolve().parent
    root = code.parents[4]
    sources = [Path(__file__), code/'body_scoring_v4.py', code/'labels_v4.py',
               code/'validation_score_v4.py', code/'validation_replay_v4.py',
               root/'gamedata.json', code.parent/'body-catalog.json']
    pins = {str(p): sha(p) for p in sources}
    cleaner = BodyLabels(root/'gamedata.json', code.parent/'body-catalog.json')
    per_match, truth_files, all_counts = {}, {}, []
    for ep in loaded['episodes']:
        folder = args.source/ep
        receipt_path = folder/'receipt.json'
        if sha(receipt_path) != loaded['admission']['validation_receipt_sha256'][ep]:
            raise ValueError('Validation receipt changed before body scoring')
        receipt = read(receipt_path)
        if receipt['split'] != 'validation' or receipt['episode'] != ep:
            raise ValueError('Body scorer only admits validation')
        filenames = ('frames.jsonl', 'objects.jsonl.gz', 'rich-objects.jsonl.gz')
        expected = {name: receipt['files'][name] for name in filenames}
        if any(sha(folder/name) != digest for name, digest in expected.items()):
            raise ValueError('Body truth payload hash changed')
        truth = BodyTruth(cleaner.clean(read_objects(folder/'objects.jsonl.gz'),
                                       read_objects(folder/'rich-objects.jsonl.gz')))
        frames = rows(folder/'frames.jsonl')
        output_path = args.replay/f'{ep}-outputs.jsonl'
        expected_output = read(args.replay/'complete.json')['files_sha256'][output_path.name]
        if sha(output_path) != expected_output:
            raise ValueError('Replay body payload changed')
        outputs = rows(output_path)
        if len(outputs) != len(frames) or len(frames) != receipt['frames']:
            raise ValueError('Body/frame population differs')
        counts = []
        for i, (frame, output) in enumerate(zip(frames, outputs)):
            if (type(output.get('source_seq')) is not int or output['source_seq'] != i
                    or frame['seq'] != i or output['payload']['episode_id'] != ep):
                raise ValueError('Body replay identity mismatch')
            tick = (frame['tick_lo']+frame['tick_hi'])/2
            counts.append(score_frame(output['payload']['tracks'], truth.at(tick)))
        if (sha(output_path) != expected_output
                or any(sha(folder/name) != digest for name, digest in expected.items())):
            raise ValueError('Body inputs changed during scoring')
        per_match[ep] = summarize(counts)
        all_counts.extend(counts)
        truth_files[ep] = expected
    if (any(sha(Path(p)) != digest for p, digest in pins.items())
            or sha(args.replay/'manifest.json') != loaded['replay_manifest_sha256']
            or sha(args.replay/'complete.json') != loaded['replay_completion_sha256']):
        raise ValueError('Body source or replay provenance changed during scoring')
    manifest = loaded['manifest']
    return dict(schema='clasher.v4.validation-body-score.v1', readiness=loaded['admission'],
                epoch=manifest['epoch'], body_threshold=manifest['body_threshold'],
                event_thresholds=loaded['thresholds'], policy=POLICY,
                micro=summarize(all_counts), per_match=per_match,
                validation_receipts=loaded['admission']['validation_receipt_sha256'],
                truth_payloads=truth_files, sources=pins,
                replay_manifest_sha256=loaded['replay_manifest_sha256'],
                replay_completion_sha256=loaded['replay_completion_sha256'],
                selection_seal=False, heldout_opening_authorized=False,
                heldout_payloads_opened=False,
                scope='body-threshold scoring preparation; source-frame alignment, not availability or Mac gate',
                pending=['complete nine-threshold validation grid', 'authenticate body selection',
                         'final selection seal'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('run', 'source', 'split', 'phase-state', 'phase-exit', 'replay', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = score_run(args)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
