# ELT diagnosis

No ELT code was changed. Permanent loss below means unrecovered by the last decision; it is right-censored, not proof of impossibility of future recovery. Event associations are descriptive and cannot establish individual-event causation.

## Findings and interpretation

The evidence supports three distinct problems; they should not be collapsed into a single “lost concentration” event.

1. **Fully known hand concentration never occurs in noisy ELT:** 0/256 A+derived games ever report it, including all 11 games with no missed/spurious/confused labels. There is therefore no observed initial concentrated hand to lose in these games. The code's hand diagnostic requires every retained branch, even a tiny-weight branch, to have the same fully resolved hand (`elt.py`, `distribution`). It is much stricter than a 90%-mass hypothesis. Unresolved initial deck/order support also matters: even perfect-event R-events becomes hand-concentrated in only 76/256 games, with 15.9% of S1-sampled decisions concentrated. A “never concentrated” result alone is not proof that one bad event destroyed a previously correct hand.
2. **Resource coverage can recover, then fail again:** among 245 A+derived games with a categorical error, all have a bad sample at or after the first error, 230 later recover coverage at least once (93.9%), and 109 finish in an unrecovered coverage episode. Seventy-seven are already uncovered at the last decision before their first categorical error. All 11 no-categorical-error games also experience a coverage failure; only one finishes uncovered. Delivery delay and the fixed arrival-minus-two-tick estimate remain noisy in those games, so they are not perfect-timestamp controls. The first bad sample after the first categorical error has median lag two ticks (100 ms); this does not imply every loss begins at that error.
3. **Missed spends are the most common preceding error for terminal coverage loss:** the 109 terminal episodes have most recent preceding errors of missed=87, spurious=18, confused=4. These are descriptive associations, not isolated causal counts. ELT inserts a latent missed play only to repair a cycle contradiction, not on every unobserved spend, and does not repair an insufficient-elixir branch by adding a missed spend. Its 128-hypothesis beam has no periodic resynchronisation/reset. These code facts are consistent with long-lived resource-ledger errors after a miss.

The ≥90%-mass-hypothesis criterion is separate: it is already false immediately before the first categorical error in 140/245 error games; 70 recover it later, but 225 finish without it. All 11 no-categorical-error games lose it at some point and 10 finish without it. Acceptance/rejection uncertainty under q<1 therefore remains relevant even when emitted card labels happen to be correct.

**Perfect-event control:** R-events has zero elixir error and 100% interval coverage at every traced decision, never loses ≥90% hypothesis concentration, and reproduces R-derived's terminal actions in all 256 games. Exact timestamps and q=1 are supplied together here; this control does not separate identity/recall errors from event timing or confidence calibration. The primary decomposition also substitutes ELT for Full's legacy posterior in this cell, as explicitly frozen in PREREG.md.

### Concrete trace evidence

| Job | Preceding categorical error | Start of terminal uncovered episode | Last observed decision |
| --- | --- | ---: | ---: |
| 16 | Missed Goblin Barrel at tick 2970 | 2972 | 5846 |
| 101 | Spurious Inferno Tower delivered at tick 4889 | 5056 | 5114 |
| 885 | Skeletons confused as Firecracker, delivered at tick 2754 | 3000 | 4712 |

Job 16 is the clearest immediate missed-spend example. At tick 2970 truth elixir is 3.069 and lies in [3.069, 8.069]. After the missed three-elixir Goblin Barrel, tick 2972 truth is 0.1404 but the interval is [3.1404, 8.1404]; it remains uncovered through tick 5846 (143.7 seconds from the first uncovered sample). The latter two examples have intervening time, so their event labels should not be read as demonstrated sole causes. Exact snapshots and event IDs are retained in completion-audit.json and elt-evidence-examples.json; full traces remain on 01.

The hand “terminal loss preceding type” counts in the frozen tables below describe persistent absence of concentration after the first error; they are **not** evidence that those errors caused hand concentration to disappear, since noisy ELT was never hand-concentrated. “Permanent” elsewhere means no recovery through the last recorded decision, not impossibility of future recovery.

No ELT implementation was changed. This diagnosis identifies the strict unanimity diagnostic, incomplete missed-spend recovery, finite beam, and event timing/confidence assumptions as distinct follow-up questions; it does not test a repaired tracker.

## A+derived

| Metric | Ever good | Error games | Already bad before first error | Later recovery | Unrecovered at end |
| --- | ---: | ---: | ---: | ---: | ---: |
| covered | 256 | 245 | 77 | 230 | 109 |
| hand_concentrated | 0 | 245 | 233 | 0 | 245 |
| hypothesis_concentrated | 256 | 245 | 140 | 70 | 225 |

Preceding error types and representative per-game evidence:

