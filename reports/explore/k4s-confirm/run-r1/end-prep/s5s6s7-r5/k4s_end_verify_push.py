"""05-only, outcome-blind post-exit verification (S6 r2; delta of T1 753722c9). No network or outcome reduction.

r2 (safe_input adoption, Sol PKG2 S6-F1/F3, rulings D3, C-d, RC-5): every read, hash, stat and write goes through the
pinned safe_input layer. Inputs are fixed role paths, never free paths:

  receive dir     /mpac/sdicks02/k4s-runner/run-r1/end-received/<host>/<attempt>   (= si.D3_RECEIVE_BASE)
  launch receipt  /mpac/sdicks02/k4s-runner/run-r1/end-launch/<host>/<attempt>/LAUNCH-RECEIPT.json   (S7, pinned SHA)
  prepare proof   /mpac/sdicks02/k4s-runner/run-r1/end-launch/<host>/<attempt>/PREPARE-PROOF.json    (committed copy)
                  r4 (INTEGRATION-AUDIT-r1 U7): written by --prepare itself, byte-equal to PREPARED.json, exclusive

* C-d: no ACK earlier than exit_utc + 1300 s; the ACK records exit/verified epochs and c_d_satisfied.
* Registry (RC-5): the wrapper's safe_input snapshot registry/attempt-NN.json is read through an exact
  ``end-claim-exact`` role (descriptor gate: regular, st_nlink 1), bound to registry-listing.json SHAs, contiguous,
  and checked against host/attempt/round; claim_without_receipt is recorded.
* Sealed members: end-raw.json / end-complete.json are hash-only (D3, si.hash_sealed_end_member) against the seal
  manifest; every other member is hashed through an exact role; a names-only listing (each name gated before it is
  stat'ed; only this seal's exact D3 names are exempt) proves there is no extra, aliased or outcome-named file.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import sys
import time
import types
import uuid

if not __debug__:
    raise SystemExit("END verifier refuses optimized Python")

SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
WRAPPER_SHA256 = "65625fc0eac95079c83f2664c5a3244dbe19941cb91075eca5b2093f135679af"   # k4s_end_exit_push.sh r2
BASE = "/mpac/sdicks02/k4s-runner/run-r1"
RECEIVE_BASE = BASE + "/end-received"
LAUNCH_BASE = BASE + "/end-launch"
C_D_SECONDS = 1300
ATTEMPT = re.compile(r"end-(127x0[34])-r([0-9]{2})-l([0-9]{2})")
MAX_CLAIMS = 100
REGISTRY_NAMES = tuple("registry/attempt-%02d.json" % i for i in range(MAX_CLAIMS))
RECEIVE_NAMES = ("PREPARED.json", "TRANSFER-DONE.json", "exit.json", "argv.nul", "detach.log", "detach.json",
                 "registry-listing.json")
SEAL_FILES = ("receipt-manifest.json", "receipt-manifest.sha256")
D3_LEAVES = ("end-raw.json", "end-complete.json")
ACK_SCHEMA = "clasher.k4s.end-durable-ack.v2"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utc_epoch(text):
    return datetime.datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()


def iso(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


SAFE_INPUT_SIZE = 133606
# r3 (END-FULL-F1): the vendored safe_input layer is read ONLY through the canonical bootstrap r1 below
# (bootstrap-r1/k4s_bootstrap_r1.py, verbatim between its BEGIN/END lines; pins outside).

# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 (bootstrap-r1/k4s_bootstrap_r1.py; paste verbatim, byte for byte) ====
# END-FULL-F1. The only way a K4S END component may read a pinned stdlib-loaded file (its vendored safe_input layer,
# or a host tool) before the shared layer exists. Stdlib only, Python 3.8+, Linux, no assert (holds under -O), no
# single-quote character (so the same text can sit inside a single-quoted shell word). Contract, in order:
#   1. the path is absolute and already normalized (normpath(p) == p; no empty, "." or ".." component, no trailing
#      slash, no control or backslash character). Nothing is canonicalized: realpath is never called;
#   2. every component (ancestors and leaf) passes the safe_input r3 OUTCOME name families (casefolded fullmatch,
#      the same regex literals; conformance-tested against si.outcome_family);
#   3. a component-wise walk from "/": each ancestor is opened O_DIRECTORY|O_NOFOLLOW relative to its parent fd and
#      fstat must say directory (a symlink, a non-directory or a missing ancestor refuses);
#   4. the leaf is fstatat-ed without following (regular, st_nlink == 1, exactly the pinned size) BEFORE it is opened,
#      then opened O_NOFOLLOW|O_NONBLOCK relative to the parent fd and fstat-ed again (same dev/ino, regular,
#      st_nlink == 1, pinned size) BEFORE any byte is read;
#   5. exactly the pinned size is read from THAT descriptor, EOF is confirmed, the SHA-256 must equal the pin, and
#      exactly those bytes are compiled and executed in a fresh module registered under the caller-given name. The
#      code object is compiled under a "<k4s-bootstrap ...>" filename (linecache is given the verified lines) so no
#      traceback, import or inspect call ever re-opens the path after hashing;
#   6. every refusal is `raise refusal(message)`, the caller-chosen refusal convention (an exception class, or a
#      callable returning the exception to raise).
K4S_BOOTSTRAP_RELEASE = "k4s-bootstrap-r1"
K4S_BOOTSTRAP_OUTCOME_FAMILIES = (                      # == safe_input r3 OUTCOME_FAMILIES (literal copy, tested)
    ("games", r"(?:.*[^a-z])?" + r"games" + r"(?:[^a-z].*)?"),
    ("hub-blocks", r"(?:.*[^a-z])?" + r"hub[-_.]?blocks?" + r"(?:[^a-z].*)?"),
    ("complete-json", r".*complete.*\.json.*"),
    ("interference-json", r".*interference.*\.json.*"),
    ("hub-ack-json", r".*hub[-_.]?ack.*\.json.*"),
    ("end-raw-json", r".*end[-_.]?raw.*\.json.*"),
)
K4S_BOOTSTRAP_MAX_SIZE = 1 << 24


def k4s_bootstrap_name_family(component):
    """The OUTCOME family label of one path component (casefolded fullmatch), or None."""
    import re
    folded = component.casefold()
    for label, rx in K4S_BOOTSTRAP_OUTCOME_FAMILIES:
        if re.fullmatch(rx, folded, re.S):
            return label
    return None


def k4s_bootstrap_default_path(module_file, leaf):
    """The sibling `leaf` of `module_file`, made absolute without resolving or normalizing anything: an alias or a
    non-normalized __file__ stays visible, so the walk refuses it."""
    import os
    directory = os.path.dirname(module_file)
    if not directory.startswith("/"):
        directory = os.getcwd() + ("/" + directory if directory else "")
    return directory + "/" + leaf


def k4s_bootstrap_read_verified(path, sha256, size, refusal):
    """Steps 1-5 up to the hash: return exactly the pinned bytes, or raise refusal(message) having read nothing that
    fails a name, walk or descriptor gate."""
    import hashlib
    import os
    import stat

    def refused(reason):
        return refusal("k4s bootstrap refused: " + reason + ": " + repr(path))

    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise refused("the SHA-256 pin is not 64 lowercase hex digits")
    if type(size) is not int or not 0 < size <= K4S_BOOTSTRAP_MAX_SIZE:
        raise refused("the size pin is not an int in 1..%d" % K4S_BOOTSTRAP_MAX_SIZE)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or path.endswith("/")
            or os.path.normpath(path) != path):
        raise refused("not an absolute normalized path")
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise refused("control or backslash character in the path")
    parts = path[1:].split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise refused("empty, . or .. component")
    for p in parts:
        family = k4s_bootstrap_name_family(p)
        if family is not None:
            raise refused("outcome name family " + family + " in component " + repr(p))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise refused("/ is not a directory")
        for name in parts[:-1]:
            try:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            except OSError as error:
                raise refused("ancestor " + repr(name) + " is a symlink, not a directory or missing ("
                              + os.strerror(error.errno) + ")")
            previous, fd = fd, child
            os.close(previous)
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise refused("ancestor " + repr(name) + " is not a directory")
        leaf = parts[-1]
        try:
            before = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as error:
            raise refused("leaf cannot be inspected (" + os.strerror(error.errno) + ")")
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise refused("leaf is not a single-link regular file of the pinned size %d" % size)
        try:
            leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC,
                              dir_fd=fd)
        except OSError as error:
            raise refused("leaf cannot be opened without following (" + os.strerror(error.errno) + ")")
        try:
            info = os.fstat(leaf_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size
                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
                raise refused("opened leaf is not the inspected single-link regular file of the pinned size")
            chunks, left = [], size
            while left > 0:
                chunk = os.read(leaf_fd, left)
                if not chunk:
                    raise refused("leaf shrank while read")
                chunks.append(chunk)
                left -= len(chunk)
            if os.read(leaf_fd, 1) != b"":
                raise refused("leaf grew while read")
        finally:
            os.close(leaf_fd)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise refused("bytes are not the pinned SHA-256 " + sha256)
    return data


def k4s_bootstrap_exec(data, path, sha256, module_name):
    """Step 5 tail: compile and execute exactly `data` (already verified) in a fresh module named `module_name`."""
    import linecache
    import sys
    import types
    filename = "<k4s-bootstrap sha256=" + sha256 + " " + path + ">"
    linecache.cache[filename] = (len(data), None, data.decode("utf-8", "replace").splitlines(True), filename)
    code = compile(data, filename, "exec", dont_inherit=True)
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__k4s_bootstrap__ = (K4S_BOOTSTRAP_RELEASE, path, sha256, len(data))
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def k4s_bootstrap_load(path, sha256, size, module_name, refusal):
    """Read `path` through the full contract and execute exactly the verified bytes as module `module_name`."""
    data = k4s_bootstrap_read_verified(path, sha256, size, refusal)
    return k4s_bootstrap_exec(data, path, sha256, module_name)
# ==== END K4S CANONICAL BOOTSTRAP r1 ====


def load_si(directory=None):
    """safe_input.py next to this file (or in `directory`, tests) through the canonical bootstrap; fingerprint."""
    path = k4s_bootstrap_default_path(__file__, "safe_input.py") if directory is None else str(directory) + "/safe_input.py"
    si = k4s_bootstrap_load(path, SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, "safe_input", ValueError)
    require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input fingerprint differs from the pin")
    require(si.D3_RECEIVE_BASE == RECEIVE_BASE, "D3 receive base differs from the S6 receive base")
    return si


def namespace(root):
    """Pure: root is <RECEIVE_BASE>/<host>/<attempt> with a launch-index END attempt name for that host."""
    require(isinstance(root, str) and os.path.normpath(root) == root, 'Noncanonical receive path')
    host, attempt = os.path.basename(os.path.dirname(root)), os.path.basename(root)
    require(os.path.dirname(os.path.dirname(root)) == RECEIVE_BASE and host in ('127x03', '127x04'),
            'Wrong receive namespace')
    m = ATTEMPT.fullmatch(attempt)
    require(m is not None and m.group(1) == host, 'Verification check failed')
    return host, attempt, int(m.group(2))


def prepare(si, root):
    """Create <receive>/<host>/<attempt>/ (mode 0700) and PREPARED.json exclusively through safe_input.

    r4 (INTEGRATION-AUDIT-r1 U7): the SAME bytes are also written exclusively to
    end-launch/<host>/<attempt>/PREPARE-PROOF.json, the pinned copy that S7 `launch` (check_receive: PREPARE-PROOF read
    with --prepare-proof-sha256 and compared with PREPARED.json) and this verifier's main (--prepare-proof-sha256)
    read. end-launch/ must already exist (canonical); its <host>/<attempt>/ levels are created if absent (S7
    build-argv may have made them). Both files are checked absent before either is created (only shared parent
    directory levels can precede a refusal)."""
    host, attempt, _ = namespace(root)
    launch_host = LAUNCH_BASE + "/" + host
    P = si.Policy("127x05", [si.Role("base", BASE, "write", 1, exact=("end-received",)),
                             si.Role("base-read", BASE, "read", 1, exact=("end-received",)),
                             si.Role("recv-base", RECEIVE_BASE, "write", 1, exact=(host,)),
                             si.Role("recv-base-read", RECEIVE_BASE, "read", 1, exact=(host,)),
                             si.Role("host", RECEIVE_BASE + "/" + host, "write", 4096,
                                     exact=(attempt + "/PREPARED.json",)),
                             si.Role("host-read", RECEIVE_BASE + "/" + host, "read", 1, exact=(attempt,)),
                             si.Role("launch-base", LAUNCH_BASE, "read", 1, exact=(host,)),
                             si.Role("launch-base-write", LAUNCH_BASE, "write", 1, exact=(host,)),
                             si.Role("launch-host", launch_host, "read", 1, exact=(attempt,)),
                             si.Role("launch-host-write", launch_host, "write", 1, exact=(attempt,)),
                             si.Role("launch-attempt", launch_host + "/" + attempt, "read", 1,
                                     exact=("PREPARE-PROOF.json",)),
                             si.Role("launch-proof", launch_host + "/" + attempt, "write", 4096,
                                     exact=("PREPARE-PROOF.json",))])
    si.check_dir(P, "launch-base")                                 # end-launch/ is never created here

    def ensure(role, writer_role, leaf):
        try:
            si.check_absent(P, role, leaf)
        except si.Refusal as error:
            require(error.code == "exists", str(error))
            si.check_dir(P, role, leaf)
            return
        with si.Writer(P, writer_role) as writer:
            writer.mkdir_excl(leaf)
    ensure("base-read", "base", "end-received")
    ensure("recv-base-read", "recv-base", host)
    si.check_absent(P, "host-read", attempt)                       # both files absent before either is created
    ensure("launch-base", "launch-base-write", host)
    ensure("launch-host", "launch-host-write", attempt)
    si.check_absent(P, "launch-attempt", "PREPARE-PROOF.json")
    proof = dict(receive=root, host=host, attempt=attempt, created_empty=True, nonce=uuid.uuid4().hex,
                 utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    data = (json.dumps(proof, sort_keys=True) + '\n').encode()
    with si.Writer(P, "host") as writer:
        writer.mkdir_excl(attempt, mode=0o700)
        prepared = writer.create_excl(attempt + "/PREPARED.json", data)
    with si.Writer(P, "launch-proof") as writer:
        copy = writer.create_excl("PREPARE-PROOF.json", data)
    require(prepared["sha256"] == copy["sha256"] == hashlib.sha256(data).hexdigest(), 'Prepare proof copy differs')
    return dict(proof, prepare_proof_sha256=copy["sha256"],
                prepare_proof=launch_host + "/" + attempt + "/PREPARE-PROOF.json")


def gated_mtime(si, policy, role, rel):
    """mtime of a gated regular single-link file (si names/allowlist, canonical root, O_NOFOLLOW components and the
    descriptor gate); nothing is read."""
    si.gate_names(policy, role, rel)
    parts = rel.split("/")
    root = si.open_root(policy.role(role).root)
    try:
        parent = si.open_dirs(root, parts[:-1], rel)
    finally:
        os.close(root)
    try:
        fd, st = si.open_leaf(parent, parts[-1], 1 << 20, None, rel)
        os.close(fd)
    finally:
        os.close(parent)
    return st.st_mtime


def sealed_names(si, data_root, d3_names):
    """Recursive names-only listing of the sealed directory (canonical root, component-wise O_NOFOLLOW). Every name is
    gated by si.name_gate BEFORE it is stat'ed: outcome families refuse, except this seal's exact D3 member names
    (hash-only role); END claim names need the exact grant. Symlinks, specials and multi-link files refuse."""
    out, root = [], si.open_root(data_root)
    stack = [(root, "")]
    try:
        while stack:
            fd, prefix = stack.pop()
            try:
                for name in sorted(os.listdir(fd)):
                    rel = prefix + name
                    si.check_rel(rel)
                    si.name_gate(data_root + "/" + rel, "127x05", ("end-claim-exact",), d3_leaf=rel in d3_names)
                    st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        stack.append((si.open_dirs(fd, [name], rel), rel + "/"))
                    elif stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
                        out.append(rel)
                    else:
                        raise ValueError("Sealed member is a symlink, special or hard-linked file: " + rel)
            finally:
                os.close(fd)
    finally:
        for fd, _ in stack:
            os.close(fd)
    return sorted(out)


def registry_claims(si, P, root, host, round_index, exit_):
    """RC-5: the wrapper's safe_input snapshot, bound to registry-listing.json. Returns (claims, mine)."""
    listing = si.read_json(P, "recv", "registry-listing.json", 1 << 20)
    require(listing.get("schema") == "clasher.k4s.end-registry-listing.v1" and listing.get("host") == host
            and listing.get("round") == round_index, 'Registry listing identity mismatch')
    listed = listing.get("claims")
    require(isinstance(listed, list) and len(listed) <= MAX_CLAIMS, 'Registry listing malformed')
    require(exit_['registry_exists'] == bool(listed), 'Registry/exit observation mismatch')
    names = ['attempt-%02d.json' % i for i in range(len(listed))]
    require([c.get("name") for c in listed] == names, 'Registry is not a contiguous claim sequence')
    if not listed:
        si.check_absent(P, "recv", "registry")
        return [], []
    walked = [f["rel"] for f in si.walk_tree(P, "registry", "registry")["files"]]   # exact names, grant, nlink 1
    require(walked == ["registry/" + n for n in names], 'Received registry differs from the host listing')
    claims = []
    for index, entry in enumerate(listed):
        claim = si.read_json(P, "registry", "registry/" + entry["name"], 1 << 20, expected_sha256=entry["sha256"])
        require(claim.get('host') == host and claim.get('attempt') == index and claim.get('round') == round_index,
                'Registry claim namespace mismatch')
        require(isinstance(claim.get('receipt_directory'), str), 'Registry claim lacks receipt_directory')
        claims.append(dict(name=entry["name"], sha256=entry["sha256"], attempt=index, round=claim['round'],
                           receipt_directory=claim['receipt_directory'], launched_utc=claim.get('launched_utc'),
                           claim=claim))
    return claims, [c for c in claims if c['receipt_directory'] == os.path.basename(root)]


