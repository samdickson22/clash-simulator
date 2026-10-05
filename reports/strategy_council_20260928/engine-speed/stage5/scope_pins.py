"""Pins for this native/public search runtime; unrelated vision jobs stay independent."""
import hashlib
from pathlib import Path
import clasher_core

HERE=Path(__file__).resolve().parent

def files():
    paths=[p for p in Path('src/clasher').rglob('*.py') if 'vision' not in p.relative_to('src/clasher').parts[:1]]
    paths += [*Path('engine-rs/src').glob('*.rs'),*Path('engine-rs').glob('*.py'),Path(clasher_core.__file__),Path('gamedata.json')]
    paths += [HERE/n for n in ('qualify.py','scope_pins.py')]
    return sorted(set(paths))

def pins():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}

def fingerprint():
    return hashlib.sha256(b''.join(str(p).encode()+p.read_bytes() for p in files())).hexdigest()
