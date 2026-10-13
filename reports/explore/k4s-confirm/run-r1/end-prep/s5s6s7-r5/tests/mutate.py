"""Mutation check of the safe_input adoption points and the new gates (offline).

Each mutant: copy the package into a fresh /dev/shm/s567r5-mut-* directory, apply its edits (each old text must occur
exactly once), re-pin the copy (tests/repin.py) so the SHA bootstraps load it, then run the named test files with
`python -O -B -m pytest -x` (test_pins.py is never included, so no mutant is killed by a pin alone). KILLED = the
suite fails. NULL controls (no edit) must SURVIVE. The verifier refuses -O at import (T1 R3-1), so its mutants run
without -O and are labelled so. The copy is removed afterwards.

  python3 tests/mutate.py --check-edits
  python3 tests/mutate.py --python /usr/bin/python3 --pythonpath /dev/shm/s567r3-pytest38 --jobs 6 --out R.json

r3: test entries may be pytest node ids (file::test) so a mutant of a canonical bootstrap region is judged by the
BEHAVIOURAL tests only (the byte-equality region tests would kill it trivially).
"""
import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = "tests/"
HT, S5, S6W, S6V, S7 = (T + "test_host_tool.py", T + "test_s5_preflight.py", T + "test_s6_wrapper.py",
                        T + "test_s6_verifier.py", T + "test_s7_gate.py")
F2I, F1 = T + "test_f2_s3_guard_integration.py", T + "test_f1_bootstrap.py"
F1PY, F1SH = F1 + "::test_python_loader_meets_every_kit_scenario", F1 + "::test_wrapper_bootstrap_meets_the_kit_scenarios"
F1SWAP = F1 + "::test_wrapper_never_executes_a_host_tool_swapped_after_verification"
R4T, A6T = T + "test_r4.py", T + "test_a6_builder.py"
R5T = T + "test_r5.py"
R5REC = R5T + "::test_u8_builder_constants_equal_the_adopted_record"
A6R5 = A6T + "::test_r5_frozen_inputs_bind_runtime_to_adopted_s9"
AJ = "k4s_a6_builder.py"
TOOL, PF, EW, PW, VER, GATE, REM = ("k4s_end_host_tool.py", "k4s_end_preflight.py", "k4s_end_exit_push.sh",
                                    "k4s_preflight_push.sh", "k4s_end_verify_push.py", "k4s_end_launch_gate.py",
                                    "k4s_end_launch_remote.py")

