# Gate (b) — complete registered results

All 1,152 registered games are included. Draws count as half a win for scores and as non-wins for the P16 McNemar comparison.

Primary: main-2026100802, step22552, released EMA checkpoint, serving T=1. Selection was dev-only and sealed before heldout. Gate (a) outcome contents were not used. The three released dev temperatures are provenance only; there was no calibrated arm.

**Gate PASS.** Adopt B as the default C56 fair player; live-loop v4 P3 uses B.

## Primary: 320 worlds, 640 controller-swap games

| group | N | W | D | L | score | win_rate |
| --- | --- | --- | --- | --- | --- | --- |
| B vs A | 640 | 420 | 0 | 220 | 0.656250 | 0.656250 |

Whole-world paired bootstrap 95% CI: [0.628125, 0.684375]; 10,000 resamples. Decisive pairs: 114/320 (q=0.356250); split pairs: 206. Pair-score distribution: `{"0.0": 7, "0.25": 0, "0.5": 206, "0.75": 0, "1.0": 107}`.

### Descriptive slices: family

| group | N | W | D | L | score | win_rate |
| --- | --- | --- | --- | --- | --- | --- |
| AQ | 90 | 66 | 0 | 24 | 0.733333 | 0.733333 |
| Goblinstein | 90 | 51 | 0 | 39 | 0.566667 | 0.566667 |
| Hog 2.6 | 92 | 60 | 0 | 32 | 0.652174 | 0.652174 |
| Hog EQ/Firecracker/MM | 92 | 63 | 0 | 29 | 0.684783 | 0.684783 |
| Royal Hogs/Furnace | 92 | 51 | 0 | 41 | 0.554348 | 0.554348 |
| X-Bow | 92 | 68 | 0 | 24 | 0.739130 | 0.739130 |
| bait | 92 | 61 | 0 | 31 | 0.663043 | 0.663043 |

### Descriptive slices: role

| group | N | W | D | L | score | win_rate |
| --- | --- | --- | --- | --- | --- | --- |
| eval | 640 | 420 | 0 | 220 | 0.656250 | 0.656250 |

## Secondary: identical script worlds, 256 games per arm

| group | N | W | D | L | score | win_rate |
| --- | --- | --- | --- | --- | --- | --- |
| A | 256 | 237 | 0 | 19 | 0.925781 | 0.925781 |
| B | 256 | 250 | 0 | 6 | 0.976562 | 0.976562 |

B minus A score: 0.050781; paired-world descriptive 95% CI [0.019531, 0.085938].

## Deadline receipts

200 ms absolute wall deadline; two Rust threads per game. All serving work is inside the deadline. Forced waits are included in the pooled latency statistics. A includes its head-to-head and script decisions; B includes both protocols.

| arm | n | p50 | p99 | maximum | over200 | over250 | searched | truncations | fallbacks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 805648 | 3.599189454689622 | 200.23656002711505 | 203.3246469218284 | 14129 | 0 | 80010 | 14057 | 0 |
| B | 797640 | 3.6741519579663873 | 200.28656157432124 | 202.82596605829895 | 18832 | 0 | 77381 | 18729 | 3 |

Latency units: milliseconds.

| bar | passed |
| --- | --- |
| primary | True |
| secondary | True |
| timing | True |
| integrity | True |

## Host receipts

Per-arm host timing is retained in the machine-readable host receipts below.

```json
{
  "127x03": {
    "games": 1152,
    "nice": [
      10
    ],
    "threads": [
      2
    ],
    "max_load1": 21.26,
    "timing_by_arm": {
      "A": {
        "n": 805648,
        "p50": 3.599189454689622,
        "p99": 200.23656002711505,
        "maximum": 203.3246469218284,
        "over200": 14129,
        "over250": 0
      },
      "B": {
        "n": 797640,
        "p50": 3.6741519579663873,
        "p99": 200.28656157432124,
        "maximum": 202.82596605829895,
        "over200": 18832,
        "over250": 0
      }
    }
  }
}
```

| host | games | nice | threads | max_load1 |
| --- | --- | --- | --- | --- |
| 127x03 | 1152 | [10] | [2] | 21.26 |

## Rejected commands

Rates use non-wait command attempts as denominator; abilities are separate. These are descriptive and never a pass bar.