def verify(si, root, launch, prepared, now=None):
    """Return a health receipt; emit no ACK for missing or inconsistent seals, or before C-d."""
    now = time.time() if now is None else now
    host, attempt, round_index = namespace(root)
    sealed = ("durable-measurement/" + s for s in SEAL_FILES)
    P = si.Policy("127x05", [
        si.Role("recv", root, "read", 64 << 20, exact=RECEIVE_NAMES + ("PUSH-FAILED.json", "registry", "durable-measurement")
                + tuple(sealed)),
        si.Role("registry", root, "read", 1 << 20, exact=REGISTRY_NAMES, grants=("end-claim-exact",))])
    try:
        si.check_absent(P, "recv", "PUSH-FAILED.json")
    except si.Refusal as error:
        require(error.code == "exists", str(error))
        failure = si.read_json(P, "recv", "PUSH-FAILED.json", 1 << 16)
        raise ValueError('PUSH-FAILED prohibits ACK; rsync_exit_code=' + str(failure.get('rsync_exit_code',
                                                                                          'legacy-unspecified')))
    proof = si.read_json(P, "recv", "PREPARED.json", 1 << 16)
    require(proof == prepared, 'Receive preparation proof changed')
    require(proof['created_empty'] is True and re.fullmatch(r'[0-9a-f]{32}', proof['nonce']), 'Invalid preparation proof')
    require(proof['receive'] == root and proof['host'] == host and proof['attempt'] == attempt,
            'Preparation namespace mismatch')
    require(launch.get('schema') == 'clasher.k4s.end-launch-receipt.v2' and launch.get('kind') == 'end'
            and launch['host'] == host and os.path.basename(launch['job']) == attempt == launch.get('attempt')
            and launch.get('launched') is True, 'Launch namespace mismatch')
    marker = si.read_json(P, "recv", "TRANSFER-DONE.json", 1 << 16)
    exit_ = si.read_json(P, "recv", "exit.json", 1 << 16)
    require(marker['transfer_complete'] is True, 'Verification check failed')
    require(marker['host'] == exit_['host'] == host, 'Verification check failed')
    require(marker['attempt'] == exit_['attempt'] == attempt, 'Verification check failed')
    code = exit_['exit_code']
    require(type(code) is int and 0 <= code <= 255, 'Verification check failed')
    require(marker['measurement_exit_code'] == code, 'Verification check failed')
    exit_epoch = utc_epoch(exit_['utc'])
    require(gated_mtime(si, P, "recv", "TRANSFER-DONE.json") >= exit_epoch, 'Transfer marker predates recorded exit')
    require(proof['utc'] < launch['utc'] <= exit_['utc'] <= marker['utc'],
            'Preparation must precede launch; transfer must follow exit')
    c_d = dict(exit_epoch=exit_epoch, verified_epoch=now, c_d_earliest_utc=iso(exit_epoch + C_D_SECONDS),
               c_d_seconds=C_D_SECONDS, c_d_satisfied=now >= exit_epoch + C_D_SECONDS)
    require(c_d['c_d_satisfied'], 'C-d: verification is allowed only at or after exit_utc + 1300 s (%s)'
            % c_d['c_d_earliest_utc'])
    require(launch['wrapper_sha256'] == WRAPPER_SHA256, 'Unapproved END campaign wrapper')
    expected_argv = b''.join(value.encode() + b'\0' for value in launch['measurement_argv'])
    require(si.read_bytes(P, "recv", "argv.nul", max_size=1 << 16) == expected_argv,
            'Recorded argv differs from approved launch')
    require(type(exit_['measurement_exists']) is bool, 'Verification check failed')
    require(marker['measurement_exists'] == exit_['measurement_exists'], 'Verification check failed')
    require(type(exit_['registry_exists']) is bool and exit_.get('registry_snapshot') is True,
            'Verification check failed')
    claims, mine = registry_claims(si, P, root, host, round_index, exit_)
    require(len(mine) <= 1, 'Several registry claims name this attempt')
    for name in ('detach.log', 'detach.json'):
        si.sha256_input(P, "recv", name)                     # descriptor gate only
    public = [{k: v for k, v in c.items() if k != 'claim'} for c in claims]
    base = dict(schema=ACK_SCHEMA, utc=now, host=host, attempt=attempt, exit_code=code, registry_claims=public,
                launch_receipt_sha256=launch.get('_sha256'), prepared_nonce=proof['nonce'], **c_d)
    try:
        stamp = si.read_bytes(P, "recv", "durable-measurement/receipt-manifest.sha256", max_size=4096)
        seal_bytes = si.read_bytes(P, "recv", "durable-measurement/receipt-manifest.json", max_size=64 << 20)
    except si.Refusal as error:
        require(error.code == "missing", str(error))
        if exit_['measurement_exists']:
            si.check_dir(P, "recv", "durable-measurement")
        else:
            si.check_absent(P, "recv", "durable-measurement")
        return dict(base, classification='UNSEALED', ack_allowed=False, claim_without_receipt=bool(mine))
    require(exit_['measurement_exists'] is True, 'Directory/exit observation mismatch')
    seal_sha = hashlib.sha256(seal_bytes).hexdigest()
    require(stamp.decode('utf-8', 'replace').split() == [seal_sha, 'receipt-manifest.json'], 'Seal SHA mismatch')
    manifest = si.loads_strict(seal_bytes, 'receipt-manifest.json')
    require(manifest['status'] in ('complete', 'failed'), 'Verification check failed')
    require(manifest['scope'] == 'K4S-END-REFERENCE', 'Unexpected seal scope')
    require((code == 0) == (manifest['status'] == 'complete'), 'Exit/status mismatch')
    files = manifest['files']
    require(isinstance(files, dict) and files, 'Verification check failed')
    for name in files:
        si.check_rel(name)
        require(name not in SEAL_FILES, 'Verification check failed')
    d3 = sorted(n for n in files if n in D3_LEAVES)
    ordinary = sorted(n for n in files if n not in D3_LEAVES)
    data = root + '/durable-measurement'
    require('attempt-claim.json' in files, 'Sealed receipt lacks attempt-claim.json')
    roles = [si.Role("sealed", data, "read", 4 << 30, exact=tuple(ordinary), grants=("end-claim-exact",))]
    if d3:
        roles.append(si.Role("s6-sealed-end", RECEIVE_BASE + "/" + host, "read", 4 << 30,
                             exact=tuple(attempt + "/durable-measurement/" + n for n in d3), exemptions=("D3",)))
    S = si.Policy("127x05", roles)
    for name in ordinary:                                    # outcome-family names refuse here by name (no syscall)
        require(si.sha256_input(S, "sealed", name)["sha256"] == files[name], 'File SHA mismatch: ' + name)
    for name in d3:                                          # D3: hash-only against the seal manifest, never parsed
        si.hash_sealed_end_member(S, "s6-sealed-end", attempt + "/durable-measurement/" + name, files[name])
    require(sealed_names(si, data, set(d3)) == sorted(set(files) | set(SEAL_FILES)), 'Extra/missing files')
    copy = si.read_json(S, "sealed", 'attempt-claim.json', 1 << 20, expected_sha256=files['attempt-claim.json'])
    require(len(mine) == 1 and copy['claim_sha256'] == mine[0]['sha256'], 'Sealed receipt lacks its registry claim')
    require(copy['claim'] == mine[0]['claim'], 'Sealed claim copy differs')
    return dict(base, classification='SEALED', status=manifest['status'], ack_allowed=True, files=len(files),
                all_hashes_verified=True, d3_hash_only=d3, receipt_manifest_sha256=seal_sha, outcomes_sealed=True,
                legacy_PUSH_FAILED_without_exit_code_is_failure=True, approved_wrapper=True,
                claim_without_receipt=False, claim_bound=True)


