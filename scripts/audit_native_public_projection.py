"""Measure public projection coverage on opened native development captures."""
import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import (
    NativeProjectileCatalog,
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicProjectionError,
    NativePublicScope,
)
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.structured_obs import StructuredObservationBuilder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='append', type=Path, required=True)
    parser.add_argument('--entity-levels', action='store_true')
    parser.add_argument('--rich', action='append', type=Path, default=[])
    parser.add_argument('--projectile-catalog', type=Path)
    parser.add_argument('--projectile-catalog-sha256')
    parser.add_argument('--gamedata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    captures = [(p, json.loads(p.read_text())) for p in args.capture]
    rich_by_source = {}
    level_authorities = {}
    for directory in args.rich:
        manifest = json.loads((directory / 'manifest.json').read_text())
        frames_path = directory / 'frames.jsonl.gz'
        if not manifest['complete'] or not manifest['attestation_unchanged'] or hashlib.sha256(frames_path.read_bytes()).hexdigest() != manifest['frames_sha256']:
            raise ValueError('incomplete or changed rich capture')
        with gzip.open(frames_path, 'rt') as stream:
            frames = [json.loads(line) for line in stream]
        by_tick = {r['ordinary']['tick']: r for r in frames}
        if len(by_tick) != len(frames) or sorted(by_tick) != manifest['verified_checkpoint_ticks']:
            raise ValueError('rich checkpoint coverage mismatch')
        rich_by_source[manifest['source_result_sha256']] = (directory, by_tick)
        if args.entity_levels:
            reader_hash = hashlib.sha256((directory / 'level-reader.py').read_bytes()).hexdigest()
            attestation = json.loads((directory / 'attestation.json').read_text())['attestation']
            level_authorities[manifest['source_result_sha256']] = (reader_hash, attestation)
    catalog = None
    if args.projectile_catalog is not None:
        catalog = NativeProjectileCatalog.from_csv(args.projectile_catalog, expected_sha256=args.projectile_catalog_sha256)
    loader = CardDataLoader(args.gamedata)
    card_names = {c._raw_entry['id']: name for name, c in loader.load_cards().items()}
    for path, capture in captures:
        if 'decks' not in capture:
            plan_path = path.parent / 'plan.json'
            plan = json.loads(plan_path.read_text())
            capture['decks'] = [[card_names[c['d']] for c in plan['config']['battle'][f'deck{owner}']['sp']] for owner in (0, 1)]
            capture['deck_source'] = {'path': str(plan_path), 'sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest()}
    # One vocabulary across the whole declared development collection.
    names_by_id = {loader.get_card(n)._raw_entry['id']: n for _, c in captures for deck in c['decks'] for n in deck}
    names = tuple(sorted(names_by_id.values()))
    builder = StructuredObservationBuilder(card_loader=loader, card_vocab=list(names), canonical_lane_globals=True, public_entity_levels=args.entity_levels)
    if catalog is not None:
        tokens = ['<pad>', '<unknown>', *sorted(set(builder.token_names[2:]) | set(catalog.names))]
        builder = StructuredObservationBuilder(card_loader=loader, card_vocab=list(names), token_names=tokens, canonical_lane_globals=True, public_entity_levels=args.entity_levels)
    adapter = NativePublicObservationAdapter(builder, NativePublicScope('15.535.86', hashlib.sha256(args.gamedata.read_bytes()).hexdigest()), card_names=names, projectile_catalog=catalog)
    masks = PublicActionMaskBuilder(builder)
    games = []
    for path, capture in captures:
        failures, accepted, examples = Counter(), 0, {}
        source_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rich_directory, rich_frames = rich_by_source.get(source_digest, (None, {}))
        histories = [None, None]
        commands = iter(sorted(capture['commands'], key=lambda c: c['execution_tick']))
        pending = next(commands, None)
        for checkpoint in capture['checkpoints']:
            while pending is not None and pending['execution_tick'] <= checkpoint['tick']:
                if pending.get('native_acceptance_spend_evidence') is not True:
                    raise ValueError('own history requires native acceptance evidence')
                if loader.get_card(pending['name'])._raw_entry['id'] != 28000006:
                    histories[pending['owner']] = AcceptedOwnPlay(pending['name'], pending['cost'])
                pending = next(commands, None)
            for owner in (0, 1):
                try:
                    rich_pair = rich_frames.get(checkpoint['tick'])
                    evidence = None
                    if args.entity_levels:
                        if rich_pair is None or 'level_source' not in rich_pair:
                            raise ValueError('level-aware audit requires paired level capture')
                        level_source = rich_pair['level_source']
                        ordinary = rich_pair['ordinary']
                        reader_hash, attestation = level_authorities[source_digest]
                        if level_source['reader_sha256'] != reader_hash or level_source['attestation'] != attestation:
                            raise ValueError('level reader source or attestation mismatch')
                        if level_source['ordinary'] != ordinary:
                            raise ValueError('level evidence frame mismatch')
                        levels = {int(k): v for k, v in level_source['levels'].items()}
                        evidence = NativePublicLevelEvidence(
                            tick=ordinary['tick'], generation=ordinary['generation'], state_epoch=ordinary['stateEpoch'],
                            source_sha256=hashlib.sha256(json.dumps(level_source, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                            levels=levels, confidence={k: 1.0 for k in levels},
                        )
                    projected = adapter.project(rich_pair['ordinary'] if rich_pair else checkpoint['native'], owner, rich_snapshot=rich_pair['rich'] if rich_pair else None, level_evidence=evidence, own_last_play=histories[owner])
                    mask = masks.build(PublicActionMaskInput.from_confidence_observation(projected))
                    assert mask[masks.no_op_action]
                    accepted += 1
                except NativePublicProjectionError as error:
                    reason = str(error)
                    failures[reason] += 1
                    examples.setdefault(reason, checkpoint['tick'])
        games.append({'rich_source': str(rich_directory) if rich_directory else None, 'source': str(path), 'deck_source': capture.get('deck_source', 'embedded'), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'own_history_from_confirmed_commands': True, 'perspective_frames': len(capture['checkpoints']) * 2, 'projected': accepted,
                      'rejections': dict(failures), 'first_rejection_ticks': examples})
    report = {'scope': 'Opened development coverage only; rejected frames are not dropped training examples. No acceptance claim.',
              'entity_levels': args.entity_levels, 'projectile_catalog_sha256': catalog.sha256 if catalog else None, 'ruleset_sha256': adapter.scope.ruleset_sha256, 'cards': names, 'token_names': builder.token_names, 'games': games}
    with args.output.open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(games, indent=2))


if __name__ == '__main__':
    main()