| arm | protocol | card | attempts | rejected | rate |
| --- | --- | --- | --- | --- | --- |
| A | ALL | ALL | 57083 | 24 | 0.0004204404113308691 |
| A | C56-scripts | ALL | 13759 | 10 | 0.0007267970055963369 |
| A | C56-scripts | ArcherQueen | 32 | 0 | 0.0 |
| A | C56-scripts | Archers | 749 | 0 | 0.0 |
| A | C56-scripts | BarbLog | 756 | 0 | 0.0 |
| A | C56-scripts | Berserker | 541 | 0 | 0.0 |
| A | C56-scripts | BlowdartGoblin | 124 | 0 | 0.0 |
| A | C56-scripts | BombTower | 361 | 9 | 0.024930747922437674 |
| A | C56-scripts | Cannon | 1075 | 0 | 0.0 |
| A | C56-scripts | Earthquake | 427 | 0 | 0.0 |
| A | C56-scripts | ElectroSpirit | 1496 | 0 | 0.0 |
| A | C56-scripts | Fireball | 51 | 0 | 0.0 |
| A | C56-scripts | Firecracker | 389 | 0 | 0.0 |
| A | C56-scripts | FirespiritHut | 186 | 0 | 0.0 |
| A | C56-scripts | Ghost | 193 | 0 | 0.0 |
| A | C56-scripts | GoblinBarrel | 226 | 0 | 0.0 |
| A | C56-scripts | GoblinGang | 11 | 0 | 0.0 |
| A | C56-scripts | GoblinHut | 89 | 0 | 0.0 |
| A | C56-scripts | Goblins | 54 | 0 | 0.0 |
| A | C56-scripts | Goblinstein | 26 | 0 | 0.0 |
| A | C56-scripts | HogRider | 209 | 0 | 0.0 |
| A | C56-scripts | IceGolem | 480 | 0 | 0.0 |
| A | C56-scripts | IceSpirit | 1209 | 0 | 0.0 |
| A | C56-scripts | InfernoTower | 3 | 0 | 0.0 |
| A | C56-scripts | Knight | 218 | 0 | 0.0 |
| A | C56-scripts | Lightning | 2 | 0 | 0.0 |
| A | C56-scripts | Log | 1682 | 0 | 0.0 |
| A | C56-scripts | MightyMiner | 9 | 0 | 0.0 |
| A | C56-scripts | Musketeer | 28 | 0 | 0.0 |
| A | C56-scripts | Princess | 184 | 0 | 0.0 |
| A | C56-scripts | RoyalDelivery | 209 | 0 | 0.0 |
| A | C56-scripts | RoyalHogs | 182 | 1 | 0.005494505494505495 |
| A | C56-scripts | SkeletonArmy | 108 | 0 | 0.0 |
| A | C56-scripts | Skeletons | 2258 | 0 | 0.0 |
| A | C56-scripts | Tesla | 47 | 0 | 0.0 |
| A | C56-scripts | Valkyrie | 2 | 0 | 0.0 |
| A | C56-scripts | Wallbreakers | 73 | 0 | 0.0 |
| A | C56-scripts | Xbow | 15 | 0 | 0.0 |
| A | C56-scripts | __ability__ | 55 | 0 | 0.0 |
| A | head-to-head | ALL | 43324 | 14 | 0.000323146523866679 |
| A | head-to-head | AngryBarbarians | 5 | 0 | 0.0 |
| A | head-to-head | ArcherQueen | 11 | 0 | 0.0 |
| A | head-to-head | Archers | 1768 | 0 | 0.0 |
| A | head-to-head | Arrows | 13 | 0 | 0.0 |
| A | head-to-head | BabyDragon | 33 | 0 | 0.0 |
| A | head-to-head | BarbLog | 2118 | 0 | 0.0 |
| A | head-to-head | Bats | 111 | 0 | 0.0 |
| A | head-to-head | Berserker | 2061 | 0 | 0.0 |
| A | head-to-head | BlowdartGoblin | 450 | 0 | 0.0 |
| A | head-to-head | BombTower | 702 | 12 | 0.017094017094017096 |
| A | head-to-head | Cannon | 3584 | 0 | 0.0 |
| A | head-to-head | DarkPrince | 40 | 0 | 0.0 |
| A | head-to-head | Earthquake | 1046 | 0 | 0.0 |
| A | head-to-head | ElectroSpirit | 4801 | 0 | 0.0 |
| A | head-to-head | FireSpirits | 83 | 0 | 0.0 |
| A | head-to-head | Fireball | 144 | 0 | 0.0 |
| A | head-to-head | Firecracker | 1276 | 0 | 0.0 |
| A | head-to-head | FirespiritHut | 658 | 0 | 0.0 |
| A | head-to-head | Ghost | 550 | 0 | 0.0 |
| A | head-to-head | GoblinBarrel | 847 | 0 | 0.0 |
| A | head-to-head | GoblinGang | 171 | 0 | 0.0 |
| A | head-to-head | GoblinHut | 307 | 0 | 0.0 |
| A | head-to-head | Goblins | 266 | 0 | 0.0 |
| A | head-to-head | Goblinstein | 25 | 0 | 0.0 |
| A | head-to-head | HogRider | 349 | 0 | 0.0 |
| A | head-to-head | IceGolem | 2224 | 0 | 0.0 |
| A | head-to-head | IceSpirit | 3491 | 0 | 0.0 |
| A | head-to-head | InfernoTower | 2 | 0 | 0.0 |
| A | head-to-head | Knight | 771 | 0 | 0.0 |
| A | head-to-head | Lightning | 4 | 0 | 0.0 |
| A | head-to-head | Log | 5650 | 0 | 0.0 |
| A | head-to-head | MightyMiner | 27 | 0 | 0.0 |
| A | head-to-head | Miner | 43 | 0 | 0.0 |
| A | head-to-head | MiniPekka | 5 | 0 | 0.0 |
| A | head-to-head | MinionHorde | 3 | 0 | 0.0 |
| A | head-to-head | Minions | 34 | 0 | 0.0 |
| A | head-to-head | Musketeer | 83 | 0 | 0.0 |
| A | head-to-head | Poison | 1 | 0 | 0.0 |
| A | head-to-head | Princess | 830 | 0 | 0.0 |
| A | head-to-head | Rocket | 3 | 0 | 0.0 |
| A | head-to-head | RoyalDelivery | 458 | 0 | 0.0 |
| A | head-to-head | RoyalHogs | 183 | 2 | 0.01092896174863388 |
| A | head-to-head | SkeletonArmy | 346 | 0 | 0.0 |
| A | head-to-head | Skeletons | 6865 | 0 | 0.0 |
| A | head-to-head | Tesla | 110 | 0 | 0.0 |
| A | head-to-head | Tornado | 20 | 0 | 0.0 |
| A | head-to-head | Valkyrie | 157 | 0 | 0.0 |
| A | head-to-head | Wallbreakers | 454 | 0 | 0.0 |
| A | head-to-head | Wizard | 25 | 0 | 0.0 |
| A | head-to-head | Xbow | 23 | 0 | 0.0 |
| A | head-to-head | Zap | 44 | 0 | 0.0 |
| A | head-to-head | __ability__ | 49 | 0 | 0.0 |
| B | ALL | ALL | 56635 | 10 | 0.00017656925929195727 |
| B | C56-scripts | ALL | 12962 | 3 | 0.00023144576454250888 |
| B | C56-scripts | ArcherQueen | 15 | 0 | 0.0 |
| B | C56-scripts | Archers | 708 | 0 | 0.0 |
| B | C56-scripts | BarbLog | 696 | 0 | 0.0 |
| B | C56-scripts | Berserker | 492 | 0 | 0.0 |
| B | C56-scripts | BlowdartGoblin | 104 | 0 | 0.0 |
| B | C56-scripts | BombTower | 345 | 0 | 0.0 |
| B | C56-scripts | Cannon | 964 | 0 | 0.0 |
| B | C56-scripts | Earthquake | 461 | 0 | 0.0 |
| B | C56-scripts | ElectroSpirit | 1401 | 0 | 0.0 |
| B | C56-scripts | Fireball | 51 | 0 | 0.0 |
| B | C56-scripts | Firecracker | 331 | 0 | 0.0 |
| B | C56-scripts | FirespiritHut | 184 | 0 | 0.0 |
| B | C56-scripts | Ghost | 179 | 0 | 0.0 |
| B | C56-scripts | GoblinBarrel | 222 | 0 | 0.0 |
| B | C56-scripts | GoblinGang | 12 | 0 | 0.0 |
| B | C56-scripts | GoblinHut | 73 | 0 | 0.0 |
| B | C56-scripts | Goblins | 46 | 0 | 0.0 |
| B | C56-scripts | Goblinstein | 24 | 3 | 0.125 |
| B | C56-scripts | HogRider | 214 | 0 | 0.0 |
| B | C56-scripts | IceGolem | 467 | 0 | 0.0 |
| B | C56-scripts | IceSpirit | 1153 | 0 | 0.0 |
| B | C56-scripts | Knight | 221 | 0 | 0.0 |
| B | C56-scripts | Lightning | 2 | 0 | 0.0 |
| B | C56-scripts | Log | 1635 | 0 | 0.0 |
| B | C56-scripts | MightyMiner | 11 | 0 | 0.0 |
| B | C56-scripts | Musketeer | 15 | 0 | 0.0 |
| B | C56-scripts | Princess | 174 | 0 | 0.0 |
| B | C56-scripts | Rocket | 1 | 0 | 0.0 |
| B | C56-scripts | RoyalDelivery | 204 | 0 | 0.0 |
| B | C56-scripts | RoyalHogs | 162 | 0 | 0.0 |
| B | C56-scripts | SkeletonArmy | 93 | 0 | 0.0 |
| B | C56-scripts | Skeletons | 2131 | 0 | 0.0 |
| B | C56-scripts | Tesla | 32 | 0 | 0.0 |
| B | C56-scripts | Valkyrie | 3 | 0 | 0.0 |
| B | C56-scripts | Wallbreakers | 78 | 0 | 0.0 |
| B | C56-scripts | Xbow | 17 | 0 | 0.0 |
| B | C56-scripts | __ability__ | 41 | 0 | 0.0 |
| B | head-to-head | ALL | 43673 | 7 | 0.00016028209648982208 |
| B | head-to-head | AngryBarbarians | 7 | 0 | 0.0 |
| B | head-to-head | ArcherQueen | 16 | 0 | 0.0 |
| B | head-to-head | Archers | 1863 | 0 | 0.0 |
| B | head-to-head | Arrows | 12 | 0 | 0.0 |
| B | head-to-head | BabyDragon | 24 | 0 | 0.0 |
| B | head-to-head | BarbLog | 2152 | 0 | 0.0 |
| B | head-to-head | Bats | 132 | 0 | 0.0 |
| B | head-to-head | Berserker | 1930 | 0 | 0.0 |
| B | head-to-head | BlowdartGoblin | 305 | 0 | 0.0 |
| B | head-to-head | BombTower | 776 | 0 | 0.0 |
| B | head-to-head | Cannon | 3686 | 0 | 0.0 |
| B | head-to-head | DarkPrince | 32 | 0 | 0.0 |
| B | head-to-head | Earthquake | 1264 | 0 | 0.0 |
| B | head-to-head | ElectroSpirit | 4786 | 0 | 0.0 |
| B | head-to-head | FireSpirits | 74 | 0 | 0.0 |
| B | head-to-head | Fireball | 136 | 0 | 0.0 |
| B | head-to-head | Firecracker | 1310 | 0 | 0.0 |
| B | head-to-head | FirespiritHut | 544 | 0 | 0.0 |
| B | head-to-head | Ghost | 477 | 0 | 0.0 |
| B | head-to-head | GoblinBarrel | 753 | 0 | 0.0 |
| B | head-to-head | GoblinGang | 154 | 0 | 0.0 |
| B | head-to-head | GoblinHut | 260 | 1 | 0.0038461538461538464 |
| B | head-to-head | Goblins | 243 | 0 | 0.0 |
| B | head-to-head | Goblinstein | 30 | 0 | 0.0 |
| B | head-to-head | HogRider | 358 | 0 | 0.0 |
| B | head-to-head | IceGolem | 2396 | 0 | 0.0 |
| B | head-to-head | IceSpirit | 3614 | 0 | 0.0 |
| B | head-to-head | InfernoTower | 1 | 0 | 0.0 |
| B | head-to-head | Knight | 717 | 0 | 0.0 |
| B | head-to-head | Lightning | 5 | 0 | 0.0 |
| B | head-to-head | Log | 5801 | 0 | 0.0 |
| B | head-to-head | MightyMiner | 32 | 0 | 0.0 |
| B | head-to-head | Miner | 42 | 0 | 0.0 |
| B | head-to-head | MiniPekka | 6 | 0 | 0.0 |
| B | head-to-head | MinionHorde | 3 | 0 | 0.0 |
| B | head-to-head | Minions | 29 | 0 | 0.0 |
| B | head-to-head | Musketeer | 58 | 0 | 0.0 |
| B | head-to-head | Poison | 1 | 0 | 0.0 |
| B | head-to-head | Princess | 709 | 0 | 0.0 |
| B | head-to-head | Rascals | 1 | 0 | 0.0 |
| B | head-to-head | Rocket | 4 | 0 | 0.0 |
| B | head-to-head | RoyalDelivery | 525 | 0 | 0.0 |
| B | head-to-head | RoyalHogs | 203 | 6 | 0.029556650246305417 |
| B | head-to-head | SkeletonArmy | 261 | 0 | 0.0 |
| B | head-to-head | Skeletons | 7178 | 0 | 0.0 |
| B | head-to-head | Tesla | 106 | 0 | 0.0 |
| B | head-to-head | Tornado | 20 | 0 | 0.0 |
| B | head-to-head | Valkyrie | 125 | 0 | 0.0 |
| B | head-to-head | Wallbreakers | 364 | 0 | 0.0 |
| B | head-to-head | Wizard | 18 | 0 | 0.0 |
| B | head-to-head | Xbow | 28 | 0 | 0.0 |
| B | head-to-head | Zap | 36 | 0 | 0.0 |
| B | head-to-head | __ability__ | 66 | 0 | 0.0 |
| script | ALL | ALL | 25880 | 36 | 0.0013910355486862441 |
| script | C56-scripts | ALL | 25880 | 36 | 0.0013910355486862441 |
| script | C56-scripts | ArcherQueen | 11 | 0 | 0.0 |
| script | C56-scripts | Archers | 497 | 0 | 0.0 |
| script | C56-scripts | BarbLog | 790 | 0 | 0.0 |
| script | C56-scripts | Bats | 90 | 0 | 0.0 |
| script | C56-scripts | Berserker | 1400 | 0 | 0.0 |
| script | C56-scripts | BlowdartGoblin | 303 | 0 | 0.0 |
| script | C56-scripts | BombTower | 296 | 33 | 0.11148648648648649 |
| script | C56-scripts | Cannon | 2148 | 2 | 0.000931098696461825 |
| script | C56-scripts | DarkPrince | 15 | 0 | 0.0 |
| script | C56-scripts | Earthquake | 675 | 0 | 0.0 |
| script | C56-scripts | ElectroSpirit | 2864 | 0 | 0.0 |
| script | C56-scripts | FireSpirits | 75 | 0 | 0.0 |
| script | C56-scripts | Fireball | 413 | 0 | 0.0 |
| script | C56-scripts | Firecracker | 588 | 0 | 0.0 |
| script | C56-scripts | FirespiritHut | 203 | 0 | 0.0 |
| script | C56-scripts | Ghost | 517 | 0 | 0.0 |
| script | C56-scripts | GoblinBarrel | 696 | 0 | 0.0 |
| script | C56-scripts | GoblinGang | 170 | 0 | 0.0 |
| script | C56-scripts | GoblinHut | 698 | 0 | 0.0 |
| script | C56-scripts | Goblinstein | 93 | 0 | 0.0 |
| script | C56-scripts | HogRider | 368 | 0 | 0.0 |
| script | C56-scripts | IceGolem | 1395 | 0 | 0.0 |
| script | C56-scripts | IceSpirit | 2062 | 0 | 0.0 |
| script | C56-scripts | InfernoTower | 64 | 0 | 0.0 |
| script | C56-scripts | Knight | 433 | 0 | 0.0 |
| script | C56-scripts | Lightning | 15 | 0 | 0.0 |
| script | C56-scripts | Log | 3062 | 0 | 0.0 |
| script | C56-scripts | MightyMiner | 27 | 0 | 0.0 |
| script | C56-scripts | Miner | 50 | 0 | 0.0 |
| script | C56-scripts | MiniPekka | 1 | 0 | 0.0 |
| script | C56-scripts | Musketeer | 73 | 0 | 0.0 |
| script | C56-scripts | Princess | 535 | 0 | 0.0 |
| script | C56-scripts | Rocket | 31 | 0 | 0.0 |
| script | C56-scripts | RoyalDelivery | 55 | 0 | 0.0 |
| script | C56-scripts | RoyalHogs | 291 | 1 | 0.003436426116838488 |
| script | C56-scripts | SkeletonArmy | 386 | 0 | 0.0 |
| script | C56-scripts | Skeletons | 3689 | 0 | 0.0 |
| script | C56-scripts | Tesla | 311 | 0 | 0.0 |
| script | C56-scripts | Valkyrie | 76 | 0 | 0.0 |
| script | C56-scripts | Wallbreakers | 356 | 0 | 0.0 |
| script | C56-scripts | Wizard | 49 | 0 | 0.0 |
| script | C56-scripts | Xbow | 9 | 0 | 0.0 |

