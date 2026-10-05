# Host GPU reference check

The existing isolated AVD now runs with the emulator's documented `-gpu host` renderer. The installed native reference, content attestation and probe are unchanged. No gameplay evidence was collected under a new readiness claim during this check.

The full attestation matched the pinned digest. Replaying 59 already-recorded commands reproduced all checked ordinary gameplay fields at native tick 3090: objects, players, clock, terminal flag and winner. The prior SwiftShader process 66877 was stopped after recording ownership and idle suspension; the new owned process is 39106. Startup and stop receipts are retained.

Six verified-session level reads at that fixed frame had median latency 0.338 seconds, compared with the earlier SwiftShader session median 0.564 seconds. Three rich-frame reads took about0.075–0.087 seconds. All six level results agreed. CPU use in the sampled process report was about 110%, compared with roughly 700% for the earlier software renderer. These are bounded observations under changing host load, not an isolated hardware benchmark or full-game throughput measurement.

The host renderer uses more memory: sampled resident size was 3.37 GB. The emulator remains paused at 3090 and available for the next explicitly owned development prefix check. It has no active collector.
