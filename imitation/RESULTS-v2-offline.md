# T11 v2 offline gate (a)

Primary entrant: **main-2026100822**, selected only by dev joint NLL. V2 eval gate: **FAIL**.

OOD gates are diagnostic. The secondary seed cannot replace the primary based on these results.

PREREG SHA256: `115ab2f62c999d96b908855ab6e45bade4d9573308a222659821f65a76e42749`. Executable manifest: `a4801df32d4a546ed7df07faf070a138d4075cf4db6c193d38373f9194ff2e44`.
V1 published report: `/mpac/sdicks02/repos/clasher-lease/t11-gate-inputs/RESULTS-v1-offline.md`, SHA256 `9f3800f88b6ed6255c81a52a67f328cdd729a0d356a8058216571972a489b751`.
Selection SHA256: `2e302d646cb3c45813aca92ae09102cf4586ae46021c1f844f6432b512e6966c`. Held-out release SHA256: `f6b627c294183365ed7746b0d326ed8b60d9416aee7b464123e111e5fac865d6`.

## Training and selection

### main-2026100821

Selected step 46460; dev joint NLL 0.26627421. Checkpoint SHA256 `88c5862c333d1f17e9871526f405293a84cf97ecdf8f17cc705bb02e6c5db466`.
Completed epochs 6; bad epochs 0; steps 46460; rows 380571633.
Dev temperatures (gate/card/tile): 1.06471729, 1.07975829, 1.03016603.
Recorded trainer wall hours 20.5052805; CPU hours 64.2584406. Wall hours include loading, checkpointing and dev; they are not active GPU compute hours.
Final segment cumulative loader-inclusive rows/s: 6717.5148.

| Dev checkpoint step | EMA joint NLL |
|---:|---:|
| 7745 | 0.283173892 |
| 15487 | 0.273868705 |
| 23230 | 0.269930718 |
| 30973 | 0.267613169 |
| 38717 | 0.266502476 |
| 46460 | 0.26627421 |

### main-2026100822

Selected step 46459; dev joint NLL 0.265916911. Checkpoint SHA256 `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae`.
Completed epochs 6; bad epochs 0; steps 46459; rows 380566524.
Dev temperatures (gate/card/tile): 1.06896782, 1.08258939, 1.03752553.
Recorded trainer wall hours 12.9137021; CPU hours 61.4177003. Wall hours include loading, checkpointing and dev; they are not active GPU compute hours.
Final segment cumulative loader-inclusive rows/s: 7319.77045.

| Dev checkpoint step | EMA joint NLL |
|---:|---:|
| 7744 | 0.282373618 |
| 15487 | 0.273457297 |
| 23230 | 0.269472504 |
| 30973 | 0.267235732 |
| 38716 | 0.266186636 |
| 46459 | 0.265916911 |

## Separate cohort gates

| Seed | Split | Corpus | A1 | A2 | A3 | A4 | All applicable |
|---|---|---|---|---|---|---|---|
| main-2026100821 | eval | c56 | PASS | PASS | FAIL | PASS | FAIL |
| main-2026100821 | eval | s122 | PASS | N/A (empty slice) | PASS | PASS | PASS |
| main-2026100821 | eval_ood | c56 | PASS | N/A (empty slice) | FAIL | PASS | FAIL |
| main-2026100821 | eval_ood | s122 | PASS | N/A (empty slice) | FAIL | PASS | FAIL |
| main-2026100822 | eval | c56 | PASS | PASS | FAIL | PASS | FAIL |
| main-2026100822 | eval | s122 | PASS | N/A (empty slice) | PASS | PASS | PASS |
| main-2026100822 | eval_ood | c56 | PASS | N/A (empty slice) | FAIL | PASS | FAIL |
| main-2026100822 | eval_ood | s122 | PASS | N/A (empty slice) | FAIL | PASS | FAIL |

## main-2026100821: eval

Analysis artifact: `/mpac/sdicks02/repos/clasher-t11-home-v1/gate-a-v2/analysis-2026100821-eval.json`, SHA256 `b52035cead3736b48dcbf85497433222aff7103aabc1f8f0862c1aeec28f4c43`.
Statistics completion SHA256 `f45b8ad6cf3ed22786fd3361b6b84c0de81476f911d4f591f44200be75dca722`. This artifact includes pooled diagnostics, per-card/arena and Battle Healer/Mirror slices, and calibration bins.