Descriptive pooled B minus A rejection rate: -0.00024387115203891184. By protocol: {"head-to-head": -0.00016286442737685692, "C56-scripts": -0.000495351241053828, "ALL": -0.00024387115203891184}.

### Rejection episodes (descriptive)

| arm | protocol | games | affected_games | episodes | decisions_lost |
| --- | --- | --- | --- | --- | --- |
| A | ALL | 896 | 10 | 10 | 24 |
| A | C56-scripts | 256 | 4 | 4 | 10 |
| A | head-to-head | 640 | 6 | 6 | 14 |
| B | ALL | 896 | 4 | 7 | 10 |
| B | C56-scripts | 256 | 1 | 1 | 3 |
| B | head-to-head | 640 | 3 | 6 | 7 |
| script | ALL | 512 | 10 | 12 | 36 |
| script | C56-scripts | 512 | 10 | 12 | 36 |

```json
{
  "head-to-head": {
    "episode_count_B_minus_A": 0,
    "exact_two_sided_p": 1.0,
    "test": "descriptive exact paired-world label permutation of episode counts; no command independence assumption"
  },
  "C56-scripts": {
    "episode_count_B_minus_A": -3,
    "exact_two_sided_p": 0.375,
    "test": "descriptive exact paired-world label permutation of episode counts; no command independence assumption"
  },
  "ALL": {
    "episode_count_B_minus_A": -3,
    "exact_two_sided_p": 0.7032470703125,
    "test": "descriptive exact paired-world label permutation of episode counts; no command independence assumption"
  }
}
```