def launch_paths(root):
    host, attempt, _ = namespace(root)
    return LAUNCH_BASE + "/" + host + "/" + attempt


def main(argv=None, si=None, now=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument('--receive', required=True)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--launch-receipt-sha256')
    p.add_argument('--prepare-proof-sha256')
    a = p.parse_args(argv)
    si = si or load_si()
    require(si.hostname_checked().split('.')[0] == '127x05', 'Verification check failed')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.sched_getaffinity(0) == {63}, 'Verification check failed')
    if a.prepare:
        made = prepare(si, a.receive)
        print(json.dumps(dict(receive=a.receive, created_empty=True, prepare_proof=made["prepare_proof"],
                              prepare_proof_sha256=made["prepare_proof_sha256"]), sort_keys=True))
        return 0
    require(all((a.launch_receipt_sha256, a.prepare_proof_sha256)),
            'Verification requires pinned launch and preparation proofs')
    host, attempt, _ = namespace(a.receive)
    L = si.Policy("127x05", [si.Role("launch", launch_paths(a.receive), "read", 16 << 20,
                                     exact=("LAUNCH-RECEIPT.json", "PREPARE-PROOF.json")),
                             si.Role("out", a.receive, "write", 1 << 20, exact=("DURABLE-ACK.json", "UNSEALED.json"))])
    launch = si.read_json(L, "launch", "LAUNCH-RECEIPT.json", 16 << 20, expected_sha256=a.launch_receipt_sha256)
    prepared = si.read_json(L, "launch", "PREPARE-PROOF.json", 1 << 16, expected_sha256=a.prepare_proof_sha256)
    launch['_sha256'] = a.launch_receipt_sha256
    result = verify(si, a.receive, launch, prepared, now)
    result['prepare_proof_sha256'] = a.prepare_proof_sha256
    with si.Writer(L, "out") as writer:
        writer.create_excl('DURABLE-ACK.json' if result['ack_allowed'] else 'UNSEALED.json',
                           (json.dumps(result, sort_keys=True) + '\n').encode())
    print(json.dumps(result, sort_keys=True))
    return 0 if result['ack_allowed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
