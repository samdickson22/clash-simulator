"""Enumerate candidate entity iteration / hit-record sites; this is not a Rust parser.

Usage: native_entity_sites.py /absolute/path/to/engine-cards/src
Includes multiline iteration, sliced iteration and indexed entity-length loops.
"""
import argparse
import bisect
import re
from pathlib import Path

PATTERN = re.compile(
    r"self\s*\.\s*entities(?:\s*\[[^]]*\])?\s*\.\s*iter(?:_mut)?\(\)"
    r"|in\s+&(?:mut\s+)?self\s*\.\s*entities\b"
    r"|hit_ids\s*\.\s*(?:push|extend)\b|struck\s*\.\s*push\b"
    r"|for\s+\w+\s+in\s+0\.\.(?:self\s*\.\s*entities\s*\.\s*len\(\)|n\b)"
)


def scan(source_dir):
    files = sorted(source_dir.glob("*.rs"))
    if not files:
        raise ValueError(f"no Rust source files in {source_dir}")
    for file in files:
        source = file.read_text()
        starts = [0] + [m.end() for m in re.finditer("\n", source)]
        functions = [(m.start(), m.group(1)) for m in re.finditer(r"\bfn\s+([a-z_0-9]+)\s*[(<]", source)]
        offsets = [p for p, _ in functions]
        lines = source.splitlines()
        for match in PATTERN.finditer(source):
            line = bisect.bisect_right(starts, match.start())
            name_index = bisect.bisect_right(offsets, match.start()) - 1
            text = lines[line - 1].strip()
            if not text.startswith("//"):
                yield f"{file.name}:{line}", functions[name_index][1] if name_index >= 0 else "?", text[:100]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    args = parser.parse_args()
    try:
        rows = list(scan(args.source_dir))
        if not rows:
            raise ValueError("no candidate sites found")
    except ValueError as error:
        parser.error(str(error))
    for row in rows:
        print("\t".join(row))
