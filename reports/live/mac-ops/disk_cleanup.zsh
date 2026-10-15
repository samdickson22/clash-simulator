#!/bin/zsh
# LIVE track: one-shot regenerable-disk cleanup on the Mac mini (coordinator-approved list, 2026-10-15; Sol r1 fixes).
# Run from 127x05:   ssh macmini-fleet 'zsh -f -s' < reports/live/mac-ops/disk_cleanup.zsh
# Dry run:           ssh macmini-fleet 'DRY=1 zsh -f -s' < reports/live/mac-ops/disk_cleanup.zsh   (no tool runs, no rm)
# Exactly ONE final line '__RC=<n>' (EXIT trap); n != 0 if any check/step failed (ssh macmini-fleet always exits 0).
# Scope (exact allowlist; nothing else is touched):
#   B  /Users/sam/.local/android-sdk                      (ours, unused; only if no process/AVD/profile references it)
#   A  npm cache clean --force                            (npm's configured cache, must be under HOME)
#      pnpm store prune                                   (unreferenced packages only; node_modules keep their links)
#      /Users/sam/Library/Caches/Google                   (skipped if Google Chrome is running)
#      /Users/sam/Library/Caches/Homebrew/downloads       (download cache only; NOT 'brew cleanup', which removes kegs)
#      /Users/sam/Library/Caches/{colima,t3code-updater,electron,node-gyp}
# Excluded by ruling: Codex caches, ~/.cargo/registry, sealed/agent/VM/other-project/other-user data, OS snapshots.
emulate -L zsh
setopt nounset pipefail no_nomatch no_err_exit no_glob_subst
fail=0
trap 'print -r -- "__RC=$fail"' EXIT
say() { print -r -- "[$(date -u +%H:%M:%SZ)] $*"; }
bad() { say "FAIL: $*"; fail=1; }
DRY=${DRY:-0}
EXPECT_HOME=/Users/sam
if [[ "${HOME:-}" != "$EXPECT_HOME" || "$(id -un)" != sam ]]; then bad "HOME/user unexpected (${HOME:-unset}, $(id -un))"; exit 1; fi

