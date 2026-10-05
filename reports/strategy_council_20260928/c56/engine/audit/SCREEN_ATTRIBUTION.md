# Screen attribution

1897 rows, 0 errors, 1191 finite event times, 706 null event times.

OLS: first_contradiction_s ~ intercept + g66_pool + real_end_s/100 + 40 any-side card-presence indicators
Design rank 43/43; RMSE 50.05 s.

Negative coefficients associate a card with earlier contradiction, conditional on the other included variables. This is queue prioritization, not causal attribution or native acceptance.

| Rank | Card | Conditional seconds | HC3 SE | Finite-event presence | End-censored sensitivity |
|---|---|---:|---:|---:|---:|
| 1 | GoblinHut | -24.99 | 19.00 | 19 | -32.83 |
| 2 | Goblinstein | -24.00 | 16.10 | 27 | -21.09 |
| 3 | Ghost | -18.31 | 4.35 | 205 | -23.22 |
| 4 | FireSpirits | -17.70 | 15.86 | 20 | -13.36 |
| 5 | FirespiritHut | -16.40 | 11.94 | 25 | -2.67 |
| 6 | Balloon | -15.08 | 5.03 | 438 | -9.15 |
| 7 | Rascals | -14.68 | 15.70 | 20 | -26.40 |
| 8 | Berserker | -13.49 | 8.32 | 102 | -13.39 |
| 9 | Bats | -12.67 | 6.63 | 114 | -12.93 |
| 10 | Earthquake | -10.24 | 11.88 | 119 | -7.42 |
| 11 | MiniPekka | -9.14 | 6.20 | 118 | -7.74 |
| 12 | Arrows | -8.91 | 4.22 | 295 | -9.29 |
| 13 | MinionHorde | -7.45 | 9.70 | 56 | -2.49 |
| 14 | Miner | -7.31 | 6.16 | 240 | -0.29 |
| 15 | GoblinGang | -6.81 | 5.65 | 178 | -0.99 |
| 16 | BlowdartGoblin | -6.55 | 7.77 | 112 | -0.20 |
| 17 | SkeletonArmy | -4.92 | 9.56 | 58 | -1.18 |
| 18 | ArcherQueen | -4.24 | 9.32 | 107 | 2.01 |
| 19 | GoblinBarrel | -3.67 | 12.38 | 248 | -11.75 |
| 20 | Minions | -2.42 | 4.41 | 196 | -2.48 |
| 21 | BabyDragon | -1.37 | 5.70 | 342 | -1.06 |
| 22 | Valkyrie | -0.88 | 4.55 | 244 | -1.67 |
| 23 | BarbLog | -0.42 | 5.02 | 581 | -0.62 |
| 24 | Firecracker | -0.17 | 7.58 | 124 | 4.26 |
| 25 | MightyMiner | 0.18 | 10.21 | 89 | 4.38 |
| 26 | Xbow | 0.33 | 6.12 | 132 | 6.12 |
| 27 | Wallbreakers | 0.65 | 6.65 | 173 | -1.42 |
| 28 | AngryBarbarians | 1.42 | 8.32 | 56 | 1.74 |
| 29 | Tornado | 2.84 | 5.60 | 438 | 0.79 |
| 30 | Wizard | 4.20 | 19.13 | 14 | 7.60 |
| 31 | Lightning | 4.25 | 8.57 | 69 | 1.29 |
| 32 | ElectroSpirit | 5.35 | 4.81 | 300 | 2.84 |
| 33 | Rocket | 7.10 | 5.71 | 220 | 5.64 |
| 34 | InfernoTower | 7.68 | 6.52 | 85 | 5.41 |
| 35 | Princess | 9.34 | 11.58 | 243 | 13.80 |
| 36 | RoyalDelivery | 13.44 | 14.17 | 62 | 15.55 |
| 37 | Golem | 14.05 | 8.10 | 40 | 10.00 |
| 38 | RoyalHogs | 14.60 | 10.46 | 97 | 2.91 |
| 39 | Poison | 15.39 | 5.44 | 171 | 10.92 |
| 40 | BombTower | 18.42 | 7.62 | 169 | 6.31 |

Finite-event subset is selected; missing real kills have no event timestamp and are not zero-time events.
Co-occurring deck cards confound attribution; rank and standard errors are diagnostic only.
Pre-repair baseline source; no evidence of repair benefit or native parity.
Sensitivity outcome is min(event time, real match end), with null events assigned match end; not survival regression.
