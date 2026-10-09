# Operational amendment09: home memory and CPU placement

Coordinator decision labeled23:35Z, received2026-10-08 23:30Z. On home01/02/03/04/08, use MemAvailable >=24GB, including a conservative launch reserve, instead of the shared-host64GB summed-PSS cap. Lease hosts retain64GB summed PSS and all current process/console/GPU/nice/load limits.

CPU scoring and the decoder equality verifier move off01 to09 under the unchanged shared lease wrapper v2.01 remains storage/cache source. R17 continues to exclude03 CPU grids.08 CPU is allowed only while its GRU GPU remains >=80% and home memory headroom holds; no08 GPU before05:00.

The CPU guard uses6GB launch memory reserve. A separate prepared home GPU guard uses8GB launch reserve and the same24GB runtime floor. It permits02,04before04:30,08from05:00;07 requires a future explicit release.04combined cap90. Existing pinned GPU code is not edited in place; the historical conservative guard stays until a clean operational recovery boundary. No model, labels, thresholds, split, evaluation or inference numerics change. All failed/backed-off attempts and partial outputs are retained.
