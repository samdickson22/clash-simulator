# S100 versus M, fresh 1,600-case power comparison

The registered game rule favors M on the frozen v3 snapshot. This is a recommendation for Sam, not a change
to the default model or a deployment. S100 remains the configured default until Sam decides.

| Quantity | Result |
|---|---:|
| Assigned cases per size | 1,600 |
| Valid complete pairs | 1,592 |
| M minus S100, equal-controller-weight game score | +3.2506 percentage points |
| Paired 95% bootstrap interval | +0.1590 to +6.2677 points |
| Conservative all-assigned lower point | +2.7500 points |
| Conservative lower 95% interval | -0.3141 to +5.8125 points |
| Registered rule | Pass: complete-pair lower CI >0 and conservative lower point >0 |

The fresh bank alone determines this readout. The earlier 400-case result was inconclusive and is not pooled
with this extension. There was no optional stopping, replacement bank or retry.

Against LIVE-K4CW-r16-fp, all 800 assigned games per size are valid. S100 won 322/800, or 40.25%; M won 373/800,
or 46.625%, a +6.375-point difference. Against R3a, 792/800 games per size are valid. S100 won 391/792 and M
392/792, a +0.1263-point difference. There are no draws among these valid games, so game score equals win rate.
The pooled registered statistic weights the two controllers equally rather than weighting the 1,592 rows equally.

Both sizes failed on the same eight R3a cases: 898, 953, 958, 970, 1205, 1216, 1559 and 1585. They are frozen
opponent own-cycle exceptions. All remain in the conservative assigned-case accounting. No case was rerun.

The 64-worker expansion finished at 08:27:42Z after draining all 24 original workers between attempts. It used
the same evaluator, bank, checkpoints, runtime, levels and accounting. Exclusive case locks prevented overlap.
The legacy parent resumed automatically and its existing owner produced the comparison artifact.

M has 8,756,421 parameters versus S100's 2,102,597. Both pass the real Mac CPU latency budget over 20,000
production Session decisions per configuration. In the Canvasdoc-idle profile with replay emulators still
running, CPU4 p95/p99 was 9.764/26.039 ms for M and 6.069/12.809 ms for S100. CPU1 p95 was 15.955 ms for M
and 3.053 ms for S100. Both failed the 30 ms MPS p95 budget in that profile. Artifacts retain actual CPU/RSS
telemetry and shared-load labels; these are not measurements on an empty machine.

Broader held-out NLL favors M, 0.34782 versus S100's 0.35824, while Hog NLL and value Brier do not improve.
Games, rather than held-out loss, support the recommendation. Both-size 25/50/100% scaling and the independent
41,328-match snapshot comparison remain in progress. The latter trains both sizes regardless of this result.
Both-size RL remains separately gated on the complete harness, throughput/soak qualification and launch GO.

Evidence: `/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/comparison-power-v3.json` and its immutable
bank/manifests/rows. Bank SHA256 `f8a21c0e9a92b8f5fffffaf4b76d517092ee3f123a4eb9eac06604cc79a0b552`.
M checkpoint SHA256 `caa5f58ff250fdd689734ad80eb426e654ab4828ff4b08e655df7265e8486f7e`.
S100 checkpoint SHA256 `e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7`.
