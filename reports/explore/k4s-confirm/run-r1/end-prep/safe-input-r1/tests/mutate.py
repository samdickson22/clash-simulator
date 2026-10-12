"""Mutation check for safe_input.py (not a pytest module). Each mutant applies exact textual edits (every `old` must
occur exactly once) to a copy in a fresh /dev/shm temp dir, then runs the whole suite against it (-x, its own
--basetemp inside that temp dir). KILLED = pytest exit 1 (a test failed). SURVIVED = exit 0. Anything else is
INVALID. Results are printed as JSON on stdout; nothing is written outside the temp dir, which is removed.

usage: python -B [-O] tests/mutate.py [--only ID[,ID...]]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), "safe_input.py")

# (id, gate, [(old, new), ...])
MUTANTS = [
    # ---- names (item 4)
    ("N01", "outcome dir games", [('OUTCOME_DIRS = ("games", "hub-blocks")', 'OUTCOME_DIRS = ("hub-blocks",)')]),
    ("N02", "outcome dir hub-blocks", [('OUTCOME_DIRS = ("games", "hub-blocks")', 'OUTCOME_DIRS = ("games",)')]),
    ("N03", "name family variants", [('return name == base or name.startswith(base + ".") or name.startswith("." + base)',
                                      'return name == base')]),
    ("N04", "casefold", [("folded = [p.casefold() for p in parts]", "folded = list(parts)")]),
    ("N05", "leaf complete.json", [('OUTCOME_LEAVES = ("complete.json", ', 'OUTCOME_LEAVES = (')]),
    ("N06", "leaf hub-ack.returned.json", [('"hub-ack.json", "hub-ack.returned.json", "end-raw.json")',
                                            '"hub-ack.json", "end-raw.json")')]),
    ("N07", "leaf end-raw.json", [('"hub-ack.json", "hub-ack.returned.json", "end-raw.json")',
                                   '"hub-ack.json", "hub-ack.returned.json")')]),
    ("N08", "leaf interference.json", [('"end-complete.json", "interference.json",', '"end-complete.json",')]),
    ("N09", "E4 leaf exemption scope", [('not (e4_leaf and i == last and parts[i] == "complete.json")',
                                         'not e4_leaf')]),
    ("N10", "reporting job grant", [('REPORTING_JOB.fullmatch(p) and "reporting-job-exact" not in grants',
                                     'REPORTING_JOB.fullmatch(p) and False')]),
    ("N11", "guard job grant", [('GUARD_JOB.fullmatch(p) and "guard-job" not in grants',
                                 'GUARD_JOB.fullmatch(p) and False')]),
    ("N12", "strict END pair", [('            if "end-json-exact" not in grants:\n', '            if False:\n')]),
    ("N13", "END: named .json only", [('if i + 1 == last or not folded[last].endswith(".json"):', 'if False:')]),
    ("N14", "T1 namespaces", [("for prefix in T1_LAUNCH_NAMESPACES + GLOBAL_FORBIDDEN_PREFIXES +",
                               "for prefix in GLOBAL_FORBIDDEN_PREFIXES +")]),
    ("N15", "04 perception root", [("PERCEPTION_PREFIXES.get(host, ())", "()")]),
    ("N16", "v4 cache repo", [("T1_LAUNCH_NAMESPACES + GLOBAL_FORBIDDEN_PREFIXES + ", "T1_LAUNCH_NAMESPACES + ")]),
    ("N17", "known host", [('    if host not in HOSTS:\n        refuse("policy", "unknown host %r" % (host,))\n    parts = check_abs(path)',
                            '    parts = check_abs(path)')]),
    # ---- paths
    ("P01", "rel '..'", [('''        refuse("path", "not a usable relative path: %r" % (rel,))
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):''', '''        refuse("path", "not a usable relative path: %r" % (rel,))
    parts = rel.split("/")
    if any(p in ("", ".") for p in parts):''')]),
    ("P02", "control/backslash chars", [('return "\\\\" in text or any(ord(c) < 32 or ord(c) == 127 for c in text)',
                                         'return False')]),
    # ---- root and component walk (item 2)
    ("W01", "root ancestor lstat layer", [('        if stat.S_ISLNK(st.st_mode):\n            refuse("root", "root %s: ancestor or root %s is a symlink" % (root, prefix))\n',
                                           '')]),
    ("W02", "root realpath layer", [('    if os.path.realpath(root) != root:\n        refuse("root", "root %s is not canonical" % root)\n',
                                     '')]),
    ("W03", "root: all three layers", [("    parts = check_abs(root)\n    for i in range(len(parts)):",
                                        "    parts = check_abs(root)\n    return os.open(root, os.O_RDONLY | os.O_DIRECTORY)\n    for i in range(len(parts)):")]),
    ("W04", "component fstatat symlink layer", [('            if stat.S_ISLNK(st.st_mode):\n                refuse("symlink", "%s: component %r is a symlink" % (label, part))\n',
                                                 '')]),
    ("W05", "component O_NOFOLLOW", [("DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC",
                                      "DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC")]),
    ("W06", "component dev/ino after open", [("if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):",
                                              "if not stat.S_ISDIR(now.st_mode):")]),
    ("W07", "leaf O_NOFOLLOW", [("LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK",
                                 "LEAF_FLAGS = os.O_RDONLY | os.O_NONBLOCK")]),
    ("W08", "leaf O_NONBLOCK", [("LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY",
                                 "LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NOCTTY")]),
    # ---- descriptor gate (item 3)
    ("D01", "pre-open symlink", [('    if stat.S_ISLNK(st.st_mode):\n        refuse("symlink", "%s: leaf is a symlink" % label)\n', '')]),
    ("D02", "pre-open regular", [('    if not stat.S_ISREG(st.st_mode):\n        refuse("not-regular", "%s: leaf is not a regular file (mode %o)" % (label, st.st_mode))\n', '')]),
    ("D03", "pre-open nlink", [('    if st.st_nlink != 1:\n        refuse("nlink", "%s: hard-linked leaf (st_nlink %d)" % (label, st.st_nlink))\n', '')]),
    ("D04", "pre-open size", [('    if st.st_size > cap or (expected_size is not None and st.st_size != expected_size):\n        refuse("size"',
                               '    if False:\n        refuse("size"')]),
    ("D05", "post-open regular", [('    if not stat.S_ISREG(now.st_mode):\n        problem = ("not-regular"', '    if False:\n        problem = ("not-regular"')]),
    ("D06", "post-open dev/ino", [('    elif (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):\n        problem = ("changed"', '    elif False:\n        problem = ("changed"')]),
    ("D07", "post-open nlink", [('    elif now.st_nlink != 1:\n        problem = ("nlink"', '    elif False:\n        problem = ("nlink"')]),
    ("D08", "post-open size", [('    elif now.st_size > cap or (expected_size is not None and now.st_size != expected_size):\n        problem = ("size"',
                                '    elif False:\n        problem = ("size"')]),
    # ---- reads (item 6)
    ("R01", "shrink", [('        if not chunk:\n            refuse("shrink", "%s: file shrank while read" % label)', '        if not chunk:\n            break')]),
    ("R02", "growth probe + fstat (joint)", [('    if os.read(fd, 1):\n        refuse("growth"', '    if False:\n        refuse("growth"'),
                                             ('    if os.fstat(fd).st_size != size:\n        refuse("growth"', '    if False:\n        refuse("growth"')]),
    ("R03", "growth fstat after read", [('    if os.fstat(fd).st_size != size:\n        refuse("growth"', '    if False:\n        refuse("growth"')]),
    ("R04", "expected sha", [('require(hashlib.sha256(data).hexdigest() == expected_sha256, "sha"', 'require(True, "sha"')]),
    ("R05", "json duplicate keys", [("object_pairs_hook=_no_dups, parse_constant=_no_constant)\n    except ValueError as error:",
                                     "parse_constant=_no_constant)\n    except ValueError as error:")]),
    ("R06", "json NaN/Infinity", [("return json.loads(text, object_pairs_hook=_no_dups, parse_constant=_no_constant)",
                                   "return json.loads(text, object_pairs_hook=_no_dups)")]),
    ("R07", "json max_size", [("cap = role.max_size if max_size is None else min(role.max_size, max_size)\n    require(type(cap) is int", "cap = role.max_size\n    require(type(cap) is int")]),
    ("R08", "Input single use", [('require(self._fd is not None, "state", "%s already consumed or closed" % self.label)', 'pass')]),
    # ---- policy and gate order (item 1)
    ("G01", "allowlist", [('require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))\n    return role, parts',
                           'return role, parts')]),
    ("G02", "name gate in _gate", [("    name_gate(role.root + \"/\" + rel, policy.host, role.grants, e4_leaf=e4_leaf)\n    require(role.allows(rel)",
                                    "    require(role.allows(rel)")]),
    ("G03", "role access", [('require(role.access == access, "policy", "role %s is not a %s role" % (role.name, access))', 'pass')]),
    ("G04", "local nodename", [('require(node == host, "policy", "local policy for %s but this host is %s" % (host, node))', 'pass')]),
    ("G05", "grants need exact names", [('require(not (grants & {"reporting-job-exact", "end-json-exact"}) or not patterns, "policy",', 'require(True, "policy",')]),
    ("G06", "role root name gate", [("            name_gate(role.root, host, role.grants)\n", "")]),
    ("G07", "unknown role", [('require(role is not None, "policy", "unknown role %r" % (name,))', 'pass')]),
    ("G08", "role declares names", [('require(exact or patterns, "policy", "role %s declares no names" % name)', 'pass')]),
    ("G09", "'*' never crosses '/'", [("fnmatch.fnmatchcase(rparts[0], head) and _match(pparts[1:], rparts[1:])",
                                       "fnmatch.fnmatchcase(\"/\".join(rparts), head)")]),
    # ---- exemptions (item 5)
    ("E01", "E1 link text", [('require(text == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (text, E1_LINK_TEXT))', 'pass')]),
    ("E02", "E1 alias must be a symlink", [('require(stat.S_ISLNK(st.st_mode), "exemption", "E1 %s is not a symlink" % E1_ALIAS)', 'pass')]),
    ("E03", "E1 role exemption", [('require("E1" in role.exemptions, "exemption", "role %s has no E1 exemption" % role.name)', 'pass')]),
    ("E04", "walk: E1 only at root", [('require("E1" in role.exemptions and rel == E1_ALIAS, "symlink", "symlink in tree: %s" % rel)',
                                        'require("E1" in role.exemptions, "symlink", "symlink in tree: %s" % rel)')]),
    ("E05", "walk: E1 target present", [('require(any(f["rel"] == E1_LINK_TEXT for f in files), "exemption", "E1 target missing from the tree")', 'pass')]),
    ("E06", "walk: E1 link text", [('require(link == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (link, E1_LINK_TEXT))', 'pass')]),
    ("E07", "E4 pin in hash_e4", [('require(digest == E4_COMPLETE_JSON[rel], "exemption", "E4 SHA mismatch for %s" % rel)', 'pass')]),
    ("E08", "E4 exact path", [('require(not e4 or e4_leaf, "exemption", "not an exact E4 path for an E4 role: %s" % rel)', 'pass')]),
    ("E09", "E4 copy: hash pass first", [("    hash_e4(policy, role_name, rel)\n    item = _open_gated(policy, role_name, rel, None, None, e4=True)",
                                          "    item = _open_gated(policy, role_name, rel, None, None, e4=True)")]),
    ("E10", "E4 copy: pin on copy pass", [('require(result["sha256"] == E4_COMPLETE_JSON[rel], "exemption", "E4 copy SHA mismatch for %s" % rel)', 'pass')]),
    ("E11", "walk: E4 bucket", [("                        if is_e4:\n                            e4.append(rel)", "                        if False:\n                            e4.append(rel)")]),
    ("E12", "walk: E4 needs role exemption", [('is_e4 = "E4" in role.exemptions and rel in E4_COMPLETE_JSON\n                    name_gate',
                                                'is_e4 = rel in E4_COMPLETE_JSON\n                    name_gate')]),
    # ---- walk_tree
    ("T01", "walk: names before lstat", [("                    name_gate(role.root + \"/\" + rel, policy.host, role.grants, e4_leaf=is_e4)\n", "")]),
    ("T02", "walk: nlink", [('require(st.st_nlink == 1, "nlink", "hard-linked file in tree: %s" % rel)', 'pass')]),
    ("T03", "walk: allowlist", [('require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))\n                        if is_e4:',
                                 'if is_e4:')]),
    ("T04", "walk: specials", [('refuse("not-regular", "special file in tree: %s" % rel)', 'pass')]),
    # ---- writes (item 7)
    ("X01", "O_EXCL", [("os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600",
                        "os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600")]),
    ("X02", "mkdir exists", [('refuse("exists", "%s:%s already exists" % (self.role.name, rel))', 'pass')]),
    ("X03", "writer parent walk", [('return open_dirs(self._fd, parts[:-1], "%s:%s" % (self.role.name, rel)), parts[-1]',
                                    'return os.open("/".join(parts[:-1]) or ".", os.O_RDONLY | os.O_DIRECTORY, dir_fd=self._fd), parts[-1]')]),
    ("X04", "writer cap", [('require(self._size + len(data) <= self._cap, "size"', 'require(True, "size"')]),
    ("X05", "writer canonical root", [("        self._fd = open_root(role.root)\n\n    def _parent", "        self._fd = os.open(role.root, os.O_RDONLY | os.O_DIRECTORY)\n\n    def _parent")]),
    ("X06", "writer file name gate", [('            _, parts = _gate(self.policy, self.role.name, rel, "write", e4)', '            parts = check_rel(rel)')]),
    ("X07", "writer dir name gate", [('            parts = check_rel(rel)\n            name_gate(self.role.root + "/" + rel, self.policy.host, self.role.grants)\n',
                                      '            parts = check_rel(rel)\n')]),
    ("X08", "writer access", [('require(role.access == "write", "policy", "role %s is not a write role" % role.name)\n        self.policy',
                               'self.policy')]),
    ("X09", "E1 symlink exemption", [('require("E1" in self.role.exemptions, "exemption", "role %s has no E1 exemption" % self.role.name)', 'pass')]),
    ("X10", "publish never replaces", [("                os.link(tleaf, fleaf, src_dir_fd=tparent, dst_dir_fd=fparent, follow_symlinks=False)",
                                        "                os.rename(tleaf, fleaf, src_dir_fd=tparent, dst_dir_fd=fparent)\n                os.link(fleaf, tleaf, src_dir_fd=fparent, dst_dir_fd=tparent)")]),
    ("X11", "publish: tmp nlink", [('require(st.st_nlink == 1, "nlink", "%s is hard-linked (st_nlink %d)" % (tmp_rel, st.st_nlink))', 'pass')]),
    ("X12", "publish: tmp regular", [('require(stat.S_ISREG(st.st_mode), "not-regular", "%s is not a regular file" % tmp_rel)', 'pass')]),
    ("C01", "CLI mode syntax", [('require(re.fullmatch(r"0[0-7]{3}", a.mode) is not None, "policy", "--mode must be octal like 0444")', 'pass')]),
    ("C02", "CLI refusal exit status", [('        sys.stderr.write("REFUSE %s\\n" % error)\n        return 3', '        sys.stderr.write("REFUSE %s\\n" % error)\n        return 0')]),
    # ---- subprocess (item 8)
    ("S01", "rc check", [('require(proc.returncode in ok_rcs, "subprocess"', 'require(True, "subprocess"')]),
    ("S02", "stdout/stderr bound", [("            if total > limit:", "            if False:")]),
    ("S03", "timeout watchdog", [("    watchdog.start()\n", "")]),
    ("S04", "lingering descendants", [('require(not lingering, "subprocess"', 'require(True, "subprocess"')]),
    ("S05", "explicit env", [("    full_env = {}\n", "    full_env = dict(os.environ)\n")]),
    ("S06", "absolute argv[0]", [('require(argv[0].startswith("/") and os.path.normpath(argv[0]) == argv[0], "subprocess",', 'require(True, "subprocess",')]),
    ("S07", "ps own row", [('require(len(me) == 1 and me[0]["ppid"] == os.getppid(), "subprocess", "ps table incomplete (own process missing)")', 'pass')]),
    ("S08", "hostname format", [('require(_HOSTNAME.fullmatch(text) is not None, "subprocess"', 'require(True, "subprocess"')]),
    ("S09", "hostname expected", [('require(expected is None or name.split(".")[0] == expected, "subprocess",', 'require(True, "subprocess",')]),
    ("S10", "git canonical repo", [('require(os.path.realpath(repo) == repo, "root", "repository %s is not canonical" % repo)', 'pass')]),
    ("S12", "ps field values", [("require(len(parts) >= n and all(re.fullmatch(_PS_FIELD_RULES[f], v) for f, v in zip(fields, parts)),",
                                 "require(len(parts) >= n,")]),
    ("S13", "ps field names", [('require(fields[:2] == ("pid", "ppid") and len(set(fields)) == len(fields)', 'require(True')]),
    ("S11", "stdin feed failure", [('require(state["stdin_error"] is None, "subprocess"', 'require(True, "subprocess"')]),
    # ---- git tree gate
    ("Q01", "tree: names", [("        _gate(policy, role_name, path, role.access, e4=is_e4)\n", "")]),
    ("Q02", "tree: only E1 symlink", [('require("E1" in role.exemptions and path == E1_ALIAS, "symlink"', 'require(True, "symlink"')]),
    ("Q03", "tree: entry type", [('require(entry["type"] == "blob", "not-regular"', 'require(True, "not-regular"')]),
    ("Q04", "tree: modes", [('require(mode in ("100644", "100755"), "not-regular", "tree entry', 'require(True, "not-regular", "tree entry')]),
    ("Q05", "tree: blob size", [('require(entry["size"] is not None and entry["size"] <= role.max_size, "size"', 'require(True, "size"')]),
    ("Q06", "tree: duplicates", [('require(path not in seen, "path", "duplicate tree path %s" % path)', 'pass')]),
    ("Q07", "tree: E1 target", [('require(any(f["path"] == E1_LINK_TEXT for f in files), "exemption", "E1 target not in the tree")', 'pass')]),
    ("Q08", "blob object id", [('require(algo(b"blob %d\\x00" % len(data) + data).hexdigest() == entry["oid"], "sha",', 'require(True, "sha",')]),
    ("Q09", "blob size", [('require(entry["size"] is None or len(data) == entry["size"], "size"', 'require(True, "size"')]),
    ("Q10", "planned entries only", [('require(any(entry is f for f in plan["files"]), "policy"', 'require(True, "policy"')]),
    ("Q11", "E1 tracked text", [('require(data == E1_LINK_TEXT.encode(), "exemption", "E1 tracked link text differs")', 'pass')]),
    ("Q12", "git E4 pin", [('require(digest == E4_COMPLETE_JSON[entry["path"]], "exemption", "E4 SHA mismatch for %s" % entry["path"])', 'pass')]),
    ("Q13", "ls-tree record format", [('require(match is not None, "subprocess", "ls-tree record malformed: %r" % text[:120])', 'pass')]),
    ("Q14", "show: role rooted at repo", [('require(role.root == repo, "root", "role %s is not rooted at the repository %s" % (role.name, repo))', 'pass')]),
    ("Q15", "show: names first", [("    _gate(policy, role_name, rel, role.access)\n    cap = role.max_size if max_size is None", "    cap = role.max_size if max_size is None")]),
    ("Q16", "show: exactly one entry", [('require(len(records) == 1 and match is not None and match.group(5) == rel, "subprocess",', 'require(match is not None, "subprocess",')]),
    ("Q17", "show: blob, not symlink", [('require(kind == "blob" and mode != "120000", "symlink" if mode == "120000" else "not-regular",', 'require(True, "x",')]),
    ("Q18", "show: size cap", [('require(int(size) <= cap, "size"', 'require(True, "size"')]),
    ("Q19", "show: expected sha", [('require(expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256, "sha",', 'require(True, "sha",')]),
    ("Q20", "export: E1 copy is the verified target", [('result = writer.create_excl(E1_ALIAS, git_blob(repo, plan, target[0], git_binary, timeout), 0o444)', 'result = writer.create_excl(E1_ALIAS, E1_LINK_TEXT.encode(), 0o444)')]),
    # ---- remote program (item 9)
    ("M01", "remote: name gates first", [('            name_gate(item["root"], host, item["grants"])\n            name_gate(full, host, item["grants"], e4_leaf=item["kind"] == "file" and item["e4"])\n', '')]),
    ("M02", "remote: host check", [('        if node != host:\n            refuse("host"', '        if False:\n            refuse("host"')]),
    ("M03", "remote: E4 hash-only/exact", [('            if item["e4"] and (item["content"] or item["rel"] not in E4_COMPLETE_JSON):', '            if False:')]),
    ("M04", "remote: E4 pin", [('                if item["e4"] and record["sha256"] != E4_COMPLETE_JSON[item["rel"]]:', '                if False:')]),
    ("M05", "remote: request keys", [('        if tuple(sorted(item)) != ITEM_KEYS[item["kind"]]:', '        if False:')]),
    ("M06", "remote: grants subset", [('if not isinstance(item["grants"], list) or not set(item["grants"]) <= set(GRANTS):', 'if not isinstance(item["grants"], list):')]),
    ("M07", "remote: two-pass (read during gate pass)", [('            gated.append((item, fd, {"size": st.st_size,', '            os.read(fd, 0)\n            gated.append((item, fd, {"size": st.st_size,')]),
    ("M08", "remote: duplicate keys", [('            req = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dups, parse_constant=_no_constant)',
                                        '            req = json.loads(raw.decode("utf-8"))')]),
    ("M09", "remote: absent check", [('                    refuse("exists", "path exists")', '                    gated.append((item, None, {}))\n                    continue')]),
    # ---- local parser and request builder
    ("L01", "parser rc", [('require(rc in (0, 3), "remote", "remote reader exited %s" % rc)', 'pass')]),
    ("L02", "parser nlink", [('require(got["nlink"] == 1, "nlink"', 'require(True, "nlink"')]),
    ("L03", "parser request sha", [('require(reply.get("request_sha256") == hashlib.sha256(request_bytes).hexdigest(), "remote", "request SHA differs")', 'pass')]),
    ("L04", "parser content sha", [('require(len(data) == got["size"] and hashlib.sha256(data).hexdigest() == got["sha256"], "remote",', 'require(True, "remote",')]),
    ("L05", "parser key sets", [('require(tuple(sorted(reply)) == _RESPONSE_OK and reply["status"] == "ok", "remote", "rc 0 without status ok")',
                                 'require(reply["status"] == "ok", "remote", "rc 0 without status ok")')]),
    ("L06", "parser rc 3 must be refusal", [('require(tuple(sorted(reply)) == _RESPONSE_REFUSED and reply["status"] == "refused", "remote",', 'require(True, "remote",')]),
    ("L07", "parser host", [('require(reply["host"] == request["host"], "remote"', 'require(True, "remote"')]),
    ("L08", "parser regular", [('require(stat.S_ISREG(got["mode"]), "not-regular"', 'require(True, "not-regular"')]),
    ("L09", "parser size cap", [('require(got["size"] <= asked["max_size"], "size"', 'require(True, "size"')]),
    ("L10", "parser E4 pin", [('                require(got["sha256"] == E4_COMPLETE_JSON[asked["rel"]], "exemption", "E4 SHA mismatch")', '                pass')]),
    ("L11", "parser unrequested content", [('require(b64 is None, "remote", "unrequested content returned")', 'pass')]),
    ("L12", "parser one line", [('require(isinstance(stdout, bytes) and stdout.endswith(b"\\n") and stdout.count(b"\\n") == 1, "remote",', 'require(True, "remote",')]),
    ("L13", "builder local gate", [('            _gate(policy, role.name, rel, "read", e4)\n            content = bool(item.get("content", False))',
                                    '            content = bool(item.get("content", False))')]),
    ("L14", "builder remote policy", [('require(isinstance(policy, Policy) and policy.remote, "policy", "a remote Policy is required")', 'pass')]),
    ("L15", "builder E4 hash-only", [('require(not (e4 and content), "exemption", "E4 is hash-only")', 'pass')]),
]


def run(python, mutant_dir, source_text, timeout):
    path = os.path.join(mutant_dir, "safe_input.py")
    with open(path, "w") as stream:
        stream.write(source_text)
    env = dict(os.environ, SAFE_INPUT_UNDER_TEST=path, PYTHONDONTWRITEBYTECODE="1")
    argv = [python, "-B"] + (["-O"] if sys.flags.optimize else []) + [
        "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-W", "ignore::pytest.PytestConfigWarning",
        "--basetemp", os.path.join(mutant_dir, "bt"), HERE]
    start = time.time()
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=timeout,
                              cwd=mutant_dir)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", round(time.time() - start, 1), ""
    tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    first_fail = next((line for line in tail if line.startswith("FAILED")), tail[-1] if tail else "")
    verdict = {1: "KILLED", 0: "SURVIVED"}.get(proc.returncode, "INVALID(rc=%d)" % proc.returncode)
    return verdict, round(time.time() - start, 1), first_fail[:200]


def main():
    only = None
    if len(sys.argv) == 3 and sys.argv[1] == "--only":
        only = set(sys.argv[2].split(","))
    with open(SOURCE) as stream:
        original = stream.read()
    ids = [m[0] for m in MUTANTS]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate mutant id")
    scratch = tempfile.mkdtemp(prefix="safe-input-mut-", dir="/dev/shm")
    results = []
    try:
        base_dir = os.path.join(scratch, "baseline")
        os.mkdir(base_dir)
        baseline = run(sys.executable, base_dir, original, 600)
        if baseline[0] != "SURVIVED":
            raise SystemExit("baseline suite does not pass: %r" % (baseline,))
        for ident, gate, edits in MUTANTS:
            if only and ident not in only:
                continue
            text, problem = original, None
            for old, new in edits:
                if text.count(old) != 1:
                    problem = "edit target occurs %d times: %r" % (text.count(old), old[:80])
                    break
                text = text.replace(old, new)
            if problem:
                results.append({"id": ident, "gate": gate, "verdict": "INVALID(edit)", "detail": problem})
                continue
            mdir = os.path.join(scratch, ident)
            os.mkdir(mdir)
            verdict, seconds, detail = run(sys.executable, mdir, text, 300)
            results.append({"id": ident, "gate": gate, "verdict": verdict, "seconds": seconds, "detail": detail})
            sys.stderr.write("%s %-45s %s\n" % (ident, gate, verdict))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    summary = {"python": sys.version.split()[0], "optimize": sys.flags.optimize, "baseline": baseline[0],
               "mutants": len(results), "killed": sum(r["verdict"] == "KILLED" for r in results),
               "not_killed": [r["id"] for r in results if r["verdict"] != "KILLED"], "results": results}
    print(json.dumps(summary, indent=1))
    return 0 if not summary["not_killed"] else 1


if __name__ == "__main__":
    sys.exit(main())
