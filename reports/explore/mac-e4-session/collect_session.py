#!/usr/bin/env python3
"""Post-session collection for the TIERS Mac session (R-M1/R-M2/R-M3, COORDINATOR 4eb6c3e5). r2 after Sol review r1.

Runs on 127x05 (python3 >= 3.8). Never prints summary values. Steps (each requires the previous steps' receipts):
  check   : post receipt + seal present on the Mac -> mode complete|failed (OUT/check.json)
  fetch   : tar stream of the sealed dir -> validated members (exact top-level, regular files/dirs only, canonical
            relative names) -> PRIVATE 05 copy; seal verified (sidecar, every file SHA streamed, regular files only,
            no unlisted files, no links) (OUT/fetch.json)
  public  : build D in a fresh temp dir with EXACTLY the allowed inventory, then rename to D (D must not exist):
            complete: 11 sealed files + a3p-poll-check.json (A3-P, required) + stage-nocopy-session-verify.json +
                      preconditions.json + session-receipt.json
            failed:   the present subset of the 11 + failure.json/cleanup-failure.json + classification/ (frozen
                      classifier, must exit 0) + stage-nocopy-session-verify.json (if any) + preconditions.json +
                      session-receipt.json
  private : Mac k4s-commit-repo, clean and at the pinned base: copy the full sealed dir to D/sealed; ISOLATED index;
            commit-tree; new local branch `private-mac-e4-session-r1` checked out (so HEAD contains the commit, as K4S
            P3 needs) + ref refs/private/mac-e4-tiers-session-r1; pushurl invalid, single remote, no pushDefault,
            pre-push hook that always fails; committed tree under D/sealed must equal the private copy by git blob id
  bundle  : git bundle base..ref on the Mac -> 05 (SHA-checked) -> restored into an isolated --shared bare repo on 05
            (index-pack checks the pack) -> restored tree blob ids == private copy
  binding : D/private-commit-binding.json
  apps    : open -a "Google Chrome"; records the observed result (failure is recorded, not hidden)
The public git commit of D is a separate operator step (temp-index procedure).
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath

REPO = Path("/mpac/sdicks02/repos/clasher")
S = "/Users/sam/Desktop/code/clasher-mac-e4-tiers-20261011"
O = S + "/session-a5-r1"
DREL = "reports/explore/mac-e4-session/tiers-session-r1"
D = REPO / DREL
PRIVROOT = Path("/mpac/sdicks02/jobs/clasher/mac-e4-private")
PRIV = PRIVROOT / "session-a5-r1"
BUNDLES = PRIVROOT / "bundles"
E4V3 = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
COMMIT = "2e2753120a768ec03d0354e47650c61c8fd34820"
K4S_REPO = S + "/k4s-commit-repo"
K4S_BASE = "3cd0e58bd7ed1416e393f3d85ccfc4c653f86bad"
BRANCH, PRIVATE_REF = "private-mac-e4-session-r1", "refs/private/mac-e4-tiers-session-r1"
HOOK_SENTINEL = "MAC_E4_PRIVATE_PUSH_REFUSED_BY_HOOK"  # the probe must see the hook itself refuse
PY12 = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
HERE = Path(__file__).resolve().parent
OUT = HERE / "receipts/phase-b-collect-20261012"
SSH = ["timeout", "1800", "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=10",
       "-o", "ServerAliveCountMax=3", "macmini-fleet"]
PUBLIC_SEALED = ("tiers-summary.json", "tiers-complete.json", "receipt-manifest.json", "receipt-manifest.sha256",
                 "tiers-identity.json", "build-tiers.json", "pre-session-census.json", "runtime-versions.json",
                 "exactness-tiers.json", "belief-exactness.json", "student-agreement.json")
FAILURE_FILES = ("failure.json", "cleanup-failure.json")


def log(message):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + message
    print(line, file=sys.stderr, flush=True)
    with open(OUT / "collect.log", "a") as stream:
        stream.write(line + "\n")


def fail(message):
    log("FAIL " + message)
    raise SystemExit(1)


def nonce():
    return os.urandom(8).hex()


def mac(command, stdin=None):
    """Run a remote command; return stdout (bytes). Exact final line must carry this call's nonce + rc 0."""
    n = nonce()
    wrapped = "setopt pipefail; { %s ; }; printf '\\n__RC_%s=%%s\\n' $?" % (command, n)
    r = subprocess.run(SSH + [wrapped], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        fail("ssh transport rc=%d: %s" % (r.returncode, command[:100]))
    out = r.stdout
    marker = ("__RC_%s=" % n).encode()
    # Output is exactly BODY + b"\n" + marker + rc + b"\n" (the wrapper adds both newlines).
    if not out.endswith(b"\n"):
        fail("no final status line: " + command[:100])
    head, _, token = out[:-1].rpartition(b"\n")
    if not token.startswith(marker) or not token[len(marker):].isdigit():
        fail("no/invalid final status line: " + command[:100])
    if token[len(marker):] != b"0":
        fail("remote rc=%s: %s" % (token[len(marker):].decode(), command[:100]))
    return head


def mac_text(command):
    return mac(command).decode().rstrip("\n")


def mac_stream(command, destination):
    """Binary stdout -> new local file; status line with this call's nonce on remote stderr (exact final line)."""
    n = nonce()
    wrapped = "setopt pipefail; { %s ; }; printf '__RC_%s=%%s\\n' $? >&2" % (command, n)
    with open(destination, "xb") as stream:
        r = subprocess.run(SSH + [wrapped], stdout=stream, stderr=subprocess.PIPE)
    lines = r.stderr.decode(errors="replace").rstrip("\n").split("\n")
    if r.returncode != 0 or lines[-1] != "__RC_%s=0" % n:
        fail("stream failed (ssh rc %d, status %r): %s" % (r.returncode, lines[-1][-40:], command[:100]))


def sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, value):
    with open(path, "x") as stream:
        json.dump(value, stream, indent=1, sort_keys=True)
        stream.write("\n")


