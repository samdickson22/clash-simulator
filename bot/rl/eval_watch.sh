#!/usr/bin/env bash
# Evaluate every RL snapshot the deployed way (exploration), on an eval host, as the learner publishes them.
#   bot/rl/eval_watch.sh SRC_HOST SRC_RUN DST WORKERS [EVERY=120]
# Every EVERY s: pull SRC_HOST:SRC_RUN/{snapshots,evalq}/ into DST (also the off-host checkpoint copy, plus the
# learner state hourly). Each new evalq entry "<snapshot path> [games]" runs bot.eval.headline (our engine, HEADLINE
# cases 0..games-1, default 300) as 'student:<snapshot>@0.5375' vs v1, R3a and it5s2 under a cpu_job.sh lease, then
# writes DST/eval-<name>/report.txt (paired vs it5s2's own games in REF) and pushes eval-<name>/ back to SRC_RUN/evals/.
# SRC_HOST 'local' = the learner runs on this host (no ssh; a host cannot ssh to itself on the fleet).
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -uo pipefail
src_host=${1:?}; src_run=${2:?}; dst=${3:?}; w=${4:?}; every=${5:-120}
R() { if [[ $src_host == local ]]; then echo "$1"; else echo "$src_host:$1"; fi; }
repo=/mpac/sdicks02/repos/clasher-bot
ref=${BOT_RL_REF:-/mpac/sdicks02/jobs/clasher/bot-exit-r1/ce-it5s2/eval:it5s2}
it5s2=/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt
mkdir -p "$dst/snapshots" "$dst/evalq" "$dst/state"; touch "$dst/evalq-done"
cd "$repo"
last_state=0
while [[ ! -e "$dst/STOP" ]]; do
    rsync -a "$(R "$src_run/snapshots/")" "$dst/snapshots/" && rsync -a "$(R "$src_run/evalq/")" "$dst/evalq/" \
        || echo "$(date -u +%FT%TZ) pull failed"
    if (( $(date +%s) - last_state > 3600 )); then
        rsync -a "$(R "$src_run/learner-state.pt")" "$(R "$src_run/train.jsonl")" "$dst/state/" \
            && last_state=$(date +%s) && echo "$(date -u +%FT%TZ) learner state mirrored"
    fi
    for q in $(ls "$dst/evalq" | sort); do
        grep -qx "$q" "$dst/evalq-done" && continue
        read -r path games < "$dst/evalq/$q"; games=${games:-300}
        snap="$dst/snapshots/$(basename "$path")"
        [[ -s "$snap" ]] || snap="$dst/snapshots/$q.pt"
        [[ -s "$snap" ]] || { echo "$(date -u +%FT%TZ) $q: snapshot not mirrored yet"; continue; }
        out="$dst/eval-$q"
        echo "$(date -u +%FT%TZ) eval $q ($games cases, $w workers)"
        bot/exit/cpu_room.sh "$w" 105   # lead rule 21:55Z: gate every multi-process launch at 105 live python procs
        bot/exit/cpu_job.sh "$w" bot/exit/run.sh -m bot.eval.headline --out "$out" --candidate "student:$snap@0.5375" \
            --opponents "v1,R3a,student:$it5s2@0.5375" --games "$games" --workers "$w"
        .venv/bin/python -B -m bot.exit.report --ref "$ref" "$out:$q" --opps v1,R3a,it5s2 > "$out/report.txt" 2>&1
        .venv/bin/python -B -m bot.eval.summarize "$out" > "$out/summary.txt" 2>&1
        cat "$out/report.txt"
        if [[ $src_host == local ]]; then mkdir -p "$src_run/evals"; else ssh "$src_host" "mkdir -p '$src_run/evals'"; fi && rsync -a "$out" "$(R "$src_run/evals/")"
        echo "$q" >> "$dst/evalq-done"
    done
    sleep "$every"
done
