# YouTube full-match event visual QA — hTG8dM4KtM4

Date: 2026-08-17

This is a manual source-frame spot check of every event marked `play_valid=true`
in the first semantic publication (`manifest.json` SHA-256
`e2412d20e32905547040fe8fbb6fbdb1c20fba73368a5b036c5d747e5ae158fa`).
It is separate from the structural contract verifier.

The 3-by-5 contact sheet is
`reports/tv_royale_youtube_fullmatch_event_qa_hTG8dM4KtM4_20260817.jpg`,
SHA-256 `3a47ec97e9d21ca73f2ba08a1199ff4ca34383aab8989f63ed9268d9469eefb7`.
Cells are chronological, left-to-right and then top-to-bottom.

| Cell | Event | Source ms | Extracted identity | Visual QA |
| ---: | --- | ---: | --- | --- |
| 0 | event-00029 | 35,800 | Tornado | Visually plausible, but part of the same persistent Tornado as cell 1. |
| 1 | event-00030 | 36,200 | Tornado | Duplicate: only 400 ms after cell 0 while the same effect remains visible. |
| 2 | event-00058 | 98,700 | BabyDragon | Plausible. |
| 3 | event-00075 | 135,800 | BabyDragon | Plausible. |
| 4 | event-00086 | 145,000 | Barbarians | Reject: not in the visibly observed bottom deck; the recognizer confuses the Knight or Barbarian Barrel family. |
| 5 | event-00112 | 181,900 | RoyalRecruits | Plausible. |
| 6 | event-00125 | 202,300 | DartBarrell (Flying Machine) | Plausible. |
| 7 | event-00132 | 204,600 | Tornado | Plausible. |
| 8 | event-00141 | 211,100 | Tombstone | Plausible. |
| 9 | event-00147 | 214,800 | BabyDragon | Plausible. |
| 10 | event-00149 | 215,600 | Arrows | Plausible; arrows are directly visible. |
| 11 | event-00170 | 240,700 | BabyDragon | Plausible. |
| 12 | event-00178 | 246,800 | MegaMinion | Reject: impossible one-off top-deck identity; only four valid hand observations in the entire replay. |
| 13 | event-00187 | 256,400 | MiniPekka | Reject: impossible one-off top-deck identity; only one valid hand observation in the entire replay. |
| 14 | event-00192 | 260,200 | RoyalHogs | Plausible. |

Result: 11 labels are visually plausible, one is a duplicate, and three have
invalid or ambiguous card identity. The initial 15-event count must not be
reported as 15 correct actions. Postprocessing should fail closed on rare
out-of-deck hand identities, suppress same-player marker duplicates inside a
short refractory window, and leave the ambiguous bottom card unlabeled.

## Filtered v2 recheck

The event-filtered v2 publication applies a 1,500 ms unconditional same-player
refractory window, requires at least 100 same-player hand observations for the
card family, and requires a public elixir drop within one second whose cost
error is at most one elixir. It retains seven complete card-and-tile plays:
The final corrected v2 manifest SHA-256 is
`709796d31cc1b27af4e115e7ea563d4eaf6b6a05a7cd8243b1a44a62db3d6054`.

| Cell | Source ms | Player | Identity | Visual QA |
| ---: | ---: | ---: | --- | --- |
| 0 | 98,700 | 0 | BabyDragon | Plausible. |
| 1 | 135,800 | 0 | BabyDragon | Plausible. |
| 2 | 181,900 | 1 | RoyalRecruits | Plausible. |
| 3 | 215,600 | 1 | Arrows | Plausible; arrows are directly visible. |
| 4 | 240,700 | 0 | BabyDragon | Plausible. |
| 5 | 249,500 | 1 | DartBarrell (Flying Machine) | Plausible. |
| 6 | 260,200 | 1 | RoyalHogs | Plausible; the deployed hog group is directly visible. |

All seven filtered labels are visually plausible in their exact source frames.
The second 4-by-2 contact sheet is
`reports/tv_royale_youtube_fullmatch_eventfiltered_v2_qa_hTG8dM4KtM4_20260817.jpg`,
SHA-256 `330a7048a075cc278501104e24f4b3bb14d78509f8da83bfa4689ae2191da35b`.
The eighth cell is intentionally blank.