Gate (b) measures B under mask v1. The shared mask/engine occupancy gap has identical no-op fallback for both arms; the cost falls on the controller that chose the rejected command. No conclusion about mask v2 and no adjusted score is computed.

### Outcome-blind rejection replay

```json
[
  {
    "seed": 1362137572929,
    "candidate_seat": 1,
    "actions_checked": 82,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 2550,
        "seat": 1,
        "action": 2075,
        "card": "GoblinHut",
        "reproduced": true,
        "guard_class": "live-building footprint/air collision",
        "guards": [
          {
            "guard": "is_building_placement_occupied",
            "blocker_type": "Building",
            "blocker_name": null,
            "blocks_deployment": null,
            "blocker_position": [
              10.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-064-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137651631,
    "candidate_seat": 0,
    "actions_checked": 191,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5910,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5920,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5930,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5940,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5950,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5960,
        "seat": 1,
        "action": 1918,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              6.5,
              20.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-142-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "A"
    ]
  },
  {
    "seed": 1362137744459,
    "candidate_seat": 1,
    "actions_checked": 91,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 510,
        "seat": 0,
        "action": 1915,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              8.5,
              11.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 520,
        "seat": 0,
        "action": 1915,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              8.5,
              11.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-234-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137764639,
    "candidate_seat": 1,
    "actions_checked": 194,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5990,
        "seat": 0,
        "action": 237,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 6000,
        "seat": 0,
        "action": 237,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-254-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137768675,
    "candidate_seat": 1,
    "actions_checked": 177,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3670,
        "seat": 0,
        "action": 766,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              10.5,
              11.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-258-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137770693,
    "candidate_seat": 1,
    "actions_checked": 173,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 4860,
        "seat": 0,
        "action": 187,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              8.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4870,
        "seat": 0,
        "action": 187,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              8.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-260-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137771702,
    "candidate_seat": 1,
    "actions_checked": 197,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 1190,
        "seat": 0,
        "action": 187,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              8.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-261-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "B"
    ]
  },
  {
    "seed": 1362137776747,
    "candidate_seat": 0,
    "actions_checked": 183,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 4970,
        "seat": 0,
        "action": 824,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              13.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4980,
        "seat": 0,
        "action": 823,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              13.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-266-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "A"
    ]
  },
  {
    "seed": 1362137781792,
    "candidate_seat": 0,
    "actions_checked": 194,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5880,
        "seat": 0,
        "action": 823,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              12.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5890,
        "seat": 0,
        "action": 822,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              12.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5900,
        "seat": 0,
        "action": 822,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              12.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5910,
        "seat": 0,
        "action": 821,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              12.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-271-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "A"
    ]
  },
  {
    "seed": 1362137865539,
    "candidate_seat": 1,
    "actions_checked": 77,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 790,
        "seat": 0,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 795,
        "seat": 0,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 800,
        "seat": 0,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 805,
        "seat": 0,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-354-A-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "A"
    ]
  },
  {
    "seed": 1362137875629,
    "candidate_seat": 0,
    "actions_checked": 83,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 2830,
        "seat": 1,
        "action": 1342,
        "card": "Cannon",
        "reproduced": true,
        "guard_class": "live-building footprint/air collision",
        "guards": [
          {
            "guard": "is_building_placement_occupied",
            "blocker_type": "Building",
            "blocker_name": null,
            "blocks_deployment": null,
            "blocker_position": [
              5.5,
              19.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-364-A-0.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "script"
    ]
  },
  {
    "seed": 1362137929106,
    "candidate_seat": 1,
    "actions_checked": 192,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5970,
        "seat": 1,
        "action": 192,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5980,
        "seat": 1,
        "action": 192,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5990,
        "seat": 1,
        "action": 192,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 6000,
        "seat": 1,
        "action": 192,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-417-A-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "A"
    ]
  },
  {
    "seed": 1362137930115,
    "candidate_seat": 1,
    "actions_checked": 166,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5600,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5610,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-418-A-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "A"
    ]
  },
  {
    "seed": 1362137934151,
    "candidate_seat": 0,
    "actions_checked": 167,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5640,
        "seat": 0,
        "action": 813,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-422-A-0.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "script"
    ]
  },
  {
    "seed": 1362137935160,
    "candidate_seat": 0,
    "actions_checked": 79,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3390,
        "seat": 1,
        "action": 1915,
        "card": "Cannon",
        "reproduced": true,
        "guard_class": "live-building footprint/air collision",
        "guards": [
          {
            "guard": "is_building_placement_occupied",
            "blocker_type": "Building",
            "blocker_name": null,
            "blocks_deployment": null,
            "blocker_position": [
              8.5,
              19.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-423-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "script"
    ]
  },
  {
    "seed": 1362137937178,
    "candidate_seat": 1,
    "actions_checked": 80,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3530,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 3540,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 3550,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-425-A-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "A"
    ]
  },
  {
    "seed": 1362137940205,
    "candidate_seat": 0,
    "actions_checked": 186,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 2580,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 2585,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 2590,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4205,
        "seat": 1,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4210,
        "seat": 1,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4215,
        "seat": 1,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4220,
        "seat": 1,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4225,
        "seat": 1,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-428-A-0.json",
    "index": 0,
    "arm_by_seat": [
      "A",
      "script"
    ]
  },
  {
    "seed": 1362137940205,
    "candidate_seat": 1,
    "actions_checked": 107,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3060,
        "seat": 0,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 3065,
        "seat": 0,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 3070,
        "seat": 0,
        "action": 183,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-428-A-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "A"
    ]
  },
  {
    "seed": 1362137940205,
    "candidate_seat": 0,
    "actions_checked": 184,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 4980,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4985,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4990,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4995,
        "seat": 1,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-428-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "script"
    ]
  },
  {
    "seed": 1362137941214,
    "candidate_seat": 0,
    "actions_checked": 100,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 4040,
        "seat": 0,
        "action": 237,
        "card": "Goblinstein",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4050,
        "seat": 0,
        "action": 237,
        "card": "Goblinstein",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4060,
        "seat": 0,
        "action": 237,
        "card": "Goblinstein",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              4.5,
              13.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-429-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "script"
    ]
  },
  {
    "seed": 1362137955340,
    "candidate_seat": 0,
    "actions_checked": 171,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 5370,
        "seat": 1,
        "action": 1911,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5375,
        "seat": 1,
        "action": 1911,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5380,
        "seat": 1,
        "action": 1911,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5385,
        "seat": 1,
        "action": 1911,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-443-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "script"
    ]
  },
  {
    "seed": 1362137956349,
    "candidate_seat": 0,
    "actions_checked": 168,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3420,
        "seat": 1,
        "action": 1353,
        "card": "RoyalHogs",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1284
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5670,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5675,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5680,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 5685,
        "seat": 1,
        "action": 1335,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              14.5,
              21.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-444-B-0.json",
    "index": 0,
    "arm_by_seat": [
      "B",
      "script"
    ]
  },
  {
    "seed": 1362137956349,
    "candidate_seat": 1,
    "actions_checked": 168,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 4925,
        "seat": 0,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4930,
        "seat": 0,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4935,
        "seat": 0,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 4940,
        "seat": 0,
        "action": 759,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              3.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-444-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "B"
    ]
  },
  {
    "seed": 1362137958367,
    "candidate_seat": 1,
    "actions_checked": 98,
    "action_replay_exact": true,
    "mismatches": [],
    "rejections": [
      {
        "tick": 3700,
        "seat": 0,
        "action": 1915,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              7.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      },
      {
        "tick": 3705,
        "seat": 0,
        "action": 1915,
        "card": "BombTower",
        "reproduced": true,
        "guard_class": "TimedExplosive.blocks_deployment",
        "guards": [
          {
            "guard": "is_deployment_payload_occupied",
            "blocker_type": "TimedExplosive",
            "blocker_name": null,
            "blocks_deployment": true,
            "blocker_position": [
              7.5,
              10.5
            ]
          },
          {
            "function": "deploy_card",
            "line": 1277
          },
          {
            "function": "apply_action",
            "line": 524
          }
        ]
      }
    ],
    "passed": true,
    "file": "pair-446-B-1.json",
    "index": 0,
    "arm_by_seat": [
      "script",
      "B"
    ]
  }
]
```

