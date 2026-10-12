"""Mutation check for safe_input.py (not a pytest module). Each mutant applies exact textual edits (every `old` must
occur exactly once) to a copy in a fresh /dev/shm temp dir, then runs the whole suite against it (-x, its own
--basetemp inside that temp dir). KILLED = pytest exit 1 (a test failed). SURVIVED = exit 0. Anything else is
INVALID. Results are printed as JSON on stdout; nothing is written outside the temp dir, which is removed.

usage: python -B [-O] tests/mutate.py [--only ID[,ID...]] [--jobs N] [--check-edits]
                                       [--recheck-without tests/FILE.py::TEST]
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), "safe_input.py")

EQUIVALENT = {
    'P03': "rel.startswith('/') redundant with the empty-component check",
    'growth-probe-alone': 'redundant with the final fstat size check (R02 joint, R03 fstat alone)',
    'O_NOFOLLOW-on-O_EXCL': 'O_CREAT|O_EXCL already fails on any existing name incl. symlinks (X01)',
    'O_NOCTTY': 'not testable without a tty; devices are refused before open',
    '--no-replace-objects alone / GIT_NO_REPLACE_OBJECTS alone': 'two layers; each alone is masked by the other (GH02 removes both)',
    'core.fsmonitor=false alone': 'masked by the repo-config refusal of core.fsmonitor and the scrubbed HOME/GIT_CONFIG_* (GH04 joint)',
    "commondir 'declared' check alone": 'masked by the target-equality check (GH12 joint, GH13 alone)',
    'objects/ real-directory check': 'masked: the alternates probe opens objects/ component-wise with O_NOFOLLOW and refuses a symlink',
    'receive post-create nlink/regular check': 'a file just created with O_CREAT|O_EXCL|O_NOFOLLOW is a single-link regular file',
    'E1 materialised-copy SHA re-check': 'create_excl hashes exactly the bytes it was given (the target blob)',
    "D3 'rel in role.exact' inside _gate": 'masked by the role allowlist, which a D3 role declares with exact names only',
    "E5 exact-path clause inside _gate alone": "masked by name_gate's own e5_rel exactness check (E5-06J joint, E5-03 alone)",
    "receive: E5 'not e4' clause": 'masked by the E4 pin rule: no E5 path is an E4 path, so e4+e5 refuses there first',
    "receive: E5 exact-path clause alone": "masked by the receiver's name_gate e5_rel exactness check before anything is created (E5-18J joint)",
    "name_gate: E5 leaf-only (i == last)": 'not mutated: every E5 path matches a family in its final component only (test_constant_is_exactly_the_ruling)',
}

# (id, gate, [(old, new), ...]); r1 ids keep their meaning, r2 ids are new gates
MUTANTS = [
    ('N04', 'casefold', [('folded = [p.casefold() for p in parts]', 'folded = list(parts)')]),
    ('N10', 'reporting job grant', [('REPORTING_JOB.fullmatch(p) and "reporting-job-exact" not in grants', 'REPORTING_JOB.fullmatch(p) and False')]),
    ('N11', 'guard job grant', [('GUARD_JOB.fullmatch(p) and "guard-job" not in grants', 'GUARD_JOB.fullmatch(p) and False')]),
    ('N12', 'strict END pair', [('            if "end-json-exact" not in grants:\n', '            if False:\n')]),
    ('N13', 'END: named .json only', [('if i + 1 == last or not folded[last].endswith(".json"):', 'if False:')]),
    ('N14', 'T1 namespaces', [('for prefix in T1_LAUNCH_NAMESPACES + GLOBAL_FORBIDDEN_PREFIXES +', 'for prefix in GLOBAL_FORBIDDEN_PREFIXES +')]),
    ('N15', '04 perception root', [('PERCEPTION_PREFIXES.get(host, ())', '()')]),
    ('N16', 'v4 cache repo', [('T1_LAUNCH_NAMESPACES + GLOBAL_FORBIDDEN_PREFIXES + ', 'T1_LAUNCH_NAMESPACES + ')]),
    ('N17', 'known host', [('    if host not in HOSTS:\n        refuse("policy", "unknown host %r" % (host,))\n    parts = check_abs(path)', '    parts = check_abs(path)')]),
    ('P01', "rel '..'", [('        refuse("path", "not a usable relative path: %r" % (rel,))\n    parts = rel.split("/")\n    if any(p in ("", ".", "..") for p in parts):', '        refuse("path", "not a usable relative path: %r" % (rel,))\n    parts = rel.split("/")\n    if any(p in ("", ".") for p in parts):')]),
    ('P02', 'control/backslash chars', [('return "\\\\" in text or any(ord(c) < 32 or ord(c) == 127 for c in text)', 'return False')]),
    ('W01', 'root ancestor lstat layer', [('        if stat.S_ISLNK(st.st_mode):\n            refuse("root", "root %s: ancestor or root %s is a symlink" % (root, prefix))\n', '')]),
    ('W02', 'root realpath layer', [('    if os.path.realpath(root) != root:\n        refuse("root", "root %s is not canonical" % root)\n', '')]),
    ('W03', 'root: all three layers', [('    parts = check_abs(root)\n    for i in range(len(parts)):', '    parts = check_abs(root)\n    return os.open(root, os.O_RDONLY | os.O_DIRECTORY)\n    for i in range(len(parts)):')]),
    ('W04', 'component fstatat symlink layer', [('            if stat.S_ISLNK(st.st_mode):\n                refuse("symlink", "%s: component %r is a symlink" % (label, part))\n', '')]),
    ('W05', 'component O_NOFOLLOW', [('DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC', 'DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC')]),
    ('W06', 'component dev/ino after open', [('if not stat.S_ISDIR(now.st_mode) or (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):', 'if not stat.S_ISDIR(now.st_mode):')]),
    ('W07', 'leaf O_NOFOLLOW', [('LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK', 'LEAF_FLAGS = os.O_RDONLY | os.O_NONBLOCK')]),
    ('W08', 'leaf O_NONBLOCK', [('LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY', 'LEAF_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NOCTTY')]),
    ('D01', 'pre-open symlink', [('    if stat.S_ISLNK(st.st_mode):\n        refuse("symlink", "%s: leaf is a symlink" % label)\n', '')]),
    ('D02', 'pre-open regular', [('    if not stat.S_ISREG(st.st_mode):\n        refuse("not-regular", "%s: leaf is not a regular file (mode %o)" % (label, st.st_mode))\n', '')]),
    ('D03', 'pre-open nlink', [('    if st.st_nlink != 1:\n        refuse("nlink", "%s: hard-linked leaf (st_nlink %d)" % (label, st.st_nlink))\n', '')]),
    ('D04', 'pre-open size', [('    if st.st_size > cap or (expected_size is not None and st.st_size != expected_size):\n        refuse("size"', '    if False:\n        refuse("size"')]),
    ('D05', 'post-open regular', [('    if not stat.S_ISREG(now.st_mode):\n        problem = ("not-regular"', '    if False:\n        problem = ("not-regular"')]),
    ('D06', 'post-open dev/ino', [('    elif (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):\n        problem = ("changed"', '    elif False:\n        problem = ("changed"')]),
    ('D07', 'post-open nlink', [('    elif now.st_nlink != 1:\n        problem = ("nlink"', '    elif False:\n        problem = ("nlink"')]),
    ('D08', 'post-open size', [('    elif now.st_size > cap or (expected_size is not None and now.st_size != expected_size):\n        problem = ("size"', '    elif False:\n        problem = ("size"')]),
    ('R01', 'shrink', [('        if not chunk:\n            refuse("shrink", "%s: file shrank while read" % label)', '        if not chunk:\n            break')]),
    ('R02', 'growth probe + fstat (joint)', [('    if os.read(fd, 1):\n        refuse("growth"', '    if False:\n        refuse("growth"'), ('    if os.fstat(fd).st_size != size:\n        refuse("growth"', '    if False:\n        refuse("growth"')]),
    ('R03', 'growth fstat after read', [('    if os.fstat(fd).st_size != size:\n        refuse("growth"', '    if False:\n        refuse("growth"')]),
    ('R04', 'expected sha', [('require(hashlib.sha256(data).hexdigest() == expected_sha256, "sha"', 'require(True, "sha"')]),
    ('R05', 'json duplicate keys', [('object_pairs_hook=_no_dups, parse_constant=_no_constant)\n    except ValueError as error:', 'parse_constant=_no_constant)\n    except ValueError as error:')]),
    ('R06', 'json NaN/Infinity', [('return json.loads(text, object_pairs_hook=_no_dups, parse_constant=_no_constant)', 'return json.loads(text, object_pairs_hook=_no_dups)')]),
    ('R07', 'json max_size', [('cap = role.max_size if max_size is None else min(role.max_size, max_size)\n    require(type(cap) is int', 'cap = role.max_size\n    require(type(cap) is int')]),
    ('G01', 'allowlist', [('require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))\n    return role, parts', 'return role, parts')]),
    ('G03', 'role access', [('require(role.access == access, "policy", "role %s is not a %s role" % (role.name, access))', 'pass')]),
    ('G04', 'local nodename', [('require(node == host, "policy", "local policy for %s but this host is %s" % (host, node))', 'pass')]),
    ('G06', 'role root name gate', [('            name_gate(role.root, host, role.grants)\n', '')]),
    ('G07', 'unknown role', [('require(role is not None, "policy", "unknown role %r" % (name,))', 'pass')]),
    ('G08', 'role declares names', [('require(exact or patterns, "policy", "role %s declares no names" % name)', 'pass')]),
    ('G09', "'*' never crosses '/'", [('fnmatch.fnmatchcase(rparts[0], head) and _match(pparts[1:], rparts[1:])', 'fnmatch.fnmatchcase("/".join(rparts), head)')]),
    ('E01', 'E1 link text', [('require(text == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (text, E1_LINK_TEXT))', 'pass')]),
    ('E02', 'E1 alias must be a symlink', [('require(stat.S_ISLNK(st.st_mode), "exemption", "E1 %s is not a symlink" % E1_ALIAS)', 'pass')]),
    ('E03', 'E1 role exemption', [('require("E1" in role.exemptions, "exemption", "role %s has no E1 exemption" % role.name)', 'pass')]),
    ('E04', 'walk: E1 only at root', [('require("E1" in role.exemptions and rel == E1_ALIAS, "symlink", "symlink in tree: %s" % rel)', 'require("E1" in role.exemptions, "symlink", "symlink in tree: %s" % rel)')]),
    ('E05', 'walk: E1 target present', [('require(any(f["rel"] == E1_LINK_TEXT for f in files), "exemption", "E1 target missing from the tree")', 'pass')]),
    ('E06', 'walk: E1 link text', [('require(link == E1_LINK_TEXT, "exemption", "E1 link text %r is not %r" % (link, E1_LINK_TEXT))', 'pass')]),
    ('E07', 'E4 pin in hash_e4', [('require(digest == E4_COMPLETE_JSON[rel], "exemption", "E4 SHA mismatch for %s" % rel)', 'pass')]),
    ('E08', 'E4 exact path', [('require(not e4 or e4_leaf, "exemption", "not an exact E4 path for an E4 role: %s" % rel)', 'pass')]),
    ('E09', 'E4 copy: hash pass first', [('    hash_e4(policy, role_name, rel)\n    item = _open_gated(policy, role_name, rel, None, None, e4=True)', '    item = _open_gated(policy, role_name, rel, None, None, e4=True)')]),
    ('E10', 'E4 copy: pin on copy pass', [('require(result["sha256"] == E4_COMPLETE_JSON[rel], "exemption", "E4 copy SHA mismatch for %s" % rel)', 'pass')]),
    ('E11', 'walk: E4 bucket', [('                        if is_e4:\n                            e4.append(rel)', '                        if False:\n                            e4.append(rel)')]),
    ('E12', 'walk: E4 needs role exemption', [('is_e4 = "E4" in role.exemptions and rel in E4_COMPLETE_JSON\n', 'is_e4 = rel in E4_COMPLETE_JSON\n')]),
    ('T01', 'walk: names before lstat', [('                    name_gate(role.root + "/" + rel, policy.host, role.grants, e4_leaf=is_e4,\n                              e5_rel=rel if is_e5 else None)\n', '')]),
    ('T02', 'walk: nlink', [('require(st.st_nlink == 1, "nlink", "hard-linked file in tree: %s" % rel)', 'pass')]),
    ('T03', 'walk: allowlist', [('require(role.allows(rel), "allowlist", "role %s does not declare %s" % (role.name, rel))\n                        if is_e4:', 'if is_e4:')]),
    ('T04', 'walk: specials', [('refuse("not-regular", "special file in tree: %s" % rel)', 'pass')]),
    ('X03', 'writer parent walk', [('return open_dirs(self._fd, parts[:-1], "%s:%s" % (self.role.name, rel)), parts[-1]', 'return os.open("/".join(parts[:-1]) or ".", os.O_RDONLY | os.O_DIRECTORY, dir_fd=self._fd), parts[-1]')]),
    ('X04', 'writer cap', [('require(self._size + len(data) <= self._cap, "size"', 'require(True, "size"')]),
    ('X05', 'writer canonical root', [('        self._fd = open_root(role.root)\n\n    def _parent', '        self._fd = os.open(role.root, os.O_RDONLY | os.O_DIRECTORY)\n\n    def _parent')]),
    ('X06', 'writer file name gate', [('            _, parts = _gate(self.policy, self.role.name, rel, "write", e4, e5=e5)', '            parts = check_rel(rel)')]),
    ('X07', 'writer dir name gate', [('            parts = check_rel(rel)\n            name_gate(self.role.root + "/" + rel, self.policy.host, self.role.grants)\n', '            parts = check_rel(rel)\n')]),
    ('X08', 'writer access', [('require(role.access == "write", "policy", "role %s is not a write role" % role.name)\n        self.policy', 'self.policy')]),
    ('X09', 'E1 symlink exemption', [('require("E1" in self.role.exemptions, "exemption", "role %s has no E1 exemption" % self.role.name)', 'pass')]),
    ('X10', 'publish never replaces', [('                os.link(tleaf, fleaf, src_dir_fd=tparent, dst_dir_fd=fparent, follow_symlinks=False)', '                os.rename(tleaf, fleaf, src_dir_fd=tparent, dst_dir_fd=fparent)\n                os.link(fleaf, tleaf, src_dir_fd=fparent, dst_dir_fd=tparent)')]),
    ('X11', 'publish: tmp nlink', [('require(st.st_nlink == 1, "nlink", "%s is hard-linked (st_nlink %d)" % (tmp_rel, st.st_nlink))', 'pass')]),
    ('X12', 'publish: tmp regular', [('require(stat.S_ISREG(st.st_mode), "not-regular", "%s is not a regular file" % tmp_rel)', 'pass')]),
    ('C01', 'CLI mode syntax', [('require(re.fullmatch(r"0[0-7]{3}", a.mode) is not None, "policy", "--mode must be octal like 0444")', 'pass')]),
    ('C02', 'CLI refusal exit status', [('        sys.stderr.write("REFUSE %s\\n" % error)\n        return 3', '        sys.stderr.write("REFUSE %s\\n" % error)\n        return 0')]),
    ('S01', 'rc check', [('require(proc.returncode in ok_rcs, "subprocess"', 'require(True, "subprocess"')]),
    ('S02', 'stdout/stderr bound', [('            if total > limit:', '            if False:')]),
    ('S03', 'timeout watchdog', [('    watchdog.start()\n', '')]),
    ('S04', 'lingering descendants', [('require(not lingering, "subprocess"', 'require(True, "subprocess"')]),
    ('S05', 'explicit env', [('    full_env = {}\n', '    full_env = dict(os.environ)\n')]),
    ('S06', 'absolute argv[0]', [('require(argv[0].startswith("/") and os.path.normpath(argv[0]) == argv[0], "subprocess",', 'require(True, "subprocess",')]),
    ('S07', 'ps own row', [('require(len(me) == 1 and me[0]["ppid"] == os.getppid(), "subprocess", "ps table incomplete (own process missing)")', 'pass')]),
    ('S08', 'hostname format', [('require(_HOSTNAME.fullmatch(text) is not None, "subprocess"', 'require(True, "subprocess"')]),
    ('S09', 'hostname expected', [('require(expected is None or name.split(".")[0] == expected, "subprocess",', 'require(True, "subprocess",')]),
    ('S12', 'ps field values', [('require(len(parts) >= n and all(re.fullmatch(_PS_FIELD_RULES[f], v) for f, v in zip(fields, parts)),', 'require(len(parts) >= n,')]),
    ('S13', 'ps field names', [('require(fields[:2] == ("pid", "ppid") and len(set(fields)) == len(fields)', 'require(True')]),
    ('Q01', 'tree: names', [('        _gate(policy, role_name, path, role.access, e4=is_e4, e5=is_e5)\n', '')]),
    ('Q02', 'tree: only E1 symlink', [('require("E1" in role.exemptions and path == E1_ALIAS, "symlink"', 'require(True, "symlink"')]),
    ('Q03', 'tree: entry type', [('require(entry["type"] == "blob", "not-regular"', 'require(True, "not-regular"')]),
    ('Q04', 'tree: modes', [('require(mode in ("100644", "100755"), "not-regular", "tree entry', 'require(True, "not-regular", "tree entry')]),
    ('Q05', 'tree: blob size', [('require(entry["size"] is not None and entry["size"] <= role.max_size, "size", "blob %s too large" % path)\n        (e4', 'require(True, "size", "blob %s too large" % path)\n        (e4')]),
    ('Q06', 'tree: duplicates', [('require(path not in seen, "path", "duplicate tree path %s" % path)', 'pass')]),
    ('Q11', 'E1 tracked text', [('require(data == E1_LINK_TEXT.encode(), "exemption", "E1 tracked link text differs")', 'pass')]),
    ('Q12', 'git E4 pin', [('require(digest == E4_COMPLETE_JSON[entry["path"]], "exemption", "E4 SHA mismatch for %s" % entry["path"])', 'pass')]),
    ('Q13', 'ls-tree record format', [('require(match is not None, "subprocess", "ls-tree record malformed: %r" % text[:120])', 'pass')]),
    ('Q15', 'show: names first', [('    _gate(policy, role_name, rel, role.access)\n    cap = role.max_size if max_size is None', '    cap = role.max_size if max_size is None')]),
    ('Q16', 'show: exactly one entry', [('require(len(records) == 1 and match is not None and match.group(5) == rel, "subprocess",', 'require(match is not None, "subprocess",')]),
    ('Q17', 'show: blob, not symlink', [('require(kind == "blob" and mode != "120000", "symlink" if mode == "120000" else "not-regular",', 'require(True, "x",')]),
    ('Q18', 'show: size cap', [('require(int(size) <= cap, "size"', 'require(True, "size"')]),
    ('M01', 'remote: name gates first', [('            name_gate(item["root"], host, item["grants"])\n            name_gate(full, host, item["grants"], e4_leaf=item["kind"] == "file" and item["e4"])\n', '')]),
    ('M03', 'remote: E4 hash-only/exact', [('            if item["e4"] and (item["content"] or item["rel"] not in E4_COMPLETE_JSON):', '            if False:')]),
    ('M04', 'remote: E4 pin', [('                if item["e4"] and record["sha256"] != E4_COMPLETE_JSON[item["rel"]]:', '                if False:')]),
    ('M05', 'remote: request keys', [('        if tuple(sorted(item)) != ITEM_KEYS[item["kind"]]:', '        if False:')]),
    ('M06', 'remote: grants subset', [('if not isinstance(item["grants"], list) or not set(item["grants"]) <= set(GRANTS):', 'if not isinstance(item["grants"], list):')]),
    ('M07', 'remote: two-pass (read during gate pass)', [('            gated.append((item, fd, {"size": st.st_size,', '            os.read(fd, 0)\n            gated.append((item, fd, {"size": st.st_size,')]),
    ('M09', 'remote: absent check', [('                    refuse("exists", "path exists")', '                    gated.append((item, None, {}))\n                    continue')]),
    ('L01', 'parser rc', [('require(rc in (0, 3), "remote", "remote reader exited %s" % rc)', 'pass')]),
    ('L02', 'parser nlink', [('require(got["nlink"] == 1, "nlink"', 'require(True, "nlink"')]),
    ('L03', 'parser request sha', [('require(reply.get("request_sha256") == hashlib.sha256(request_bytes).hexdigest(), "remote", "request SHA differs")', 'pass')]),
    ('L04', 'parser content sha', [('require(len(data) == got["size"] and hashlib.sha256(data).hexdigest() == got["sha256"], "remote",', 'require(True, "remote",')]),
    ('L05', 'parser key sets', [('require(tuple(sorted(reply)) == _RESPONSE_OK and reply["status"] == "ok", "remote", "rc 0 without status ok")', 'require(reply["status"] == "ok", "remote", "rc 0 without status ok")')]),
    ('L06', 'parser rc 3 must be refusal', [('require(tuple(sorted(reply)) == _RESPONSE_REFUSED and reply["status"] == "refused", "remote",', 'require(True, "remote",')]),
    ('L07', 'parser host', [('require(reply["host"] == request["host"], "remote"', 'require(True, "remote"')]),
    ('L08', 'parser regular', [('require(stat.S_ISREG(got["mode"]), "not-regular"', 'require(True, "not-regular"')]),
    ('L09', 'parser size cap', [('require(got["size"] <= asked["max_size"], "size"', 'require(True, "size"')]),
    ('L10', 'parser E4 pin', [('                require(got["sha256"] == E4_COMPLETE_JSON[asked["rel"]], "exemption", "E4 SHA mismatch")', '                pass')]),
    ('L11', 'parser unrequested content', [('require(b64 is None, "remote", "unrequested content returned")', 'pass')]),
    ('L13', 'builder local gate', [('            _gate(policy, role.name, rel, "read", e4)\n            content = bool(item.get("content", False))', '            content = bool(item.get("content", False))')]),
    ('L15', 'builder E4 hash-only', [('require(not (e4 and content), "exemption", "E4 is hash-only")', 'pass')]),
    ('N01', 'family: games', [('    ("games", _TOKEN_START + r"games" + _TOKEN_END),\n', '')]),
    ('N02', 'family: hub-blocks', [('    ("hub-blocks", _TOKEN_START + r"hub[-_.]?blocks?" + _TOKEN_END),\n', '')]),
    ('N03', 'family token start (prefix variants)', [('_TOKEN_START = r"(?:.*[^a-z])?"', '_TOKEN_START = r""')]),
    ('N03b', 'family token end (suffix variants)', [('_TOKEN_END = r"(?:[^a-z].*)?"', '_TOKEN_END = r""')]),
    ('N05', 'family: *complete*.json*', [('    ("complete-json", r".*complete.*\\.json.*"),\n', '')]),
    ('N05b', 'complete family breadth', [('r".*complete.*\\.json.*"', 'r"complete\\.json"')]),
    ('N06', 'family: hub-ack*.json', [('    ("hub-ack-json", r".*hub[-_.]?ack.*\\.json.*"),\n', '')]),
    ('N07', 'family: end-raw*.json', [('    ("end-raw-json", r".*end[-_.]?raw.*\\.json.*"),\n', '')]),
    ('N08', 'family: interference*.json', [('    ("interference-json", r".*interference.*\\.json.*"),\n', '')]),
    ('N09', 'E4 leaf exemption: exactly complete.json', [('(e4_leaf and parts[i] == E4_LEAF)', 'e4_leaf')]),
    ('R08', 'Input single use', [('    def _consume(self, sink):\n        require(self._fd is not None, "state", "%s already consumed or closed" % self.label)', '    def _consume(self, sink):\n        pass')]),
    ('G02', 'name gate in _gate', [('    name_gate(role.root + "/" + rel, policy.host, role.grants, e4_leaf=e4_leaf, d3_leaf=d3_leaf,\n              e5_rel=rel if e5_ok else None)\n', '')]),
    ('G05', 'grants need exact names', [('require(not (grants & {"reporting-job-exact", "end-json-exact", "end-claim-exact"}) or not patterns, "policy",', 'require(True, "policy",')]),
    ('X01', 'O_EXCL', [('CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC', 'CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC')]),
    ('X02', 'mkdir exists', [('        refuse("exists", "%s already exists" % label)\n    os.fsync(parent_fd)', '        pass\n    os.fsync(parent_fd)')]),
    ('S10', 'git: work tree canonical', [('        os.close(open_root(repo.work_tree))\n', '        pass\n')]),
    ('S11', 'stdin feed failure', [('require(state["stdin_error"] is None or early_exit, "subprocess",', 'require(True, "subprocess",')]),
    ('Q07', 'tree: E1 target present', [('require(target is not None, "exemption", "E1 target not in the tree")', 'require(True, "exemption", "E1 target not in the tree")')]),
    ('Q08', 'object id recomputed', [('require(algo(b"%s %d\\x00" % (kind.encode(), size) + data).hexdigest() == oid, "sha",', 'require(True, "sha",')]),
    ('Q09', 'object body size', [('require(len(body) == size + 1 and body.endswith(b"\\n"), "size",', 'require(True, "size",')]),
    ('Q10', 'planned entries only', [('require(any(entry is f for f in plan["files"]) or (plan.get("e1_target") is not None and entry is plan["e1_target"]),', 'require(True,')]),
    ('Q14', 'show: role rooted at repo', [('            % (role.name, repo.work_tree or repo.git_dir))\n    _gate(policy, role_name, rel, role.access)', '            % (role.name, repo.work_tree or repo.git_dir)) if False else None\n    _gate(policy, role_name, rel, role.access)')]),
    ('Q19', 'show: expected sha', [('    require(expected_sha256 is None or hashlib.sha256(data).hexdigest() == expected_sha256, "sha",\n            "tracked %s SHA-256 mismatch" % rel)', '    require(True, "sha",\n            "tracked %s SHA-256 mismatch" % rel)')]),
    ('Q20', 'export: E1 copy is the verified target', [('result = writer.create_excl(E1_ALIAS, data, 0o444)', 'result = writer.create_excl(E1_ALIAS, E1_LINK_TEXT.encode(), 0o444)')]),
    ('M02', 'remote: host check', [('        if node != host:\n            refuse("host", "request for %s ran on %s" % (host, node))\n        # 3. gate pass', '        if False:\n            refuse("host", "request for %s ran on %s" % (host, node))\n        # 3. gate pass')]),
    ('M08', 'remote: duplicate keys', [('            req = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dups, parse_constant=_no_constant)\n        except ValueError:\n            refuse("request", "request is not JSON")', '            req = json.loads(raw.decode("utf-8"))\n        except ValueError:\n            refuse("request", "request is not JSON")')]),
    ('L12', 'parser one line', [('require(isinstance(stdout, bytes) and stdout.endswith(b"\\n") and stdout.count(b"\\n") == 1, "remote",\n            "remote output is not exactly one line")', 'require(True, "remote",\n            "remote output is not exactly one line")')]),
    ('L14', 'builder remote policy', [('    require(isinstance(policy, Policy) and policy.remote, "policy", "a remote Policy is required")\n    require(isinstance(items, list)', '    pass\n    require(isinstance(items, list)')]),
    ('F01', 'family: END-JOB*', [('    ("end-job", _TOKEN_START + r"end[-_.]?job.*"),\n', '')]),
    ('F02', 'family: END-FINAL*', [('    ("end-final", _TOKEN_START + r"end[-_.]?final.*"),\n', '')]),
    ('F03', 'family: attempt-*.json', [('    ("attempt-json", r".*attempt[-_.].*\\.json.*"),\n', '')]),
    ('F04', 'END-claim grant', [('if family is not None and "end-claim-exact" not in grants:', 'if family is not None and False:')]),
    ('F05', 'outcome casefold', [('    """The OUTCOME family label a single component belongs to (casefolded), or None."""\n    folded = component.casefold()', '    """The OUTCOME family label a single component belongs to (casefolded), or None."""\n    folded = component')]),
    ('F06', 'END-claim casefold', [('    """The END-CLAIM family label a single component belongs to (casefolded), or None."""\n    folded = component.casefold()', '    """The END-CLAIM family label a single component belongs to (casefolded), or None."""\n    folded = component')]),
    ('F07', 'D3 leaf exemption: exactly the two names', [('(d3_leaf and parts[i] in D3_LEAVES)', 'd3_leaf')]),
    ('F08', 'E/D exemptions only on the final component', [('exempt = i == last and (', 'exempt = (')]),
    ('F09', 'claim grant requires exact names', [('{"reporting-job-exact", "end-json-exact", "end-claim-exact"}', '{"reporting-job-exact", "end-json-exact"}')]),
    ('D3-01', 'D3: S6-only role name', [('require(name.startswith("s6-"), "policy",', 'require(True, "policy",')]),
    ('D3-02', 'D3: read, exact, no grant, only D3', [('require(access == "read" and not patterns and exemptions == frozenset(("D3",)) and not grants, "policy",', 'require(True, "policy",')]),
    ('D3-03', 'D3: root is the declared receive parent', [('require(root in tuple(D3_RECEIVE_BASE + "/" + h for h in D3_HOSTS), "policy",', 'require(True, "policy",')]),
    ('D3-04', 'D3: exact name shape', [('require(len(parts) >= 3 and D3_ATTEMPT.fullmatch(parts[0]) is not None and parts[1] == D3_SEALED_DIR\n                and parts[-1] in D3_LEAVES, "policy",', 'require(True, "policy",')]),
    ('D3-05', 'D3: inside durable-measurement', [('and parts[1] == D3_SEALED_DIR\n', '\n')]),
    ('D3-06', 'D3: role must carry D3', [('d3_leaf = bool(d3) and "D3" in role.exemptions and rel in role.exact', 'd3_leaf = bool(d3) and rel in role.exact')]),
    ('D3-07', 'D3: non-D3 refuses as exemption', [('require(not d3 or d3_leaf, "exemption",', 'require(True, "exemption",')]),
    ('D3-08', 'D3: seal sha format', [('require(isinstance(seal_sha256, str) and SHA256_HEX.fullmatch(seal_sha256) is not None, "policy",', 'require(True, "policy",')]),
    ('D3-09', 'D3: sealed (both seal files)', [('        for name in D3_SEAL_FILES:\n            fd, _ = open_leaf(sealed, name, 64 << 20, None, "%s seal %s" % (label, name))\n            os.close(fd)\n', '')]),
    ('D3-10', 'D3: seal sha compared', [('require(digest == seal_sha256, "sha",', 'require(True, "sha",')]),
    ('GH01', 'git: no inherited environment', [('    env = dict(GIT_FIXED_ENV)\n    for key, value in sorted((extra_env', '    env = dict(os.environ)\n    env.update(GIT_FIXED_ENV)\n    for key, value in sorted((extra_env')]),
    ('GH02', 'git: replace objects off (flag + env, joint)', [('GIT_GLOBAL_ARGS = ("--no-replace-objects", "--no-optional-locks",', 'GIT_GLOBAL_ARGS = ("--no-optional-locks",'), ('"GIT_ATTR_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1",', '"GIT_ATTR_NOSYSTEM": "1",')]),
    ('GH03', 'git: core.hooksPath=/dev/null', [('"-c", "core.hooksPath=/dev/null",\n', '\n')]),
    ('GH04', 'git: fsmonitor (override + config refusal, joint)', [('                   "-c", "core.fsmonitor=false", "-c", "protocol.allow=never")', '                   "-c", "protocol.allow=never")'), ('GIT_CONFIG_REFUSED_CORE_KEYS = ("worktree", "fsmonitor", ', 'GIT_CONFIG_REFUSED_CORE_KEYS = ("worktree", ')]),
    ('GH05', 'git: protocol.allow=never', [('"-c", "core.fsmonitor=false", "-c", "protocol.allow=never")', '"-c", "core.fsmonitor=false")')]),
    ('GH06', 'git: explicit --git-dir', [('    argv.append("--git-dir=" + repo.git_dir)\n', '')]),
    ('GH07', 'git: fresh empty HOME', [('env["HOME"], env["XDG_CONFIG_HOME"] = home, home + "/xdg-config-absent"', 'env["HOME"], env["XDG_CONFIG_HOME"] = os.environ.get("HOME", home), home + "/xdg-config-absent"')]),
    ('GH07b', 'git: XDG_CONFIG_HOME inside the fresh HOME', [('env["HOME"], env["XDG_CONFIG_HOME"] = home, home + "/xdg-config-absent"', 'env["HOME"], env["XDG_CONFIG_HOME"] = home, os.environ.get("XDG_CONFIG_HOME", home)')]),
    ('GH08', 'git: subcommand allowlist', [('require(args[0] in GIT_SUBCOMMANDS, "subprocess",', 'require(True, "subprocess",')]),
    ('GH09', 'git: extra env allowlist', [('require(key in GIT_EXTRA_ENV_ALLOWED and isinstance(value, str), "subprocess",', 'require(isinstance(value, str), "subprocess",')]),
    ('GH10', 'git: preflight before every call', [('    _git_preflight(repo, creating=args[0] == "init")\n', '')]),
    ('GH11', 'git: alternates/grafts/shallow refused', [('if kind not in repo.allow and _exists_nofollow(fd, list(parts), repo.git_dir):', 'if False:')]),
    ('GH11b', 'git: declared allowance honoured', [('if kind not in repo.allow and _exists_nofollow(fd, list(parts), repo.git_dir):', 'if _exists_nofollow(fd, list(parts), repo.git_dir):')]),
    ('GH12', 'git: commondir declared + target (joint)', [('require(repo.common_dir is not None, "indirection",', 'require(True, "indirection",'), ('require(target == repo.common_dir, "indirection",', 'require(True, "indirection",')]),
    ('GH13', 'git: commondir target equals declaration', [('require(target == repo.common_dir, "indirection",', 'require(True, "indirection",')]),
    ('GH14', 'git: declared common_dir needs commondir', [('require(repo.common_dir is None, "indirection", "common_dir declared', 'require(True, "indirection", "common_dir declared')]),
    ('GH16', 'git config: driver/include sections', [('require(section not in GIT_CONFIG_REFUSED_SECTIONS, "indirection",', 'require(True, "indirection",')]),
    ('GH17', 'git config: core keys', [('require(not (section == "core" and key in GIT_CONFIG_REFUSED_CORE_KEYS), "indirection",', 'require(True, "indirection",')]),
    ('GH18', 'git config: config file checked', [('            _check_git_config(fd, "config", repo.git_dir)\n', '')]),
    ('GH18b', 'git config: config.worktree checked', [('            _check_git_config(fd, "config.worktree", repo.git_dir)\n', '')]),
    ('GH19', 'git config: section names casefolded', [('.strip(\'"\').casefold()', '.strip(\'"\')')]),
    ('GH20', 'git: init only where no git dir exists', [('require(not _exists_nofollow(pfd, [leaf], repo.git_dir), "exists",', 'require(True, "exists",')]),
    ('GH21', 'git: nothing left in HOME', [('require(not leftover, "subprocess",', 'require(True, "subprocess",')]),
    ('GH22', 'git: run counter', [('    GIT_COUNTERS["runs"] += 1\n', '')]),
    ('GO01', 'object: header oid/type/size', [('require(nl >= 0 and out[:nl] == header, "git",', 'require(nl >= 0, "git",')]),
    ('GO02', 'object: bounded output', [('len(header) + size + 2, (oid + "\\n").encode(),', '1 << 30, (oid + "\\n").encode(),')]),
    ('GO03', 'object: read counter', [('    GIT_COUNTERS["object_reads"] += 1\n', '')]),
    ('GC01', 'commit id must be a commit', [('require(kind == b"commit\\n", "git",', 'require(True, "git",')]),
    ('ST01', 'E4 fail-closed for every tracked complete.json', [('require(path in E4_COMPLETE_JSON, "name", "tracked complete.json outside the exact E4 list: %s" % path)', 'pass')]),
    ('ST02', 'E4 pinned blob identity', [('require(entry["type"] == "blob" and entry["mode"] == "100644" and entry["oid"] == E4_GIT_BLOB_OIDS[path],', 'require(True,')]),
    ('ST02b', 'E4 mode', [('and entry["mode"] == "100644" and entry["oid"] == E4_GIT_BLOB_OIDS[path]', 'and entry["oid"] == E4_GIT_BLOB_OIDS[path]')]),
    ('ST03', 'D1: non-members skipped', [('        if not _is_member(members, entry, paths):\n            continue\n', '')]),
    ('ST04', 'D1: declared members present', [('require(not missing, "missing",', 'require(True, "missing",')]),
    ('ST05', 'E1 entry: exact link oid', [('require(entry["oid"] == E1_LINK_OID and entry["size"] == len(E1_LINK_TEXT), "exemption",', 'require(True, "exemption",')]),
    ('ST06', 'E1 target gated when not a member', [('            _gate(policy, role_name, E1_LINK_TEXT, role.access)\n', '')]),
    ('ST07', 'E1 target regular blob', [('require(target["type"] == "blob" and target["mode"] in ("100644", "100755") and target["size"] is not None', 'require(True')]),
    ('ST08', 'D1 predicate: exactly True', [('return members(dict(entry)) is True', 'return bool(members(dict(entry)))')]),
    ('ST09', 'plan: role rooted at repo', [('            % (role.name, repo.work_tree or repo.git_dir))\n    entries = git_ls_tree(', '            % (role.name, repo.work_tree or repo.git_dir)) if False else None\n    entries = git_ls_tree(')]),
    ('E1-01', 'D2: plan has an E1 entry', [('require(plan["e1"] is not None and plan["e1"]["mode"] == "120000", "exemption", "the plan has no E1 entry")', 'pass')]),
    ('E1-02', 'D2: shipped bytes equal the target blob', [('require(shipped["sha256"] == info["target_sha256"], "exemption",', 'require(True, "exemption",')]),
    ('E1-03', 'D2: export copy only', [('require(e1_mode == "copy", "exemption",', 'require(True, "exemption",')]),
    ('E4-01', 'export: E4 pin', [('        require(hashlib.sha256(data).hexdigest() == E4_COMPLETE_JSON[entry["path"]], "exemption",\n                "E4 SHA mismatch for %s" % entry["path"])\n        ensure_dirs', '        ensure_dirs')]),
    ('RV01', 'receive: request keys', [('if not isinstance(req, dict) or sorted(req) != REQUEST_KEYS:', 'if not isinstance(req, dict):')]),
    ('RV02', 'receive: duplicate names', [('if rel in names or rel.casefold() in folded:', 'if False:')]),
    ('RV03', 'receive: casefold duplicates', [('if rel in names or rel.casefold() in folded:', 'if rel in names:')]),
    ('RV04', 'receive: dir after its parent', [('if _parent(rel) not in made and _parent(rel) != "":', 'if False:')]),
    ('RV05', 'receive: file inside declared dirs', [('if _parent(f["rel"]) != "" and _parent(f["rel"]) not in made:', 'if False:')]),
    ('RV06', 'receive: file keys', [('if sorted(f) != FILE_KEYS:', 'if False:')]),
    ('RV07', 'receive: modes', [('or f["mode"] not in FILE_MODES or', 'or')]),
    ('RV08', 'receive: E4 pin', [('if f["e4"] and E4_COMPLETE_JSON.get(f["rel"]) != f["sha256"]:', 'if False:')]),
    ('RV09', 'receive: max_total', [('    if total > req["max_total"]:\n        refuse("size"', '    if False:\n        refuse("size"')]),
    ('RV10', 'receive: name gates (all)', [('        name_gate(root, host, grants)\n        for rel in dirs:\n            name_gate(root + "/" + rel, host, grants)\n        for f in files:\n            name_gate(root + "/" + f["rel"], host, grants, e4_leaf=f["e4"], e5_rel=f["rel"] if f["e5"] else None)\n', '')]),
    ('RV10b', 'receive: file name gates', [('        for f in files:\n            name_gate(root + "/" + f["rel"], host, grants, e4_leaf=f["e4"], e5_rel=f["rel"] if f["e5"] else None)\n', '')]),
    ('RV11', 'receive: host', [('        if node != host:\n            refuse("host", "request for %s ran on %s" % (host, node))\n        # 3. the destination root', '        if False:\n            refuse("host", "request for %s ran on %s" % (host, node))\n        # 3. the destination root')]),
    ('RV12', 'receive: manifest sha vs argv', [('if status["manifest_sha256"] != sys.argv[3]:', 'if False:')]),
    ('RV13', 'receive: root created exclusively', [('            mkdir_excl_at(pfd, top, 0o755, root)\n', '            os.makedirs(root, exist_ok=True)\n')]),
    ('RV14', 'receive: short stream', [('if not chunk:\n                                refuse("stream", "the stream ended inside %s (partial kept)" % f["rel"])', 'if not chunk:\n                                break')]),
    ('RV15', 'receive: sha', [('if digest.hexdigest() != f["sha256"]:', 'if False:')]),
    ('RV16', 'receive: extra bytes', [('            if stream.read(1):\n                refuse("stream", "extra bytes after the last file")', '            if False:\n                refuse("stream", "extra bytes after the last file")')]),
    ('RV17', 'receive: manifest length bound', [('if not 0 < size <= MAX_MANIFEST:', 'if False:')]),
    ('RV19', 'receive: bootstrap program sha', [('hashlib.sha256(b).hexdigest()==sys.argv[2] or sys.exit(4);', 'True or sys.exit(4);')]),
    ('RV20', 'receive: argv shape', [('if len(sys.argv) != 4 or SHA_RE.fullmatch(sys.argv[3]) is None:', 'if False:')]),
    ('RV21', 'receive: dir name gates', [('        for rel in dirs:\n            name_gate(root + "/" + rel, host, grants)\n        for f in files:\n            name_gate(root + "/" + f["rel"], host, grants, e4_leaf=f["e4"], e5_rel=f["rel"] if f["e5"] else None)\n', '        for f in files:\n            name_gate(root + "/" + f["rel"], host, grants, e4_leaf=f["e4"], e5_rel=f["rel"] if f["e5"] else None)\n')]),
    ('RP01', 'receipt: rc', [('require(type(rc) is int and rc in (0, 3), "remote", "receiver exited %r" % (rc,))', 'pass')]),
    ('RP02', 'receipt: one line', [('require(isinstance(stdout, bytes) and stdout.endswith(b"\\n") and stdout.count(b"\\n") == 1, "remote",\n            "receiver output is not exactly one line")', 'require(True, "remote",\n            "receiver output is not exactly one line")')]),
    ('RP03', 'receipt: manifest sha', [('require(reply.get("manifest_sha256") == hashlib.sha256(manifest_bytes).hexdigest(), "remote",', 'require(True, "remote",')]),
    ('RP04', 'receipt: rc 3 refusal shape', [('require(tuple(sorted(reply)) == _RECEIPT_REFUSED and reply["status"] == "refused", "remote",', 'require(True, "remote",')]),
    ('RP05', 'receipt: ok key set', [('require(tuple(sorted(reply)) == _RECEIPT_OK and reply["status"] == "ok", "remote", "rc 0 without status ok")', 'require(reply["status"] == "ok", "remote", "rc 0 without status ok")')]),
    ('RP06', 'receipt: host/root/dirs', [('require(reply["host"] == request["host"] and reply["root"] == request["root"] and reply["dirs"] == request["dirs"],', 'require(True,')]),
    ('RP07', 'receipt: file count', [('require(isinstance(got, list) and len(got) == len(request["files"]), "remote", "receipt file count differs")', 'require(isinstance(got, list), "remote", "receipt file count differs")')]),
    ('RP08', 'receipt: rel/size/sha', [('require(record["rel"] == asked["rel"] and record["size"] == asked["size"]\n                and record["sha256"] == asked["sha256"], "remote",', 'require(True, "remote",')]),
    ('RP09', 'receipt: nlink', [('require(record["nlink"] == 1, "nlink",', 'require(True, "nlink",')]),
    ('RP10', 'receipt: mode', [('require(stat.S_ISREG(record["mode"]) and stat.S_IMODE(record["mode"]) == asked["mode"], "not-regular",', 'require(True, "not-regular",')]),
    ('SD01', 'sender: local source names before ssh', [('        _gate(local_policy, f.get("src_role"), f.get("src_rel"), "read", f.get("e4", False) is True, e5=e5)\n', '')]),
    ('SD02', 'sender: size and sha required', [('require(isinstance(f, dict) and type(f.get("size")) is int and isinstance(f.get("sha256"), str)\n                and SHA256_HEX.fullmatch(f["sha256"]) is not None, "policy",', 'require(isinstance(f, dict), "policy",')]),
    ('SD03', 'sender: streamed sha', [('require(digest.hexdigest() == f["sha256"], "sha", "local source', 'require(True, "sha", "local source')]),
    ('SD04', 'sender: destination file gates', [('        _gate(policy, role_name, f.get("dst"), "write", e4, e5=e5)\n', '')]),
    ('SD05', 'sender: destination dir gates', [('        check_rel(rel)\n        name_gate(role.root + "/" + rel, policy.host, role.grants)\n    records = []', '        check_rel(rel)\n    records = []')]),
    ('SD06', 'sender: local manifest validation', [('        _RECEIVE_NS["validate_receive"](req)\n', '        pass\n')]),
    ('SD07', 'sender: descriptor gate before ssh', [('        _open_gated(local_policy, f["src_role"], f["src_rel"], f["size"], None, f.get("e4", False) is True).close()\n', '        pass\n')]),
    ('SD08', 'sender: builder write role', [('require(role.access == "write", "policy", "role %s is not a write role" % role.name)\n    require(isinstance(dirs, (list, tuple))', 'require(isinstance(dirs, (list, tuple))')]),
    ('S14', 'stdin break tolerated only on nonzero rc', [('early_exit = stdin_break_ok_on_nonzero and proc.returncode != 0', 'early_exit = stdin_break_ok_on_nonzero')]),
    ('S15', 'feeder Refusal surfaces as itself', [('    if isinstance(state["stdin_error"], Refusal):\n        raise state["stdin_error"]\n', '')]),
    ('R09', 'Input.chunks single use', [('    def chunks(self):\n        """Generator over exactly the gated bytes (iter_exact semantics); single use; closes the fd."""\n        require(self._fd is not None, "state", "%s already consumed or closed" % self.label)', '    def chunks(self):\n        """Generator over exactly the gated bytes (iter_exact semantics); single use; closes the fd."""\n        pass')]),
    ('E5-01', 'E5: constant guard (test mode may change OIDs only)', [('        refuse("policy", "E5_RUNTIME_MEMBERS is not the ruled list (only the OIDs may differ)")', '        pass')]),
    ('E5-02', 'E5: exact, case-sensitive path lookup', [('        if path == rel:\n            return oid', '        if path.casefold() == str(rel).casefold():\n            return oid')]),
    ('E5-03', 'name_gate: e5_rel exactness (E5 path and suffix)', [('    if e5_leaf and (e5_blob_oid(e5_rel) is None or not path.endswith("/" + e5_rel)):', '    if False:')]),
    ('E5-03b', 'name_gate: e5_rel must be the suffix', [('    if e5_leaf and (e5_blob_oid(e5_rel) is None or not path.endswith("/" + e5_rel)):', '    if e5_leaf and e5_blob_oid(e5_rel) is None:')]),
    ('E5-05', '_gate: E5 needs the role exemption', [('e5_ok = bool(e5) and "E5" in role.exemptions and e5_blob_oid(rel) is not None', 'e5_ok = bool(e5) and e5_blob_oid(rel) is not None')]),
    ('E5-06J', '_gate exact path + name_gate exactness (joint; the _gate clause alone is masked)', [('e5_ok = bool(e5) and "E5" in role.exemptions and e5_blob_oid(rel) is not None', 'e5_ok = bool(e5) and "E5" in role.exemptions'), ('    if e5_leaf and (e5_blob_oid(e5_rel) is None or not path.endswith("/" + e5_rel)):', '    if False:')]),
    ('E5-07', '_gate: e5 request refuses unless granted', [('    require(not e5 or e5_ok, "exemption", "not an exact E5 path for an E5 role: %s" % rel)\n', '')]),
    ('E5-08', 'tree: E5 mode 100644', [('require(mode == "100644" and entry["oid"] == e5_blob_oid(path), "exemption",', 'require(entry["oid"] == e5_blob_oid(path), "exemption",')]),
    ('E5-09', 'tree: E5 pinned blob OID (phase 1)', [('require(mode == "100644" and entry["oid"] == e5_blob_oid(path), "exemption",', 'require(mode == "100644", "exemption",')]),
    ('E5-10', 'tree: E5 cap', [('require(entry["size"] is not None and entry["size"] <= role.max_size, "size", "blob %s too large" % path)\n            e5.append', 'require(True, "size", "blob %s too large" % path)\n            e5.append')]),
    ('E5-11', 'tree: E5 needs the role exemption', [('is_e5 = "E5" in role.exemptions and e5_blob_oid(path) is not None', 'is_e5 = e5_blob_oid(path) is not None')]),
    ('E5-12', 'hash_e5: pinned blob OID', [('    require(blob.hexdigest() == e5_blob_oid(rel), "exemption", "E5 %s does not hash to its pinned blob OID" % rel)', '    pass')]),
    ('E5-13', 'copy_e5: copy pass re-checked', [('require(blob.hexdigest() == e5_blob_oid(rel), "exemption", "E5 copy of %s', 'require(True, "exemption", "E5 copy of %s')]),
    ('E5-14', 'copy_e5: hash pass before any write', [('    hash_e5(policy, role_name, rel)\n    item = _open_gated(policy, role_name, rel, None, None, False, e5=True)', '    item = _open_gated(policy, role_name, rel, None, None, False, e5=True)')]),
    ('E5-15', 'git_hash_e5: planned E5 entry only', [('require(any(entry is f for f in plan["e5"]), "exemption", "entry is not a planned E5 entry")', 'pass')]),
    ('E5-16', 'walk: E5 path must not be a directory', [('                        require(not is_e5, "not-regular", "E5 path %s is a directory" % rel)\n', '')]),
    ('E5-17', 'walk: E5 needs the role exemption', [('is_e5 = "E5" in role.exemptions and e5_blob_oid(rel) is not None', 'is_e5 = e5_blob_oid(rel) is not None')]),
    ('E5-18', 'receive: E5 exact path / mode 0444 / not E4', [('        if f["e5"] and (f["e4"] or f["mode"] != 0o444 or e5_blob_oid(f["rel"]) is None):', '        if False:')]),
    ('E5-18a', 'receive: E5 mode 0444', [('        if f["e5"] and (f["e4"] or f["mode"] != 0o444 or e5_blob_oid(f["rel"]) is None):', '        if f["e5"] and (f["e4"] or e5_blob_oid(f["rel"]) is None):')]),
    ('E5-18J', 'receive: E5 exact path + name_gate exactness (joint; the path clause alone is masked)', [('        if f["e5"] and (f["e4"] or f["mode"] != 0o444 or e5_blob_oid(f["rel"]) is None):', '        if f["e5"] and (f["e4"] or f["mode"] != 0o444):'), ('    if e5_leaf and (e5_blob_oid(e5_rel) is None or not path.endswith("/" + e5_rel)):', '    if False:')]),
    ('E5-19', 'receive: e5 flag is a strict bool', [('or type(f["e5"]) is not bool:', 'or f["e5"] not in (True, False):')]),
    ('E5-20', 'receive: E5 name exemption only when flagged', [('e4_leaf=f["e4"], e5_rel=f["rel"] if f["e5"] else None)', 'e4_leaf=f["e4"], e5_rel=f["rel"] if f["rel"] in E5_PATHS else None)')]),
    ('E5-21', 'receive: blob OID re-hash on the host', [('                if f["e5"] and blob.hexdigest() != e5_blob_oid(f["rel"]):', '                if False:')]),
    ('E5-22', 'sender: hash_e5 of every E5 source before ssh', [('            got = hash_e5(local_policy, f["src_role"], f["src_rel"])\n            require(got["sha256"] == f["sha256"] and got["size"] == f["size"], "sha",', '            got = f\n            require(True, "sha",')]),
    ('E5-22b', 'sender: E5 source SHA/size equal the declared ones', [('require(got["sha256"] == f["sha256"] and got["size"] == f["size"], "sha",', 'require(True, "sha",')]),
    ('E5-23', 'sender: E5 keeps its exact path', [('        require(not e5 or f.get("src_rel") == f.get("dst"), "exemption", "an E5 file keeps its exact path")\n', '')]),
    ('Q11J', 'E1 link text + link OID pin (joint; Q11 alone is masked by the OID pin and recompute)', [('require(data == E1_LINK_TEXT.encode(), "exemption", "E1 tracked link text differs")', 'pass'), ('require(entry["oid"] == E1_LINK_OID and entry["size"] == len(E1_LINK_TEXT), "exemption",', 'require(True, "exemption",')]),
    ('SD01J', 'sender pre-ssh names + descriptor gate (joint; SD01 alone is masked by SD07)', [('        _gate(local_policy, f.get("src_role"), f.get("src_rel"), "read", f.get("e4", False) is True, e5=e5)\n', ''), ('        _open_gated(local_policy, f["src_role"], f["src_rel"], f["size"], None, f.get("e4", False) is True).close()\n', '        pass\n')]),
    ('SD08J', 'builder write role + _gate access (joint; SD08 alone is masked by G03)', [('require(role.access == "write", "policy", "role %s is not a write role" % role.name)\n    require(isinstance(dirs, (list, tuple))', 'require(isinstance(dirs, (list, tuple))'), ('require(role.access == access, "policy", "role %s is not a %s role" % (role.name, access))', 'pass')]),
]


def run(python, mutant_dir, source_text, timeout, extra=()):
    path = os.path.join(mutant_dir, "safe_input.py")
    with open(path, "w") as stream:
        stream.write(source_text)
    env = dict(os.environ, SAFE_INPUT_UNDER_TEST=path, PYTHONDONTWRITEBYTECODE="1")
    argv = [python, "-B"] + (["-O"] if sys.flags.optimize else []) + [
        "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-W", "ignore::pytest.PytestConfigWarning",
        "--basetemp", os.path.join(mutant_dir, "bt")] + list(extra) + [HERE]
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


def apply(original, edits):
    text = original
    for old, new in edits:
        if text.count(old) != 1:
            return None, "edit target occurs %d times: %r" % (text.count(old), old[:80])
        text = text.replace(old, new)
    return text, None


def main():
    args = sys.argv[1:]
    only, jobs, check, recheck = None, 1, False, None
    while args:
        flag = args.pop(0)
        if flag == "--only":
            only = set(args.pop(0).split(","))
        elif flag == "--jobs":
            jobs = int(args.pop(0))
        elif flag == "--check-edits":
            check = True
        elif flag == "--recheck-without":
            recheck = args.pop(0)
        else:
            raise SystemExit(__doc__)
    with open(SOURCE) as stream:
        original = stream.read()
    ids = [m[0] for m in MUTANTS]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate mutant id")
    if check:
        bad = [(i, apply(original, e)[1]) for i, _, e in MUTANTS if apply(original, e)[1]]
        print(json.dumps({"mutants": len(MUTANTS), "invalid_edits": bad}, indent=1))
        return 1 if bad else 0
    scratch = tempfile.mkdtemp(prefix="safe-input-mut-", dir="/dev/shm")
    results = []
    try:
        base_dir = os.path.join(scratch, "baseline")
        os.mkdir(base_dir)
        baseline = run(sys.executable, base_dir, original, 900)
        if baseline[0] != "SURVIVED":
            raise SystemExit("baseline suite does not pass: %r" % (baseline,))
        todo = [m for m in MUTANTS if not only or m[0] in only]
        nulls = [("NULL-%02d" % i, "control: unmodified source (must SURVIVE)", []) for i in range(max(2, jobs // 2))]
        step = max(1, len(todo) // len(nulls))
        for k, null in enumerate(nulls):                  # spread over the campaign: flakiness under load shows
            todo.insert(min(len(todo), k * (step + 1)), null)

        def one(mutant):
            ident, gate, edits = mutant
            text, problem = apply(original, edits)
            if problem:
                return {"id": ident, "gate": gate, "verdict": "INVALID(edit)", "detail": problem}
            mdir = os.path.join(scratch, ident)
            os.mkdir(mdir)
            verdict, seconds, detail = run(sys.executable, mdir, text, 600)
            sys.stderr.write("%s %-45s %s\n" % (ident, gate, verdict))
            shutil.rmtree(mdir, ignore_errors=True)
            return {"id": ident, "gate": gate, "verdict": verdict, "seconds": seconds, "detail": detail}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(one, todo))
        if recheck:                                       # kills attributed to `recheck` alone are re-run without it
            def again(r):
                if r["verdict"] != "KILLED" or recheck.split("::")[-1] not in r["detail"]:
                    return r
                text, _ = apply(original, dict((m[0], m[2]) for m in MUTANTS)[r["id"]])
                mdir = os.path.join(scratch, r["id"] + "-recheck")
                os.mkdir(mdir)
                verdict, seconds, detail = run(sys.executable, mdir, text, 600,
                                               ["--deselect", os.path.join(HERE, recheck)])
                shutil.rmtree(mdir, ignore_errors=True)
                sys.stderr.write("%s recheck-without %s\n" % (r["id"], verdict))
                return dict(r, verdict_without=verdict, detail_without=detail)
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                results = list(pool.map(again, results))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    with open(SOURCE, "rb") as stream:
        digest = hashlib.sha256(stream.read()).hexdigest()
    controls = [r for r in results if r["id"].startswith("NULL-")]
    results = [r for r in results if not r["id"].startswith("NULL-")]
    summary = {"safe_input_sha256": digest, "python": sys.version.split()[0], "optimize": sys.flags.optimize,
               "jobs": jobs, "baseline": baseline[0], "mutants": len(results),
               "killed": sum(r["verdict"] == "KILLED" for r in results),
               "not_killed": [r["id"] for r in results if r["verdict"] != "KILLED"],
               "recheck_without": recheck,
               "killed_only_by_recheck_test": [r["id"] for r in results if r.get("verdict_without") not in (None, "KILLED")],
               "null_controls": controls, "null_controls_all_survived": all(r["verdict"] == "SURVIVED" for r in controls),
               "equivalent_excluded": EQUIVALENT, "results": results}
    print(json.dumps(summary, indent=1))
    return 0 if (not summary["not_killed"] and summary["null_controls_all_survived"]
                 and not summary["killed_only_by_recheck_test"]) else 1


if __name__ == "__main__":
    sys.exit(main())
