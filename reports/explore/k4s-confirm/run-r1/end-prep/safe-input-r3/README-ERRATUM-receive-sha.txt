recorded 2026-10-12T22:43:41Z by the runner: README.md §8 states receive_program_sha256() = 979b37a1…; the r3 bytes (safe_input.py 806e5ebb) produce
39a92e9d55f9ffefba57bae453677bad7c834f7761283268b84e40bb2d1210b4 (checked by the runner under /usr/bin/python3 3.8.10 and k4s-freeze 3.12.12, and by the S1b/S3/S9/S10 r2 author).
remote_program_sha256() = 2d2f212d73b49176c53b1a03a621b64fbc6a8d4c15bd18051ac31f91016a6152 as stated. Documentation error only; safe_input.py unchanged. Consumers pin 39a92e9d….
