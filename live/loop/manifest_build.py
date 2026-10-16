"""Build MANIFEST.json for drive.py's start-of-session deployment check from a commit and the deployed file list.

  python manifest_build.py --repo REPO --commit SHA --out MANIFEST.json [--snapshot HASHES] live/loop/drive.py ...

Hashes come from `git show <commit>:<path>` (a file missing from the commit is an error: deploy what is committed).
--snapshot adds 'sha256  relpath' lines for deployed files that are not one commit (the pinned bot tree on the Mac
runs older bot files than main), taken from the verified deployed state.
Copy MANIFEST.json to ~/clasher-live/loop/MANIFEST.json with the files; the next session checks every listed file.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--repo', required=True)
    ap.add_argument('--commit', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--snapshot', help="file of 'sha256  relpath' lines added as-is")
    a = ap.parse_args()
    full = subprocess.run(['git', '-C', a.repo, 'rev-parse', a.commit], capture_output=True, text=True, check=True).stdout.strip()
    files, missing = {}, []
    for rel in a.files:
        p = subprocess.run(['git', '-C', a.repo, 'show', f'{full}:{rel}'], capture_output=True)
        if p.returncode:
            missing.append(rel)
        else:
            files[rel] = hashlib.sha256(p.stdout).hexdigest()
    if missing:
        sys.exit(f'not in {full[:12]}: {missing}')
    if a.snapshot:
        for line in Path(a.snapshot).read_text().splitlines():
            if line.strip():
                h, rel = line.split(None, 1)
                if len(h) != 64 or rel in files:
                    sys.exit(f'bad or duplicate snapshot line: {line!r}')
                files[rel.strip()] = h
    Path(a.out).write_text(json.dumps(dict(commit=full, files=files), indent=1, sort_keys=True) + '\n')
    print(json.dumps(dict(commit=full, files=len(files), sha256=hashlib.sha256(Path(a.out).read_bytes()).hexdigest())))


if __name__ == '__main__':
    main()
