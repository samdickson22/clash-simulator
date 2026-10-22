"""Freeze fresh LIVE-only banks and six launch configs. No engine/model imports.

The input bundle contains the explicit weighted populations, old-bank seed
inventory, pinned audit inputs, runtime locations, and both selected anchors.
Missing scientific inputs fail; they are never generated from planning medians.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bot.pretrain_v1 import rl_schedule as S


def reference(path):
    return dict(path=str(Path(path).resolve()), sha256=S.file_sha(path))


def relocate(config, receipt, mapping, *, mapping_sha256):
    """Rewrite reviewed dependency locations; byte identities stay fixed."""
    S.require(config.get('qualification_only') is True and config['host'] == receipt['host'],
              'only the matching leased qualification config may relocate')
    S.require(mapping_sha256 == receipt['relocated_references_sha256'], 'relocation manifest SHA differs from readiness')
    entries = {r['path']: r for r in mapping['files']}
    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        if isinstance(value, dict):
            if 'path' in value and value['path'] in entries:
                row = entries[value['path']]
                S.require(value['sha256'] == row['sha256'], 'dependency SHA changed during relocation')
                return dict(value, path=row['relocated_path'])
            return {k: rewrite(v) for k, v in value.items()}
        return value
    result = rewrite(copy.deepcopy(config))
    result.update(runtime=receipt['runtime_root'], actor_source=receipt['actor_source_root'])
    for key, value in result['live']['environment'].items():
        original = value
        for source, row in sorted(entries.items(), key=lambda kv: -len(kv[0])):
            value = value.replace(source, row['relocated_path'])
        if key == 'CLASHER_LOPP_MODELS':
            candidates = [r['relocated_path'][:-len(p[len(original):])]
                          for p, r in entries.items() if p.startswith(original+'/')]
            S.require(candidates and len(set(candidates)) == 1, 'unresolved relocated opponent-model directory')
            value = candidates[0]
        result['live']['environment'][key] = value
    return result


def freeze(bundle, out):
    pop = S.validate_populations(json.loads(S.pinned(bundle['populations']).read_text()))
    evaluation_pop = S.validate_populations(json.loads(S.pinned(bundle['evaluation_populations']).read_text()))
    S.require(pop['role'] == 'training-only' and evaluation_pop['role'] == 'evaluation-only'
              and not set(pop['physical_source_ids']) & set(evaluation_pop['physical_source_ids']),
              'training/evaluation historical source identities must be disjoint')
    inventory = json.loads(S.pinned(bundle['excluded_seeds']).read_text())
    S.require(bool(inventory['sources']) and bool(inventory['seeds']), 'complete prior-bank exclusion inventory required')
    for ref in inventory['sources']:
        S.pinned(ref)
    for ref in bundle['audits'].values():
        S.pinned(ref)
    out = Path(out).resolve()
    out.mkdir()  # No overwrite, including a prior failed registration attempt.
    outputs = []
    for seed_index, seed in enumerate(S.SEEDS):
        def bank(phase, count, base):
            rows = []
            for index in range(count):
                kind = S.category(S.LEVELS, S.rng(seed, index, phase+'-level-kind'))
                opponent = S.pick(evaluation_pop['opponents'][kind], S.rng(seed, index, phase+'-profile'))
                seat = index % 2
                decks, cards, towers = [None, None], {}, [None, None]
                for s, deck, levels, tower in ((seat, list(S.HOG), S.HOG, 9),
                                              (1-seat, opponent['deck'], opponent['cards'], opponent['tower'])):
                    decks[s], cards[str(s)], towers[s] = list(deck), dict(levels), tower
                    S.rng(seed, index, phase+f'-order-{s}').shuffle(decks[s])
                rows.append(dict(index=index, seed=base+index, seat=seat, opponent='live', decks=decks,
                    levels=dict(cards=cards, towers=towers, planner='l11'), level_kind=kind,
                    profile_source_id=opponent['source_id']))
            return rows
        base = bundle['evaluation_seed_base']+seed_index*10000
        primary, dev = bank('primary', 1600, base), bank('dev', 200, base+2000)
        banks = dict(schema='pv1-rl-banks-v1', seed=seed, primary=primary,
            dev={str(v): dev for v in (0, 10, 20, 30)}, audits=bundle['audits'],
            audit_input_manifest=bundle['audit_input_manifest'], excluded_engine_seeds=inventory['seeds'],
            exclusion_inventory=bundle['excluded_seeds'], populations=bundle['populations'])
        banks['evaluation_populations'] = bundle['evaluation_populations']
        S.validate_banks(banks, seed)
        bank_path = out/f'banks-{seed}.json'
        bank_path.write_bytes(S.encoded(banks)+b'\n')
        for size in ('M', 'S100'):
            config = copy.deepcopy(bundle['common'])
            config.update(copy.deepcopy(bundle.get('size_overrides', {}).get(size, {})))
            config.update(schema='pv1-rl-launch-v1', size=size, seed=seed,
                host={'M': '127x01', 'S100': '127x02'}[size], anchor=bundle['anchors'][size],
                model_cfg=bundle['model_cfg'][size], populations=bundle['populations'], banks=reference(bank_path),
                evaluation_populations=bundle['evaluation_populations'],
                workers=32, chunk_rows=128, steps_per_update=262144, updates=32, minibatch=2048, microbatch=128,
                actor_threads=1, learner_threads=1, hp1_threshold=0.019753086419753086,
                scripts=['scripted-pressure', 'scripted-defense'])
            config_path = out/f'{size}-{seed}.json'
            config_path.write_bytes(S.encoded(config)+b'\n')
            outputs.append(reference(config_path))
            if seed_index == 0:
                fallback = copy.deepcopy(config)
                fallback.update(host={'M': '127x09', 'S100': '127x12'}[size], qualification_only=True)
                if 'qualification_placements' in bundle:
                    fallback.update(bundle['qualification_placements'][size])
                fallback_path = out/f'SOAK-{size}-{seed}.json'
                fallback_path.write_bytes(S.encoded(fallback)+b'\n')
                outputs.append(reference(fallback_path))
    (out/'manifest.json').write_bytes(S.encoded(dict(configs=outputs, bundle_sha256=S.digest(bundle),
                                                   launch_go=False))+b'\n')
    return outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--bundle', type=Path)
    source.add_argument('--config', type=Path)
    p.add_argument('--readiness', type=Path)
    p.add_argument('--relocated-references', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    if a.bundle:
        print(json.dumps(freeze(json.loads(a.bundle.read_text()), a.out), indent=2))
    else:
        if a.readiness is None or a.relocated_references is None:
            p.error('--readiness and --relocated-references required with --config')
        config = relocate(json.loads(a.config.read_text()), json.loads(a.readiness.read_text()),
                          json.loads(a.relocated_references.read_text()),
                          mapping_sha256=S.file_sha(a.relocated_references))
        with a.out.open('xb') as output:
            output.write(S.encoded(config)+b'\n')
        print(json.dumps(reference(a.out), indent=2))


if __name__ == '__main__':
    main()