```json
{
  "metrics": {
    "covered": {
      "counts": {
        "games": 256,
        "ever_good": 256,
        "corrupt_event_games": 245,
        "already_bad_before_first_error": 77,
        "bad_after_first_error": 245,
        "later_recovered": 230,
        "unrecovered_at_end": 109,
        "no_corrupt_event": 11,
        "no_corrupt_event_ever_bad": 11,
        "no_corrupt_event_bad_at_end": 1
      },
      "terminal_loss_preceding_event_types": {
        "missed": 87,
        "spurious": 18,
        "confused": 4
      },
      "first_loss_lag_ticks_median": 2.0
    },
    "hand_concentrated": {
      "counts": {
        "games": 256,
        "ever_good": 0,
        "corrupt_event_games": 245,
        "already_bad_before_first_error": 233,
        "bad_after_first_error": 245,
        "later_recovered": 0,
        "unrecovered_at_end": 245,
        "no_corrupt_event": 11,
        "no_corrupt_event_ever_bad": 11,
        "no_corrupt_event_bad_at_end": 11
      },
      "terminal_loss_preceding_event_types": {
        "missed": 110,
        "spurious": 125,
        "confused": 10
      },
      "first_loss_lag_ticks_median": 0.0
    },
    "hypothesis_concentrated": {
      "counts": {
        "games": 256,
        "ever_good": 256,
        "corrupt_event_games": 245,
        "already_bad_before_first_error": 140,
        "bad_after_first_error": 245,
        "later_recovered": 70,
        "unrecovered_at_end": 225,
        "no_corrupt_event": 11,
        "no_corrupt_event_ever_bad": 11,
        "no_corrupt_event_bad_at_end": 10
      },
      "terminal_loss_preceding_event_types": {
        "missed": 115,
        "spurious": 102,
        "confused": 8
      },
      "first_loss_lag_ticks_median": 1.0
    }
  },
  "examples": [
    {
      "job": 16,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 2970,
        "arrival_tick": null,
        "truth_name": "GoblinBarrel",
        "seen_name": null,
        "event_id": "26-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 2970,
        "arrival_tick": null,
        "truth_name": "GoblinBarrel",
        "seen_name": null,
        "event_id": "26-miss"
      },
      "first_loss_tick": 2972,
      "recovered": false,
      "terminal_loss_tick": 2972,
      "last_decision_tick": 5846
    },
    {
      "job": 17,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 450,
        "arrival_tick": null,
        "truth_name": "GoblinBarrel",
        "seen_name": null,
        "event_id": "4-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 1032,
        "arrival_tick": null,
        "truth_name": "GoblinGang",
        "seen_name": null,
        "event_id": "8-miss"
      },
      "first_loss_tick": 452,
      "recovered": true,
      "terminal_loss_tick": 2406,
      "last_decision_tick": 6000
    },
    {
      "job": 73,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "spurious",
        "truth_tick": 562,
        "arrival_tick": 564,
        "truth_name": null,
        "seen_name": "Earthquake",
        "event_id": "6-fp0"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 1798,
        "arrival_tick": null,
        "truth_name": "Berserker",
        "seen_name": null,
        "event_id": "16-miss"
      },
      "first_loss_tick": 564,
      "recovered": true,
      "terminal_loss_tick": 2364,
      "last_decision_tick": 5292
    },
    {
      "job": 100,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "spurious",
        "truth_tick": 676,
        "arrival_tick": 679,
        "truth_name": null,
        "seen_name": "IceSpirit",
        "event_id": "7-fp0"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 5986,
        "arrival_tick": null,
        "truth_name": "Berserker",
        "seen_name": null,
        "event_id": "104-miss"
      },
      "first_loss_tick": 734,
      "recovered": true,
      "terminal_loss_tick": 5988,
      "last_decision_tick": 6000
    },
    {
      "job": 101,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 2032,
        "arrival_tick": null,
        "truth_name": "Log",
        "seen_name": null,
        "event_id": "20-miss"
      },
      "preceding_error": {
        "kind": "spurious",
        "truth_tick": 4886,
        "arrival_tick": 4889,
        "truth_name": null,
        "seen_name": "InfernoTower",
        "event_id": "69-fp0"
      },
      "first_loss_tick": 2034,
      "recovered": true,
      "terminal_loss_tick": 5056,
      "last_decision_tick": 5114
    },
    {
      "job": 128,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 112,
        "arrival_tick": null,
        "truth_name": "ElectroSpirit",
        "seen_name": null,
        "event_id": "2-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 3334,
        "arrival_tick": null,
        "truth_name": "Skeletons",
        "seen_name": null,
        "event_id": "36-miss"
      },
      "first_loss_tick": 114,
      "recovered": true,
      "terminal_loss_tick": 3336,
      "last_decision_tick": 6000
    },
    {
      "job": 157,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 2534,
        "arrival_tick": null,
        "truth_name": "Skeletons",
        "seen_name": null,
        "event_id": "23-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 2660,
        "arrival_tick": null,
        "truth_name": "Log",
        "seen_name": null,
        "event_id": "26-miss"
      },
      "first_loss_tick": 2536,
      "recovered": true,
      "terminal_loss_tick": 3400,
      "last_decision_tick": 6000
    },
    {
      "job": 184,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 182,
        "arrival_tick": null,
        "truth_name": "Skeletons",
        "seen_name": null,
        "event_id": "2-miss"
      },
      "preceding_error": {
        "kind": "spurious",
        "truth_tick": 5390,
        "arrival_tick": 5397,
        "truth_name": null,
        "seen_name": "Wallbreakers",
        "event_id": "70-fp0"
      },
      "first_loss_tick": 184,
      "recovered": true,
      "terminal_loss_tick": 5690,
      "last_decision_tick": 6000
    },
    {
      "job": 212,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 338,
        "arrival_tick": null,
        "truth_name": "ElectroSpirit",
        "seen_name": null,
        "event_id": "5-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 4886,
        "arrival_tick": null,
        "truth_name": "Skeletons",
        "seen_name": null,
        "event_id": "67-miss"
      },
      "first_loss_tick": 340,
      "recovered": true,
      "terminal_loss_tick": 5112,
      "last_decision_tick": 6000
    },
    {
      "job": 240,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 3642,
        "arrival_tick": null,
        "truth_name": "BlowdartGoblin",
        "seen_name": null,
        "event_id": "38-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 5018,
        "arrival_tick": null,
        "truth_name": "Wallbreakers",
        "seen_name": null,
        "event_id": "60-miss"
      },
      "first_loss_tick": 3644,
      "recovered": true,
      "terminal_loss_tick": 5242,
      "last_decision_tick": 6000
    },
    {
      "job": 241,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 178,
        "arrival_tick": null,
        "truth_name": "ElectroSpirit",
        "seen_name": null,
        "event_id": "2-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 178,
        "arrival_tick": null,
        "truth_name": "ElectroSpirit",
        "seen_name": null,
        "event_id": "2-miss"
      },
      "first_loss_tick": 180,
      "recovered": true,
      "terminal_loss_tick": 708,
      "last_decision_tick": 6000
    },
    {
      "job": 296,
      "metric": "covered",
      "first_corrupt_event": {
        "kind": "missed",
        "truth_tick": 90,
        "arrival_tick": null,
        "truth_name": "HogRider",
        "seen_name": null,
        "event_id": "0-miss"
      },
      "preceding_error": {
        "kind": "missed",
        "truth_tick": 4812,
        "arrival_tick": null,
        "truth_name": "Skeletons",
        "seen_name": null,
        "event_id": "72-miss"
      },
      "first_loss_tick": 92,
      "recovered": true,
      "terminal_loss_tick": 4814,
      "last_decision_tick": 6000
    }
  ]
}
```

