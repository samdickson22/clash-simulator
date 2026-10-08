# Android emulator without KVM on 127x04

Measured on 2026-10-07 PDT (2026-10-08 UTC). **Draft: the clean eight-vCPU test is still running.**

The stock emulator can boot without KVM, but the completed measurements do not support Clasher's requirement of real-time game rendering with 20 FPS capture. The first four-vCPU Settings workload rendered 7 frames in 45.570 host seconds: **0.154 FPS**, about **130 times below 20 FPS**. Its frame-timing histogram reported a 1,250 ms median, against a 50 ms frame budget. This is a Settings measurement, not a game benchmark.

All emulator work ran over `ssh 127x04`, after `source /mpac/sdicks02/env.sh`. 127x05 only orchestrated SSH, collected small receipts, and wrote this report. No game APK, private-server client, Mac artifact, or other fleet host was used. Downloads went only to Google's SDK repository. Emulator/ADB processes ran inside an unprivileged user/network namespace with loopback enabled and no external network interfaces, so guest background services and emulator update checks could not contact the internet.

The initial `who` output was empty. Hardware was Ubuntu 20.04, x86_64 Threadripper 3990X, 128 logical CPUs, approximately 125 GB RAM, and RTX A6000 with driver 470.256.02. `/dev/kvm` existed but was neither readable nor writable by this account; emulator logs explicitly reported CPU acceleration disabled. Initial load averages were approximately 76/59/33. Load changed substantially during testing, so this was not a controlled idle-host benchmark. All emulator runs used niceness 15. Later runs and all measured UI windows used CPUs 0–15. The first run initially inherited CPUs 48–63; SwiftShader reassigned some workers to 0–15, which was detected and corrected by pinning all owned threads to 0–15. Aggregate observed consumption was far below 16 cores. The GPU was idle at the initial checks and remained usable during the software-rendered tests.

Completed results:

- **Four vCPUs, `swiftshader_indirect`, fresh userdata:** `sys.boot_completed=1` at **768.666 s (12 min 48.666 s)**. Twelve `adb shell echo ok` requests had **819 ms median**, **1,123 ms p95**, and 588–1,185 ms range. Fourteen upward Settings swipes ran over 45.570 s; `dumpsys gfxinfo` reported **7 frames, 0.154 FPS, 100% jank**. Six valid frame-stat rows had 953 ms median and 2,932 ms p95; none finished within 50 ms. Settings itself returned `Status: timeout` from its launch wait. **0 of 10 PNG captures** completed before their individual 10-second deadlines, across 100.112 s of requests. Post-boot emulator-group CPU averaged **111.9% of one host CPU**, approximately **1.12 host-core equivalents total / 0.280 per configured vCPU**. A dominant QEMU thread consumed approximately 99% by itself. Peak sampled group RSS was 6,327 MiB; this includes the late sequence of timed-out capture requests.
- **Four vCPUs, `-gpu host`, retained userdata:** cold boot with snapshots disabled completed in **221.305 s (3 min 41.305 s)**. This excludes fresh-image provisioning and is not directly comparable to the first boot. `DISPLAY` was unset; `QT_QPA_PLATFORM=offscreen`, `EGL_PLATFORM=surfaceless`, and `ANDROID_EGL_ON_EGL=1` were set, with Vulkan explicitly disabled. The emulator warned that the GPU could not be used for hardware rendering and identified **Google SwiftShader**, not NVIDIA. Therefore this was a **software fallback, not a successful RTX/EGL acceleration measurement**. Shell latency was **651 ms median**, **793 ms p95**, range 524–817 ms. Settings again returned a launch-wait timeout. Its frame-stat dump failed, so **FPS is unavailable**, not zero. **0 of 3 PNG requests** completed within 10 seconds each. Post-boot CPU averaged **110.5%**, or **1.11 host-core equivalents / 0.276 per configured vCPU**. Peak sampled RSS was 4,266 MiB.
- **Experimental four-vCPU multi-threaded TCG:** adding `-qemu -accel tcg,thread=multi` created four CPU worker threads and consumed roughly 160–305% aggregate host CPU. QEMU warned `Guest not yet converted to MTTCG - you may get unexpected results`. Android repeatedly exited/restarted `media`, `netd`, and `zygote`; no completed boot or usable ADB resulted. The test was stopped after **313.069 s**, through the verified harness's cleanup handler. This was not a usable optimization. A subsequent retained-userdata eight-vCPU attempt had encryption/APEX failures and rebooted with `boringssl-self-check-failed`; that attempt was excluded, and the test AVD was reset before the clean eight-vCPU measurement.
- **Eight vCPUs, default TCG, `swiftshader_indirect`, fresh userdata:** pending. Early samples show one QEMU CPU thread at approximately 99%, with about 101–104% group CPU overall. Eight guest CPUs have not created eight independent host CPU workers in this mode.

