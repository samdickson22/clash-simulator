"""Copy the v7r4h recipe exactly, relocating paths and adding only T32/B16 flags."""
import json
import tomllib
from pathlib import Path

KIT = Path(__file__).resolve().parent
BASE = KIT.with_name('v7r4h-launch')
FLAGS = {'recurrent_update_mode': 'stored-state', 'tbptt_chunk': 32, 'tbptt_burn_in': 16}
SEEDS = (2901, 2902)


def render(seed):
    text = (BASE / 'configs' / f'council-pilot-v7r4h-seed{seed}.toml').read_text()
    text = text.replace('v7r4h', 'v7r5').replace('pilot-runtime-v5', 'pilot-runtime-v6')
    return text + '\n# Stored actor-state TBPTT; all other recipe values remain v7r4h.\n' + ''.join(f'{k} = {json.dumps(v)}\n' for k, v in FLAGS.items())


def main():
    (KIT / 'configs').mkdir(exist_ok=True)
    for seed in SEEDS:
        path = KIT / 'configs' / f'council-pilot-v7r5-seed{seed}.toml'
        text = render(seed)
        original = tomllib.loads((BASE / 'configs' / f'council-pilot-v7r4h-seed{seed}.toml').read_text())
        expected = json.loads(json.dumps(original).replace('v7r4h', 'v7r5').replace('pilot-runtime-v5', 'pilot-runtime-v6'))
        assert tomllib.loads(text) == expected | FLAGS
        with path.open('x') as f:
            f.write(text)
        path.chmod(0o444)
        print(path)

if __name__ == '__main__':
    main()
