# Install steps: soft cycle model on the RESUME stage (loop owner, Mac window, driver STOPPED)

Primary variant: **wint** (base `fullpool-r1-wint`, live-diag 7322efaa). Fallback: **plain** (base `fullpool-r1`,
e855d300). Use the variant whose base is running. Do this after the boundary file at RESUME battle 5, with the driver
stopped, never between battles.

**Before pasting** (loop owner's notes, 2026-10-17):
- `PRESTOP_SHA` is set to the LEAD-cleared checker, f43d5863… (Sol r4 OK-to-run; it replaces 95d8336a, which had a
  fail-open path). It is enforced before the run. One foreground run, no signals; any failure means stay on the current
  stage.
- Run `unset FP_TEST_STALL FP_TEST_NOWATCH` in the shell first, because the wrapper doesn't clear these test hooks.
- Gate on the checker's JSON (`$B/tmp/cyc-prestop.json`: fresh file, ok=true, exact file and player sets, code path) as
  well as its rc, as for RESUME.

Paste the block into a fresh zsh. It runs in a subshell with err_exit/nounset. Every failed check prints `STOP: …` and
aborts, and nothing after a failure runs. The new launcher stays NON-executable until the pre-start check exits 0.
After a STOP:
- the base dir, base launcher and base manifest are untouched, so start the next session with the base launcher;
- delete the partial `$B/loop/code/$NEW` and `$B/loop/$L` before any retry (step 2 refuses an existing NEW).

```zsh
(
setopt err_exit nounset pipe_fail
die() { print -u2 "STOP: $*"; exit 1 }
# 0. variables. wint shown; for plain: V=plain BASE=fullpool-r1 NEW=fullpool-r1-cyc L=run-fullpool-cyc.sh
#    M=MANIFEST-fullpool-cyc.json NAME=LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res
B=/Users/sam/clasher-live; PKG=$B/stage/pkg-cyc-resume; V=wint
BASE=fullpool-r1-wint; NEW=fullpool-r1-wint-cyc; L=run-fullpool-wint-cyc.sh; M=MANIFEST-fullpool-wint-cyc.json
NAME=LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint
WRAP_SHA=8e2489a0e50a0737598c144c2a94cc273d38251c8145d6a18ff70939a8edbff3      # live-diag run-fpbench-mac.sh
PRESTOP_SHA=f43d58639094f08d849ddfa730e2e7f71c74a8fad8d4b39045ee3ebdb7074d5b      # the LEAD-cleared fp_prestop_check.py (f43d5863, Sol r4 OK-to-run)
sha() { shasum -a 256 "$1" | cut -d' ' -f1 }

# 1. integrity: package files, env wrapper and pre-start checker
hex64() { [[ ${#1} -eq 64 && $1 != *[^0-9a-f]* ]] }
hex64 $PRESTOP_SHA || die "PRESTOP_SHA not set"
( cd $PKG/$V && shasum -a 256 -c --quiet SHA256SUMS ) || die "package integrity ($V)"
[[ $(sha $B/livediag-bench/run-fpbench-mac.sh) == $WRAP_SHA ]] || die "run-fpbench-mac.sh sha"
[[ $(sha $B/livediag-bench/fp_prestop_check.py) == $PRESTOP_SHA ]] || die "fp_prestop_check.py sha"

# 2. new code dir from the running base (base never modified); refuse existing paths, including symlinks
[[ -d $B/loop/code/$BASE && ! -L $B/loop/code/$BASE ]] || die "base dir $BASE missing"
[[ -z $(find $B/loop/code/$BASE -type l -print -quit) ]] || die "symlink inside $BASE (cp -a would let writes reach the base)"
[[ ! -e $B/loop/code/$NEW && ! -L $B/loop/code/$NEW ]] || die "$NEW exists"
[[ ! -e $B/loop/$L && ! -L $B/loop/$L ]] || die "$L exists"
[[ ! -e $B/loop/$M && ! -L $B/loop/$M ]] || die "$M exists"
cp -a $B/loop/code/$BASE $B/loop/code/$NEW || die "copy base"

# 3. copy by FILES in order (code files, manifest, launcher last); verify every destination sha. The packaged launcher has
#    mode 0644, so the installed copy is never executable before step 5.
grep -v '^#' $PKG/$V/FILES | while read -r src dest want; do
  [[ -n $src && -n $dest ]] && hex64 $want || die "bad FILES row: $src"
  mkdir -p "$(dirname "$B/$dest")" || die "mkdir $dest"
  [[ ! -L "$B/$dest" ]] || die "destination is a symlink: $dest"
  cp "$PKG/$V/$src" "$B/$dest" || die "copy $src"
  chmod a-x "$B/$dest" || die "chmod -x $dest"     # whatever mode the transfer gave the package files
  [[ $(sha "$B/$dest") == $want ]] || die "sha $dest"
done
chmod a-x $B/loop/$L || die "chmod -x launcher"
[[ -f $B/loop/$M && -f $B/loop/$L ]] || die "manifest/launcher not installed"

# 4. pre-start check (live-diag's env wrapper + checker, unchanged; the LEAD's clearance needed for this run).
#    LL_CODE points --code at NEW; MANIFEST-LINES covers every manifest entry + the installed manifest and launcher.
LL_CODE=$NEW $B/livediag-bench/run-fpbench-mac.sh prestop --lines $PKG/$V/MANIFEST-LINES.sha256 \
  --players $NAME --out $B/tmp/cyc-prestop.json || die "pre-start check failed (rc=$?)"

# 5. only now enable the new launcher
chmod a+x $B/loop/$L && print "INSTALL-OK $V $NEW"
)
```

6. **Start** the next session with `$B/loop/<L> <out name> <drive.py args as for the base launcher>`.

7. **Battle-1 confirmation (babysitter).** The session must show all of:
   - events.jsonl `manifest_ok` with the sha256 of `$B/loop/<M>`;
   - stderr `cycle-model: mode=soft preal=$B/loop/code/<NEW>/reports/bot/cycle-model/preal-v1.json sha256=f9096e22…`;
   - session.json tr_stats key `cycle_model:soft:preal_sha256:f9096e223b61d285` (and `cycle_conflict_soft:1` counts).

   If the P(real) file is missing or bad, the session refuses to start (the translator constructor raises before any
   tap).

8. **Rollback at any time:** the next session with the base launcher (run-fullpool-wint.sh / run-fullpool.sh). Base dir
   and manifest are untouched.