# (id, description, file, [(old, new)], tests)
MUTANTS = [
    # ---- k4s_end_host_tool.py
    ("H01", "registry: claim-name regex off", TOOL, [("if CLAIM.fullmatch(name) is None:", "if False:")], [HT]),
    ("H02", "registry: claim nlink/regular check off",
     TOOL, [("if st is None or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:", "if st is None:")], [HT]),
    ("H03", "verify_clone: replace refs ignored", TOOL, [('if replace != b"":', "if False:")], [HT]),
    ("H04", "verify_clone: any hook allowed", TOOL, [('patterns=("*.sample",)', 'patterns=("*",)')], [HT]),
    ("H05", "frozen env: inherited GIT_* kept",
     TOOL, [('env = {k: v for k, v in inherited.items() if not k.startswith("GIT_")}', "env = dict(inherited)")],
     [HT]),
    ("H06", "frozen env: no GIT_CONFIG_PARAMETERS", TOOL, [('    env["GIT_CONFIG_PARAMETERS"] = GIT_CONFIG_PARAMETERS\n',
                                                          "")], [HT]),
    ("H07", "global git config not checked",
     TOOL, [("si._check_git_config(parent, parts[-1], os.path.dirname(path))", "pass")], [HT]),
    ("H08", "bootstrap (host tool copy): leaf nlink not checked before open (r3: canonical region)",
     TOOL, [("        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:",
             "        if not stat.S_ISREG(before.st_mode) or before.st_size != size:")], [F1PY]),
    ("H09", "bootstrap (host tool copy): SHA not checked (r3: canonical region)",
     TOOL, [("    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:",
             "    if len(data) != size:")], [F1PY]),
    ("H10", "snapshot copies no claim",
     TOOL, [('names = listing["claims"].get("round-%02d/%s" % (round_index, host), []) if listing["exists"] else []',
             "names = []")], [HT, S6W]),
    ("H11", "Q3 seed commits not checked", TOOL, [("    for commit in commits:\n        si.git_run",
                                                   "    for commit in commits[:0]:\n        si.git_run")], [HT, S5]),
    ("H12", "frozen-exec: clone not verified",
     TOOL, [('record = verify_clone(si, host, option_value(command, "--repository"), role="repository")',
             "record = {}")], [S6W]),
    # ---- k4s_end_preflight.py (S5)
    ("P01", "caller manifest SHA accepted", PF, [("if k4s_manifest_sha256 != K4S_MANIFEST_SHA256:", "if False:")], [S5]),
    ("P02", "manifest read without the anchor",
     PF, [("expected_sha256=K4S_MANIFEST_SHA256), MANIFEST_REL)", "expected_sha256=None), MANIFEST_REL)")], [S5]),
    ("P03", "closure table not compared", PF, [("require(derived == FROZEN_CLOSURE,", "require(True,")], [S5]),
    ("P04", "closure files not hashed against pins",
     PF, [('si.read_bytes(policy, "runtime", rel, max_size=64 << 20, expected_sha256=pin)',
           'si.read_bytes(policy, "runtime", rel, max_size=64 << 20, expected_sha256=None)')], [S5]),
    ("P05", "pre-import pins skipped", PF, [("row.update(pre_import_pins(si, policy))", "pass")], [S5]),
    ("P06", "S4 synthetic stamp accepted", PF, [("require(SYNTHETIC_KEY not in manifest,", "require(True,")], [S5]),
    ("P07", "non-production assembly receipt accepted",
     PF, [('receipt.get("production_pins") is True', "True")], [S5]),
    ("P08", "bundle manifest read without its SHA",
     PF, [('"tiers-pins.json", 64 << 20, expected_sha256=pins_sha256)', '"tiers-pins.json", 64 << 20)')], [S5]),
    ("P09", "runtime-<commit12> layout not enforced",
     PF, [("and RUNTIME_NAME.fullmatch(os.path.basename(runtime)),", ",")], [S5]),
    ("P10", "pf/rd guard-job form not enforced",
     PF, [('require(m.group(1).startswith("pf") == preflight,', "require(True,")], [S5]),
    ("P11", "guard repo clone not verified",
     PF, [('row.update(tool.verify_clone(si, host, guard_job + "/repo", grants=("guard-job",), role="guard-repo"))',
           "pass")], [S5]),
    ("P12", "repository clone not verified",
     PF, [('row.update(tool.verify_clone(si, host, str(a.repository), role="repository"))', "pass")], [S5]),
    ("P13", "frozen git env not applied",
     PF, [("env, record = tool.frozen_env_checked(si, host, dict(os.environ))", "env, record = dict(os.environ), {}")],
     [S5]),
    ("P14", "binding without reference work",
     PF, [('result["mode_requested"] == "binding" and load.get("reference_slot_work") is True',
           'result["mode_requested"] == "binding"')], [S5]),
    ("P15", "binding without measured duration",
     PF, [("and measured is not None and measured >= MIN_LOADED_SECONDS.get(host, float(\"inf\")))",
           "and True)")], [S5]),
    ("P16", "bus stop band never reached",
     PF, [('"stop" if percent >= BUS_STOP_MIN else', '"stop" if percent >= 99 else')], [S5]),
    ("P17", "attempt parent / guard-source copy not required",
     PF, [("unchanged and empty and copied and", "unchanged and")], [S5]),
    ("P18", "guard job freshness not checked",
     PF, [('                si.check_absent(policy, "guard-job", name)', "                pass")], [S5]),
    ("P19", "sample minimum not enforced",
     PF, [("require(len(admitted) >= a.min_samples,", "require(True,")], [S5]),
    ("P20", "loaded non-closure runtime module accepted",
     PF, [("require(rel in runtime_files,", "require(True,")], [S5]),
    ("P21", "closure_only off", PF, [("require(not outside,", "require(True,")], [S5]),
    ("P22", "verify-received: extra files accepted",
     PF, [("require(walked == set(names),", "require(True,")], [S5]),
    ("P23", "verify-received: file SHAs not compared",
     PF, [('require(si.sha256_input(S, "sealed", name)["sha256"] == digest,', "require(True,")], [S5]),
    ("P24", "verify-received: PUSH-FAILED ignored",
     PF, [('    si.check_absent(P, "recv", "PUSH-FAILED.json")\n', "")], [S5]),
    ("P25", "frozen manifest not bound to the pinned bundle",
     PF, [("require(canonical(manifest) == canonical(ctx.manifest),", "require(True,")], [S5]),
    # ---- wrappers (S6)
    ("W01", "END wrapper: argv.nul by truncating redirection (r1 bug)",
     EW, [('for name in "$attempt" exit.json exit.json.tmp argv.nul TRANSFER-DONE.json',
           'for name in "$attempt" exit.json exit.json.tmp TRANSFER-DONE.json'),
          ("receipt=$(printf '%s\\0' \"$@\" | tool si -- create-excl --host \"$host\" --root \"$job\" --rel argv.nul "
           "--max-size 65536) \\\n  || exit 91", "printf '%s\\0' \"$@\" > \"$job/argv.nul\" || exit 91")], [S6W]),
    ("W02", "END wrapper: metadata pre-checks off",
     EW, [('  test ! -e "$job/$name" && test ! -L "$job/$name" || exit 90', "  true")], [S6W]),
    ("W03", "END wrapper: command not through frozen-exec", EW, [('tool frozen-exec -- "$@"', '"$@"')], [S6W]),
    ("W04", "END wrapper: refused registry snapshot ignored", EW, [('"$snapshot" || failed=1', "true")], [S6W]),
    ("W05", "END wrapper: canonical verify step skipped (r3; was the sha256sum check)",
     EW, [("k4s_verify_host_tool || exit 90\n", "true\n")], [F1SH]),
    ("W06", "END wrapper: PUSH-FAILED by redirection",
     EW, [("    | tool si -- create-excl --host \"$host\" --root \"$job\" --rel PUSH-FAILED.json --max-size 4096) "
           "|| exit 92", "    > \"$job/PUSH-FAILED.json\")")], [S6W]),
    ("W07", "preflight wrapper: argv.nul by truncating redirection",
     PW, [('for name in "$attempt" exit.json exit.json.tmp argv.nul TRANSFER-DONE.json',
           'for name in "$attempt" exit.json exit.json.tmp TRANSFER-DONE.json'),
          ("receipt=$(printf '%s\\0' \"$@\" | tool si -- create-excl --host \"$host\" --root \"$job\" --rel argv.nul "
           "--max-size 65536) \\\n  || exit 91", "printf '%s\\0' \"$@\" > \"$job/argv.nul\" || exit 91")], [S6W]),
    # ---- verifier (S6; refuses -O: run without -O)
    ("V01", "C-d not enforced", VER, [("c_d_satisfied=now >= exit_epoch + C_D_SECONDS)", "c_d_satisfied=True)")], [S6V]),
    ("V02", "D3 members not hashed", VER, [('        si.hash_sealed_end_member(S, "s6-sealed-end", attempt + '
                                            '"/durable-measurement/" + name, files[name])', "        pass")], [S6V]),
    ("V03", "sealed listing not compared", VER, [("require(sealed_names(si, data, set(d3)) == sorted(set(files) | "
                                                  "set(SEAL_FILES)),", "require(True,")], [S6V]),
    ("V04", "received registry not bound to the listing",
     VER, [('require(walked == ["registry/" + n for n in names],', "require(True,")], [S6V]),
    ("V05", "registry claims read without listing SHA",
     VER, [('1 << 20, expected_sha256=entry["sha256"])', "1 << 20)")], [S6V]),
    ("V06", "ordinary member SHA not compared",
     VER, [('require(si.sha256_input(S, "sealed", name)["sha256"] == files[name],', "require(True,")], [S6V]),
    ("V07", "PUSH-FAILED ignored", VER, [('        si.check_absent(P, "recv", "PUSH-FAILED.json")\n',
                                          "        pass\n")], [S6V]),
    ("V08", "wrapper SHA not checked", VER, [("require(launch['wrapper_sha256'] == WRAPPER_SHA256,", "require(True,")],
     [S6V]),
    # ---- gate (S7, 05 side)
    ("G01", "RC-6 roots not bound to k4s-end-r1/Q4",
     GATE, [('and d["guard_parent"] == si.Q4_GUARD_PARENTS[host], "RC-6 %s: roots differ',
             'or True, "RC-6 %s: roots differ')], [S7]),
    ("G02", "undeclared bundle accepted",
     GATE, [('    raise GateRefusal("Not a declared RC-6 bundle for %s: %s" % (host, path))',
             '    return dict(path=path, tiers_pins_sha256="0" * 64, guard_job=path)')], [S7]),
    ("G03", "preflight receipt schema not checked",
     GATE, [('require(v.get("schema") == VERIFIED_SCHEMA and v.get("scope") == "K4S-END-PREFLIGHT" and',
             'require(True and')], [S7]),
    ("G04", "diagnostic preflight accepted for RC-9",
     GATE, [('require(v.get("mode") == "binding" and v.get("qualifying") is True,', "require(True,")], [S7]),
    ("G05", "reference load not required",
     GATE, [('require(load.get("reference_slot_work") is True and', "require(True or")], [S7]),
    ("G06", "loaded duration not required",
     GATE, [('require((duration.get("loaded_seconds_measured") or 0) >= MIN_LOADED_SECONDS[host],',
             "require(True,")], [S7]),
    ("G07", "04 bus STOP band accepted",
     GATE, [('require(v.get("bus_band") == "proceed",', "require(True,")], [S7]),
    ("G08", "preflight provenance not re-hashed",
     GATE, [('            == v.get("receipt_manifest_sha256")\n', '            == si.sha256_input(P, "pf-recv", base + '
                                                                  '"preflight/receipt-manifest.json")["sha256"]\n')],
     [S7]),
    ("G09", "preflight input binding not checked",
     GATE, [('require(inputs.get("runtime_root") == d["runtime"] and', "require(True or")], [S7]),
    ("G10", "03 ACK verified before C-d accepted",
     GATE, [('and ack["verified_epoch"] >= ack["exit_epoch"] + C_D_SECONDS, "03 ACK', 'or True, "03 ACK')], [S7]),
    ("G11", "RC-7 admission not required",
     GATE, [('and adm.get("closed_before_admission") is True, "03 launch', 'or True, "03 launch')], [S7]),
    ("G12", "03 failed seal accepted", GATE, [('and ack.get("status") == "complete"', "")], [S7]),
    ("G13", "open ControlMaster accepted", GATE, [("ok_rcs=(255,))", "ok_rcs=(0, 255))")], [S7]),
    ("G14", "diagnostic preflight launch without the flag",
     GATE, [('require("--no-reference-work" not in opts or diagnostic,', "require(True,")], [S7]),
    ("G15", "preflight receive dir not empty accepted",
     GATE, [('require(names == [], "Preflight receive directory must be empty")', "pass")], [S7]),
    ("G16", "END bundle of another round accepted",
     GATE, [('require(g.group(1).startswith("rd%02d-a" % int(opts["--round"])),', "require(True,")], [S7]),
    # ---- host program (S7, host side)
    ("R01", "failed ps not reported", REM, [('        failures.append("ps: %s" % str(error)[:300])\n', "")], [S7]),
    ("R02", "hostname not bound to the host", REM, [('expected=cfg["host"])', "expected=None)")], [S7]),
    ("R03", "frozen-reader checks skipped", REM, [("    frozen_reader(cfg, P, res, failures)\n", "")], [S7]),
    ("R04", "staged pins not compared",
     REM, [('ok = si.sha256_input(P, "tools", os.path.basename(path))["sha256"] == expected',
            'ok = bool(si.sha256_input(P, "tools", os.path.basename(path)))')], [S7]),
    ("R05", "C5 nice not checked", REM, [('(gate["ps_nice"] == "0" and', '(True and')], [S7]),
    ("R06", "two claims accepted", REM, [("if len(names) >= 2:", "if False:")], [S7]),
    # ---- r3 (SOL END-FULL F1/F2/F3/F5/F6): one mutant per new guard
    ('F2a', 'shallow allowed for every role', TOOL, [('allow=("shallow",) if role == "guard-repo" else ()', 'allow=("shallow",)')], [HT, F2I]),
    ('F2b', 'unknown clone role accepted', TOOL, [('    if role not in CLONE_ROLES:\n', '    if False:\n')], [HT]),
    ('F2c', 'guard role need not be shallow', TOOL, [('        if flag != b"true\\n":', '        if False:')], [HT]),
    ('F2d', 'guard .git/shallow content not checked', TOOL, [('if shallow[-1] != "" or not shallow[:-1] or not all(OID40.fullmatch(s) for s in shallow[:-1]):', 'if False:')], [HT]),
    ('F2e', 'guard shallow commits not required present', TOOL, [('        for commit in shallow[:-1]:\n', '        for commit in shallow[:0]:\n')], [HT]),
    ('F2f', 'promisor/partial-clone config accepted', TOOL, [('    if promisor:\n', '    if False:\n')], [HT]),
    ('F2g', 'promisor pack accepted', TOOL, [('    if any(name.endswith(".promisor") for name in packs):', '    if False:')], [HT]),
    ('F2h', 'seed_commits outside the guard role', TOOL, [('    if role != "guard-repo":\n', '    if False:\n')], [HT]),
    ('F2i', 'S5 checks the real S3 guard repo in the repository role', PF, [('grants=("guard-job",), role="guard-repo"))', 'grants=("guard-job",), role="repository"))')], [F2I]),
    ('F2j', 'S5 checks the --repository clone in the guard role', PF, [('row.update(tool.verify_clone(si, host, str(a.repository), role="repository"))', 'row.update(tool.verify_clone(si, host, str(a.repository), role="guard-repo"))')], [F2I]),
    ('F2k', 'S7 host checks the guard repo in the repository role', REM, [('out["guard_repo"] = tool.verify_clone(si, cfg["host"], cfg["guard_job"] + "/repo", grants=("guard-job",),\n                                              role="guard-repo")', 'out["guard_repo"] = tool.verify_clone(si, cfg["host"], cfg["guard_job"] + "/repo", grants=("guard-job",),\n                                              role="repository")')], [F2I]),
    ('F2l', 'S7 host checks the --repository clone in the guard role', REM, [('tool.verify_clone(si, cfg["host"], cfg["repository"], role="repository")', 'tool.verify_clone(si, cfg["host"], cfg["repository"], role="guard-repo")')], [F2I]),
    ('F3a', 'relative HOME/XDG accepted', TOOL, [('    if not value.startswith("/"):\n        refuse("git-env", "%s is relative', '    if False:\n        refuse("git-env", "%s is relative')], [HT]),
    ('F3b', 'empty-but-set XDG accepted', TOOL, [('    if not isinstance(value, str) or value == "":', '    if not isinstance(value, str):')], [HT]),
    ('F3c', 'symlinked HOME/XDG accepted', TOOL, [('    if os.path.realpath(value) != value:', '    if False:')], [HT]),
    ('F3d', 'canonical HOME not installed in the executed env', TOOL, [('    env["HOME"] = home\n', '')], [HT]),
    ('F3e', 'GIT_CONFIG_NOSYSTEM not required', TOOL, [('    if env.get("GIT_CONFIG_NOSYSTEM") != "1":', '    if False:')], [HT]),
    ('F3f', 'XDG location ignored (r2: always $HOME/.config)', TOOL, [('return ((xdg if xdg is not None else home + "/.config") + "/git/config"', 'return ((home + "/.config") + "/git/config"')], [HT]),
    ('F3g', 'config paths skip the name gate', TOOL, [('        parts = si.name_gate(path, host, ())', '        parts = si.check_abs(path)')], [HT]),
    ('F3h', 'frozen-exec execs a re-derived env', TOOL, [('os.execvpe(command[0], command, env)', 'os.execvpe(command[0], command, frozen_git_env(si, dict(os.environ)))')], [HT]),
    ('F3i', 'S7 host program skips the frozen-reader env check', REM, [('out["global_git_config"] = tool.frozen_env_checked(si, cfg["host"], dict(os.environ))[1]', 'out["global_git_config"] = {}')], [S7]),
    ('F5a', 'preflight native identity not compared', GATE, [('require(isinstance(ident, dict) and ident.get("native_sha256") == NATIVE_SHA256', 'require(isinstance(ident, dict) and True')], [S7]),
    ('F5b', 'preflight corpus identity not compared', GATE, [('            and ident.get("corpus_sha256") == CORPUS_SHA256\n', '\n')], [S7]),
    ('F5c', 'preflight corpus-inventory identity not compared', GATE, [('            and ident.get("corpus_inventory_sha256") == inputs.get("corpus_inventory_sha256") == CORPUS_INVENTORY_SHA256,', '            ,')], [S7]),
    ('F5d', 'native/corpus paths not bound to the END argv', GATE, [('require(inputs.get("native") == identity["native"] == o["--native"]', 'require(True or inputs.get("native") == identity["native"] == o["--native"]')], [S7]),
    ('F5e', 'preflight compare-bundle identity not required', GATE, [('require(isinstance(digest, str) and SHA.fullmatch(digest) and ids.get("compare_bundle_sans_guard_sha256") == digest,', 'require(True,')], [S7]),
    ('F5f', 'host does not verify the bundle equivalence', REM, [('if cfg["kind"] == "end" and digest != cfg.get("bundle_sans_guard_sha256"):', 'if False:')], [S7]),
    ('F5g', 'guard-job-free digest keeps the guard job', TOOL, [('    del guard["job"]\n', '')], [S5, S7]),
    ('F5h', '03 attempt round not bound', GATE, [('require(int(ATTEMPT["end"].fullmatch(attempt).group(2)) == round_index,', 'require(True,')], [S7]),
    ('F5i', '03 admission not bound to the ACK/launch receipt', GATE, [('and adm.get("verified_sha256") == ack_sha and adm.get("launch_receipt_sha256") == receipt_sha,', 'and True,')], [S7]),
    ('F5j', '03 launch receipt round not bound', GATE, [('and rounds == [str(round_index)], "03 launch receipt', ', "03 launch receipt')], [S7]),
    ('F5k', '03 RC-6 declaration not bound', GATE, [('require(launch_.get("roots_sha256") == a.roots_sha256,', 'require(True,')], [S7]),
    ('F5l', '03 qualifying preflights not bound', GATE, [('require(sorted(used) == list(END_HOSTS) and all(', 'require(True or all(')], [S7]),
    ('F5m', '03 lineage check removed', GATE, [('\n                               **lineage_03(si, P, a, shape, pf, attempt, ack, ack_sha, adm))', ')')], [S7]),
    ('F5n', 'bus band not recomputed from the number', GATE, [('require(v.get("bus_band") == bus_band(pct),', 'require(True,')], [S7]),
    ('F5o', 'bus evidence finiteness not checked', GATE, [('require(finite(pct) and pct >= 0 and finite(secs)', 'require(True or finite(pct) and pct >= 0 and finite(secs)')], [S7]),
    ('F5p', 'bus percent/ticks consistency not checked', GATE, [('require(abs(pct - 100. * ticks / hz / secs) <= 1e-9 * max(1., abs(pct))', 'require(True')], [S7]),
    ('F5q', 'bus span not bound to the measured duration', GATE, [('            and secs == duration.get("loaded_seconds_measured"),\n', '            ,\n')], [S7]),
    ('F5r', 'bus gate/host not checked', GATE, [('require(v.get("bus_gate") == (v["bus_band"] if host == "127x04" else "not-gated-on-" + host),', 'require(True,')], [S7]),
    ('F5s', 'S5 frozen identity not the K4S END identity', PF, [('require(pins["native_sha256"] == NATIVE_SHA256 and r.corpus_sha256 == CORPUS_SHA256,', 'require(True,')], [S5]),
    ('F5t', 'S5 corpus inventory pin not the K4S inventory', PF, [('require(a.corpus_inventory_sha256 == CORPUS_INVENTORY_SHA256,', 'require(True,')], [S5]),
    ('F5u', 'S5 verified summary drops hz', PF, [('bus_cumulative_loaded=dict(loaded, hz=bus.get("hz")) if isinstance(loaded, dict) else loaded,', 'bus_cumulative_loaded=loaded,')], [S5]),
    ('F6a', 'non-executable shims tolerated', T + "helpers.py", [('if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) & 0o111 != 0o111 or not os.access(path, os.X_OK):', 'if False:')], [HT]),
    ('F1a', 'preflight default layer path normalized (hides aliases)', PF, [('return k4s_bootstrap_default_path(__file__, leaf) if directory is None', 'return os.path.abspath(k4s_bootstrap_default_path(__file__, leaf)) if directory is None')], [F1PY]),
    ('F1b', 'gate default layer path normalized (hides aliases)', GATE, [('return k4s_bootstrap_default_path(__file__, leaf) if directory is None', 'return os.path.abspath(k4s_bootstrap_default_path(__file__, leaf)) if directory is None')], [F1PY]),
    ('F1c', 'host tool default safe_input path normalized', TOOL, [('path = k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE) if path is None else path', 'path = os.path.abspath(k4s_bootstrap_default_path(__file__, SAFE_INPUT_FILE)) if path is None else path')], [F1PY]),
    ('F1d', 'verifier default safe_input path normalized', VER, [('path = k4s_bootstrap_default_path(__file__, "safe_input.py") if directory is None', 'path = os.path.abspath(k4s_bootstrap_default_path(__file__, "safe_input.py")) if directory is None')], [F1PY]),
    ('F1e', 'preflight region: ancestor walk follows symlinks', PF, [('child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)', 'child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=fd)')], [F1PY]),
    ('F1f', 'gate region: outcome-name gate off', GATE, [('        if family is not None:\n            raise refused("outcome name family "', '        if False:\n            raise refused("outcome name family "')], [F1PY]),
    ('F1g', 'END wrapper: tool() opens the host tool by path', EW, [('tool() { "$python" -I -S -c "$k4s_loader" "$host_tool" "$host_tool_sha" "$host_tool_size" -- "$@"; }', 'tool() { "$python" -I -S "$host_tool" "$@"; }')], [F1SWAP]),
    ('F1h', 'preflight wrapper: canonical verify step skipped', PW, [('k4s_verify_host_tool || exit 90\n', 'true\n')], [F1SH]),
    ('F1i', 'preflight wrapper: tool() opens the host tool by path', PW, [('tool() { "$python" -I -S -c "$k4s_loader" "$host_tool" "$host_tool_sha" "$host_tool_size" -- "$@"; }', 'tool() { "$python" -I -S "$host_tool" "$@"; }')], [F1SWAP]),
    ('F1j', 'END wrapper loader: nlink checked neither before nor after open (hard-linked canary read)', EW, [('        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:', '        if not stat.S_ISREG(before.st_mode) or before.st_size != size:'), ('            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size', '            if (not stat.S_ISREG(info.st_mode) or info.st_size != size')], [F1SH]),
    # ---- r4 (INTEGRATION-AUDIT-r1): U5 build-argv + argv pins, U6, U7, L1, L6, U12, U8
    ('R01', 'argv: host python not pinned', GATE, [('require(python == HOST_PYTHON,', 'require(True,')], [R4T]),
    ('R02', 'argv: evidence path not the bundle copy', GATE, [('require(opts["--end-evidence"] == opts["--bundle"] + "/" + END_EVIDENCE_REL,', 'require(True,')], [R4T]),
    ('R03', 'argv: evidence SHA not the evidence of record', GATE, [('require(opts["--end-evidence-sha256"] == END_EVIDENCE_SHA256,', 'require(True,')], [R4T]),
    ('R04', 'argv: SD1 SHA not pinned', GATE, [('require(opts["--sd1-manifest-sha256"] == SD1_MANIFEST_SHA256,', 'require(True,')], [R4T]),
    ('R05', 'argv: preflight corpus-inventory SHA not pinned', GATE, [('require(kind == "end" or opts["--corpus-inventory-sha256"] == CORPUS_INVENTORY_SHA256,', 'require(True,')], [R4T]),
    ('R06', 'argv: --end-job-sha256 format not checked', GATE, [('require(job_sha is None or SHA.fullmatch(job_sha),', 'require(True,')], [R4T]),
    ('R07', 'build-argv: assembly receipt not checked', GATE, [('require(receipt.get("schema") == ASSEMBLY_SCHEMA and receipt.get("production_pins") is True', 'require(True or receipt.get("schema") == ASSEMBLY_SCHEMA and receipt.get("production_pins") is True')], [R4T]),
    ('R08', 'build-argv: tiers-pins sidecar not checked', GATE, [('require(si.read_bytes(P, "staging", name + "/tiers-pins.sha256", max_size=4096)', 'require(True or si.read_bytes(P, "staging", name + "/tiers-pins.sha256", max_size=4096)')], [R4T]),
    ('R09', 'build-argv: bundle manifest evidence/profile not checked', GATE, [('require("k4s_s4_synthetic" not in manifest and manifest.get("profile") == "fleet-reference"', 'require(True or "k4s_s4_synthetic" not in manifest and manifest.get("profile") == "fleet-reference"')], [R4T]),
    ('R10', 'build-argv: tiers-pins read without the RC-6 SHA', GATE, [('                            expected_sha256=declared["tiers_pins_sha256"])', '                            expected_sha256=None)')], [R4T]),
    ('R11', 'build-argv: END-JOB binding not checked', GATE, [('require(isinstance(job, dict) and job.get("schema") == END_JOB_SCHEMA and job.get("study") == "PREREG-K4S"', 'require(True or isinstance(job, dict) and job.get("schema") == END_JOB_SCHEMA and job.get("study") == "PREREG-K4S"')], [R4T]),
    ('R12', 'build-argv: composed argv not validated before writing', GATE, [('    shape = validate_argv(si, argv, a.kind, a.host, a.attempt, roots, a.diagnostic_preflight)\n    data =', '    shape = dict(mode="diagnostic" if a.diagnostic_preflight else "binding")\n    data =')], [R4T]),
    ('R13', 'build-argv: END native/corpus identity not validated', GATE, [('        identity = launch_identity(v, d, a.host)\n', '        identity = v["identity"]\n')], [R4T]),
    ('R14', 'build-argv: preflight receipt schema/host not checked', GATE, [('require(v.get("schema") == VERIFIED_SCHEMA and v.get("host") == a.host and v.get("attempt") == attempt_,', 'require(True,')], [R4T]),
    ('R15', 'build-argv: END input set not enforced', GATE, [('require(a.end_job_commit and sorted(pf) == [a.host] and a.native is None', 'require(True or a.end_job_commit and sorted(pf) == [a.host] and a.native is None')], [R4T]),
    ('R16', 'build-argv: preflight input set not enforced', GATE, [('require(a.native and a.corpus and a.compare_bundle and a.hold_seconds is not None and not pf,', 'require(True,')], [R4T]),
    ('R17', 'prepare-preflight-receive: not 0700', GATE, [('writer.mkdir_excl(a.attempt, mode=0o700)', 'writer.mkdir_excl(a.attempt, mode=0o755)')], [R4T]),
    ('R18', 'U12: bus decision value not checked', GATE, [('and decision.get("decision") == "proceed" and decision.get("preflight_attempt") == attempt', 'and decision.get("preflight_attempt") == attempt')], [R4T]),
    ('R19', 'U12: repeat ruling attempt not checked', GATE, [('and ruling.get("attempt") == attempt and isinstance(ruling.get("coordinator_ref"), str)', 'and isinstance(ruling.get("coordinator_ref"), str)')], [R4T]),
    ('L01', 'L1: end_reference.py pin not compared', REM, [('if got != cfg["end_reference_sha256"]:', 'if False:')], [R4T]),
    ('L02', 'L1: native/corpus not checked on the host', REM, [('for i, path in enumerate(cfg["inputs"]):\n            role = "input-%d" % i', 'for i, path in enumerate(cfg["inputs"][:0]):\n            role = "input-%d" % i')], [R4T]),
    ('L03', 'L1: END-JOB at HEAD not checked', REM, [('        if cfg.get("end_job_sha256"):\n', '        if False:\n')], [R4T]),
    ('L04', 'L1: END-JOB at HEAD read without its SHA', REM, [('expected_sha256=cfg["end_job_sha256"])', 'expected_sha256=None)')], [R4T]),
    ('L05', 'L1: END-JOB evidence/manifest binding not checked', REM, [('bound = (isinstance(job, dict) and job.get("schema") == cfg["end_job_schema"]', 'bound = (True or isinstance(job, dict) and job.get("schema") == cfg["end_job_schema"]')], [R4T]),
    ('L06', 'L1: staged checks never called', REM, [('    staged_runtime_and_job(cfg, res, failures)\n', '')], [R4T]),
    ('L07', 'L6: S5 does not read DELTA-MANIFEST', PF, [('    si.read_bytes(policy, "runtime", DELTA_MANIFEST_REL, max_size=4 << 20, expected_sha256=DELTA_MANIFEST_SHA256)\n', '')], [R4T]),
    ('L08', 'L6: S5 reads DELTA-MANIFEST without its pin', PF, [('max_size=4 << 20, expected_sha256=DELTA_MANIFEST_SHA256)', 'max_size=4 << 20, expected_sha256=None)')], [R4T]),
    ('U01', 'U7: verifier --prepare writes no PREPARE-PROOF copy', VER, [('        copy = writer.create_excl("PREPARE-PROOF.json", data)', '        copy = prepared')], [R4T]),
    ('U02', 'U7: existing PREPARE-PROOF not checked before creating', VER, [('    si.check_absent(P, "launch-attempt", "PREPARE-PROOF.json")\n', '')], [R4T]),
    ('U03', 'U7: end-launch base not required canonical first', VER, [('    si.check_dir(P, "launch-base")                                 # end-launch/ is never created here\n', '')], [R4T]),
    ('J01', 'U8: evidence read without its pin', AJ, [('max_size=16 << 20, expected_sha256=END_EVIDENCE_SHA256)\n    evidence = si.loads_strict(raw, END_EVIDENCE_REL)\n    require(', 'max_size=16 << 20, expected_sha256=None)\n    evidence = si.loads_strict(raw, END_EVIDENCE_REL)\n    require(')], [A6T]),
    ('J02', 'U8: K4S manifest read without its pin', AJ, [('max_size=1 << 20, expected_sha256=K4S_MANIFEST_SHA256)', 'max_size=1 << 20, expected_sha256=None)')], [A6T]),
    ('J03', 'U8: completion of record not required', AJ, [('require(completion_item["sha256"] == COMPLETION_SHA256,', 'require(True,')], [A6T]),
    ('J04', 'U8: counted hosts not required', AJ, [('require(isinstance(hosts, dict) and sorted(hosts) == COUNTED_HOSTS', 'require(isinstance(hosts, dict)')], [A6T]),
    ('J05', 'U8: plan study not checked', AJ, [('require(isinstance(plan, dict) and plan.get("study") == STUDY,', 'require(True,')], [A6T]),
    ('J06', 'U8: R6 END namespace at P not checked', AJ, [('require(end_names == [],', 'require(True,')], [A6T]),
    ('J07', 'U8: item commit ancestry not checked', AJ, [('require(is_ancestor(si, g, item["commit"], commit),', 'require(True,')], [A6T]),
    ('J08', 'U8: item repository path not checked', AJ, [('require(isinstance(rel, str) and rel == STUDY_DIR + "/" + item["path"] and ".." not in rel.split("/"),\n            "END evidence', 'require(isinstance(rel, str),\n            "END evidence')], [A6T]),
    ('J09', 'U8: item blob read without its pin', AJ, [('                            expected_sha256=item["sha256"])\n    return item, data', '                            expected_sha256=None)\n    return item, data')], [A6T]),
    ('J10', 'U8: item keys not exact', AJ, [('require(isinstance(item, dict) and set(item) == {"commit", "path", "repository_path", "sha256"}', 'require(isinstance(item, dict)')], [A6T]),
    ('J11', 'U8: declared_by not checked', AJ, [('require(isinstance(declared_by, str) and DECLARED_BY.fullmatch(declared_by) and declared_by.strip(),', 'require(isinstance(declared_by, str),')], [A6T]),
    ('J12', 'U8: JOB_FIELDS drifted from the frozen set', AJ, [('"k4s_manifest_sha256", "plan_sha256", "schema", "study")', '"k4s_manifest_sha256", "plan_sha256", "schema", "study", "extra")')], [A6T]),
    ('J13', 'U8: scratch diff not exactly the END-JOB', AJ, [('require(x != commit and names == [END_JOB_REL.encode()],', 'require(x != commit,')], [A6T]),
    ('J14', 'U8: scratch HEAD not required to be P\'', AJ, [('require(head == commit, "scratch clone HEAD is not P\'")', 'require(True, "scratch clone HEAD is not P\'")')], [A6T]),
    ('J15', 'U8: frozen end_job result not checked', AJ, [('require(frozen_result["end_job"]["commit"] == x and frozen_result["end_job"]["sha256"] == job_sha256', 'require(True or frozen_result["end_job"]["commit"] == x and frozen_result["end_job"]["sha256"] == job_sha256')], [A6T]),
    ('J16', 'U8: S9 equivalence result not checked', AJ, [('require(equivalence.get("end_job_commit") == x and equivalence.get("runtime_commit") == commit', 'require(True or equivalence.get("end_job_commit") == x and equivalence.get("runtime_commit") == commit')], [A6T]),
    ('J17', 'U8: scratch directory kept', AJ, [('        shutil.rmtree(scratch, ignore_errors=True)\n    require(not os.path.exists(scratch), "scratch directory not removed: " + scratch)\n', '        pass\n')], [A6T]),
    ('J18', 'U8: S9 runtime manifest pin not checked', AJ, [('require(sha_bytes(raw) == FROZEN_RUNTIME_MANIFEST_SHA256,', 'require(True,')], [A6T]),
    ('J19', 'U8: frozen driver files not checked against their pins', AJ, [('require(si.sha256_input(P, "rt-files", rel)["sha256"] == pin,', 'require(True,')], [A6T]),
    ('J20', 'U8: S9 code not checked against its pin', AJ, [('require(si.sha256_input(P, "s9", os.path.basename(S9_PATH))["sha256"] == S9_SHA256,', 'require(True,')], [A6T]),
    ('U04', 'U7: receive attempt not checked absent before the launch dirs are made', VER, [('    si.check_absent(P, "host-read", attempt)                       # both files absent before either is created\n', '')], [R4T]),
]