### c56: 3644 perspectives, 2862378 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.16892235 | 0.168451637 | [0.167504314, 0.169377828] |
| play_wait_brier | 0.0437857285 | 0.0436922722 | [0.0434075726, 0.0439705763] |
| play_wait_nll_all | 0.162150308 | 0.161697954 | [0.160811053, 0.162578733] |
| play_wait_brier_all | 0.0420224518 | 0.0419327915 | [0.0416668659, 0.0421949129] |
| joint_nll | 0.338567287 | 0.338050634 | [0.335794861, 0.340258574] |
| card_nll | 0.895215809 | 0.893684387 | [0.888703399, 0.898558214] |
| card_top1 | 0.60766834 | 0.607675791 | [0.604610867, 0.610638552] |
| card_top3 | 0.963992119 | 0.963992119 | [0.962868137, 0.965128491] |
| tile_nll | 2.84405994 | 2.84427118 | [2.83150527, 2.85695824] |
| tile_within1 | 0.475941151 | 0.475971073 | [0.472798487, 0.479249228] |
| top8_recall | 0.537649691 | 0.537874103 | [0.534543819, 0.541327005] |
| top8_within1 | 0.663310707 | 0.663819373 | [0.660644621, 0.666981764] |
| ability_nll | 4.38959789 | 4.14172745 | [4.09085649, 4.19403613] |
| intent_hazard_nll | 1.73911774 | 1.73911774 | [1.73378308, 1.74417345] |
| intent_card_nll | 1.38090336 | 1.38090336 | [1.37561566, 1.38635241] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.100498807 | [-0.101304342, -0.0996919709] |
| play_wait_nll | -0.0214955076 | [-0.0218527884, -0.0211528819] |
| card_nll | -0.485696435 | [-0.491902521, -0.479698895] |
| tile_nll | -1.18839031 | [-1.19822758, -1.17875291] |

A2: {"card_nll": {"baseline": 1.0076806024184548, "delta": -0.12031253421317012, "model": 0.8873680682052847, "pass_": true}, "tile_nll": {"baseline": 3.5364494500604375, "delta": -0.6972962402504614, "model": 2.839153209809976, "pass_": true}}
A3 passing/assessed/scoped: 52/52/56.
A3 significantly worse cards: none.
A3 unassessed cards: 20, 38, 114, 328.
A4 calibrated gate ECE 0.00296897931; bar ≤0.01.

### s122: 12369 perspectives, 8553701 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.134001583 | 0.133451313 | [0.132920487, 0.133993559] |
| play_wait_brier | 0.0333683118 | 0.0332924426 | [0.033141521, 0.0334477455] |
| play_wait_nll_all | 0.123010293 | 0.122505598 | [0.121989195, 0.123033786] |
| play_wait_brier_all | 0.0306288674 | 0.0305592325 | [0.0304141276, 0.0307088039] |
| joint_nll | 0.250593781 | 0.250031114 | [0.248786091, 0.251333071] |
| card_nll | 0.892923594 | 0.891652524 | [0.888567461, 0.89478504] |
| card_top1 | 0.607928336 | 0.6079005 | [0.605938598, 0.609866311] |
| card_top3 | 0.964827955 | 0.964827955 | [0.964097252, 0.965557644] |
| tile_nll | 2.88784432 | 2.88737249 | [2.879024, 2.89566707] |
| tile_within1 | 0.466033161 | 0.466005325 | [0.463906155, 0.468111391] |
| top8_recall | 0.538895488 | 0.539239883 | [0.53696752, 0.541458127] |
| top8_within1 | 0.661395967 | 0.662175059 | [0.660087991, 0.664276346] |
| ability_nll | 4.57259464 | 4.3081255 | [4.25832529, 4.35774602] |
| intent_hazard_nll | 1.64866912 | 1.64866912 | [1.64550199, 1.65182721] |
| intent_card_nll | 1.40693915 | 1.40693915 | [1.40353043, 1.41030794] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.0813266474 | [-0.0817530765, -0.0808994388] |
| play_wait_nll | -0.0163426567 | [-0.0165226792, -0.0161633128] |
| card_nll | -0.592359986 | [-0.597026514, -0.587619811] |
| tile_nll | -1.36836172 | [-1.37507417, -1.36168484] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 121/121/121.
A3 significantly worse cards: none.
A3 unassessed cards: none.
A4 calibrated gate ECE 0.00109747294; bar ≤0.01.