## R-events

| Metric | Ever good | Error games | Already bad before first error | Later recovery | Unrecovered at end |
| --- | ---: | ---: | ---: | ---: | ---: |
| covered | 256 | 0 | 0 | 0 | 0 |
| hand_concentrated | 76 | 0 | 0 | 0 | 0 |
| hypothesis_concentrated | 256 | 0 | 0 | 0 | 0 |

Preceding error types and representative per-game evidence:

```json
{
  "metrics": {
    "covered": {
      "counts": {
        "games": 256,
        "ever_good": 256,
        "no_corrupt_event": 256,
        "no_corrupt_event_ever_bad": 0,
        "no_corrupt_event_bad_at_end": 0
      },
      "terminal_loss_preceding_event_types": {},
      "first_loss_lag_ticks_median": null
    },
    "hand_concentrated": {
      "counts": {
        "games": 256,
        "ever_good": 76,
        "no_corrupt_event": 256,
        "no_corrupt_event_ever_bad": 256,
        "no_corrupt_event_bad_at_end": 180
      },
      "terminal_loss_preceding_event_types": {},
      "first_loss_lag_ticks_median": null
    },
    "hypothesis_concentrated": {
      "counts": {
        "games": 256,
        "ever_good": 256,
        "no_corrupt_event": 256,
        "no_corrupt_event_ever_bad": 0,
        "no_corrupt_event_bad_at_end": 0
      },
      "terminal_loss_preceding_event_types": {},
      "first_loss_lag_ticks_median": null
    }
  },
  "examples": []
}
```

## Code mechanisms to compare with the traces

ELT only inserts one latent missed play when an observed play is rejected for a cycle contradiction. It does not branch on missed spends after every gap and cannot repair an insufficient-elixir rejection by inserting a spend. Accepted/rejected event branches are truncated to a 128-hypothesis beam. Hand concentration in distribution() requires every retained branch to report the same fully resolved hand, regardless of its weight. Consequently a 90%-mass hypothesis is not the same criterion as a concentrated hand. No periodic reset or resynchronisation exists. The noisy adapter also estimates execution time as arrival minus two ticks; timing error can therefore precede the first missed/spurious/confused event.

R-events uses exact event identities/timestamps when configured as the perfect-event ELT control. This separates event corruption from remaining finite-prior ambiguity; exact public state can remain unconcentrated without any tracking failure. Consult PREREG.md for the frozen tracker convention.