## Legality, candidate counts and role audits

PASS: every C56 candidate role/opponent train membership; b prior support

```json
{
  "candidate_illegal": 3,
  "opponent_illegal": 2,
  "candidate_rejected": 20,
  "opponent_rejected": 50,
  "matched_candidate_roots": 77381,
  "candidate_count_mismatches": 0,
  "non_deterministic_B_rejections": []
}
```

## Compute and execution

```json
{
  "host": "127x03",
  "gpu_used": false,
  "workers": 16,
  "threads_per_game": 2,
  "nice": 10,
  "torch_blas_threads": 1,
  "worker_cpus": "0-47 (three physical CPUs per worker)",
  "reserved_smt": "64-111",
  "headroom": "48-63,112-127",
  "execution": {
    "host": "127x03",
    "started_utc": "2026-10-09T00:14:08.597769+00:00",
    "ended_utc": "2026-10-09T01:10:47.857417+00:00",
    "wall_seconds": 3399.259669780731,
    "child_user_seconds": 62148.398462,
    "child_system_seconds": 102.61255,
    "peak_owned_processes": 65,
    "peak_pss_bytes": 14259475456,
    "stop_reason": null,
    "returncodes": [
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0
    ],
    "completed": true
  },
  "game_child_cpu_hours": 17.291947503333333,
  "execution_wrapper_cpu_hours": 17.347319444444445,
  "post_gate_verification_analysis_cpu_hours": 0.2829277777777778,
  "wrapper_cpu_hours_total": 17.630247222222227,
  "peak_gate_pss_GiB": 13.280171394348145,
  "resources": {
    "samples": 642,
    "max_load1": 21.3,
    "above_ceiling20": 322
  },
  "baseline": {
    "duration_seconds": 3400.6430151849054,
    "average_cores": 0.004158037152638659,
    "peak_5s_cores": 0.013956235528571097,
    "passed": true,
    "sampling": "5-second cumulative process CPU; exiting processes have unobserved final fractional interval; births counted in full when observed",
    "gate_outcomes_read": false,
    "service_affinity_changed": false
  },
  "wrapper_compute": [
    {
      "label": "imitation-gate-b-v1-r1",
      "log": "/mpac/sdicks02/jobs/clasher/imitation-gate-b-v1-r1.log",
      "exit": 0,
      "wrapper_pid": 268887,
      "wrapper_pid_present": false,
      "user_seconds": "62180.55",
      "system_seconds": "269.80",
      "wall_time": "56:41.13",
      "max_rss_kb": "1333124"
    },
    {
      "label": "gates-bc-b-verification-v1",
      "log": "/mpac/sdicks02/jobs/clasher/gates-bc-b-verification-v1.log",
      "exit": 0,
      "wrapper_pid": 762778,
      "wrapper_pid_present": false,
      "user_seconds": "736.71",
      "system_seconds": "6.21",
      "wall_time": "12:23.58",
      "max_rss_kb": "691800"
    },
    {
      "label": "gates-bc-b-spot-verification-v1",
      "log": "/mpac/sdicks02/jobs/clasher/gates-bc-b-spot-verification-v1.log",
      "exit": 1,
      "wrapper_pid": 767751,
      "wrapper_pid_present": false,
      "user_seconds": "25.13",
      "system_seconds": "0.74",
      "wall_time": "0:25.93",
      "max_rss_kb": "1347848"
    },
    {
      "label": "gates-bc-b-spot-verification-v2",
      "log": "/mpac/sdicks02/jobs/clasher/gates-bc-b-spot-verification-v2.log",
      "exit": 0,
      "wrapper_pid": 776591,
      "wrapper_pid_present": false,
      "user_seconds": "93.97",
      "system_seconds": "0.86",
      "wall_time": "1:13.90",
      "max_rss_kb": "1324392"
    },
    {
      "label": "gates-bc-b-analysis-v1",
      "log": "/mpac/sdicks02/jobs/clasher/gates-bc-b-analysis-v1.log",
      "exit": 0,
      "wrapper_pid": 800439,
      "wrapper_pid_present": false,
      "user_seconds": "7.02",
      "system_seconds": "0.64",
      "wall_time": "0:07.69",
      "max_rss_kb": "867224"
    },
    {
      "label": "gates-bc-b-legality-explanation-v1",
      "log": "/mpac/sdicks02/jobs/clasher/gates-bc-b-legality-explanation-v1.log",
      "exit": 0,
      "wrapper_pid": 803636,
      "wrapper_pid_present": false,
      "user_seconds": "144.94",
      "system_seconds": "2.32",
      "wall_time": "0:32.36",
      "max_rss_kb": "515048"
    }
  ],
  "release_utc": "2026-10-09T01:28:07.985887+00:00",
  "scope": "Gate execution (including its manager/baseline wrapper) and post-gate verification/analysis. Historical qualification and shared inventory/freezing work are separate preflight costs, not included or attributed to this gate. Historical evidence remains indexed in the sealed registration; partial 03 preflight accounting is receipts/compute-03-preflight.json. Child CPU and enclosing wrapper CPU overlap and must not be added."
}
```

