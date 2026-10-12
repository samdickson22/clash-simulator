"""Offline test helpers: K4SStore-equivalent sealing (k4s_logic.py:1140-1167), shims, wrapper copies."""
import difflib
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHIMS = HERE / "shims"


def canonical(value):                                       # k4s_logic.py:106-107
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Store:
    """Same file semantics as k4s_logic.K4SStore (exclusive files, scope key, seal + sidecar)."""

    def __init__(self, directory, scope, forbidden=()):
        self.directory = Path(directory)
        for root in forbidden:
            root = Path(root).resolve()
            out = self.directory.resolve()
            if out == root or root in out.parents or out in root.parents:
                raise ValueError("overlap " + str(root))
        self.directory.mkdir(parents=True, exist_ok=False)
        self.scope = scope

    def write(self, name, value):
        with (self.directory / name).open("x") as stream:
            stream.write(canonical(dict(scope=self.scope, **value)) + "\n")

    def seal(self, status):
        files = {str(p.relative_to(self.directory)): sha(p) for p in sorted(self.directory.rglob("*")) if p.is_file()}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        with (self.directory / "receipt-manifest.sha256").open("x") as stream:
            stream.write(sha(self.directory / "receipt-manifest.json") + "  receipt-manifest.json\n")


def shim_env(tmp, **extra):
    env = dict(os.environ)
    env["PATH"] = str(SHIMS) + os.pathsep + env["PATH"]
    env["FAKE_LOG"] = str(Path(tmp) / "fake.log")
    env.update({k: str(v) for k, v in extra.items()})
    return env


def substituted(source, target, replacements):
    """Copy a script replacing exactly the given lines (each must occur once); return the changed-line count."""
    text = Path(source).read_text()
    for old, new in replacements:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    Path(target).write_text(text)
    os.chmod(target, 0o755)
    changed = [l for l in difflib.unified_diff(Path(source).read_text().splitlines(), text.splitlines(), lineterm="")
               if l.startswith("-") and not l.startswith("---")]
    return len(changed)


def write_detach(base):
    target = Path(base) / "END-frozen-detach-1648dfdc.sh"
    shutil.copy(ROOT / "t1-originals" / "detach.sh", target)
    return target


def run(argv, env, **kw):
    return subprocess.run([str(a) for a in argv], env=env, capture_output=True, text=True, **kw)