## main-2026100821: eval_ood

Analysis artifact: `/mpac/sdicks02/repos/clasher-t11-home-v1/gate-a-v2/analysis-2026100821-eval_ood.json`, SHA256 `c669aff894b8d8592d20f2d442b89cc53a4fc2cfd22ec1f1e0ee2105bdf3abbe`.
Statistics completion SHA256 `cf2413bd531626bcb4f551df28a3dcbbfadaf12d05a46bbc373e387d77da4425`. This artifact includes pooled diagnostics, per-card/arena and Battle Healer/Mirror slices, and calibration bins.

### c56: 3643 perspectives, 2796216 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.163358182 | 0.162780598 | [0.16181458, 0.163746866] |
| play_wait_brier | 0.0417546779 | 0.0416704044 | [0.0413915717, 0.0419543999] |
| play_wait_nll_all | 0.156490505 | 0.155937269 | [0.15500972, 0.15686483] |
| play_wait_brier_all | 0.0399992503 | 0.0399185568 | [0.0396489193, 0.0401907563] |
| joint_nll | 0.324028254 | 0.323409766 | [0.321129846, 0.325681817] |
| card_nll | 0.890544832 | 0.888492584 | [0.883645622, 0.89333266] |
| card_top1 | 0.607255757 | 0.607295871 | [0.604242601, 0.610311343] |
| card_top3 | 0.967621028 | 0.967613041 | [0.966536043, 0.968680734] |
| tile_nll | 2.85925913 | 2.85985017 | [2.84770447, 2.87215443] |
| tile_within1 | 0.471914172 | 0.471898109 | [0.468430906, 0.475306897] |
| top8_recall | 0.53504312 | 0.53551656 | [0.532102553, 0.538874199] |
| top8_within1 | 0.661830544 | 0.662705243 | [0.659551006, 0.665865401] |
| ability_nll | 4.91096354 | 4.62743044 | [3.68234897, 4.80189347] |
| intent_hazard_nll | 1.75553656 | 1.75553656 | [1.74938865, 1.76157107] |
| intent_card_nll | 1.38567901 | 1.38567901 | [1.37940316, 1.39196319] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.09289141 | [-0.0936236795, -0.0921613787] |
| play_wait_nll | -0.0188905042 | [-0.0192768531, -0.018523363] |
| card_nll | -0.489440627 | [-0.496311692, -0.482591625] |
| tile_nll | -1.1845815 | [-1.19463621, -1.17421921] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 40/40/56.
A3 significantly worse cards: none.
A3 unassessed cards: 6, 10, 17, 20, 30, 38, 114, 115, 181, 232, 238, 258, 259, 277, 328, 356.
A4 calibrated gate ECE 0.00134683292; bar ≤0.01.