## Failures and technical interruptions

```json
{
  "game_execution_failures": [],
  "technical_restarts": [],
  "completed_games_discarded": 0,
  "score_adjustments": 0,
  "load_pauses": {
    "ceiling": 20,
    "resource_sample_max_load1": 21.3,
    "worker_wait_records": 1190,
    "handling": "Pinned may_start loop paused new games above load1 20 in 5-second intervals. Running games completed unchanged; pauses overlap across workers and are not additive wall time.",
    "receipt": "load-pauses.json"
  },
  "verification_helper_failures": [
    {
      "label": "gates-bc-b-spot-verification-v1",
      "exit": 1,
      "reason": "Native search rejects an infinite verification deadline",
      "repair": "Use a finite one-hour budget only for originally completed prefix roots",
      "preserved": "spot-helper-v1.py, spot-helper-repair.json and original wrapper log/exit",
      "gate_bytes_changed": false
    }
  ],
  "verification_limit": "Original full candidate-list hashes and initial-state hashes were not logged. Direct original equality cannot be asserted. Coordinator accepted deterministic duplicate prefix checks with no adjusted score or decision-rule change (actual ~01:18Z).",
  "legality_flags": {
    "count": 5,
    "B": 3,
    "A": 0,
    "script": 2,
    "all_seat1": true,
    "decision_time_public_legal": true,
    "changed_after_seat0_application": true,
    "replayed_engine_rejections": 3,
    "replayed_engine_acceptances": 2,
    "passed": true,
    "receipt": "legality-apply-order.json",
    "interpretation": "Retained application-time audit flags. All commands were legal before either command was applied; seat0 applied first changes public mask for seat1. No score or decision-rule adjustment."
  }
}
```