def _drift(name, constant):
    """r5: a one-hex-digit drift of a builder SHA constant, computed from the current file (no SHA typed here)."""
    m = re.search(r'\n%s = "[0-9a-f]{64}"' % constant, (ROOT / name).read_text())
    if m is None:
        return ("\n%s = MISSING" % constant, "")
    line = m.group(0)
    return (line, line[:-2] + ("0" if line[-2] != "0" else "1") + '"')


MUTANTS += [
    # ---- r5 (SOL-REVIEW-END-INTEGRATION-r1): U4 host interpreter, finding 1 builder binding
    ('I01', 'U4: host python reverted to the bare uv binary', GATE, [('HOST_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"', 'HOST_PYTHON = "/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12"')], [R5T]),
    ('I02', 'U4: composed argv runs the interpreter without -B', GATE, [('+ [HOST_PYTHON, "-B"]', '+ [HOST_PYTHON]')], [R5T]),
    ('I03', 'U4: interpreter flag not required to be exactly -B', GATE, [('os.path.basename(python).startswith("python") and flag == "-B",', 'os.path.basename(python).startswith("python"),')], [R5T]),
    ('J21', 'U8 r5: runtime manifest not bound to the adopted S9 (script_sha256)', AJ, [('require(isinstance(manifest, dict) and manifest.get("script_sha256") == S9_SHA256,', 'require(isinstance(manifest, dict),')], [A6R5]),
    ('J22', 'U8 r5: runtime manifest commit/repository/python not bound', AJ, [('require(manifest.get("commit") == EVIDENCE_COMMIT and manifest.get("repository") == REPO_FULL', 'require(True or manifest.get("commit") == EVIDENCE_COMMIT and manifest.get("repository") == REPO_FULL')], [A6R5]),
    ('J23', 'U8 r5: builder S9 path drifts to the predecessor package', AJ, [('S9_PATH = RUNNER + "/end-prep/s3s9s10-r5/s9_end_runtime.py"', 'S9_PATH = RUNNER + "/end-prep/s3s9s10-r4/s9_end_runtime.py"')], [R5REC]),
    ('J24', 'U8 r5: builder S9 SHA drifts from the adoption record', AJ, [_drift(AJ, "S9_SHA256")], [R5REC]),
    ('J25', 'U8 r5: builder runtime-manifest SHA drifts from the adoption record', AJ, [_drift(AJ, "FROZEN_RUNTIME_MANIFEST_SHA256")], [R5REC]),
    ('J26', 'U8 r5: builder runtime path drifts to the superseded runtime', AJ, [('FROZEN_RUNTIME = RUNNER + "/end-staging/runtime-98566c032d0b"', 'FROZEN_RUNTIME = RUNNER + "/end-staging/SUPERSEDED-r3-runtime-98566c032d0b"')], [R5REC]),
]
# Equivalent mutants (masked by a stronger check on the same path; documented, not test gaps):
EQUIVALENT = {
    "P14": "load['reference_slot_work'] and mode_requested == 'binding' both derive from the same --no-reference-work "
           "argument (result['load'] is set from a.reference_work); the states-worked > 0 condition remains",
    "P22": "the walk role allows exactly the sealed names (an extra file refuses as allowlist) and every listed file is "
           "hashed (a missing one refuses as missing), so the set equality cannot fail on its own",
}
NULLS = [("N%02d" % i, "NULL control (unmodified)", None, [], files)
         for i, files in enumerate([[HT, S5], [S6W, S6V], [S7], [S5], [S7], [S6W], [F2I], [F1], [R4T], [A6T], [R5T]],
                                   1)]


