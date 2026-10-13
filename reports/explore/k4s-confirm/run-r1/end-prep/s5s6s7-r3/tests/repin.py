"""Dev tool: rewrite the cross-file SHA pins of this package in dependency order (offline; edits only files in the
package directory). safe_input -> host tool -> preflight / wrappers -> verifier -> gate (SHA-256 and, r3, the canonical bootstrap's
size pins). test_pins.py checks them.

  python3 tests/repin.py            rewrite and print every pin
  python3 tests/repin.py --check    exit 1 if any pin is stale (no write)
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def size(name):
    return str(len((ROOT / name).read_bytes()))


def put(name, pattern, value, check, stale):
    path = ROOT / name
    text = path.read_text()
    new, count = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), text)
    if count != 1:
        raise SystemExit("pattern %r matched %d times in %s" % (pattern, count, name))
    if new != text:
        stale.append("%s: %s" % (name, pattern))
        if not check:
            path.write_text(new)


def main():
    check = "--check" in sys.argv
    stale = []
    si = sha("safe_input.py")
    for name in ("k4s_end_host_tool.py", "k4s_end_preflight.py", "k4s_end_verify_push.py", "k4s_end_launch_gate.py"):
        put(name, r'(\nSAFE_INPUT_SHA256 = ")[0-9a-f]{64}(")', si, check, stale)
        put(name, r'(\nSAFE_INPUT_SIZE = )[0-9]+(\n)', size("safe_input.py"), check, stale)   # r3: bootstrap size pin
    tool = sha("k4s_end_host_tool.py")
    put("k4s_end_preflight.py", r'(\nHOST_TOOL_SHA256 = ")[0-9a-f]{64}(")', tool, check, stale)
    for name in ("k4s_end_preflight.py", "k4s_end_launch_gate.py"):
        put(name, r'(\nHOST_TOOL_SIZE = )[0-9]+(\n)', size("k4s_end_host_tool.py"), check, stale)
    for name in ("k4s_end_exit_push.sh", "k4s_preflight_push.sh"):
        put(name, r'(\nhost_tool_sha=)[0-9a-f]{64}(\n)', tool, check, stale)
        put(name, r'(\nhost_tool_size=)[0-9]+(\n)', size("k4s_end_host_tool.py"), check, stale)
    put("k4s_end_verify_push.py", r'(\nWRAPPER_SHA256 = ")[0-9a-f]{64}(")', sha("k4s_end_exit_push.sh"), check, stale)
    gate = "k4s_end_launch_gate.py"
    put(gate, r'(\nHOST_TOOL_SHA256 = ")[0-9a-f]{64}(")', tool, check, stale)
    put(gate, r'(WRAPPER_SHA256 = \{"end": ")[0-9a-f]{64}(")', sha("k4s_end_exit_push.sh"), check, stale)
    put(gate, r'(\n                  "preflight": ")[0-9a-f]{64}(")', sha("k4s_preflight_push.sh"), check, stale)
    put(gate, r'(\nPREFLIGHT_SHA256 = ")[0-9a-f]{64}(")', sha("k4s_end_preflight.py"), check, stale)
    put(gate, r'(\nREMOTE_SHA256 = ")[0-9a-f]{64}(")', sha("k4s_end_launch_remote.py"), check, stale)
    for name in ("safe_input.py", "k4s_end_host_tool.py", "k4s_end_preflight.py", "k4s_end_exit_push.sh",
                 "k4s_preflight_push.sh", "k4s_end_verify_push.py", "k4s_end_launch_remote.py", gate):
        print(sha(name), name)
    if check and stale:
        print("STALE:", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