### s122: 11281 perspectives, 7642235 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.131009236 | 0.130728111 | [0.130196649, 0.131259763] |
| play_wait_brier | 0.0324983448 | 0.0324435085 | [0.0322914848, 0.0325949204] |
| play_wait_nll_all | 0.120959878 | 0.120700158 | [0.120194237, 0.121196121] |
| play_wait_brier_all | 0.0300030336 | 0.0299523771 | [0.0298081568, 0.0300954958] |
| joint_nll | 0.247200266 | 0.24686709 | [0.245650561, 0.248102443] |
| card_nll | 0.906984806 | 0.905157208 | [0.901836953, 0.908505721] |
| card_top1 | 0.601824164 | 0.601899624 | [0.599790099, 0.604000985] |
| card_top3 | 0.961903632 | 0.961907625 | [0.961089958, 0.96271131] |
| tile_nll | 2.91229224 | 2.91189933 | [2.90346216, 2.92036868] |
| tile_within1 | 0.459362149 | 0.459354192 | [0.45716686, 0.461573257] |
| top8_recall | 0.529915571 | 0.530138075 | [0.527885455, 0.532392498] |
| top8_within1 | 0.653241932 | 0.653921485 | [0.65171463, 0.656113916] |
| ability_nll | 4.72006607 | 4.44568968 | [4.38956489, 4.50408942] |
| intent_hazard_nll | 1.64297354 | 1.64297354 | [1.63969175, 1.64619292] |
| intent_card_nll | 1.44655967 | 1.44655967 | [1.44301723, 1.45017626] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.0787822983 | [-0.0792101285, -0.0783549266] |
| play_wait_nll | -0.0154472686 | [-0.0156358243, -0.0152625875] |
| card_nll | -0.574955076 | [-0.57989839, -0.570003672] |
| tile_nll | -1.37245832 | [-1.37951113, -1.36545668] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 111/111/121.
A3 significantly worse cards: none.
A3 unassessed cards: 25, 31, 66, 75, 84, 102, 153, 228, 239, 242.
A4 calibrated gate ECE 0.00217979234; bar ≤0.01.

| Corpus | Metric | OOD minus eval (descriptive) |
|---|---|---:|
| c56 | play_wait_nll | -0.00567103922 |
| c56 | play_wait_brier | -0.00202186778 |
| c56 | play_wait_nll_all | -0.00576068461 |
| c56 | play_wait_brier_all | -0.00201423466 |
| c56 | joint_nll | -0.0146408677 |
| c56 | card_nll | -0.00519180298 |
| c56 | card_top1 | -0.000379920006 |
| c56 | card_top3 | 0.00362092257 |
| c56 | tile_nll | 0.0155789852 |
| c56 | tile_within1 | -0.00407296419 |
| c56 | top8_recall | -0.00235754251 |
| c56 | top8_within1 | -0.00111413002 |
| c56 | ability_nll | 0.485702991 |
| c56 | intent_hazard_nll | 0.0164188147 |
| c56 | intent_card_nll | 0.00477564335 |
| c56 | median_tile_error | 0 |
| s122 | play_wait_nll | -0.00272320211 |
| s122 | play_wait_brier | -0.000848934054 |
| s122 | play_wait_nll_all | -0.00180543959 |
| s122 | play_wait_brier_all | -0.000606855378 |
| s122 | joint_nll | -0.00316402316 |
| s122 | card_nll | 0.013504684 |
| s122 | card_top1 | -0.00600087643 |
| s122 | card_top3 | -0.00292032957 |
| s122 | tile_nll | 0.0245268345 |
| s122 | tile_within1 | -0.0066511333 |
| s122 | top8_recall | -0.00910180807 |
| s122 | top8_within1 | -0.00825357437 |
| s122 | ability_nll | 0.137564182 |
| s122 | intent_hazard_nll | -0.00569558144 |
| s122 | intent_card_nll | 0.0396205187 |
| s122 | median_tile_error | 0 |

## main-2026100822: eval

Analysis artifact: `/mpac/sdicks02/repos/clasher-t11-home-v1/gate-a-v2/analysis-2026100822-eval.json`, SHA256 `9220318ebedec5b9f4d41b03bbfc82d4856754054ab3deee9c9bfa73606a24ae`.
Statistics completion SHA256 `fbb4576e246dd99648ee732258875db47fc5b8c322efc58071a3855fc7d4a8e9`. This artifact includes pooled diagnostics, per-card/arena and Battle Healer/Mirror slices, and calibration bins.

