# Clasher coordinator: PROGRESS (new tree, from 2026-10-18)

Coordinator thread: b4f05b1c-9d3a-4e38-a58a-98ab4407fa25 (Opus). Created 2026-10-18T02:32Z.
The old coordinator 0523ae6f and its 1,403 descendants plus 47 schedules were deleted on 2026-10-18 ~00:40Z (soft delete).
Archive: /mpac/sdicks02/clasher-archive/old-coordinator-0523ae6f-20261018/ (transcripts, subagents, schedules, Sam's messages with the key redacted).
State snapshot: reports/coordinator/STATE-SURVEY-20261018.md. Readouts: reports/coordinator/readouts/.

## Direction (Sam)
- BOT-FIRST: the strongest bot, judged by reports/bot/HEADLINE.md. LIVE: play the real ladder.
- 10-17/18: read-only memory OK for play, capped to what ClashAI/Hasty-CR feed; never the opponent's hand/next card/elixir. Go straight to memory on MuMu. BlueStacks retired.

## Standing rules
Sol (gpt-6.1-sol high) for watching, scoring, reviews, images and mechanical work; Opus only code and decisions; no Opus polling.
Say less: results, failures, decisions only. Thread sends steer, then auto; never queue.
No sealing; no hard-coded cases. Max card levels for play-quality tests. Force a break between battles to load a fix. Pacific time for Sam.
Commit via temp index plus clasher-secret-scan. 05 light-only; 09–18 roader; 03 down.

## Active agents (new tree)
| Role | Model | childThreadId suffix |
|---|---|---|
| CARD live16402d gate watch + publish | Sol | clasher-card-publish-sol-20261018-r1 |
| BOT + perception results collector (until ≥07:00Z) | Sol | clasher-results-collector-sol-20261018-r1 |
| LIVE owner: MuMu memory route, stream, ladder | Opus | clasher-live-memory-owner-opus-20261018-r1 |
Full ids: thread:delegated-task:command%3Amcp%3Ad79ecf9a-f2cb-43db-9495-7693a64ee564%3Adelegate-task%3A<suffix>

## Not restarted on purpose
No BOT lead and no CARD lead: detached jobs keep running, and the collector reports results. The coordinator decides the next BOT experiments from those readouts.
No hourly heartbeat schedule (it would run Opus turns); the collector checks utilisation hourly.
