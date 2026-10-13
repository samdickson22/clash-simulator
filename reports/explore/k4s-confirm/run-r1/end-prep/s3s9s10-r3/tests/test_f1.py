"""r3 END-FULL-F1 (end_prep_common half + every Part A entrypoint): every pre-layer read of a sibling file (the vendored
safe_input.py, end_prep_common.py, and the sibling modules s1b / s3 / s9) goes through the bootstrap-r1 CANONICAL
BOOTSTRAP, pasted verbatim, with SHA-256 + size pins. Checks: the pasted blocks are byte-equal to the canonical text;
the pin chain is consistent; no sys.path import of a sibling remains; and the bootstrap-r1 conformance kit runs every
alias scenario (ancestor symlink into a synthetic games/, outcome-named ancestors, leaf symlink, hard link, wrong size,
same-size mismatching bytes, FIFO/dir leaf, non-normalized paths, post-hash swap) against every Part A entrypoint and
every pinned file it loads, asserting zero canary consumption (recorders + kernel atime + execution markers)."""
import ast
import hashlib
import os
import shutil
import sys
import tempfile

import pytest

import k4s_adopt
import k4s_bootstrap_kit as KIT
from conftest import C, ROOT, ok, read

HERE = os.path.dirname(os.path.abspath(__file__))
# bootstrap-r1 CANONICAL-READY (2026-10-13T00:13:28Z): the final canonical text, byte for byte.
CANONICAL_SHA256 = "5611c6049b5495a6cec283bd57ee662bcb4601873fb0300ece32e27ed8da760b"
CANONICAL_SIZE = 8372
BOOTSTRAP_R1 = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/bootstrap-r1/k4s_bootstrap_r1.py"
# The vendored conformance kit (bootstrap-r1/tests at CANONICAL-READY), byte copies.
KIT_SHA256 = {"k4s_bootstrap_kit.py": "a1d2021c006b128b4ac60eaf6d9011c36268efd69d8fd478edf19326d856522f",
              "kit_harness.py": "57ffa09921225a769d5ea8d45015bad79e4bb7ad1ebbcb99855e0c05d1e32515"}
MODULES = k4s_adopt.MODULES
SIBLINGS = ("end_prep_common", "safe_input", "s1b_copy_admissions", "s3_guard_job", "s9_end_runtime")


def canonical():
    return read(os.path.join(HERE, "k4s_bootstrap_r1.py"))


def block(name):
    text = read(os.path.join(ROOT, name)).decode()
    i, j = k4s_adopt.block_span(text, name)
    return text, i, j


# ---------------------------------------------------------------- verbatim adoption and pins

def test_vendored_canonical_is_the_bootstrap_r1_text():
    data = canonical()
    ok(hashlib.sha256(data).hexdigest() == CANONICAL_SHA256 and len(data) == CANONICAL_SIZE)
    if os.path.exists(BOOTSTRAP_R1):                     # the source of record, when this tree sits beside it
        ok(read(BOOTSTRAP_R1) == data, "bootstrap-r1/k4s_bootstrap_r1.py differs from the vendored copy")
    for name, digest in KIT_SHA256.items():
        ok(hashlib.sha256(read(os.path.join(HERE, name))).hexdigest() == digest, name)


@pytest.mark.parametrize("name", MODULES)
def test_block_is_byte_equal_to_the_canonical_text(name):
    text, i, j = block(name)
    ok(text[i:j].encode() == canonical(), "%s: the pasted block differs from k4s_bootstrap_r1.py" % name)
    ok(text.count("K4S CANONICAL BOOTSTRAP") == 2, name)


def test_pin_chain_is_consistent():
    texts, done = k4s_adopt.adopt(ROOT)
    for name in MODULES:
        ok(texts[name].encode() == read(os.path.join(ROOT, name)), "%s: pins are stale (run tests/k4s_adopt.py)" % name)
        data = read(os.path.join(ROOT, name))
        ok(done[name] == (hashlib.sha256(data).hexdigest(), len(data)))
    ok(C.SAFE_INPUT_SIZE == len(read(os.path.join(ROOT, "safe_input.py"))))


def test_loaded_modules_carry_their_bootstrap_tags():
    for name in SIBLINGS:
        module = sys.modules[name]
        tag = module.__k4s_bootstrap__
        path = os.path.join(ROOT, name + ".py")
        data = read(path)
        ok(tag == (C.K4S_BOOTSTRAP_RELEASE, path, hashlib.sha256(data).hexdigest(), len(data)), (name, tag))


