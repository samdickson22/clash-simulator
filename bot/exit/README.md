# bot/exit host tools (exploration)

- `cpu_job.sh N CMD...`: run CMD once the host has room for N python processes under the 105 cap (`cpu_room.sh`), holding a lease for N.
- `cpu_room.sh N [CAP]`: block, or check once with BOT_CPU_TRY=1, until the host has room. It counts live python, leased-idle room and waiting claims.
- `cpu_feeder.sh`: overlapping ExIt generation batches.
- `filler.sh STATE [TARGET=95] [CAP=105]`: a standing low-priority filler, one per host, run detached.
  - Each block is one queue line, `<workers ≤12> <group> <command>`.
  - It launches the next line as `cpu_job.sh workers+1 nice -n 19 …` only when no job is waiting for admission and live + leased-idle + block ≤ TARGET.
  - Blocks in one group run serially.
  - Queues for the full-pool owner's content (K1 recording, then leaf/value data) come from `bot/fullpool/run/filler_queue.py`.
  - STATE/STOP stops new launches.