def read(name):
    path = OUT / name
    if not path.is_file():
        fail("prerequisite receipt missing: " + name)
    return json.loads(path.read_text())


def canonical(name):
    p = PurePosixPath(name)
    return name and not p.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/"))


def regular_inventory(root):
    """Map relative path -> path for regular files; fail on links/special entries anywhere."""
    result = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            mode = os.lstat(full).st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                fail("non-regular entry " + full)
            if stat.S_ISREG(mode):
                result[os.path.relpath(full, root)] = Path(full)
    return result


def step_check():
    if (OUT / "check.json").exists():
        fail("check already done")
    if mac_text("test -f '%s/session-a5-r1.post.json' && test -f '%s/session-a5-r1.pre.json' && echo yes" % (S, S)) != "yes":
        fail("post receipt not present")
    (OUT / "session-a5-r1.post.json").write_bytes(mac("cat '%s/session-a5-r1.post.json'" % S) + b"\n")
    (OUT / "session-a5-r1.pre.json").write_bytes(mac("cat '%s/session-a5-r1.pre.json'" % S) + b"\n")
    post = json.loads((OUT / "session-a5-r1.post.json").read_text())
    sealed = mac_text("if test -f '%s/receipt-manifest.json' && test -f '%s/receipt-manifest.sha256'; then cat '%s/receipt-manifest.sha256'; else echo NOSEAL; fi" % (O, O, O))
    if mac_text("ps -Ao command | awk '/measure_tiers[.]py|session_wrapper[.]py/ && !/awk/ {n++} END {print n+0}'") != "0":
        fail("session processes still running")
    ok = (post["final_returncode"] == 0 and not post["wrapper_failure"]
          and [s["step"] for s in post["steps"]] == ["verify-bundle", "build", "measure"]
          and all(s.get("returncode") == 0 for s in post["steps"]))
    seal = sealed.split()[0] if sealed != "NOSEAL" else None
    write_new(OUT / "check.json", dict(mode="complete" if ok and seal else "failed", seal_sha256=seal,
              final_returncode=post["final_returncode"], steps=[(s["step"], s.get("returncode")) for s in post["steps"]]))
    log("check OK mode=" + read("check.json")["mode"])