### c56: 3644 perspectives, 2862378 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.168842763 | 0.16828984 | [0.167349833, 0.169204735] |
| play_wait_brier | 0.0437759012 | 0.0436744094 | [0.0433902845, 0.0439528894] |
| play_wait_nll_all | 0.162072241 | 0.161541581 | [0.160658284, 0.162420203] |
| play_wait_brier_all | 0.0420130044 | 0.0419156477 | [0.0416487228, 0.042176473] |
| joint_nll | 0.33814013 | 0.337546319 | [0.335288498, 0.339754203] |
| card_nll | 0.893895626 | 0.892385662 | [0.887449129, 0.897173304] |
| card_top1 | 0.60824424 | 0.60825175 | [0.60524726, 0.611210799] |
| card_top3 | 0.964448392 | 0.964448392 | [0.963315843, 0.965546737] |
| tile_nll | 2.83825779 | 2.83835411 | [2.82552657, 2.85081086] |
| tile_within1 | 0.477481991 | 0.477489471 | [0.474301203, 0.480742595] |
| top8_recall | 0.54073137 | 0.540506959 | [0.537188697, 0.543894769] |
| top8_within1 | 0.664776742 | 0.665038586 | [0.661935391, 0.668195502] |
| ability_nll | 4.30198479 | 4.04477787 | [3.99936051, 4.0910455] |
| intent_hazard_nll | 1.73573148 | 1.73573148 | [1.73041604, 1.74074056] |
| intent_card_nll | 1.42701471 | 1.42701471 | [1.42181876, 1.43221483] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.101002953 | [-0.101820648, -0.100183276] |
| play_wait_nll | -0.0216573175 | [-0.0220080686, -0.0213147417] |
| card_nll | -0.48699507 | [-0.493206414, -0.48096073] |
| tile_nll | -1.19430781 | [-1.20431196, -1.18469728] |

A2: {"card_nll": {"baseline": 1.0076806024184548, "delta": -0.12119012135057372, "model": 0.8864904810678811, "pass_": true}, "tile_nll": {"baseline": 3.5364494500604375, "delta": -0.7030727212522283, "model": 2.8333767288082092, "pass_": true}}
A3 passing/assessed/scoped: 52/52/56.
A3 significantly worse cards: none.
A3 unassessed cards: 20, 38, 114, 328.
A4 calibrated gate ECE 0.00279486097; bar ≤0.01.

### s122: 12369 perspectives, 8553701 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.133911386 | 0.133280218 | [0.132748304, 0.133816385] |
| play_wait_brier | 0.0333636366 | 0.0332796276 | [0.0331287849, 0.0334344266] |
| play_wait_nll_all | 0.122927316 | 0.122348391 | [0.121832503, 0.122873077] |
| play_wait_brier_all | 0.0306245927 | 0.0305474997 | [0.03040192, 0.0306972862] |
| joint_nll | 0.250248104 | 0.24959527 | [0.248358759, 0.250881259] |
| card_nll | 0.890594482 | 0.889248729 | [0.886074928, 0.892327313] |
| card_top1 | 0.609691799 | 0.609702229 | [0.607735131, 0.611614763] |
| card_top3 | 0.964772284 | 0.96476531 | [0.964037793, 0.965481946] |
| tile_nll | 2.88237453 | 2.88150096 | [2.87318348, 2.88967251] |
| tile_within1 | 0.46827662 | 0.468273163 | [0.46619548, 0.470373064] |
| top8_recall | 0.540575504 | 0.541128576 | [0.538889906, 0.543331458] |
| top8_within1 | 0.663364649 | 0.664241195 | [0.662144521, 0.666319031] |
| ability_nll | 4.58323288 | 4.30220175 | [4.25593776, 4.3493443] |
| intent_hazard_nll | 1.6463387 | 1.6463387 | [1.64316839, 1.64948724] |
| intent_card_nll | 1.44877958 | 1.44877958 | [1.44539592, 1.45215683] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.0817624501 | [-0.0821941487, -0.081326575] |
| play_wait_nll | -0.0165138216 | [-0.0166940795, -0.0163348797] |
| card_nll | -0.594763812 | [-0.599419922, -0.590014121] |
| tile_nll | -1.37423318 | [-1.38095125, -1.36748376] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 121/121/121.
A3 significantly worse cards: none.
A3 unassessed cards: none.
A4 calibrated gate ECE 0.0010552221; bar ≤0.01.

## main-2026100822: eval_ood

Analysis artifact: `/mpac/sdicks02/repos/clasher-t11-home-v1/gate-a-v2/analysis-2026100822-eval_ood.json`, SHA256 `4d3e41abb3a0d717c2c60d5ca826c4e1c421c7d6af07a470ce7a15afff04be95`.
Statistics completion SHA256 `3d75b00bf0c9fd0f422f50c2bace77591d601437f878ddafddcd1e2890b13428`. This artifact includes pooled diagnostics, per-card/arena and Battle Healer/Mirror slices, and calibration bins.