## Frozen provenance

```json
{
  "gate": "b",
  "canonical_prereg_sha256": "7524a4e14c70bab4304acd996ac910330bfc3f56d9bee295e4e7b237514fc347",
  "frozen_prereg_sha256": "50823cd38a4406bd45839e6de083cd3d00cc74458c9fdd0e647fbbaf3ec36023",
  "manifest_sha256": "18f08db24a1474491c2a86e303f23dbe0f18ae834ca0d7692f2ebeca822ce858",
  "snapshot_tree_sha256": "016b42fac2c40614fa55a8bb859a80893f6bea91c189a350d2f34fb3bab1b907",
  "checkpoint_sha256": "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed",
  "selection_sha256": "1cbb2bf54c98dc570eb1715950f9ec21e9f4459560727bb4ac26c0d63789fc69",
  "release_sha256": "c8a44c8dcb04e07f582570bdf994e9c8c576c256f201a7f7b53de4b44412d3c5",
  "review_sha256": "f199e096c3574dc6b4bf256cccd4a8b82f37ead4cc4d42338ddf1cad9707cf06",
  "serving_temperature": 1,
  "dev_temperatures_provenance_only": [
    1.0635037422180176,
    1.1410114765167236,
    1.0741008520126343
  ],
  "namespace_commitment": "e730c9f1f71f4402b47a8dff2593e5b659c947fd7b0184c3cdeafa2799f49f50",
  "seed_base": 1359319908352,
  "seed_union_sha256": "c92f33839665d705e1579ae9f758c8ca621b895cefeab992f438d8d2752e58a8",
  "analysis_source_sha256": "8710ab6b5baa6b02761bae408e7d8e5e0ed215650917e25f7270e8fe108ad85a",
  "replay_source_sha256": "9ce5852e248c4848f4fca5cac27a33ec9d7b0ad0bdf6089fab14e1d1859430ef",
  "spot_helper_sha256": "2685b347d26b634cbada743a6460cd243c1db9d9ada966caa9bc2b339c6c8b13",
  "spot_receipt_sha256": "a11b3de6cec816f481a95aad52fc4e619ad506d996fe8f3197ab023c4daa18e6",
  "gate_a_outcome_material_used": false,
  "post_gate_receipt_sha256": {
    "statistics.json": "abb4ca0f593257a2329c02f9162d4f61dc70c52b34e6add1972672daf1a1eae4",
    "rejection-replay.json": "6dccfa4fec21d999de13501e0effa7ca29565a5540f8d3c34bad139645995579",
    "legality-apply-order.json": "ad4704cb6361c9709772375da6bed75090c8e08b5bfa153fc5fb20b633e65355",
    "spot-replay.json": "a11b3de6cec816f481a95aad52fc4e619ad506d996fe8f3197ab023c4daa18e6",
    "release-03.json": "4d5bd4f85a3458f7575acab38b159f4d256e62abb0c2061b17580e75035c1bd7"
  }
}
```

