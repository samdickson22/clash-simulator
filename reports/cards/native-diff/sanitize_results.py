"""Retain diagnostic state while excluding source/config stat tables from reports.

Full raw evidence stays on the job host. Do not copy the config cache to the repo.
"""
import argparse
import json
from pathlib import Path

DROP = {'config', 'clone_template', 'unit_data', '_raw_entry', 'projectile_data',
        'spawnProjectileData', 'targetBuffData', 'card_stats', 'stages', 'ramp_stages',
        'area_data', 'death_spawn_data', 'spawn_character_data', 'spawn_projectile_data',
        'buffData', 'spawnDataData', 'onStartingActionData'}


def scrub(value, key=''):
    if isinstance(value, dict):
        if 'source' in value and any(k in value for k in ('hitSpeed', 'hitpoints', 'tid')):
            return {'name': value.get('name'), 'source_table_omitted': True}
        if key == 'stats':
            return {k: v for k, v in value.items() if k in ('name', 'payload_key')}
        return {k: scrub(v, k) for k, v in value.items() if k not in DROP}
    if isinstance(value, list):
        return [scrub(v, key) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    args = p.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.source.glob('*.json')):
        target = args.destination / path.name
        if target.exists() and args.source != args.destination:
            continue
        value = json.loads(path.read_text())
        target.write_text(json.dumps(scrub(value), indent=1, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