### c56: 3643 perspectives, 2796216 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.163268313 | 0.162447348 | [0.161472634, 0.163416028] |
| play_wait_brier | 0.0417325236 | 0.0416227542 | [0.0413440183, 0.0419070455] |
| play_wait_nll_all | 0.156404436 | 0.155617937 | [0.154693375, 0.156548343] |
| play_wait_brier_all | 0.0399780385 | 0.0398728736 | [0.0396014262, 0.0401462161] |
| joint_nll | 0.323753923 | 0.322897434 | [0.320627014, 0.325169469] |
| card_nll | 0.891199291 | 0.888845801 | [0.883998867, 0.893651597] |
| card_top1 | 0.60727185 | 0.607279837 | [0.604226221, 0.610332851] |
| card_top3 | 0.967388332 | 0.967388332 | [0.966263049, 0.968486789] |
| tile_nll | 2.85440326 | 2.85519361 | [2.84294228, 2.86734344] |
| tile_within1 | 0.47423327 | 0.47425732 | [0.470823142, 0.477641671] |
| top8_recall | 0.53571713 | 0.535869598 | [0.532503725, 0.53927692] |
| top8_within1 | 0.663002133 | 0.663202763 | [0.660058565, 0.666277416] |
| ability_nll | 4.43415737 | 4.16539478 | [3.30053377, 4.35313272] |
| intent_hazard_nll | 1.75199509 | 1.75199509 | [1.74590835, 1.75796548] |
| intent_card_nll | 1.44566321 | 1.44566321 | [1.43965933, 1.45157114] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.0934036192 | [-0.0941442266, -0.0926635214] |
| play_wait_nll | -0.0192237484 | [-0.0196050738, -0.0188526163] |
| card_nll | -0.48908727 | [-0.495983816, -0.48223372] |
| tile_nll | -1.18923841 | [-1.19942081, -1.17875841] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 40/40/56.
A3 significantly worse cards: none.
A3 unassessed cards: 6, 10, 17, 20, 30, 38, 114, 115, 181, 232, 238, 258, 259, 277, 328, 356.
A4 calibrated gate ECE 0.00159211258; bar ≤0.01.

### s122: 11281 perspectives, 7642235 stored rows

| Metric | Before calibration | After calibration | 95% CI after |
|---|---:|---:|---|
| play_wait_nll | 0.130871087 | 0.130513921 | [0.12998206, 0.131047957] |
| play_wait_brier | 0.0324920826 | 0.0324281305 | [0.032276434, 0.03257913] |
| play_wait_nll_all | 0.120832264 | 0.120502181 | [0.119993275, 0.121001765] |
| play_wait_brier_all | 0.0299972352 | 0.0299381893 | [0.0297939749, 0.0300809558] |
| joint_nll | 0.246875331 | 0.246447936 | [0.24522688, 0.247688241] |
| card_nll | 0.905763984 | 0.903520763 | [0.900234523, 0.906846883] |
| card_top1 | 0.602734208 | 0.602738202 | [0.600665651, 0.604867745] |
| card_top3 | 0.962309003 | 0.962305009 | [0.961479451, 0.96311802] |
| tile_nll | 2.90755343 | 2.90684676 | [2.89826978, 2.91521303] |
| tile_within1 | 0.46028018 | 0.460256338 | [0.457991523, 0.462466732] |
| top8_recall | 0.530575275 | 0.530932963 | [0.528631905, 0.533210161] |
| top8_within1 | 0.653945327 | 0.65437454 | [0.652225855, 0.656544459] |
| ability_nll | 4.67797327 | 4.39020205 | [4.33916286, 4.44313641] |
| intent_hazard_nll | 1.63898659 | 1.63898659 | [1.63577535, 1.642177] |
| intent_card_nll | 1.48042345 | 1.48042345 | [1.47693711, 1.48396152] |
| median_tile_error | 1.41421354 | 1.41421354 | [1.41421354, 1.41421354] |