Machine-readable statistics: `imitation/gates-bc/receipts/gate-b-completion-v1/statistics.json`. All reported estimates and decision bars were fixed before gate games.

## Verification limits and supplemental prefix checks

The frozen receipts retain initial decks and seeds, actions, per-root candidate
counts and deadline completed/truncated flags. They do **not** retain original
full candidate-list hashes or an initial-state hash. Direct equality to those
unrecorded originals cannot be asserted. The coordinator explicitly accepted
this limitation and the checks below at actual ~01:18Z on 2026-10-09, with no
score adjustment, new gate games or change to the decision rule.

The fixed checks use the first primary world in both seats and the first
secondary world at B0/A0. Each stops before the first originally truncated root
(or at the terminal boundary when none was truncated). Two independent
replays passed, with exact original non-truncated actions and retained B
candidate counts. Each replay checked 1,434 decisions, 111 candidate lists and
six B candidate-count roots. Reconstructed full candidate-list hashes and
initial **public-state** hashes agree between the two replays. This establishes
replay consistency; it cannot establish equality to unlogged original hashes.
The complete gate-wide per-B-root count assertions are reported above.

| Fixed prefix | Stop (tick, seat) | Decisions per replay | Candidate lists per replay |
| --- | --- | --- | --- |
| pair-000-B-0.json | [120, 0] | 12 | 5 |
| pair-000-B-1.json | [120, 0] | 12 | 5 |
| pair-320-B-0.json | [100, 0] | 4 | 1 |
| pair-320-A-0.json | [3601, 0] | 1406 | 100 |

The initial helper attempt failed because native search rejects an infinite
deadline. Its source and failed wrapper receipt were preserved. The corrected
verification-only helper used a finite one-hour budget for roots that had
originally completed; frozen serving and analysis bytes were unchanged.

Receipts: `imitation/gates-bc/receipts/gate-b-completion-v1/spot-replay.json`,
`spot-summary.json`, `spot-helper-repair.json`. Future registrations should
record a full candidate-list hash per root and an initial-state hash per game.

Inference is conditional on the registered deck schedule (320 primary and
128 secondary eval-role worlds; zero eval_ood worlds; 42 distinct primary own
deck identities). No deck-population, eval_ood or mask-v2 generalization is
claimed. The primary design's approximate 80% MDE was +4.3 to +5.5 percentage
points under its stated decisive-fraction assumptions; a failed gate does not
exclude a smaller improvement. The secondary point bar is not a statistical
non-inferiority claim. No completed game, late decision or rejected command
was removed or adjusted.

## Decision thresholds and legality explanation

All registered bars passed: primary score 0.656250 ≥0.53 with paired 95% lower
bound 0.628125 >0.50; secondary B−A 0.050781 ≥−0.03; B had zero decisions over
250 ms and p99 200.286562 ms ≤ A p99 200.236560 ms +15 ms. Integrity passed:
every rejection reproduced under exact recorded-action replay and mapped to a
pinned known occupancy guard. All 77,381 retained B-root candidate-count pairs
match. Selection and serving remain the released EMA checkpoint at T=1.

The legality counters are application-time audits. All five flagged commands
(B:3, A:0, scripts:2) were issued by seat1. A descriptive recorded-action replay
of every affected game reproduced all flags and acceptance histories. Every
flagged command was public-mask legal before either seat's command was applied;
seat0's immediately preceding action made it mask-illegal at application time.
The engine rejected three and accepted two. No command, game or score was
excluded or adjusted. This explanation is a post-gate audit, not a new bar.
Detailed evidence: `imitation/gates-bc/receipts/gate-b-completion-v1/legality-apply-order.json`.

Gate execution used 3,399.260 seconds (56m39s) wall time and 17.292 child CPU
hours; the enclosing execution/monitor wrapper plus all retained verification
attempts and analysis used 17.630 CPU hours. These overlapping CPU measures
must not be summed. Peak gate summed PSS was 13.280 GiB. The report's compute
receipt gives exact measurements and the scope of preflight costs. All original
game receipts remain on03 under `confirmation-bc-v1/gate-b/games/`; only reports
and small receipts were mirrored to05. Host03 was released at
2026-10-09T01:28:07.985887Z after verification and analysis completed.
