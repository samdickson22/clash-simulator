# Persistent Prime TV Royale batch

- Pod: `bcf08d325ee54e2284d8f94e7b576e97`
- Name: `clasher-persistent-data`
- Shape: 2× NVIDIA L40 48 GB, 26 vCPU, 144 GB RAM, 1.25 TB disk
- Rate: $1.72/hour
- Provider: Massed Compute, US Central
- Remote checkout: `/home/ubuntu/clasher`
- Driver PID at launch: `7274` (wrapper shell `7272`)
- Driver: `scripts/run_tv_royale_persistent_l40_batch.sh`
- First batch: 40 recent replay-disjoint channel videos
- Concurrency: six acquisition workers; six semantic workers, three per GPU
- Acquisition format policy: exact native 1182×2560 format 308, else supported
  886×1920 format 303, else typed skip
- Lifecycle policy: keep the pod active after each batch; do not terminate it as
  part of normal batch completion

The driver publishes each source and semantic match atomically. A completed
manifest is the resume marker; reruns skip it. Partial files are never treated
as training data.

Connection command:

```bash
ssh -i ~/.ssh/id_ed25519_prime_clasher ubuntu@216.81.248.173
```

Status command:

```bash
ssh -i ~/.ssh/id_ed25519_prime_clasher ubuntu@216.81.248.173 \
  'cd /home/ubuntu/clasher; find datasets/external/persistent_batch_v1 \
  -mindepth 2 -maxdepth 2 -name manifest.json | wc -l; find \
  datasets/derived/persistent_batch_v1 -mindepth 2 -maxdepth 2 \
  -name manifest.json | wc -l; nvidia-smi'
```
