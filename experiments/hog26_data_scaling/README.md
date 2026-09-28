# Scalar training-data scaling

This experiment adds exactly1,152 fresh training games to the original384-game
birth-corrected pilot. It retains the original32training decks, six styles and
both learner seats, with three new paired scenarios per deck/style. Original
pilot and fresh-seed diagnostic outputs remain unchanged. Diagnostic and
reserved-role labels cannot enter the combined training data.

The protocol checks all new relative-deal clusters against both earlier corpora,
fixes campaign seeds1279701/2/3, and preserves every reserved role and acceptance
requirement. The collector publishes only complete games, retains every learner
decision, checks source/RNG/opening authority and resumes only matching outputs.
The excluded12-game preflight always declares one episode per style/seat.

The combined loader independently audits both corpora and validates exact
384+1152game counts,192+576paired scenarios and48+144games per family. Four
family exclusions yield1152fitting and384excluded games per fold. A partial new
corpus is refused before original arrays are opened.

Storage compaction occurs only after each full game audit. It removes trailing
entity slots only when always masked and zero in every entity field. Variable
width batches reconstruct the original model tensors exactly. All384original
games matched in192paired batches. Neither visible entities nor timesteps are
removed. The original compact audit peaks at1.41GB RSS; measured full1536-game
loader/model/tree memory remains a separate prerequisite before fitting.

Run with OMP_NUM_THREADS=1 and
PYTHONPATH=experiments/hog26_data_scaling:experiments/hog26_scalar_pilot:src:.
Collection uses collect_scaling.py and the separately frozen scaling plan/pin.
No collector completion authorizes fitting. Preserve original model definitions,
fixed epochs, seeds and family folds when implementing the later fitting stage.
Do not add or change Python in this directory while collection is source-frozen;
prepare new fitting code in a separate experiment directory with its own pin.
