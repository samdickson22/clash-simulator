"""Separate synthetic startup tap sensitivity from steady transport hops."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from clasher.live.runtime import quantiles


def main(a):
    if a.output.exists():
        raise ValueError('Fresh derived receipt required')
    benchmark = json.loads((a.input/'queue-benchmark.json').read_text())
    samples = {mode: [] for mode in ('polling', 'blocking')}
    pins = {}
    for path in sorted(a.input.glob('*-*/latency.jsonl.gz')):
        mode = path.parent.name.split('-', 1)[1]
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in gzip.open(path, 'rt'):
            row = json.loads(line)
            if row['metric'] == 'frame_to_tap' and row['command_id'] != 1:
                samples[mode].append(row['ms'])
    result = dict(schema='clasher.live-perf.queue-analysis.v1', synthetic_only=True,
        steady_mock_tap_ms={mode: quantiles(values) for mode, values in samples.items()},
        original_benchmark_sha256=hashlib.sha256((a.input/'queue-benchmark.json').read_bytes()).hexdigest(),
        log_sha256=pins, limitations=[
            f'Post-startup mock tap counts={ {k: len(v) for k, v in samples.items()} }; not an E4 latency measurement',
            'First tap source can change between sequence0 and1 after cold belief initialization',
            'Unfiltered median of run medians retained in original receipt: '+str({
                mode: benchmark['median_of_run_medians_ms'][mode]['frame_to_tap']['p50'] for mode in samples})])
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['steady_mock_tap_ms']), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
