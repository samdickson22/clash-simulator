#!/usr/bin/env python3
"""Phase 2 check on 05: the local copy holds exactly the 32 pinned capture files, each SHA-equal.

Never unpickles. Exit status 0 means "release 03"; anything else means stop and report.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpora", type=Path, required=True)
    p.add_argument("--captures", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--remote-sha256", type=Path, help="sha256sum output taken on 127x03 before the copy (same session)")
    a = p.parse_args(argv)
    corpora = io.read_pinned_json(a.corpora, io.CORPORA_SHA256)
    files = io.capture_inventory(corpora, a.captures)
    present = sorted(str(Path(root, name).relative_to(a.captures)) for root, _, names in os.walk(a.captures) for name in names)
    expected = sorted(f["relative"] for f in files)
    results = [dict(relative=f["relative"], expected=f["sha256"], actual=io.file_sha(f["local"]) if Path(f["local"]).is_file() else None,
                    bytes=Path(f["local"]).stat().st_size if Path(f["local"]).is_file() else None) for f in files]
    mismatched = [r["relative"] for r in results if r["actual"] != r["expected"]]
    remote = None
    if a.remote_sha256:
        listed = {}
        for line in a.remote_sha256.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and len(parts[0]) == 64 and all(c in "0123456789abcdef" for c in parts[0]):
                listed[parts[1]] = parts[0]
        remote_bad = sorted(f["relative"] for f in files if listed.get(f["relative"]) != f["sha256"])
        remote = dict(file_sha256=io.file_sha(a.remote_sha256), files=len(listed), all_equal_corpora=not remote_bad and len(listed) == 32,
                      mismatched=remote_bad)
        mismatched = sorted(set(mismatched) | set(remote_bad))
    receipt = dict(schema="clasher.tiers-a4.capture-copy.v1", utc=io.utc(), **io.process_identity(), source_host="127x03",
                   corpora_sha256=io.CORPORA_SHA256, files=results, total_bytes=sum(r["bytes"] or 0 for r in results),
                   only_pinned_files=present == expected, extra_files=sorted(set(present) - set(expected)),
                   remote_before=remote, mismatched=mismatched,
                   passes=not mismatched and present == expected and (remote is None or remote["all_equal_corpora"]),
                   games_copied=False, outcomes_read=False)
    io.write_json(a.output, receipt)
    print(json.dumps({k: receipt[k] for k in ("passes", "total_bytes", "mismatched", "extra_files")}))
    return 0 if receipt["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
