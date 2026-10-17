// dispgrab: display-only window capture for the clasher live viewer (read-only: no input, writes only stdout/stderr).
// Derived from loop/src/mac/bsgrab.swift (same BlueStacks window choice); bsgrab itself is unchanged (the bot's capture).
//
//   dispgrab info [--owner NAME] [--title SUBSTR]
//       JSON for the largest on-screen window of app NAME (default BlueStacks): id/pid/bounds/content rect/scale.
//   dispgrab windows
//       JSON list of on-screen normal-layer windows: id, owner, title, bounds (points), for picking capture sources.
//   dispgrab stream --crop x,y,w,h --size W,H [--fps 30] [--seconds 0] [--owner NAME] [--title SUBSTR]
//       One window (crop in window points) scaled to W x H.
//   dispgrab grid --size W,H --tile ID:x,y,w,h [--tile ...] [--fps 30] [--seconds 0]
//       Several windows (by window id, each captured whole, scaled to its tile) composed into one W x H canvas.
//   Output (stream/grid): raw NV12 frames on stdout, tightly packed (W*H luma, then W*H/2 interleaved CbCr; BT.709 video
//   range), at a CONSTANT --fps from the newest captured content (static screens repeat). Nothing is written before
//   the first captured frame. A capture interruption (e.g. SCK -3805) or app relaunch is restarted in-process while
//   the last frame keeps being emitted; a source window missing for 30 s -> exit 3. Closed stdout -> exit 0.
//   --gate PATH: while the file reads "hold" (the caller's driver is in a battle), no SCK stream is (re)started; the last
//   frame keeps being emitted until it reads anything else. stderr: status lines and a stats line every 10 s.
import CoreGraphics
import CoreMedia
import CoreVideo
import Foundation
import ScreenCaptureKit

func fail(_ msg: String, _ code: Int32) -> Never {
    FileHandle.standardError.write(("dispgrab error: " + msg + "\n").data(using: .utf8)!)
    exit(code)
}

func say(_ msg: String) { FileHandle.standardError.write(("dispgrab: " + msg + "\n").data(using: .utf8)!) }

func parseRect(_ s: String) -> CGRect? {
    let v = s.split(separator: ",").compactMap { Double($0) }
    guard v.count == 4, v[2] > 0, v[3] > 0 else { return nil }
    return CGRect(x: v[0], y: v[1], width: v[2], height: v[3])
}

func arg(_ args: [String], _ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}

func allArgs(_ all: [String], _ name: String) -> [String] {
    var out: [String] = []
    var i = 0
    while i < all.count { if all[i] == name, i + 1 < all.count { out.append(all[i + 1]); i += 2 } else { i += 1 } }
    return out
}

/// The output canvas (NV12), prefilled black; tiles copy into it under the lock. Emitted by `emit`.
final class Canvas: @unchecked Sendable {   // state guarded by lock
    let w: Int, h: Int, n: Int
    let buf: UnsafeMutableRawPointer
    let lock = NSLock()
    var have = false
    var captured = 0, rejected = 0
    var lastNs: UInt64 = 0

    init(w: Int, h: Int) {
        self.w = w; self.h = h; self.n = w * h * 3 / 2
        buf = UnsafeMutableRawPointer.allocate(byteCount: n, alignment: 64)
        memset(buf, 16, w * h)                      // black, video range
        memset(buf + w * h, 128, w * h / 2)
    }
}

/// One SCK stream's frames -> its rect (even x, y, w, h) of the canvas; copied out of the SCK surface at once.
final class Tile: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {   // mutable state under canvas.lock
    let canvas: Canvas
    let x: Int, y: Int, w: Int, h: Int
    let windowID: CGWindowID?                         // grid tiles: the window to (re)capture; nil = by owner/title
    let crop: CGRect?                                 // stream mode: window-relative points; nil = whole window
    var stopError: String? = nil
    var stream: SCStream? = nil                       // touched only by the main task

