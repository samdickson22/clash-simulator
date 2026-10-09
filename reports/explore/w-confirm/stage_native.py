"""Stage a private WAIT extension to the existing delay-command path."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def stage(root, dest):
    if dest.exists():
        raise ValueError('fresh destination required')
    source = root / 'engine-rs'
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns('target', '*.so', '__pycache__'))
    path = dest / 'src/delay_commands.rs'
    text = path.read_text()
    text = text.replace('|| action > 2304 ||', '|| (action > 2304 && !(2400..=2402).contains(&action)) ||')
    text = text.replace('let mut sim = battle.clone();', '''let wait_ticks = match action { 2400 => 10, 2401 => 20, 2402 => 40, _ => 0 };
        let action = if wait_ticks > 0 { 2304 } else { action };
        let mut sim = battle.clone();''', 1)
    text = text.replace('(actor != seat || continue_own)', '(actor != seat || (continue_own && tick >= wait_ticks))')
    assert 'tick >= wait_ticks' in text and '2402' in text
    path.write_text(text)
    hashes = {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(dest.rglob('*')) if p.is_file()}
    (dest / 'w-source-manifest.json').write_text(json.dumps(hashes, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('dest', type=Path)
    a = p.parse_args()
    stage(a.root, a.dest)
