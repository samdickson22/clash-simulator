#!/usr/bin/env bash
# HP1 RL (b): PPO from the human v2 init, KL-anchored to it, vs a league with strong search opponents, in a mixture of
# match environments at L16 (pre-registration reports/bot/hp1/RL-PREREG.md). One run dir per host, same path on each:
#   learner host: JOB=<job> bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh 5 $JOB/source/bot/rl/hp1_run.sh learner
#   actor block:  JOB=<job> bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh <W+2> $JOB/source/bot/rl/hp1_run.sh actor BLOCK W
#   other hosts:  plus bot/rl/remote_sync.sh <learner host> $JOB/run (policies in, rollouts out)
#   parity test:  JOB=<job> ... hp1_run.sh py -m bot.rl.test_rl --init <v2> --device cuda   (GPU python, same env)
# Smoke knobs: RUN (default $JOB/run), MAX_GAMES (per actor worker), GAMES / MAXGAMES / WARMUP / MAX_UPDATES (learner).
# Everything (source, models, run) lives under JOB; models are sha-checked against $JOB/models/SHA256SUMS first.
set -euo pipefail
ROLE=${1:?actor|learner}; shift
: "${JOB:?JOB dir}"
case "$(hostname -s)" in
  127x01) ROOT=/mpac/sdicks02/jobs/clasher/bot-fullpool/roots/live16402b-r3 ;;
  127x04|127x08) ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 ;;
  *) echo "hp1_run: host $(hostname -s) not allowed" >&2; exit 2 ;;
esac
PINS=live16402b-r3
NUMBA_CACHE_DIR=$JOB/numba-cache
M=$JOB/models
cd "$JOB/source"
(cd "$M" && sha256sum --quiet -c SHA256SUMS)
source bot/fullpool/run/env.sh
unset BOT_CYCLE_MODEL BOT_LEAF_VALUE CLASHER_LIVE_FAST
export PYTHONPATH="$JOB/source" BOT_FULLPOOL_POLICIES="v1=$M/main02-fp.pt,R3a=$M/R3a-fp.pt"
TAU=0.019753086419753086                       # v2 tau* (S0 calibration, reports/bot/hp1/S0-RESULTS.md)
FP=fullpool:11433651:freq=b53b02a1fde4         # FP-TRAIN sampler (= the search players' belief prior)
# OWN_DECK: Sam's live deck (a launch input; follow reports/live/loop/ACCOUNT-LOG.md deck changes by relaunching blocks)
: "${OWN_DECK:=HogRider+Archers+Cannon+Skeletons+Fireball+Zap+ElectroSpirit+Valkyrie}"
export BOT_RL_TAU0=${BOT_RL_TAU0:-$TAU} \
  BOT_RL_BANK=${BOT_RL_BANK:?BOT_RL_BANK (RL-PREREG.md)} \
  BOT_RL_SELF0=${INIT:=$M/v2-best-dev-step-00046459.pt} \
  BOT_RL_OPP_C56=0 BOT_BELIEF_PRIOR=$FP BOT_RL_DECKS=$FP \
  BOT_RL_ENVS=${ENVS:-"rsim16402;max;sam@.25|ours;max;sam@.148|rsim16402;max;meta@.181|ours;max;meta@.180|ours;max;rand@.241"} \
  BOT_RL_OWN_DECK=$OWN_DECK BOT_RL_CORPUS_DECKS=$M/corpus-decks-v1.jsonl \
  BOT_RL_OPP_MIX=${OPP_MIX:-"corpus@.4|$FP@.3|fullpool-uniform:11433651@.3"} \
  BOT_RL_RSIM_EXCLUDE=${RSIM_EXCLUDE:-Fisherman,GiantBuffer,GoblinCurse,GoblinDemolisher,GoblinDrill,GoblinGiant,GoblinHut,Graveyard,MegaKnight,MovingCannon,Phoenix,RamRider,SkeletonBalloon,SuspiciousBush,ThreeMusketeers,WitchMother,ElectroGiant,Tombstone,GoldenKnight} \
  BOT_RL_RSIM_VOCAB=$M/vocab-full.json \
  BOT_RL_LEAGUE_NAMES=${LEAGUE_NAMES:-LIVE-K4CW-r16-fp:.18,R3a:.15,f1a2:.17,rl5:.08,v1:.05,self:.2,SEARCH:.17} \
  BOT_RL_LEAGUE_SPECS="f1a2=student:$M/f1a2-step-001200.pt@0.5375|rl5=student:$M/rl5-v10-fp.pt@0.5375|SEARCH=livesearch:LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-RF-wint" \
  BOT_RL_K4CW_FAST="student:$M/f1a2-step-001200.pt" \
  BOT_RL_RSIM_NAMES=${RSIM_NAMES:-SEARCH} BOT_RL_RSIM_ENV='rsim16402;max;sam'
RUN=${RUN:-$JOB/run}
mkdir -p "$RUN"
echo "hp1 rl $ROLE start $(date -u +%FT%TZ) host $(hostname -s) source $(cat "$JOB/source-commit.txt" 2>/dev/null) root $ROOT init $INIT tau0 $BOT_RL_TAU0 bank $BOT_RL_BANK envs $BOT_RL_ENVS league $BOT_RL_LEAGUE_NAMES"
if [[ "$ROLE" = actor ]]; then
  BLOCK=${1:?BLOCK}; W=${2:?workers}
  exec nice -n 15 "$PY" -B -m bot.rl.actor --run "$RUN" --workers "$W" --block "$BLOCK" ${MAX_GAMES:+--max-games $MAX_GAMES}
fi
[[ "$ROLE" = learner || "$ROLE" = py ]] || { echo "role $ROLE" >&2; exit 2; }
export CUDA_VISIBLE_DEVICES=${GPU:-0} BOT_GPU_MAX_GB=${BOT_GPU_MAX_GB:-16}
GPY=/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python
if [[ "$ROLE" = py ]]; then exec nice -n 15 "$GPY" -B "$@"; fi
r=(); [[ -e "$RUN/learner-state.pt" ]] && r=(--resume)
exec nice -n 15 "$GPY" -B -m bot.rl.learner --run "$RUN" --init "$INIT" "${r[@]}" --games-per-update "${GAMES:-240}" \
  --max-games-per-update "${MAXGAMES:-480}" ${WARMUP:+--critic-warmup $WARMUP} --max-lag 2 --epochs 2 --microbatch 512 --lr 1e-5 --kl-coef 0.05 --kappa 0.1 --temp 0.1 \
  --snapshot-every 5 ${MAX_UPDATES:+--max-updates $MAX_UPDATES} ${EXTEND_LEAGUE:+--extend-league}
