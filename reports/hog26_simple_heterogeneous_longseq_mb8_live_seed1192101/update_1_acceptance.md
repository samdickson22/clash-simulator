# Long-sequence mb8 update-one acceptance

Date: 2026-08-29

Checkpoint:
`checkpoints/hog26_simple_heterogeneous_longseq_mb8_live_seed1192101/policy_v2_update_000001.pt`

The first complete 64-decision PPO update passed the technical gate:

- learner transitions: 4,096
- collection: 106.714 seconds
- learning: 10.010 seconds
- end-to-end throughput: 35.091 transitions/second
- loss / policy / value: -0.002755 / -0.000887 / 0.002610
- entropy: 0.613438
- gradient norm: 0.393803
- anchor-policy KL: 0.000528
- PPO approximate KL: 0.000553
- clip fraction: 0.005981
- play rate: 0.130859
- no-op when playable: 0.028986
- all numeric metrics finite

Persisted metadata retains the exact Simple PyTorch backend, eager MPS
execution, public-action-mask v2, `objective-v1-gamma-v1` reward, current
494-token vocabulary, supported-deck digest, paired learner-only schedule, and
the exact parent SHA-256.  No simulator or optimizer state was inherited from
the parent.

This accepts runtime/memory/gradient viability only.  It makes no gameplay or
promotion claim.  The first paired gameplay screen remains update 15.