CPU percentages above are host process/thread accounting, where 100% means one fully occupied host logical CPU. “Per configured vCPU” divides aggregate host CPU consumption by the guest vCPU count; it is not a claim that each vCPU owns that host-core share. The default TCG path shares one dominant CPU execution thread. CPU averages use elapsed-time-weighted counter differences from `/proc`, and group RSS includes emulator helper processes. Shell p95 uses linear interpolation over twelve successful samples.

The guest's clock advanced at approximately **1.001× host wall time** during the first Settings window and **1.000×** in the host-requested window. This only establishes clock progression: it does not establish that application computation or rendering keeps pace. The scrolling workload includes repeated upward swipes and end-of-list overscroll. FPS is the frame counter divided by the host swipe window, not a display refresh-rate property. Slow Settings launch/reset processing and first-boot background work limit its interpretation as a steady-state renderer ceiling. PNG timeout results mean no complete images arrived within the stated deadlines; they do not prove that every alternate capture transport would have identical performance.

ARM translation was checked inside the booted guest, in addition to inspecting the packaged `build.prop`:

```text
ro.dalvik.vm.native.bridge = libndk_translation.so
ro.product.cpu.abilist    = x86_64,arm64-v8a
ro.product.cpu.abilist32  = [empty]
ro.product.cpu.abilist64  = x86_64,arm64-v8a
```

This image advertises **ARM64 translation only**, not 32-bit `armeabi-v7a`. No ARM binary was executed, so native-bridge presence does not establish compatibility with the real client. TCG also logged unsupported AVX/F16C CPU features.

The installation is entirely under **`/mpac/sdicks02/tools/android-sdk-nokvm/` on 127x04**, outside the NFS home. The fresh download directory is `downloads-oiJ1lqY1/`. Published archive sizes and SHA-1 checksums were read from `https://dl.google.com/android/repository/repository2-1.xml` and `https://dl.google.com/android/repository/sys-img/google_apis/sys-img2-1.xml`, and verified before extraction:

```text
Command-line tools 9.0, commandlinetools-linux-9477386_latest.zip
  133507477 bytes; 7f92d6e0783a6d73ade5396fe4cfcb58544ef14b
Platform-tools 37.0.1, platform-tools_r37.0.1-linux.zip
  9054187 bytes; 477254aa5f903c15cf51001717bdf347fb6b53e0
Emulator stable 37.2.12, emulator-linux_x64-16428233.zip
  349654171 bytes; cd7362ea55dfb86a418958138dc396e74165dd01
Google APIs API 34 x86_64 revision 14, x86_64-34_r14.zip
  1563721130 bytes; e0f6c9a0691aa27bd597d0deb1bcfdc943ac8ca7
```

Command-line tools 9.0 were selected for the existing Java 11 runtime. SDK archives were downloaded/extracted directly with executable permissions restored; local package metadata was derived from the official repository XML. The older `avdmanager` failed to create this AVD, so its standard configuration and AVD index were written directly. The emulator accepted them. No Android platform package, build tools, extra system image, or Java download was needed.