    init(canvas: Canvas, x: Int, y: Int, w: Int, h: Int, windowID: CGWindowID?, crop: CGRect?) {
        self.canvas = canvas; self.x = x; self.y = y; self.w = w; self.h = h; self.windowID = windowID; self.crop = crop
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sb.isValid,
              let atts = CMSampleBufferGetSampleAttachmentsArray(sb, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              let a = atts.first, let st = a[.status] as? Int, SCFrameStatus(rawValue: st) == .complete,
              let pb = CMSampleBufferGetImageBuffer(sb) else { return }
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
        let c = canvas
        guard CVPixelBufferGetPlaneCount(pb) == 2,
              CVPixelBufferGetWidthOfPlane(pb, 0) == w, CVPixelBufferGetHeightOfPlane(pb, 0) == h,
              CVPixelBufferGetHeightOfPlane(pb, 1) == h / 2, CVPixelBufferGetWidthOfPlane(pb, 1) * 2 == w,
              let y0 = CVPixelBufferGetBaseAddressOfPlane(pb, 0), let c0 = CVPixelBufferGetBaseAddressOfPlane(pb, 1)
        else { c.lock.lock(); c.rejected += 1; c.lock.unlock(); return }
        let ys = CVPixelBufferGetBytesPerRowOfPlane(pb, 0), cs = CVPixelBufferGetBytesPerRowOfPlane(pb, 1)
        c.lock.lock()
        for r in 0..<h { memcpy(c.buf + (y + r) * c.w + x, y0 + r * ys, w) }
        let cbase = c.buf + c.w * c.h
        for r in 0..<(h / 2) { memcpy(cbase + (y / 2 + r) * c.w + x, c0 + r * cs, w) }
        c.have = true
        c.captured += 1
        c.lastNs = DispatchTime.now().uptimeNanoseconds
        c.lock.unlock()
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        canvas.lock.lock(); stopError = "\(error)"; canvas.lock.unlock()   // keep emitting the last frame
    }

    func streamDidBecomeInactive(_ stream: SCStream) {          // e.g. the shared window closed
        canvas.lock.lock(); if stopError == nil { stopError = "stream became inactive" }; canvas.lock.unlock()
    }

    func markStopped(_ why: String) { canvas.lock.lock(); if stopError == nil { stopError = why }; canvas.lock.unlock() }

    func takeStop() -> String? { canvas.lock.lock(); defer { stopError = nil; canvas.lock.unlock() }; return stopError }
}

/// Constant-rate writer on its own thread: copy the canvas under the lock, write it without the lock.
func emit(_ src: Canvas, fps: Int) {
    let out = UnsafeMutableRawPointer.allocate(byteCount: src.n, alignment: 64)
    let period = 1.0 / Double(fps)
    let mono = { Double(DispatchTime.now().uptimeNanoseconds) / 1e9 }   // monotonic: immune to wall-clock steps
    var next = mono()
    var emitted = 0, resyncs = 0, lastStats = next
    var writeSec = 0.0
    while true {
        let now = mono()
        if now < next { Thread.sleep(forTimeInterval: next - now) }
        next += period
        let after = mono()
        if after - next > 0.25 { next = after + period; resyncs += 1 }       // fell behind: skip, never burst
        src.lock.lock()
        let ok = src.have
        if ok { memcpy(out, src.buf, src.n) }
        src.lock.unlock()
        if ok {
            let t0 = mono()
            if fwrite(out, 1, src.n, stdout) != src.n { fail("stdout closed", 0) }
            fflush(stdout)
            writeSec += mono() - t0
            emitted += 1
        }
        if after - lastStats >= 10 {
            src.lock.lock(); let cap = src.captured, rej = src.rejected, last = src.lastNs; src.captured = 0; src.rejected = 0; src.lock.unlock()
            let dt = after - lastStats
            let age = last == 0 ? -1.0 : after - Double(last) / 1e9
            say(String(format: "stats %.0fs: captured %.2f fps, emitted %.2f fps, rejected %d, resyncs %d, write %.2f ms/frame, last_capture_age %.1f s",
                       dt, Double(cap) / dt, Double(emitted) / dt, rej, resyncs, emitted > 0 ? 1e3 * writeSec / Double(emitted) : 0, age))
            emitted = 0; resyncs = 0; writeSec = 0; lastStats = after
        }
    }
}

struct NoWindow: Error {}
struct Held: Error {}

/// --gate PATH reads "hold" while the caller's driver is in a battle: no capture client may start or stop then.
nonisolated(unsafe) var gatePath: String? = nil
func held() -> Bool {
    guard let g = gatePath, let s = try? String(contentsOfFile: g, encoding: .utf8) else { return false }
    return s.trimmingCharacters(in: .whitespacesAndNewlines) == "hold"
}

func shareable() async throws -> [SCWindow] {
    try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true).windows
        .filter { $0.windowLayer == 0 && $0.isOnScreen }
}

