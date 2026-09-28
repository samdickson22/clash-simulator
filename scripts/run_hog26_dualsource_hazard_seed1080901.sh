#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

experiment_seed=${EXPERIMENT_SEED:-1080901}
start_update=${START_UPDATE:-1}
end_update=${END_UPDATE:-10}
control=checkpoints/hog26_dualsource_hazard_seed${experiment_seed}/control.pt
checkpoint_root=checkpoints/hog26_dualsource_hazard_seed${experiment_seed}/train
report_root=reports/hog26_dualsource_hazard_seed${experiment_seed}
human_corpus=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/corpus.npz
human_sidecar=datasets/derived/tv_royale_youtube_causal_imitation_seed1067007/public_v2.npz
spatial_corpus=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/corpus.npz
spatial_sidecar=datasets/derived/hog26_medium_reactive_dagger_mix2_seed1078601/public_v2.npz
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
endpoint="$checkpoint_root/policy_v2_update_$(printf '%06d' "$end_update").pt"

for required in "$control" "$human_corpus" "$human_sidecar" "$spatial_corpus" "$spatial_sidecar" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing dual-source hazard input: $required"; exit 1; }
done
[[ ! -e "$endpoint" ]] || { print -u2 -- "refusing existing dual-source hazard endpoint"; exit 1; }
mkdir -p "$checkpoint_root" "$report_root"
if (( start_update == 1 )); then
  : > "$report_root/train.log"
fi

resume=${RESUME_FROM:-$control}
stability_parent=$resume
for target in $(seq "$start_update" "$end_update"); do
  if (( target % 2 == 1 )); then
    phase=human-hazard
    corpus=$human_corpus
    sidecar=$human_sidecar
    rehearsal_coef=0.125
    decision_coef=1.0
    card_coef=0.0
    tile_coef=0.0
    rehearsal_batch=8
  else
    phase=strategy-spatial
    corpus=$spatial_corpus
    sidecar=$spatial_sidecar
    rehearsal_coef=1.0
    decision_coef=0.0
    card_coef=1.0
    tile_coef=0.25
    rehearsal_batch=16
  fi
  print -r -- "dual_source_phase=$phase target_update=$target resume=$resume" >> "$report_root/train.log"
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python run_clasher.py train -- \
    --decks-path decks.json --sampling-decks-path "$opponent_decks" \
    --learner-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --checkpoint-dir "$checkpoint_root" --resume-from "$resume" \
    --seed $((experiment_seed + target)) --updates "$target" \
    --num-envs 64 --actor-workers 12 --actor-threads 1 \
    --rollout-steps 64 --decision-interval 8 --max-ticks 6000 \
    --reward-profile objective-v1 --elixir-leak-penalty-scale 1 \
    --opponent-mode league --engine-fast-path on --device mps --actor-device cpu \
    --league-opponent random --league-opponent "$control" \
    --pfsp-report reports/hog26_card_rehearsal_repair_gate_seed1070901/u46_full/strategy.json \
    --pfsp-strategy-workers 10 --learning-rate 0.0001 \
    --gamma 0.995 --gae-lambda 0.95 --clip-ratio 0.2 --value-coef 0.5 \
    --entropy-coef 0.01 --action-type-entropy-coef 0.01 \
    --location-entropy-coef 0.01 --conditional-slot-entropy-coef 0.01 \
    --hand-aux-coef 0 --elixir-aux-coef 0 --epochs 1 --sequence-batch-size 4 \
    --target-kl 0.05 --save-every 1 --log-every 1 --no-lr-anneal \
    --causal-rehearsal-corpus "$corpus" --causal-rehearsal-public-sidecar "$sidecar" \
    --causal-rehearsal-sequence-length 64 --causal-rehearsal-coef "$rehearsal_coef" \
    --causal-rehearsal-decision-coef "$decision_coef" \
    --causal-rehearsal-card-coef "$card_coef" \
    --causal-rehearsal-tile-coef "$tile_coef" \
    --causal-rehearsal-batch-sequences "$rehearsal_batch" --quiet-engine \
    >> "$report_root/train.log" 2>&1
  resume="$checkpoint_root/policy_v2_update_$(printf '%06d' "$target").pt"
done

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$stability_parent" --checkpoint-dir "$checkpoint_root" \
  --start-update "$start_update" --end-update "$end_update" --max-approx-kl 0.05 \
  --max-anchor-policy-kl 0.05 --max-clip-fraction 0.30 \
  --output "$report_root/training_stability_u${start_update}_u${end_update}.json"
print -r -- "hog26_dualsource_hazard_seed${experiment_seed}_update${end_update}_complete_v1" > "$report_root/COMPLETE"
