# Frozen-model seed transfer

The completed 384-game scalar pilot showed positive overall tree margin gains,
inconsistent globals probability gains, and worse entity/history generalization
in both seeds. This experiment evaluates those same models on fresh complete
games before another fitting run or larger collection campaign.

The fixed diagnostic has 384 games, 192 paired scenarios, the same 32 training
decks and six opponent styles, and fresh campaign seeds1279601/2/3. Every new
relative-deal cluster must differ from the original pilot. These are diagnostic
labels, never untouched acceptance data. Reserved roles are not collected.

For each original fit, evaluate fresh games from its 288-game fitting-family
set separately from fresh games from its 96-game excluded-family set. All model
seeds and folds are retained. Original fitting-game priors and model parameters
are frozen. No training, calibration fitting, winner selection or promotion.

The collector and data auditor are exact copies of the previous verified
versions except their protocol import and collector root path. A regression
test checks that narrow difference. The new authority also hashes these files,
the evaluator, the original model implementation and all model checkpoints.
Do not edit any of those files during collection or evaluation.

Run with OMP_NUM_THREADS=1 and
PYTHONPATH=experiments/hog26_seed_transfer:experiments/hog26_scalar_pilot:src:.
Use collect_transfer.py with the same CLI as the original collector, but the new
transfer plan/pin. evaluate_transfer.py takes --data, --plan, --preflight and
--output. Both reject inappropriate existing outputs; evaluation refuses a
partial corpus and performs the full independent audit before prediction.

The fixed early/middle/late and representative definitions remain unchanged.
Zero natural draws and sparse late coverage stay inconclusive. A fresh-seed
improvement cannot substitute for unseen-family or final acceptance evidence.
