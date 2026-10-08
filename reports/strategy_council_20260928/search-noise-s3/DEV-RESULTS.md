# Development calibration

56 fresh script-v-script worlds, both seats. Indices 0–27 calibrate; 28–55 validate. Validation diagnostics informed development revisions, so this is not an untouched confirmation set. Confirmation outcomes remain unobserved. Final interval radii come only from indices 0–27.

| Level | Coverage | Post-error coverage | Width | MAE | Legacy width | Legacy MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T2-N97 | 0.9131 | 0.8862 | 2.697 | 0.633 | 6.507 | 0.787 |
| T2-N90 | 0.9104 | 0.9017 | 2.635 | 0.739 | 6.995 | 0.865 |
| T2-N64 | 0.9079 | 0.9071 | 4.133 | 0.866 | 7.945 | 1.591 |

Final radii: {"T2-N97": 0.06820000000000004, "T2-N90": 0.11040000000000028, "T2-N64": 0.8908999999999998}

Eight unit tests pass. Original 24 P16 recorded games: 23,058 observations; zero exactness errors, including checks against deck-free DerivedD1. All three S2 anchor action-sequence checks pass.

Synthetic tests exercise full resource support under missed/spurious injections, confused identity alternatives and recovery, board/event deduplication, phase/cap equality, reserved fallback under pruning, and hidden-card/RNG invariance. They do not establish statistical coverage; the fresh dev replay and confirmation measure that.
