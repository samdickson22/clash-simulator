#!/usr/bin/env python3
"""Recompute the expected Mac E4 runtime tree and compare it with the staged Mac copy.

Run on 127x05 from the clasher checkout. It reads git objects, the 05 Linux-smoke runtime
(read-only) and a SHA listing of the Mac runtime. It writes one new JSON receipt and
modifies nothing else. The expected tree is:
  1. every regular file of `git archive COMMIT`;
  2. plus each runtime-pin-r2 file absent from COMMIT, copied from the smoke runtime only if
     its bytes equal the pinned SHA;
  3. with engine-rs replaced by the committed reports/explore/e1/stage_native.py output, which
     must reproduce every runtime-pin-r2 `native_source` SHA except the non-compiled
     e1-source-manifest.json.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PIN = "reports/explore/s1/receipts/runtime-pin-r2.json"
STAGER = "reports/explore/e1/stage_native.py"
NONCOMPILED = {"e1-source-manifest.json"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(repo, commit):
    """Map path -> sha256 for regular blobs and path -> target for symlinks of the commit."""
    files, links = {}, {}
    for line in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, obj = meta.split()
        if kind != b"blob":
            raise ValueError("Unsupported tree entry (submodule?): " + path.decode())
        data = git(repo, "cat-file", "blob", obj.decode())
        if mode == b"120000":
            links[path.decode()] = data.decode()
        else:
            files[path.decode()] = sha(data)
    return files, links


def relative(path):
    """Normalize a listing path; refuse absolute, parent and duplicate-prone forms."""
    path = path[2:] if path.startswith("./") else path
    parts = path.split("/")
    if not path or path.startswith("/") or any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid listing path: " + repr(path))
    return path


def parse(lines, separator=None):
    result = {}
    for line in lines:
        left, path = line.split(separator, 1) if separator else line.split(None, 1)
        if separator:
            left, path = path, left
        path = relative(path)
        if path in result:
            raise ValueError("Duplicate listing path: " + path)
        result[path] = left
    return result


def expected(repo, commit, smoke):
    files, links = tree(repo, commit)
    pin = json.loads(git(repo, "show", f"{commit}:{PIN}"))
    overlay = {}
    for name, digest in sorted(pin["files"].items()):
        if name in files:
            continue
        path = Path(smoke) / name
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError("Uncommitted runtime-pin file unavailable at pinned SHA: " + name)
        overlay[name] = digest
    files.update(overlay)
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        source = work / "src"
        source.mkdir()
        archive = git(repo, "archive", "--format=tar", commit, "engine-rs")
        subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
        script = work / "stage_native.py"
        script.write_bytes(git(repo, "show", f"{commit}:{STAGER}"))
        spec = importlib.util.spec_from_file_location("stage_native", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        dest = work / "dest"
        module.stage(source / "engine-rs", dest)
        staged = {str(p.relative_to(dest)): sha(p.read_bytes()) for p in dest.rglob("*") if p.is_file()}
    native = pin["native_source"]
    mismatched = sorted(n for n in native if staged.get(n) != native[n])
    if set(mismatched) - NONCOMPILED or set(staged) != set(native):
        raise ValueError("E1 stager does not reproduce the pinned native source: " + repr(mismatched))
    e1 = {"engine-rs/" + n: d for n, d in staged.items() if files.get("engine-rs/" + n) != d}
    # Replace (not update) the native subtree: only the stager's output may remain.
    files = {p: d for p, d in files.items() if not p.startswith("engine-rs/")}
    files.update({"engine-rs/" + n: d for n, d in staged.items()})
    if any(p.startswith("engine-rs/") for p in links):
        raise ValueError("Symlink inside the native source subtree")
    return files, links, overlay, e1, mismatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--smoke-runtime", type=Path, required=True)
    ap.add_argument("--mac-listing", type=Path, required=True,
                    help="`shasum -a 256` lines for every regular file under the Mac runtime, paths relative")
    ap.add_argument("--mac-symlinks", type=Path, required=True,
                    help="`PATH<TAB>TARGET` lines (readlink) for every symlink under the Mac runtime")
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    files, links, overlay, e1, mismatched = expected(a.repo, a.commit, a.smoke_runtime)
    mac = parse(a.mac_listing.read_text().splitlines())
    mac_links = parse(a.mac_symlinks.read_text().splitlines(), "\t")
    if set(mac) & set(mac_links):
        raise ValueError("Path listed as both file and symlink")
    link_mismatch = sorted(set(links) ^ set(mac_links) | {p for p in set(links) & set(mac_links) if links[p] != mac_links[p]})
    missing = sorted(set(files) - set(mac))
    extra = sorted(set(mac) - set(files))
    differ = sorted(p for p in set(files) & set(mac) if files[p] != mac[p])
    result = dict(schema="clasher.mac-e4-session.runtime-verify.v1", commit=a.commit,
                  expected_files=len(files), mac_files=len(mac), missing=missing, extra=extra,
                  differ=differ, symlinks=links, symlink_mismatch=link_mismatch, overlay_uncommitted=overlay, e1_native_overlay=e1,
                  e1_noncompiled_mismatch=mismatched,
                  expected_manifest_sha256=sha(json.dumps(files, sort_keys=True).encode()),
                  passes=not (missing or extra or differ or link_mismatch))
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=1, sort_keys=True)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("expected_files", "mac_files", "symlink_mismatch", "passes")}))
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    sys.exit(main())
