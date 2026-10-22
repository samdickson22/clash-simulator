# Full synthetic CPU queue exposure

Pass on127x05 under R46's standalone method GO. Exact source9db1beeec023b25b2bccf31a5a3c23bfb55e9bc6,
Python aggregate6ad3e1e2775c4ce712cc90ea5a7a09f41e7ecf304b99da3b6b33ef427d78be78 and qualifier file
7a99592277bcf11bac53c88ec894c9355afcabec337a18adc4d3005fd4ec4fc6.

The single attempt started2026-10-22T22:05:14Z and completed in509.21 seconds under a900-second timeout.
Its timeout owner PID571379/start249648650/session571379 and Python child were verified exited; no owned
process survived. Admission had114.51GiB available/load4.01. Torch2.7.1, CUDA hidden, nice10 and one math thread.
The initial operator preflight used the wrong aggregate-hashing algorithm; it failed before any process or
output started. The reviewed canonical file-map digest matched before this actual attempt launched.

| Measurement | Result |
|---|---:|
| Synthetic rows | 262,144 |
| Simultaneously mapped chunks | 2,048 at128 rows each |
| Maximum entity/event/reveal axes | 256 /32 /16 |
| Queue bytes | 2,099,716,096 |
| Peak RSS | 2,652,229,632 bytes,2.47GiB |
| Mapped descriptors | 38,917 |
| Descriptors after close/drain | 5 |
| Conservative admitted disk bytes | 36,446,928,896 |
| Descriptor requirement | 39,168 |
| Soft/hard descriptor limits | 1,048,576 unchanged |
| Exit status | 0, queue empty |
| Engine games /experiment polls /optimizer steps | 0 /0 /0 |

Raw result, all2,048 content-bound receipts, operator launch/exit records and the pinned source are retained at
/mpac/sdicks02/jobs/clasher/rl-qualification-r46-20261022/queue-full-attempt1*.
Result SHA256 is1178152297c13a0412969e0392bb11ddb688b73d6b0bd9062d70709f931a057c.
The evidence index full-queue-evidence.json has SHAdb321ed8372a556beef1a387b865606191fe82e83d863ec1773c5a7ce37ffbda.

This passes the standalone maximum-axis host storage/mapping exposure. It does not measure32 real actors,
full PPO optimization, physical GPU memory, recycling or six-hour growth. R46's integrated driver remains
NO-GO pending its independent learner-failure and high-FD fixes. Reuse after an aggregate-source change needs
an unchanged-method composition check; it does not silently certify different queue code or a registered run.
