# Width-480 microbatch repair after allocator OOM

2026-10-09 20:43Z, explicitly authorized by coordinator at 20:42Z, before any
width-480 dev outcome. Scientific freeze 841c44b0 remains the historical plan.
Width 288 and 384 continue with their original configs; their fits are untouched.

The full width480-v2 traceback confirms torch.OutOfMemoryError in the encoder
FFN dropout: a 1.41 GiB allocation could not fit the 37.08 GiB allocator allowance
(0.78 of the GPU), despite 9.68 GiB physical memory free. Last successful update
was step598 / 4,898,816rows. The latest saved checkpoint is step175 /
1,433,600rows, SHA91c66427e0c23ce7d2d2d519a7e2dcffc8a4b449d33219adf8f3e5b86f29ebba.
All six previous processes have exited and GPU15 is idle. Complete traceback,
exit receipt and checkpoint pointers are retained in `480-micro2048-oom.json`.

Resume the same model, EMA, optimizer, scheduler, RNG and sampler cursor from
step175. Change only width480 microbatch2048 to1024, retaining effective batch8192
through eight accumulated microbatches and the same effective-batch loss
denominators. This preserves the mathematical batch objective; summation order
and dropout draws can differ, so it is not bit-identical. Work176–598 is replayed.
The seed, data, architecture (480/6heads), optimizer, learning-rate schedule,
quarter boundary95,144,680rows, full-dev scoring and gain<0.005 kill rule remain
fixed. Frozen T11 trainer files are not modified. Allocator cap0.78, ≥8GiB free,
48GBPSS, ≤16processes and nice≥10 remain mandatory.

The original `configs/width-480.json` and `freeze.json` remain archived unchanged.
The new `configs/width-480-micro1024.json` is pinned by
`freeze-480-micro1024.json`, deployed only on15. Both are committed and pushed
before the new detached `width480-v3` launch. Controller active-label history
continues to account for every failed, paused and resumed segment.

If this micro1024 run also cannot fit under the lease limits, stop width480 as
**infeasible under lease limits**, preserve its artifacts and report288/384 only.
That disposition is not a scientific NLL kill and requires no further recipe
adjustment. The final report must disclose this microbatch amendment.
