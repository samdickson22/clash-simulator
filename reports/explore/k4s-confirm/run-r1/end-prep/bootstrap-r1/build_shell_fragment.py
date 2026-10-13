#!/usr/bin/env python3
"""Regenerate k4s_bootstrap_shell_r1.sh from k4s_bootstrap_loader_r1.py (stdlib only; prints to stdout).

The shell fragment is the canonical shell-wrapper form of the bootstrap: it embeds the loader program verbatim in one
single-quoted shell word (the loader contains no single quote) and defines the verify call and `tool()`.
tests/test_bootstrap_conformance.py checks that the delivered fragment equals this output byte for byte and that bash
hands the loader to python unchanged.

    python3 -I build_shell_fragment.py LOADER_FILE > k4s_bootstrap_shell_r1.sh
"""
import sys

HEAD = """\
# ==== BEGIN K4S CANONICAL SHELL BOOTSTRAP r1 (bootstrap-r1/k4s_bootstrap_shell_r1.sh; paste verbatim) ====
# END-FULL-F1 for the host-tool wrappers. Requires, set before this fragment: python (/usr/bin/python3), host_tool
# (absolute normalized path), host_tool_sha (64 lowercase hex), host_tool_size (decimal byte count). Replaces the
# `test -f "$host_tool"` + `sha256sum --check` pair and the plain `tool()` definition. Every tool run re-walks,
# re-gates and re-hashes the host tool and executes exactly the verified bytes as __main__; nothing is hashed by
# sha256sum and the interpreter opens no script by path. Loader refusal: exit status 90, one line on stderr.
k4s_loader='"""
TAIL = """'
k4s_verify_host_tool() { "$python" -I -S -c "$k4s_loader" "$host_tool" "$host_tool_sha" "$host_tool_size" --verify-only; }
tool() { "$python" -I -S -c "$k4s_loader" "$host_tool" "$host_tool_sha" "$host_tool_size" -- "$@"; }
k4s_verify_host_tool || exit 90
# ==== END K4S CANONICAL SHELL BOOTSTRAP r1 ====
"""


def fragment(loader):
    if "'" in loader:
        raise SystemExit("the loader contains a single quote; it cannot be embedded")
    return HEAD + loader + TAIL


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        sys.stdout.write(fragment(handle.read()))
