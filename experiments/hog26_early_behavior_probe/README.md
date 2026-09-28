This training-only information probe asks whether recent public entity history makes bridge-pressure behavior more identifiable at the existing early representative positions. It follows the training error localization: early bridge-pressure margin failures occur in ordinary early play and often within fitting families, while late gains mainly improve earlier late positions.

Every one of the 6,144 complete training games contributes its unchanged early representative. The simulated opponent style is used only as a binary auxiliary target. Actual win/loss and terminal margin are not targets, and no opponent-policy label enters a feature. This sample does not establish behavior recognition throughout the entire early phase.

Two public representations are compared: the existing 814 features, which already include global-resource history, and those same features plus 97 entity-history features. Both use the same fixed histogram classifier, two seeds and four whole-family folds, for 16 fits. There is no class balancing, hyperparameter sweep or outcome-model update.

Run `supervise.py --mode pin`, then `--mode memory`, `--mode fit` and `--mode review`. The full-shape memory check uses synthetic labels and saves no checkpoint. Fitting requires that proof and its guard receipt. The exact review reproduces every checkpoint and point metric, then computes paired whole-scenario intervals for the two representations on identical held-family examples.

Auxiliary probability predictions are not supplied to an outcome model. The result can inform a training-only representation hypothesis; it cannot establish outcome calibration, permit reserved collection, or authorize search or policy updates.