/// The largest on-screen window of app `owner` (title containing `title`, if given); exactly window `id` if set.
func findWindow(owner: String, title: String?, id: CGWindowID?) async throws -> SCWindow {
    let ws = try await shareable()
    if let id = id {
        guard let w = ws.first(where: { $0.windowID == id }) else { throw NoWindow() }
        return w
    }
    let cands = ws.filter { $0.owningApplication?.applicationName == owner && $0.frame.width >= 200 && $0.frame.height >= 200
                            && (title == nil || ($0.title ?? "").contains(title!)) }
    guard let w = cands.max(by: { $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height }) else { throw NoWindow() }
    return w
}

/// (Re)start one tile's capture (the window is looked up again: its id may differ after an app relaunch).
func startTile(_ t: Tile, owner: String, title: String?, fps: Int) async throws {
    let win = try await findWindow(owner: owner, title: title, id: t.windowID)
    let crop = t.crop ?? CGRect(x: 0, y: 0, width: win.frame.width, height: win.frame.height)
    guard crop.maxX <= win.frame.width + 0.5, crop.maxY <= win.frame.height + 0.5
    else { fail("crop \(crop) outside window \(win.windowID) \(win.frame.size)", 2) }
    let cfg = SCStreamConfiguration()
    cfg.sourceRect = crop
    cfg.width = t.w
    cfg.height = t.h
    cfg.pixelFormat = kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
    cfg.colorMatrix = CGDisplayStream.yCbCrMatrix_ITU_R_709_2
    cfg.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(fps))
    cfg.queueDepth = 4
    cfg.showsCursor = false
    let stream = SCStream(filter: SCContentFilter(desktopIndependentWindow: win), configuration: cfg, delegate: t)
    try stream.addStreamOutput(t, type: .screen, sampleHandlerQueue: DispatchQueue(label: "dispgrab.tile.\(t.x).\(t.y)"))
    if held() { throw Held() }                   // re-checked after the asynchronous window lookup
    try await stream.startCapture()
    t.stream = stream
    say("capturing window \(win.windowID) (\(win.owningApplication?.applicationName ?? "?")) crop \(crop) -> tile \(t.x),\(t.y) \(t.w)x\(t.h)")
}

func jsonStr(_ s: String) -> String {
    let d = try! JSONSerialization.data(withJSONObject: [s], options: [])
    let a = String(data: d, encoding: .utf8)!
    return String(a.dropFirst().dropLast())
}

