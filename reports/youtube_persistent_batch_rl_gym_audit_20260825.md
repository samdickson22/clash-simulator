# Persistent YouTube batch RL-gym audit (2026-08-25)

Read-only command:

```bash
uv run python scripts/audit_youtube_rl_gym_corpus.py \
  /Users/sam/Desktop/code/clasher/datasets/derived/tv_royale_youtube_persistent_batch_causal_clocked_20260825 \
  --format markdown
```

The audited root contains 29 match directories and 76,148 neutral frames. All
29 match IDs are distinct, observed frame counts equal manifest declarations,
and scanned signal counters equal the manifests.

| Signal or target | Valid | Total | Coverage | Availability |
| --- | ---: | ---: | ---: | --- |
| Typed entity identity | 618,747 | 754,033 | 82.06% | available |
| Entity HP | 364,898 | 754,033 | 48.39% | available |
| Resolved absolute-world position | 699,631 | 754,033 | 92.79% | available |
| Public clock | 65,285 | 76,148 | 85.73% | available |
| Complete offline action identity + placement | 241 | 4,078 | 5.91% | available |
| Offline action identity | 241 | 4,078 | 5.91% | available |
| Offline action placement | 4,078 | 4,078 | 100.00% | available |
| Entity status target | 0 | 754,033 | 0.00% | unavailable |
| Projectile target | 0 | 754,033 | 0.00% | unavailable |

Resolved positions have mean confidence 0.885822, median 0.959320, p10
0.619913, and p90 0.976947. Every frame declares `absolute_world`; no non-null
position is malformed and no resolved position lacks confidence.

The corpus exposes 918 offline actor targets. Action labels remain offline-only.
Status is unavailable because every detection reports
`no_calibrated_status_head`; projectile targets are unavailable because every
detection reports `no_projectile_target_head`. These zero-coverage targets must
remain explicit missing supervision rather than inferred negative labels. This
is an RL-gym validation inventory, not authorization to start or scale training.