| A1 paired model-minus-frequency | Mean | 95% CI |
|---|---:|---|
| joint_nll | -0.0792015007 | [-0.0796330869, -0.0787708604] |
| play_wait_nll | -0.0156614961 | [-0.0158486821, -0.0154790049] |
| card_nll | -0.576591418 | [-0.581506155, -0.571633112] |
| tile_nll | -1.37751097 | [-1.38457034, -1.37033512] |

A2: N/A, empty structural P16 slice.
A3 passing/assessed/scoped: 111/111/121.
A3 significantly worse cards: none.
A3 unassessed cards: 25, 31, 66, 75, 84, 102, 153, 228, 239, 242.
A4 calibrated gate ECE 0.0020784989; bar ≤0.01.

| Corpus | Metric | OOD minus eval (descriptive) |
|---|---|---:|
| c56 | play_wait_nll | -0.00584249198 |
| c56 | play_wait_brier | -0.0020516552 |
| c56 | play_wait_nll_all | -0.00592364371 |
| c56 | play_wait_brier_all | -0.00204277411 |
| c56 | joint_nll | -0.0146488845 |
| c56 | card_nll | -0.00353986025 |
| c56 | card_top1 | -0.000971913338 |
| c56 | card_top3 | 0.0029399395 |
| c56 | tile_nll | 0.0168395042 |
| c56 | tile_within1 | -0.00323215127 |
| c56 | top8_recall | -0.00463736057 |
| c56 | top8_within1 | -0.00183582306 |
| c56 | ability_nll | 0.120616913 |
| c56 | intent_hazard_nll | 0.0162636042 |
| c56 | intent_card_nll | 0.0186485052 |
| c56 | median_tile_error | 0 |
| s122 | play_wait_nll | -0.00276629627 |
| s122 | play_wait_brier | -0.000851497054 |
| s122 | play_wait_nll_all | -0.00184620917 |
| s122 | play_wait_brier_all | -0.000609310344 |
| s122 | joint_nll | -0.00314733386 |
| s122 | card_nll | 0.0142720342 |
| s122 | card_top1 | -0.00696402788 |
| s122 | card_top3 | -0.00246030092 |
| s122 | tile_nll | 0.0253458023 |
| s122 | tile_within1 | -0.00801682472 |
| s122 | top8_recall | -0.0101956129 |
| s122 | top8_within1 | -0.00986665487 |
| s122 | ability_nll | 0.0880002975 |
| s122 | intent_hazard_nll | -0.00735211372 |
| s122 | intent_card_nll | 0.0316438675 |
| s122 | median_tile_error | 0 |

## Input provenance

- qualified_code_sha256: `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`.
- throughput_receipt_sha256: `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`.
- assets_sha256: `3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737`.
- store_receipt_sha256: `0e14fefa47388dc0f8a436d2c6415224ac30af1cc3aed98a9092485deaf4b524`.
- store_manifest_sha256: `7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f`.
- role_file_sha256: `1f45f1d147040e4502a18820ed9eec172b2d5f304589eaf96cbd87aa84f547e8`.
- eval_spec_sha256: `d9f978f75191b5d5a474d127dbccd618b93dad5069dd851ab4f8b2a47fdaa7ae`.
- frequency_counts_sha256: `fef76fcb1dd5eac5cd1ac51c72244afe06eaa22daddd53eba1c6a9520640d752`.
- adapter_validation_sha256: `d9ca2f8265c24509a943c59a400cd0de18851cf1dd1a60eda69a4b0e4ebae091`.
- guard_validation_sha256: `39a7c67b874885a45de80061260af7c59caea5c56daba8da074ede1dd25a44ef`.
- padding_validation_sha256: `1c4729630b9dd20dea745b26fee2b99bf75324de57f28779f01f5615d4ca2758`.
- padding_amendment_sha256: `45ef4d0e3396daf4ab64e9fd3775d0b0ba0ce3035b9d9175ce65fe73fb8487dd`.
- t5_resource_r2_manifest_sha256: `2854ce1f96fdd2fcc04dd0e6ef15dce3435758ec40369a80bba29b1a1e29db13`.
- p16_checkpoint_sha256: `49be14806a7e7e6ab26621e25230d3f6f7f0be4d84aabd480cbb8097de4ab482`.
