# Troop-badge rejection in tower OCR

An enemy troop's level-5 badge overlapping a hidden king tower was accepted as HP 5 for about 22 seconds in s28-m03, leading to a Fireball at the king. The source is the screen OCR reader.

The fix rejects compact red badge components during number reading. If any component is rejected, the whole number is unreadable rather than becoming a shorter HP value. TowerReader is identical to the deployed baseline: no reset-to-full, first-read, confirmation, death, maximum-HP or occlusion behavior changes. Existing digit templates are unchanged.

Exact base SHA256: `8209787893f0bc19cddcf174d78acfae004b197fcc65dd0e9ead64e6a34ecc3c`. Reviewed source: `58033f080ecafe1f80d45e43c287253cd0ebd5010f04de695f3cad060edbfdf4`. Final hardened test: `0ce1bc711f2ace46b88c9950b10ce84914b680beb0375573b3356ddc814d6c69`.

Fresh independent Sol review returned GO for exact source bytes. It reran 12 badge and 10 guard checks, verified all 796 baseline HP readings unchanged and all four actual normalized regression badges rejected, checked 127 king readings including damaged kings, brightness gains 0.6–1.25, and 3,007 forced component rejections without shortened numbers. Two nonblocking test weaknesses were then hardened (require all five recordings and require rejected HP 5 to become None); final hardened badge checks passed 13/13. Source bytes stayed unchanged. Normalization is extracted from the actual driver; artificial brightness offsets are used only to reproduce the old fault.

The badge heuristic remains scene-dependent; the reviewed corpus supports this bounded repair and does not prove general segmentation accuracy. One-thread 05 timing was median/p95 4.084/5.846 ms versus baseline 3.108/3.684 ms; live decision latency remains subject to the existing gate.

Sole-babysitter deployment at a normal boundary changes only towers.py after exact base and backup checks. Keep the same model, driver settings, deck and launcher. First-battle evidence should check hidden king HP, genuine damaged readings, decision latency and errors from the primary recording. Rollback restores only the exact base towers.py backup at a safe boundary.