The AVD is `avd/nokvm-api34.avd/`, with its index in `avd/nokvm-api34.ini`. Important `config.ini` values are:

```ini
abi.type=x86_64
hw.cpu.arch=x86_64
hw.cpu.ncore=4
hw.ramSize=4096
hw.lcd.width=1080
hw.lcd.height=1920
hw.lcd.density=420
hw.gpu.enabled=yes
hw.gpu.mode=swiftshader_indirect
image.sysdir.1=system-images/android-34/google_apis/x86_64/
tag.id=google_apis
PlayStore.enabled=false
disk.dataPartition.size=4G
```

Runtime `-cores` overrides the configured count. The emulator expanded the userdata partition to its approximately 6 GiB minimum. Android user/AVD/cache/temp paths and ADB vendor keys were directed into the SDK tree. The existing NFS `.android` directory is inaccessible; ADB's denied default-key attempts did not install data there, and the server loaded the SDK-local vendor key.

The default launch was equivalent to the following, inside the isolated namespace with loopback enabled and a private foreground ADB server on port 5037:

```bash
source /mpac/sdicks02/env.sh
/mpac/sdicks02/tools/android-sdk-nokvm/emulator/emulator \
  -avd nokvm-api34 -no-window -accel off \
  -gpu swiftshader_indirect -cores 4 -memory 4096 \
  -no-audio -no-boot-anim -no-snapshot -no-metrics \
  -feature -Wifi -verbose -show-kernel -wipe-data
```

`-wipe-data` was used only for the fresh-data measurements; later cold boots retained userdata but still used `-no-snapshot`. The namespace, paths, deadlines, sampling, and cleanup are implemented in **`evidence/measure.py` on 127x04**. Reproduction of the clean eight-vCPU test:

```bash
ssh 127x04 'source /mpac/sdicks02/env.sh; \
  unshare -Urn nice -n 15 taskset -c 0-15 python3 \
  /mpac/sdicks02/tools/android-sdk-nokvm/evidence/measure.py \
  swiftshader_indirect 8 swiftshader-8-factory 1800'
```

Each boot has a 1,800-second process-lifetime watchdog, canceled after a successful `sys.boot_completed=1` check. The initial valid run used a separate PID/start-time-verified watchdog; later runs use the harness timer. Boot polling used bounded ADB calls. Measurements used:

```bash
adb -s emulator-5554 shell getprop sys.boot_completed
adb -s emulator-5554 shell echo ok
adb -s emulator-5554 shell am start -W -a android.settings.SETTINGS
adb -s emulator-5554 shell dumpsys gfxinfo com.android.settings reset
adb -s emulator-5554 shell input swipe 540 1550 540 450 300
adb -s emulator-5554 shell dumpsys gfxinfo com.android.settings framestats
adb -s emulator-5554 exec-out screencap -p
adb -s emulator-5554 exec-out screencap
```

The last command avoids PNG compression and is included in the final eight-vCPU test. Completed failed-capture sequences were bounded and stopped once repeated timeouts were conclusive. Two short ADB harness setup retries were excluded from boot/performance figures. The first valid run was stopped after ten capture timeouts, using its cleanup handler.

With **KVM access**, x86 guest CPU instructions would execute on hardware rather than through this TCG interpreter, and guest vCPUs could use separate host CPU threads. That removes the observed CPU-emulation bottleneck; it does not remove ARM-to-x86 native translation or fix the tested host/EGL software fallback. Neither a KVM speedup nor actual game performance was measured, so no numerical KVM FPS claim is warranted. A KVM-enabled test with ARM64 compatibility verification and a working graphics backend would be needed to establish the 20 FPS margin.

Raw results, launch/kernel logs, frame stats, thread counters, checksum receipts, and PID cleanup receipts are under **`/mpac/sdicks02/tools/android-sdk-nokvm/evidence/` on 127x04**. `summarize.py` generates `summary.json`. Final cleanup and the eight-vCPU verdict will be recorded here when that run finishes. No git commit was made; unrelated checkout changes were left alone.