def apply(root, mutant):
    _, _, name, edits, _ = mutant
    if name is None:
        return
    path = root / name
    text = path.read_text()
    for old, new in edits:
        count = text.count(old)
        if count != 1:
            raise SystemExit("%s: edit target occurs %d times in %s: %r" % (mutant[0], count, name, old[:80]))
        text = text.replace(old, new)
    path.write_text(text)


def run_one(mutant, python, pythonpath, timeout):
    ident, desc, name, edits, files = mutant
    work = Path(tempfile.mkdtemp(prefix="s567r5-mut-%s-" % ident, dir="/dev/shm"))
    try:
        pkg = work / "s5s6s7-r5"
        shutil.copytree(ROOT, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        apply(pkg, mutant)
        subprocess.run([sys.executable, "-B", str(pkg / "tests" / "repin.py")], check=True, capture_output=True)
        optimized = name != VER and not (name is None and S6V in files)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        if pythonpath:
            env["PYTHONPATH"] = pythonpath
        argv = ["nice", "-n", "19", python] + (["-O"] if optimized else []) + ["-B", "-m", "pytest", "-x", "-q",
                                                                               "-p", "no:cacheprovider"] + files
        started = time.time()
        try:
            done = subprocess.run(argv, cwd=str(pkg), env=env, capture_output=True, text=True, timeout=timeout)
            rc, tail = done.returncode, (done.stdout + done.stderr)[-600:]
        except subprocess.TimeoutExpired:
            rc, tail = "timeout", "timeout"
        verdict = "KILLED" if rc != 0 else "SURVIVED"
        return dict(id=ident, description=desc, file=name, tests=files, optimized=optimized, rc=rc,
                    verdict=verdict, seconds=round(time.time() - started, 1), tail=tail)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-edits", action="store_true")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--pythonpath", default="")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.check_edits:
        for mutant in MUTANTS:
            path = ROOT / mutant[2]
            text = path.read_text()
            for old, _ in mutant[3]:
                if text.count(old) != 1:
                    raise SystemExit("%s: target occurs %d times: %r" % (mutant[0], text.count(old), old[:80]))
        print("%d mutants, every edit target occurs exactly once" % len(MUTANTS))
        return 0
    todo = [m for m in MUTANTS + NULLS if not a.only or m[0] in a.only]
    results = []
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
        for result in pool.map(lambda m: run_one(m, a.python, a.pythonpath, a.timeout), todo):
            results.append(result)
            print("%-4s %-9s %6ss  %s" % (result["id"], result["verdict"], result["seconds"], result["description"]),
                  flush=True)
    import hashlib
    for r in results:
        if r["id"] in EQUIVALENT:
            r["equivalent"] = EQUIVALENT[r["id"]]
    summary = dict(python=a.python, equivalent_survivors=sorted(r["id"] for r in results if r["id"] in EQUIVALENT
                                                                   and r["verdict"] == "SURVIVED"), created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   package_sha256={n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
                                   for n in (TOOL, PF, EW, PW, VER, GATE, REM, AJ, "safe_input.py")},
                   mutants=len([r for r in results if not r["id"].startswith("N")]),
                   killed=len([r for r in results if not r["id"].startswith("N") and r["verdict"] == "KILLED"]),
                   nulls_survived=len([r for r in results if r["id"].startswith("N") and r["verdict"] == "SURVIVED"]),
                   nulls=len([r for r in results if r["id"].startswith("N")]), results=results)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, sort_keys=True))
    if a.out:
        Path(a.out).write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
