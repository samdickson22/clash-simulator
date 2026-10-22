"""Prepare a fresh, reviewable local input closure for leased qualification.

Raw inputs retain their exact bytes. JSON reference containers receive new
locations and hashes. This neither writes to another host nor issues GO.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(config_paths, inventory, readiness, out):
    out = Path(out).resolve()
    if Path('/mpac/sdicks02/jobs/clasher') not in out.parents or out.exists():
        raise ValueError('fresh output below jobs/clasher required')
    rows = {row['path']: row for row in inventory['files']}
    if len(rows) != len(inventory['files']):
        raise ValueError('duplicate source input')
    # Validate every declared input before creating an output attempt.
    for name, row in rows.items():
        path = Path(name)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('noncanonical input path')
        raw = path.read_bytes()
        if digest(raw) != row['sha256'] or len(raw) != row['bytes']:
            raise ValueError('source input changed: '+name)
    out.mkdir(parents=True)
    cached, active = {}, set()

    def reference(value, *, container=True):
        # Only reachable reference containers are interpreted. Optional staging
        # receipts retain their original bytes, including their historical paths.
        name, expected = value['path'], value['sha256']
        if not Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('noncanonical reference path')
        if 'PENDING' in Path(name).parts:
            if expected != '0'*64:
                raise ValueError('pending evidence must retain its zero digest')
            suffix = Path(*Path(name).parts[Path(name).parts.index('PENDING')+1:])
            return dict(value, path=str(out/'PENDING'/suffix))
        if name not in rows or rows[name]['sha256'] != expected:
            raise ValueError('reference absent from pinned inventory: '+name)
        if name in active:
            raise ValueError('cyclic input reference: '+name)
        if name not in cached:
            active.add(name)
            raw = Path(name).read_bytes()
            if digest(raw) != expected:
                raise ValueError('source changed while preparing: '+name)
            payload = raw
            if container and Path(name).suffix == '.json':
                original = json.loads(raw)
                rewritten = rewrite(original)
                if rewritten != original:
                    payload = encoded(rewritten)
            destination = out/'files'/Path(name).relative_to('/')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as output:
                output.write(payload)
            cached[name] = dict(path=str(destination), sha256=digest(payload), bytes=len(payload),
                                source_sha256=expected, rewritten=payload != raw)
            active.remove(name)
        result = dict(value, path=cached[name]['path'], sha256=cached[name]['sha256'])
        if 'bytes' in result:
            result['bytes'] = cached[name]['bytes']
        return result

    def rewrite(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                return reference(value)
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value

    outputs = []
    for config_path in config_paths:
        original = json.loads(Path(config_path).read_bytes())
        if (original.get('qualification_only') is not True or original.get('size') not in ('M', 'S100')
                or original.get('host') != {'M': '127x09', 'S100': '127x12'}[original['size']]
                or original['host'] not in readiness):
            raise ValueError('matching qualification configuration required')
        config = rewrite(copy.deepcopy(original))
        host = readiness[original['host']]
        config.update(runtime=host['runtime_root'], actor_source=host['actor_source_root'])
        config['audit_roots'] = {key: str(out/'files'/Path(path).relative_to('/')) for key, path in
            dict(defense='/mpac/sdicks02/scratch/defense-failures-20261020',
                 spell='/mpac/sdicks02/scratch/spell-usage-20261020',
                 mirror='/mpac/sdicks02/scratch/live-mem/mirror').items()}
        for key, value in config['live']['environment'].items():
            for source in sorted(rows, key=len, reverse=True):
                target = str(out/'files'/Path(source).relative_to('/'))
                value = value.replace(source, target)
            if key == 'CLASHER_LOPP_MODELS':
                prefix = original['live']['environment'][key]
                if not any(name.startswith(prefix+'/') for name in rows):
                    raise ValueError('opponent model directory is not pinned')
                value = str(out/'files'/Path(prefix).relative_to('/'))
            config['live']['environment'][key] = value
        destination = out/('SOAK-'+config['size']+'-'+config['host']+'.json')
        destination.write_bytes(encoded(config))
        outputs.append(dict(path=str(destination), sha256=digest(destination.read_bytes())))
    # Include declared optional inputs, not only the paths reached from configs.
    for name, row in rows.items():
        reference(dict(path=name, sha256=row['sha256']), container=False)
    record = dict(schema='pv1-qualified-input-relocation-v1', status='PREPARED-NOT-GO',
        files=cached, configs=outputs, remote_writes=False, experiment_changes=False)
    (out/'relocation.json').write_bytes(encoded(record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configs', nargs='+', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--readiness', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.configs, json.loads(args.inventory.read_bytes()),
                     json.loads(args.readiness.read_bytes()), args.out)
    print(json.dumps(dict(configs=result['configs'], files=len(result['files']), status=result['status'])))


if __name__ == '__main__':
    main()
