#!/usr/bin/env bash
# Full-pool per-tick RL warm-up (plan step 2, policy side): PPO fine-tune of the extended rl5 v10 student vs a league
# with strong search opponents, on full-pool decks. One host runs both roles (rollouts stay local):
#   ROOT=<root> PINS=<pins> RUN=$J/rl/<name> bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh 22 bot/fullpool/run/rl_fp.sh actor BLOCK
#   ROOT=<root> PINS=<pins> RUN=$J/rl/<name> bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh 4  bot/fullpool/run/rl_fp.sh learner
# RL bank 3368089670243744 = int.from_bytes(os.urandom(6),'big')<<4, drawn on 127x08 2026-10-16T23:27Z (checked against
# HEADLINE, TRAIN1 and every bot/fullpool eval bank by actor.check_bank). Learner and actors must share the league.
set -euo pipefail
ROLE=${1:?actor|learner}; shift
if [[ "$ROLE" = learner ]]; then : "${PY:=/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python}"; fi
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
: "${RUN:?RUN dir}" "${INIT:=$EXT/rl5-v10-fp.pt}" "${W:=20}"
export BOT_RL_BANK=${BOT_RL_BANK:-3368089670243744} BOT_RL_DECKS=${BOT_RL_DECKS:-$DECKS} BOT_RL_OPP_C56=0 BOT_RL_SELF0=$INIT \
  BOT_RL_LEAGUE_NAMES=${LEAGUE_NAMES:-v1:.15,R3a:.15,self:.25,K4C-r16:.35,LIVE-K4CW-r16:.10} BOT_BELIEF_PRIOR=$DECKS
mkdir -p "$RUN"
echo "rl $ROLE start $(date -u +%FT%TZ) tree $(cat STAGED-REV 2>/dev/null) root $ROOT pins $PINS init $INIT decks $BOT_RL_DECKS league $BOT_RL_LEAGUE_NAMES"
if [[ "$ROLE" = actor ]]; then
  BLOCK=${1:?BLOCK}
  exec nice -n 15 "$PY" -B -m bot.rl.actor --run "$RUN" --workers "$W" --block "$BLOCK" ${MAX_GAMES:+--max-games $MAX_GAMES}
fi
export CUDA_VISIBLE_DEVICES=${GPU:-0} BOT_GPU_MAX_GB=${BOT_GPU_MAX_GB:-12}
r=(); [[ -e "$RUN/learner-state.pt" ]] && r=(--resume)
exec nice -n 15 "$PY" -B -m bot.rl.learner --run "$RUN" --init "$INIT" "${r[@]}" --games-per-update "${GPU_GAMES:-120}" \
  --max-games-per-update 240 --max-lag 2 --epochs 2 --microbatch 512 --snapshot-every 5 ${CRITIC_INIT:+--critic-init $CRITIC_INIT}