def step_fetch():
    check = read("check.json")
    if check["seal_sha256"] is None:
        fail("no seal on the Mac; nothing sealed to fetch (report to coordinator)")
    if PRIV.exists():
        fail(str(PRIV) + " exists")
    PRIVROOT.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVROOT, 0o700)
    archive = PRIVROOT / "session-a5-r1.fetch.tar"
    mac_stream("tar -C '%s' -cf - session-a5-r1" % S, archive)
    PRIV.mkdir()
    with tarfile.open(archive, "r:") as tar:
        for member in tar:
            name = member.name.rstrip("/")
            if not canonical(name) or not (name == "session-a5-r1" or name.startswith("session-a5-r1/")):
                fail("bad archive member " + member.name)
            if not (member.isreg() or member.isdir()):
                fail("non-regular archive member " + member.name)
            rel = name[len("session-a5-r1"):].lstrip("/")
            target = PRIV / rel if rel else PRIV
            if member.isdir():
                target.mkdir(exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            with open(target, "xb") as stream:
                shutil.copyfileobj(source, stream, 1 << 20)
    archive.unlink()
    inventory = regular_inventory(PRIV)
    sidecar = (PRIV / "receipt-manifest.sha256").read_text().split()
    if sidecar != [sha(PRIV / "receipt-manifest.json"), "receipt-manifest.json"] or sidecar[0] != check["seal_sha256"]:
        fail("seal sidecar")
    files = json.loads((PRIV / "receipt-manifest.json").read_text())["files"]
    if any(not canonical(n) for n in files):
        fail("non-canonical manifest path")
    bad = sorted(n for n, h in files.items() if n not in inventory or sha(inventory[n]) != h)
    unlisted = sorted(set(inventory) - set(files) - {"receipt-manifest.json", "receipt-manifest.sha256"})
    if bad or unlisted:
        fail("private copy seal mismatch bad=%r unlisted=%r" % (bad[:5], unlisted[:5]))
    write_new(OUT / "fetch.json", dict(private_copy=str(PRIV), files=len(files), seal_sha256=sidecar[0], passes=True))
    log("fetch OK %d sealed files" % len(files))


def step_public():
    check, fetch = read("check.json"), read("fetch.json")
    if D.exists():
        fail(str(D) + " exists")
    tmp = D.parent / (".tmp-" + D.name + "-" + nonce())
    (tmp / "sealed").mkdir(parents=True)
    names = [n for n in PUBLIC_SEALED if (PRIV / n).is_file()]
    if check["mode"] == "complete":
        if names != list(PUBLIC_SEALED):
            fail("complete mode requires all public sealed files")
    else:
        names += [n for n in FAILURE_FILES if (PRIV / n).is_file()]
    for name in names:
        shutil.copyfile(PRIV / name, tmp / "sealed" / name)
        if sha(tmp / "sealed" / name) != sha(PRIV / name):
            fail("copy " + name)
    if check["mode"] == "complete":
        r = subprocess.run([sys.executable, "-I", str(HERE / "a3p_poll_check.py"), "--receipts", str(PRIV),
                            "--receipt-manifest-sha256", fetch["seal_sha256"], "--output", str(tmp / "a3p-poll-check.json")],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            fail("A3-P reducer failed: " + r.stderr.decode()[-300:])
    else:
        r = subprocess.run([PY12, "-B", str(REPO / E4V3 / "classify_failure.py"), "--receipts", str(PRIV),
                            "--output", str(tmp / "classification")], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode != 0:
            fail("frozen classifier failed (report to coordinator): " + r.stderr.decode()[-300:])
    post = json.loads((OUT / "session-a5-r1.post.json").read_text())
    pre = json.loads((OUT / "session-a5-r1.pre.json").read_text())
    verification = post.get("nocopy_session_verification") or {}
    if "path" in verification:
        name = os.path.basename(verification["path"])
        if not canonical(name) or "/" in name:
            fail("bad verify receipt name")
        mac_stream("cat '%s/staged-a5/%s'" % (S, name), tmp / "stage-nocopy-session-verify.json")
        if sha(tmp / "stage-nocopy-session-verify.json") != verification["sha256"]:
            fail("verify receipt SHA")
    elif check["mode"] == "complete":
        fail("complete mode requires the session verify receipt")
    mac_stream("cat '%s/preflight/preconditions-r3.json'" % S, tmp / "preconditions.json")
    go = (HERE / "receipts/phase-b-session-20261012/GO-reference.txt").read_text().strip()
    items = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
    write_new(tmp / "session-receipt.json", dict(schema="clasher.mac-e4-session.session-receipt.v1", mode=check["mode"],
        runtime_commit=COMMIT, manifest_sha256=pre["manifest_sha256"], go_reference=go, stage_nocopy_helper_used=True,
        session_pre=pre, session_post=post,
        apps_quit_for_window=dict(google_chrome="SIGTERM to main PID 56345 at 2026-10-12T11:56:42Z (exited ~1 s)",
            claude="not quit (PID 63277 belongs to the other console user simonfarshid)",
            chatgpt="left running (hosts Codex agents)"),
        software_update=dict(change="none (no sudo/GUI route; coordinator dbe683e0)",
            prefs_before=pre["software_update_prefs_before"], prefs_after=post["software_update_prefs_after"]),
        caffeinate=dict(argv=pre["caffeinate_argv"], pid=pre["caffeinate_pid"]),
        files={n: dict(sha256=sha(tmp / n), bytes=(tmp / n).stat().st_size) for n in items}, outcomes_read=False))
    allowed = {"sealed/" + n for n in names} | {"preconditions.json", "session-receipt.json"}
    allowed |= {"stage-nocopy-session-verify.json"} if "path" in verification else set()
    allowed |= {"a3p-poll-check.json"} if check["mode"] == "complete" else set()
    actual = set(regular_inventory(tmp))
    extra = {n for n in actual - allowed if not (check["mode"] == "failed" and n.startswith("classification/"))}
    if extra or (allowed - actual):
        fail("public inventory mismatch extra=%r missing=%r" % (sorted(extra), sorted(allowed - actual)))
    os.rename(tmp, D)
    write_new(OUT / "public.json", dict(directory=DREL, files=sorted(regular_inventory(D)), mode=check["mode"]))
    log("public OK %d files in %s (not yet committed)" % (len(actual), DREL))


def git_blob_ids(root):
    files = regular_inventory(root)
    names = sorted(files)
    r = subprocess.run(["git", "hash-object", "--no-filters", "--stdin-paths"], input="\n".join(str(files[n]) for n in names) + "\n",
                       stdout=subprocess.PIPE, check=True, text=True, cwd=str(REPO))
    return dict(zip(names, r.stdout.split()))


def step_private():
    read("fetch.json")
    if (OUT / "private.json").exists():
        fail("private already done")
    R, target = K4S_REPO, DREL + "/sealed"
    if mac_text("git -C '%s' rev-parse HEAD" % R) != K4S_BASE:
        fail("k4s-commit-repo HEAD is not the pinned base")
    if mac_text("git -C '%s' status --porcelain --untracked-files=all | wc -l | tr -d ' '" % R) != "0":
        fail("k4s-commit-repo is not clean")
    if mac_text("git -C '%s' remote" % R) != "origin" or mac_text("git -C '%s' config --get remote.pushDefault || echo UNSET" % R) != "UNSET":
        fail("unexpected remotes/pushDefault")
    if mac_text("test ! -e '%s/%s' && echo absent" % (R, DREL)) != "absent":
        fail(DREL + " exists in k4s-commit-repo")
    size = sum(p.stat().st_size for p in regular_inventory(PRIV).values())
    mac_free = int(mac_text("df -k '%s' | tail -1 | awk '{print $4}'" % S)) * 1024
    if mac_free < 3 * size + 2 * 2**30 or shutil.disk_usage(PRIVROOT).free < 3 * size + 2 * 2**30:
        fail("insufficient headroom for copy + objects + bundle (need >= 3x %d B + 2 GiB)" % size)
    hooks = R + "/.git/hooks"
    mac("git -C '%s' config core.hooksPath '%s' && git -C '%s' config remote.origin.pushurl PRIVATE-NEVER-PUSH-mac-e4-session" % (R, hooks, R))
    mac("set -C; printf '#!/bin/sh\\necho %s >&2\\nexit 1\\n' > '%s/pre-push' && chmod +x '%s/pre-push'" % (HOOK_SENTINEL, hooks, hooks))
    if mac_text("cd '%s' && git rev-parse --path-format=absolute --git-path hooks" % R) != hooks:
        fail("effective hooks path differs")
    # Probe BEFORE any private object exists: a push of the public base to a throwaway local repo must be refused.
    probe = S + "/.push-probe-" + nonce()
    probe_out = mac_text("git init -q --bare '%s' && (git -C '%s' push -q '%s' HEAD:refs/heads/probe 2>&1 && echo PUSH_SUCCEEDED || echo PUSH_REFUSED); rm -rf '%s'" % (probe, R, probe, probe))
    if not probe_out.endswith("PUSH_REFUSED") or "PUSH_SUCCEEDED" in probe_out or HOOK_SENTINEL not in probe_out:
        fail("pre-push refusal probe did not refuse: " + probe_out[-200:])
    mac("mkdir -p '%s/%s' && cp -Rp '%s' '%s/%s'" % (R, DREL, O, R, target))
    want = git_blob_ids(PRIV)
    index = R + "/.git/index.private-mac-e4"
    commit = mac_text("cd '%s' && export GIT_INDEX_FILE='%s' && rm -f \"$GIT_INDEX_FILE\" && git read-tree HEAD && git add -f -- '%s' && "
                      "tree=$(git write-tree) && git -c user.name='Sam Dickson' -c user.email=sjedickson@gmail.com commit-tree $tree -p HEAD "
                      "-m 'PRIVATE: TIERS Mac session sealed receipts (session-a5-r1); NEVER PUSH' "
                      "-m 'Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>' && rm -f \"$GIT_INDEX_FILE\"" % (R, index, target))
    if len(commit) != 40:
        fail("commit id")
    changed = mac_text("git -C '%s' diff --name-only %s %s" % (R, K4S_BASE, commit)).splitlines()
    if not changed or any(not c.startswith(target + "/") for c in changed):
        fail("private commit touches paths outside " + target)
    listing = mac_text("git -C '%s' ls-tree -r %s -- '%s'" % (R, commit, target)).splitlines()
    have = {}
    for line in listing:
        meta, path = line.split("\t", 1)
        mode, kind, blob = meta.split()
        if kind != "blob" or mode != "100644" and mode != "100755":
            fail("unexpected tree entry " + line)
        have[path[len(target) + 1:]] = blob
    if have != want:
        fail("committed inventory differs from the private copy")
    # Attach HEAD to a new local branch at the commit without touching the (identical, verified) working copy:
    # refs + symbolic HEAD + normal index from the commit tree, then status must be clean.
    mac("cd '%s' && git update-ref %s %s && git update-ref refs/heads/%s %s '' && git symbolic-ref HEAD refs/heads/%s && "
        "git read-tree %s && git update-index -q --refresh; git config branch.%s.pushRemote PRIVATE-NEVER-PUSH"
        % (R, PRIVATE_REF, commit, BRANCH, commit, BRANCH, commit, BRANCH))
    if mac_text("git -C '%s' rev-parse HEAD" % R) != commit or mac_text("git -C '%s' status --porcelain | wc -l | tr -d ' '" % R) != "0":
        fail("checkout of the private branch")
    tree = mac_text("git -C '%s' rev-parse %s^{tree}" % (R, commit))
    write_new(OUT / "private.json", dict(base=K4S_BASE, commit=commit, tree=tree, ref=PRIVATE_REF, branch=BRANCH,
                                         repo_path=target, files=len(have)))
    log("private OK commit %s (never pushed)" % commit)


def step_bundle():
    private = read("private.json")
    bundle_mac = S + "/session-a5-r1-private.bundle"
    BUNDLES.mkdir(mode=0o700, parents=True, exist_ok=True)
    local = BUNDLES / "session-a5-r1-private.bundle"
    if local.exists():
        fail("bundle exists on 05")
    mac("test ! -e '%s' && git -C '%s' bundle create '%s' %s..%s" % (bundle_mac, K4S_REPO, bundle_mac, private["base"], PRIVATE_REF))
    mac_stream("cat '%s'" % bundle_mac, local)
    remote = mac_text("shasum -a 256 '%s'" % bundle_mac).split()[0]
    if sha(local) != remote:
        fail("bundle SHA")
    restore = BUNDLES / ("restore-" + nonce())
    subprocess.run(["git", "clone", "-q", "--bare", "--shared", "--no-checkout", str(REPO), str(restore)], check=True)
    subprocess.run(["git", "-C", str(restore), "fetch", "-q", str(local), PRIVATE_REF + ":" + PRIVATE_REF], check=True)
    restored = subprocess.run(["git", "-C", str(restore), "rev-parse", PRIVATE_REF], stdout=subprocess.PIPE, text=True, check=True).stdout.strip()
    if restored != private["commit"]:
        fail("restored ref differs")
    out = subprocess.run(["git", "-C", str(restore), "ls-tree", "-r", restored, "--", private["repo_path"]],
                         stdout=subprocess.PIPE, text=True, check=True).stdout.splitlines()
    have = {line.split("\t", 1)[1][len(private["repo_path"]) + 1:]: line.split()[2] for line in out}
    subprocess.run(["git", "-C", str(restore), "cat-file", "-e", restored + "^{tree}"], check=True)
    if have != git_blob_ids(PRIV):
        fail("restored inventory differs")
    write_new(OUT / "bundle.json", dict(path_05=str(local), path_mac=bundle_mac, sha256=sha(local), bytes=local.stat().st_size,
                                        range=private["base"] + ".." + PRIVATE_REF, restored_commit=restored, restore_repo=str(restore)))
    log("bundle OK (restored and inventory-verified)")


def step_binding():
    private, bundle = read("private.json"), read("bundle.json")
    target = D / "private-commit-binding.json"
    if target.exists():
        fail("binding exists")
    files = regular_inventory(PRIV)
    write_new(target, dict(schema="clasher.mac-e4-session.private-commit-binding.v1",
        repository="Mac:" + K4S_REPO + " (single remote; pushurl invalid; pre-push hook refuses)",
        private_ref=PRIVATE_REF, private_branch=BRANCH, base_commit=private["base"], private_commit=private["commit"],
        private_tree=private["tree"], repo_path=private["repo_path"], never_push=True,
        content="sealed TIERS Mac session receipts (timing/capacity/health; no game outcomes)",
        files={n: dict(sha256=sha(files[n]), bytes=files[n].stat().st_size) for n in sorted(files)},
        bundle={k: bundle[k] for k in ("path_05", "path_mac", "sha256", "bytes", "range")}))
    log("binding OK")


def step_apps():
    read("check.json")  # only after the session has ended (post receipt present)
    running = mac_text("ps -Ao command | awk '/measure_tiers[.]py|session_wrapper[.]py/ && !/awk/ {n++} END {print n+0}'")
    if running != "0":
        fail("session processes still running; refusing to relaunch apps")
    result = mac_text("open -a 'Google Chrome' 2>&1; echo open_rc=$?; sleep 8; pgrep -x 'Google Chrome' > /dev/null && echo CHROME_RUNNING || echo CHROME_NOT_RUNNING")
    write_new(OUT / "apps.json", dict(utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), relaunch_output=result,
                                      chrome_running=result.endswith("CHROME_RUNNING"),
                                      claude="never quit (other user's process)", chatgpt="never quit"))
    log("apps recorded: " + result.replace("\n", " | "))


STEPS = dict(check=step_check, fetch=step_fetch, public=step_public, private=step_private, bundle=step_bundle,
             binding=step_binding, apps=step_apps)

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = open(OUT / ".collect.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for step in sys.argv[1:]:
        if step not in STEPS:
            fail("unknown step " + step)
        log("step %s begin" % step)
        STEPS[step]()
        log("step %s end" % step)
