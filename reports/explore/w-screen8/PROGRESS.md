# W-screen8 progress

Freeze `d0e9dc2f` pushed before games. Seed audit: no intersections, including helper offsets and W-confirm ranges.

03-only private job `/mpac/sdicks02/jobs/clasher/w-screen8-20261009-r1`; nice 10 / SCHED_IDLE, setsid. Six smoke games terminal; seed/seat/deck/queue checks pass. Reporting: 785/1,800 games complete at last census, combined processes 52 (cap 60). Raw games remain on 03; reporting source/binary pinned independently of production work.

Authorized quickwins/delay baseline committed/pushed `f9d3b454`. Fresh baseline build is byte-identical to build48 reference (71826488…). 47 tests pass; 1,000 terminal games / 7,000 traced rollouts and 1,000 d27 roots / 3,000 traces compare exactly. Resources config/meta/templates match.

W extension built into fresh `native-w-screen8-v1` (06d8e539…). 51 tests pass. OFF: 125 states × d0/d27 = 250 exact score/action/trace checks, digest identical to baseline. ON: 125/125 screen8 action and retained-score matches; expired-deadline fallback passes on every state. No prohibited files changed; no runtime wiring patch needed. Default OFF. Implementation commit pending; outcome reduction waits for all games.