@main
struct DispGrab {
    static func main() async {
        signal(SIGPIPE, SIG_IGN)
        _ = CGMainDisplayID()   // initializes CoreGraphics (SCContentFilter asserts otherwise)
        let av = Array(CommandLine.arguments.dropFirst())
        guard let cmd = av.first else { fail("usage: dispgrab info | windows | stream ... | grid ...", 2) }
        let owner = arg(av, "--owner") ?? "BlueStacks", title = arg(av, "--title")
        gatePath = arg(av, "--gate")
        if cmd == "windows" {
            do {
                let rows = try await shareable().map { w -> String in
                    let b = w.frame
                    return "{\"id\":\(w.windowID),\"owner\":\(jsonStr(w.owningApplication?.applicationName ?? "")),\"title\":\(jsonStr(w.title ?? "")),"
                        + "\"pid\":\(w.owningApplication?.processID ?? 0),\"bounds\":[\(b.minX),\(b.minY),\(b.width),\(b.height)]}"
                }
                print("[" + rows.joined(separator: ",") + "]")
                exit(0)
            } catch { fail("SCShareableContent: \(error)", 3) }
        }
        guard cmd == "info" || cmd == "stream" || cmd == "grid" else { fail("unknown command \(cmd)", 2) }
        var win: SCWindow? = nil
        if cmd != "grid" {
            do { win = try await findWindow(owner: owner, title: title, id: nil) }
            catch is NoWindow { fail("no on-screen \(owner) window", 3) }
            catch { fail("SCShareableContent: \(error)", 3) }
        }
        if cmd == "info", let win = win {
            let filter = SCContentFilter(desktopIndependentWindow: win)
            let b = win.frame, c = filter.contentRect
            print("{\"window_id\":\(win.windowID),\"pid\":\(win.owningApplication?.processID ?? 0),\"bounds\":[\(b.minX),\(b.minY),\(b.width),\(b.height)],"
                + "\"content_rect\":[\(c.minX),\(c.minY),\(c.width),\(c.height)],\"scale\":\(filter.pointPixelScale)}")
            exit(0)
        }
        guard let size = arg(av, "--size").flatMap({ parseRect("0,0," + $0) }) else { fail("--size W,H is required", 2) }
        let W = Int(size.width), H = Int(size.height)
        guard W % 2 == 0, H % 2 == 0, W <= 4096, H <= 4096 else { fail("--size must be even and <= 4096", 2) }
        let fps = max(1, min(60, Int(arg(av, "--fps") ?? "30") ?? 30))
        let seconds = max(0, Double(arg(av, "--seconds") ?? "0") ?? 0)
        let canvas = Canvas(w: W, h: H)
        var tiles: [Tile] = []
        if cmd == "stream", let win = win {
            guard let crop = arg(av, "--crop").flatMap(parseRect) else { fail("--crop x,y,w,h is required", 2) }
            guard crop.maxX <= win.frame.width + 0.5, crop.maxY <= win.frame.height + 0.5, crop.minX >= 0, crop.minY >= 0
            else { fail("crop \(crop) outside the window \(win.frame.size)", 2) }
            tiles = [Tile(canvas: canvas, x: 0, y: 0, w: W, h: H, windowID: nil, crop: crop)]
        } else {
            for spec in allArgs(av, "--tile") {
                let p = spec.split(separator: ":", maxSplits: 1)
                guard p.count == 2, let id = UInt32(p[0]), let r = parseRect(String(p[1])) else { fail("bad --tile \(spec)", 2) }
                let x = Int(r.minX) & ~1, y = Int(r.minY) & ~1, w = Int(r.width) & ~1, h = Int(r.height) & ~1
                guard w >= 2, h >= 2, x >= 0, y >= 0, x + w <= W, y + h <= H else { fail("tile \(spec) outside the canvas", 2) }
                tiles.append(Tile(canvas: canvas, x: x, y: y, w: w, h: h, windowID: id, crop: nil))
            }
            guard !tiles.isEmpty else { fail("grid needs at least one --tile", 2) }
            canvas.lock.withLock { canvas.have = true }   // black background is a valid grid frame
        }
        for t in tiles {
            while true {
                while held() { try? await Task.sleep(nanoseconds: 500_000_000) }   // never start during a battle
                do { try await startTile(t, owner: owner, title: title, fps: fps); break }
                catch is Held { continue }
                catch is NoWindow { fail("window \(t.windowID.map { String($0) } ?? owner) not found", 3) }
                catch { fail("startCapture: \(error)", 4) }
            }
        }
        say("\(cmd) \(tiles.count) tile(s) -> \(W)x\(H) NV12 @\(fps) for \(seconds == 0 ? "unlimited" : "\(seconds)") s")
        let th = Thread { emit(canvas, fps: fps) }
        th.qualityOfService = .utility
        th.start()
        // Supervise each SCK stream in-process (see header): restart on interruption, exit 3 after 30 s without a window.
        let mono = { Double(DispatchTime.now().uptimeNanoseconds) / 1e9 }
        let t0 = mono()
        var restarts = 0, lastCheck = t0
        while seconds == 0 || mono() - t0 < seconds {
            try? await Task.sleep(nanoseconds: 200_000_000)
            if mono() - lastCheck >= 10 {              // a closed window may not report an error: check it exists
                lastCheck = mono()
                if let ws = try? await shareable() {
                    for t in tiles where t.stream != nil {
                        let alive = t.windowID.map { id in ws.contains { $0.windowID == id } }
                            ?? ws.contains { $0.owningApplication?.applicationName == owner }
                        if !alive { t.markStopped("source window is gone") }
                    }
                }
            }
            for t in tiles {
                guard let why = t.takeStop() else { continue }
                if held() {                            // battle: neither stop nor restart; keep the request pending
                    t.markStopped(why)
                    continue
                }
                restarts += 1
                say("tile \(t.x),\(t.y) stream stopped (\(why.prefix(160))); restarting in-process, restart \(restarts)")
                if let s = t.stream { try? await s.stopCapture() }
                t.stream = nil
                var started = false, waited = false
                let deadline = mono() + 30
                while mono() < deadline {
                    try? await Task.sleep(nanoseconds: 1_000_000_000)
                    if held() {                        // never (re)start a capture client during the caller's battle
                        if !waited { say("restart held by gate"); waited = true }
                        continue
                    }
                    do { try await startTile(t, owner: owner, title: title, fps: fps); started = true; break }
                    catch is Held { continue }
                    catch { say("restart attempt: \(error)") }
                }
                if !started && !held() { fail("no source window to restart on for 30 s", 3) }
                if !started { t.markStopped("restart still held") }   // keep the last frame; try again next loop
            }
        }
        for t in tiles { try? await t.stream?.stopCapture() }
        say("done")
        exit(0)
    }
}