freek() { local v; v=$(df -k /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $4}'); [[ $v == <-> ]] || { bad "df failed"; v=0; }; print -r -- $v; }
sizek() { local v; v=$(du -sk -- "$1" 2>/dev/null | cut -f1); print -r -- "${v:-?}"; }

# no symlink in the path or any ancestor below /Users/sam
no_symlinks() {
  local p=$1 cur=$EXPECT_HOME rest=${1#$EXPECT_HOME/} part
  [[ "$p" == $EXPECT_HOME/* ]] || return 1
  for part in ${(s:/:)rest}; do cur=$cur/$part; [[ -L "$cur" ]] && return 1; done
  return 0
}

typeset -a ALLOW
ALLOW=(
  $EXPECT_HOME/.local/android-sdk
  $EXPECT_HOME/Library/Caches/Google
  $EXPECT_HOME/Library/Caches/Homebrew/downloads
  $EXPECT_HOME/Library/Caches/colima
  $EXPECT_HOME/Library/Caches/t3code-updater
  $EXPECT_HOME/Library/Caches/electron
  $EXPECT_HOME/Library/Caches/node-gyp
)
rm_dir() {
  local p=$1
  (( ${ALLOW[(Ie)$p]} )) || { bad "not in allowlist: $p"; return 0; }
  if [[ ! -e "$p" && ! -L "$p" ]]; then say "skip (absent): $p"; return 0; fi
  no_symlinks "$p" || { bad "symlink in path: $p"; return 0; }
  [[ -d "$p" ]] || { bad "not a directory: $p"; return 0; }
  say "rm  $p  ($(sizek "$p") KiB)"
  [[ $DRY == 1 ]] && return 0
  rm -rf -- "$p" || { bad "rm $p"; return 0; }
  [[ -e "$p" ]] && bad "still exists: $p"
  return 0
}

F0=$(freek); say "free before: $((F0/1048576)) GiB ($F0 KiB)  DRY=$DRY"

# ---- B: ~/.local/android-sdk ----
SDK=$EXPECT_HOME/.local/android-sdk
if [[ -e "$SDK" ]]; then
  ok=1
  # (1) no process (any user) has the SDK path in its command line; ps output captured first => no self-match
  psout=$(ps -axww -o pid=,command= 2>/dev/null); st=$?
  if (( st != 0 )) || [[ -z "$psout" ]]; then bad "ps failed ($st)"; ok=0
  else
    hits=$(print -r -- "$psout" | grep -c -F -- "$SDK")
    say "processes whose command line references the SDK: $hits"; (( hits == 0 )) || ok=0
  fi
  # (2) no open files under it by our processes (other users cannot read 0750 ~/.local subtrees' opens via lsof; their
  #     command lines are covered by (1)). lsof: 0 = matches, 1 = none (also returned on some errors) -> require empty stderr.
  lerr=$(mktemp -t lsoferr); lout=$(lsof -n +D "$SDK" 2>"$lerr"); lst=$?
  if (( lst == 0 )); then say "open files under SDK:"; print -r -- "$lout" | head -5; ok=0
  elif (( lst == 1 )) && [[ ! -s "$lerr" || -z "$(grep -v -E '^lsof: WARNING' "$lerr")" ]]; then say "open files under SDK: 0"
  else bad "lsof error ($lst): $(head -c 300 "$lerr")"; ok=0; fi
  rm -f -- "$lerr"
  # (3) no AVD / shell-profile reference (fixed-string), in all AVD homes we know of on this Mac
  typeset -a CFG
  CFG=( $EXPECT_HOME/.android/avd/*.ini(N) $EXPECT_HOME/.android/avd/*/*.ini(N)
        $EXPECT_HOME/.cache/clasher-native-reference/avd/*.ini(N) $EXPECT_HOME/.cache/clasher-native-reference/avd/*/*.ini(N)
        $EXPECT_HOME/.cache/clasher-official/avd/*.ini(N) $EXPECT_HOME/.cache/clasher-official/avd/*/*.ini(N)
        $EXPECT_HOME/.zshrc(N) $EXPECT_HOME/.zprofile(N) $EXPECT_HOME/.zshenv(N) $EXPECT_HOME/.bash_profile(N) $EXPECT_HOME/.bashrc(N) $EXPECT_HOME/.profile(N) )
  refs=0
  for f in $CFG; do
    if [[ ! -r "$f" ]]; then bad "unreadable config $f"; ok=0; continue; fi
    grep -q -F -- ".local/android-sdk" "$f"; g=$?
    if (( g == 0 )); then say "referenced in $f"; refs=$((refs+1)); elif (( g != 1 )); then bad "grep error $f"; ok=0; fi
  done
  say "config files checked: ${#CFG}; references: $refs"; (( refs == 0 )) || ok=0
  if (( ok )); then rm_dir "$SDK"; else say "REFUSE android-sdk (in use, referenced, or checks incomplete)"; fail=1; fi
else
  say "skip (absent): $SDK"
fi

# ---- A1: npm cache (configured location must be under HOME) ----
NPM=$(command -v npm 2>/dev/null); [[ -z "$NPM" ]] && NPM=$(print -r -- $EXPECT_HOME/.nvm/versions/node/*/bin/npm(N[-1]))
if [[ -n "$NPM" && -x "$NPM" ]]; then
  NC=$(PATH="${NPM:h}:$PATH" "$NPM" config get cache 2>/dev/null)
  if [[ "$NC" == $EXPECT_HOME/* ]]; then
    say "npm cache clean --force ($NC, $(sizek "$NC") KiB)"
    if [[ $DRY != 1 ]]; then PATH="${NPM:h}:$PATH" "$NPM" cache clean --force >/dev/null 2>&1 || bad "npm cache clean"; fi
    say "npm cache after: $(sizek "$NC") KiB"
  else bad "npm cache path unexpected: '$NC'"; fi
else bad "npm not found"; fi

# ---- A2: pnpm store prune ----
PNPM=$(command -v pnpm 2>/dev/null); [[ -z "$PNPM" && -x $EXPECT_HOME/Library/pnpm/pnpm ]] && PNPM=$EXPECT_HOME/Library/pnpm/pnpm
if [[ -n "$PNPM" && -x "$PNPM" ]]; then
  PS=$(PATH="${PNPM:h}:$PATH" "$PNPM" store path 2>/dev/null)
  if [[ "$PS" == $EXPECT_HOME/* ]]; then
    say "pnpm store prune ($PS)"
    if [[ $DRY != 1 ]]; then PATH="${PNPM:h}:$PATH" "$PNPM" store prune >/dev/null 2>&1 || bad "pnpm store prune"; fi
  else bad "pnpm store path unexpected: '$PS'"; fi
else bad "pnpm not found"; fi

# ---- A3: Chrome cache, only if Chrome is not running ----
pgrep -x "Google Chrome" >/dev/null 2>&1; pg=$?
case $pg in
  0) say "skip $EXPECT_HOME/Library/Caches/Google (Google Chrome is running)" ;;
  1) rm_dir $EXPECT_HOME/Library/Caches/Google ;;
  *) bad "pgrep error ($pg); Chrome cache not touched" ;;
esac

# ---- A4: Homebrew download cache only ----
rm_dir $EXPECT_HOME/Library/Caches/Homebrew/downloads

# ---- A5: four named cache dirs ----
for d in colima t3code-updater electron node-gyp; do rm_dir $EXPECT_HOME/Library/Caches/$d; done

F1=$(freek); say "free after: $((F1/1048576)) GiB ($F1 KiB); freed $(((F1-F0)/1048576)) GiB"
exit 0