@pytest.mark.parametrize("name", MODULES)
def test_no_sys_path_import_of_a_sibling(name):
    """Outside the canonical block: no import statement, __import__ or importlib for a sibling; no sys.path edit."""
    text, i, j = block(name)
    tree = ast.parse(text[:i] + text[j:])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            ok(not [a.name for a in node.names if a.name.split(".")[0] in SIBLINGS + ("importlib", "runpy")],
               "%s imports a sibling by sys.path" % name)
        if isinstance(node, ast.ImportFrom):
            ok((node.module or "").split(".")[0] not in SIBLINGS + ("importlib", "runpy"), name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            ok(node.func.id != "__import__", name)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "sys":
            ok(node.attr != "path", "%s edits sys.path" % name)


def test_existing_unpinned_module_is_never_reused(monkeypatch):
    """A module already in sys.modules under a sibling name is reused only with the same bootstrap tag."""
    fake = type(sys)("s9_end_runtime")
    monkeypatch.setitem(sys.modules, "s9_end_runtime", fake)
    with pytest.raises(SystemExit) as info:
        C.load_sibling("s9_end_runtime", "0" * 64, 1)
    ok("k4s bootstrap refused" in str(info.value))
    fake.__k4s_bootstrap__ = (C.K4S_BOOTSTRAP_RELEASE, C.HERE + "/s9_end_runtime.py", "0" * 64, 2)
    with pytest.raises(SystemExit):
        C.load_sibling("s9_end_runtime", "0" * 64, 1)


# ---------------------------------------------------------------- the conformance kit, every entrypoint x pinned file

def code_files():
    return {name: read(os.path.join(ROOT, name)) for name in C.CODE_FILES}


def pin_of(files, leaf):
    return hashlib.sha256(files[leaf]).hexdigest(), len(files[leaf])


# (entry, layer, first): `first` = the layer is the FIRST file the entry bootstraps, so the kit's post-hash swap
# (triggered by the first "<k4s-bootstrap " compile) targets it; deeper layers run every other scenario.
CHAIN = (("end_prep_common.py", "safe_input.py", True),
         ("s9_end_runtime.py", "end_prep_common.py", True), ("s9_end_runtime.py", "safe_input.py", False),
         ("s1b_copy_admissions.py", "end_prep_common.py", True), ("s1b_copy_admissions.py", "safe_input.py", False),
         ("s1b_copy_admissions.py", "s9_end_runtime.py", False),
         ("s3_guard_job.py", "end_prep_common.py", True), ("s3_guard_job.py", "safe_input.py", False),
         ("s3_guard_job.py", "s1b_copy_admissions.py", False), ("s3_guard_job.py", "s9_end_runtime.py", False),
         ("s10_stage_host.py", "end_prep_common.py", True), ("s10_stage_host.py", "safe_input.py", False),
         ("s10_stage_host.py", "s3_guard_job.py", False), ("s10_stage_host.py", "s1b_copy_admissions.py", False),
         ("s10_stage_host.py", "s9_end_runtime.py", False))
# The full outcome-name list runs for each entry's first layer; deeper layers use two representative names (the
# name gate is the same canonical code for every path, and the ancestor walk is exercised by every other scenario).
SHORT_NAMES = ("games", "END-RAW.json.bak")


def entrypoint(entry, layer, first):
    files = code_files()
    sha256, size = pin_of(files, layer)
    if entry == "end_prep_common.py":
        return KIT.Entrypoint("C<-" + layer, files, entry, layer, sha256, size, mode="import",
                              module_name="end_prep_common", supports_swap=first)
    names = KIT.OUTCOME_DIR_NAMES if first else SHORT_NAMES
    return KIT.Entrypoint("%s<-%s" % (entry[:-3], layer), files, entry, layer, sha256, size, argv=["--help"],
                          supports_swap=first, outcome_dir_names=names)


def cases():
    out = []
    for entry, layer, first in CHAIN:
        for scenario in entrypoint(entry, layer, first).scenarios():
            out.append(pytest.param(entry, layer, first, scenario, id="%s<-%s:%s" % (entry[:-3], layer[:-3], scenario)))
    return out


@pytest.fixture
def kitdir():
    path = tempfile.mkdtemp(prefix="k4s-f1kit-", dir="/tmp")
    yield path
    for directory, dirs, _ in os.walk(path):
        os.chmod(directory, 0o755)
    shutil.rmtree(path)


@pytest.mark.parametrize("entry,layer,first,scenario", cases())
def test_entrypoint_alias_scenarios(kitdir, entry, layer, first, scenario):
    KIT.check_scenario(KIT.run_scenario(entrypoint(entry, layer, first), scenario, kitdir))


def test_kit_covers_every_entrypoint_and_pinned_file():
    entries = {e for e, _, _ in CHAIN}
    ok(entries == set(MODULES), entries)
    for name, deps in k4s_adopt.ORDER:
        ok({l for e, l, _ in CHAIN if e == name} >= set(deps) | {"safe_input.py"}, name)
    ok({l for e, l, f in CHAIN if f} == {"end_prep_common.py", "safe_input.py"})


@pytest.mark.parametrize("module", ["s9_end_runtime", "s1b_copy_admissions", "s3_guard_job", "s10_stage_host"])
def test_entrypoint_refuses_a_foreign_end_prep_common(monkeypatch, module):
    """Each entrypoint reuses an already loaded end_prep_common only with its own bootstrap tag (path, pins)."""
    entry = sys.modules[module]
    ok(entry._k4s_common() is C)                                   # the real one: same tag, reused
    fake = type(sys)("end_prep_common")
    monkeypatch.setitem(sys.modules, "end_prep_common", fake)
    with pytest.raises(SystemExit) as info:
        entry._k4s_common()
    ok("k4s bootstrap refused" in str(info.value))
    fake.__k4s_bootstrap__ = C.__k4s_bootstrap__[:3] + (C.__k4s_bootstrap__[3] + 1,)
    with pytest.raises(SystemExit):
        entry._k4s_common()
