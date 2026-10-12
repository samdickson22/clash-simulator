# safe-input-r3 PROGRESS (resume file)

Started 2026-10-12T21:29:49Z on 127x05. r3 = r2 + ruling E5. Copied r2 with cp -a; r2 file hashes in R2-BASELINE-SHA256.txt (verify r2 unchanged with: cd ../safe-input-r2 && sha256sum -c ../safe-input-r3/R2-BASELINE-SHA256.txt).
PROGRESS-r2.md removed from r3 copy (stays in r2).

## Done
- [x] M0 copy r2 -> r3, baseline recorded
- [x] M1 read r2 README/ADOPTION/safe_input.py/D5/tests, E5-OIDS-ls-tree.txt, COORDINATOR 21:28Z ruling E5 (origin/main 27b54d9d)
- [x] M1b pytest: /dev/shm/si-r3-pytest38 (8.3.5), /dev/shm/si-r3-pytest312 (9.1.1); matrix runner /dev/shm/si-r3-matrix.sh <pkgdir>; baseline r3 copy 472 passed (k4s-freeze)

## Design (r3)
- _CORE: E5_RUNTIME_MEMBERS (9 (path, oid) pairs, tuple); E5_PATHS snapshot; e5_blob_oid(rel) refuses 'policy' unless paths == E5_PATHS in order and OIDs 40-hex (tests may patch OIDs only).
- name_gate(..., e5_rel=None): e5_rel must be an exact E5 path and the path's suffix; exempts only the final component's OUTCOME family.
- EXEMPTIONS += E5. _gate(e5=) needs 'E5' in role.exemptions and exact path. Ordinary reads never pass e5 -> E5 names refuse by family (opaque: no read_bytes/read_json/open_input/sha256_input/copy_input/GitPlan.read/git_show_file).
- On disk: hash_e5 (normal gates; blob sha1 == pin), copy_e5 (hash pass then copy pass; copy re-checked), walk_tree lists E5 in 'e5' (regular only).
- Git: _screen_tree phase 1: E5 member must be blob, mode 100644, oid == pin, within cap -> plan['e5']; git_hash_e5; git_export writes E5 0444; GitPlan.e5 / hash_e5.
- Receive (S10 ships runtime): manifest file key 'e5'; validate: exact path, mode 0444, not e4; name_gate e5_rel; receiver re-hashes blob sha1 while streaming; remote_receive runs hash_e5 on each E5 source before ssh.
- Remote reader (remote_check) NOT extended: E5 names still refuse there (disclose).
- [x] M2 code: E5 in _CORE (constant, e5_blob_oid, name_gate e5_rel), _gate/_open_gated e5, hash_e5/copy_e5, walk_tree e5, Writer e5, _screen_tree/git_hash_e5/git_export/GitPlan e5, receive (FILE_KEYS e5 strict bool, validate, blob re-hash, local hash_e5 pre-ssh)
- [x] M3 r2 tests patched (receive manifest helper e5:False; EXEMPTIONS set; fingerprint pin 33f594ed...); new tests/test_e5.py (75); suite 547 on k4s-freeze
- [x] M4 mutate.py: 12 r2 targets re-pointed (same meaning), 26 E5 mutants + equivalents; --check-edits 273 valid; quick 3.12 -O run of E5+retargeted: 37/38 killed (SD01 = r2 documented equivalent); NULLs survived. test_e5.py now 76.
- M5 NEXT: D1 re-run vs origin/main metadata (/dev/shm/si-r3-d1.py), then D5 file, full matrix, full mutation campaigns (py38 -O, py312 -O), docs, SHA256SUMS
- [x] M5 D1 re-run at origin/main 02805c97 (safe_input 806e5ebb, fp 33f594ed): member-set refusals 0; plan accepted (files 4173, e4 [E2], e1, e5 9); object_reads 0; no --batch. Evidence D1-RERUN-r3.json + d1_rerun_r3.py; D5 file updated. E5 constant == E5-OIDS-ls-tree.txt == tree metadata at 02805c97. (If safe_input.py changes, RE-RUN D1.)
- M6 RUNNING: mutation py38 -O -> /dev/shm/si-r3-mut38.json, py312 (k4s-freeze) -O -> /dev/shm/si-r3-mut312.json (setsid; TMPDIR /dev/shm/si-r3-mut-tmp*)
- [x] M5b matrix: 548 passed x 6 (py3.8.10, k4s-freeze 3.12.12, e4v3 3.12.12; normal and -O; -O warning = PytestConfigWarning only)
- [x] M6 mutation FINAL (safe_input 806e5ebb): py38 -O 270/273, py312 -O 270/273; not killed = Q11/SD01/SD08 (r2 equivalents; joints killed); 26/26 E5 mutants killed both; 6/6 NULL survived; 15 pin-only kills re-killed without the pin. Installed (annotated) MUTATION-RESULTS-py38-O.json / -py312-O.json. No leftovers (/dev/shm/safe-input-mut-*, /tmp/si-git-home-*, si-r3-mut-tmp*).
- [x] M7a ADOPTION r3 written; README §0, table, §2, §8, §9 written
- M7b NEXT: README §10/§11, SHA256SUMS, final r2 check, cleanup /dev/shm scratch, report
- [x] M7b README §10/§11 written; r2 re-verified byte-identical (23/23 OK, no extra files); /dev/shm scratch of this run removed (si-r3-*, r2-baseline copy); 0 /tmp/si-git-home-*; no __pycache__
- [x] M8 SHA256SUMS written (2026-10-12T21:52:58Z). DONE - r3 candidate ready for Sol review. Nothing committed/pushed; no ssh.
