// bsgrab: capture ONLY the BlueStacks window with ScreenCaptureKit (read-only; no input, no writes besides stdout).
//
//   bsgrab info
//       JSON: window id/pid/bounds (points), SCK content rect and point->pixel scale.
//   bsgrab stream --crop x,y,w,h --size W,H [--fps 10] [--seconds 60] [--frames 0]
//       --crop is in window-relative points (the Android viewport); SCK scales it to WxH on the GPU.
//       stdout: per frame a 32-byte little-endian header
//         'BSF1' | u32 seq | u32 width | u32 height | u64 display_unix_ns | u64 emit_unix_ns
//       followed by width*height*4 bytes BGRA (tightly packed). stderr: status lines.
//       Ends by itself after --seconds (hard cap 900) or --frames; on a closed stdout; or when the window goes away.
import CoreMedia
import CoreVideo
import Foundation
import ScreenCaptureKit

final class FrameSink: NSObject, SCStreamOutput, SCStreamDelegate {
    let maxFrames: Int
    var seq: UInt32 = 0
    let timebase: mach_timebase_info_data_t = { var t = mach_timebase_info_data_t(); mach_timebase_info(&t); return t }()

    init(maxFrames: Int) { self.maxFrames = maxFrames }

    func machToUnixNs(_ m: UInt64) -> UInt64 {   // mach absolute time -> CLOCK_REALTIME ns
        let toNs = { (x: UInt64) in x * UInt64(self.timebase.numer) / UInt64(self.timebase.denom) }
        let nowM = toNs(mach_absolute_time()), nowU = nowUnixNs(), t = toNs(m)
        return t <= nowM ? nowU - (nowM - t) : nowU
    }

    func put(_ p: UnsafeRawPointer, _ n: Int) {
        if fwrite(p, 1, n, stdout) != n { fail("stdout closed", 0) }
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sb.isValid,
              let atts = CMSampleBufferGetSampleAttachmentsArray(sb, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              let a = atts.first, let st = a[.status] as? Int, SCFrameStatus(rawValue: st) == .complete,
              let pb = CMSampleBufferGetImageBuffer(sb) else { return }
        let disp = machToUnixNs((a[.displayTime] as? UInt64) ?? mach_absolute_time())
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(pb) else { return }
        let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), stride = CVPixelBufferGetBytesPerRow(pb)
        var hdr = Data("BSF1".utf8)
        for v in [seq, UInt32(w), UInt32(h)] { withUnsafeBytes(of: v.littleEndian) { hdr.append(contentsOf: $0) } }
        for v in [disp, nowUnixNs()] { withUnsafeBytes(of: v.littleEndian) { hdr.append(contentsOf: $0) } }
        hdr.withUnsafeBytes { put($0.baseAddress!, $0.count) }
        for y in 0..<h { put(base + y * stride, w * 4) }
        fflush(stdout)
        seq += 1
        if maxFrames > 0 && Int(seq) >= maxFrames { exit(0) }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) { fail("stream stopped: \(error)", 4) }
}

func arg(_ args: [String], _ name: String) -> String? {
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}

/// The BlueStacks window as ScreenCaptureKit sees it (the session SCK serves, which is NOT necessarily the session
/// CoreGraphics' window list and CGEvents reach from ssh): the largest on-screen layer-0 window of the app "BlueStacks".
func scBlueStacks() async -> SCWindow {
    do {
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        let ws = content.windows.filter { $0.windowLayer == 0 && $0.isOnScreen && $0.owningApplication?.applicationName == bsOwner
                                          && $0.frame.width >= 200 && $0.frame.height >= 200 }
        guard let w = ws.max(by: { $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height })
        else { fail("no on-screen BlueStacks window", 3) }
        return w
    } catch { fail("SCShareableContent: \(error)", 3) }
}

@main
struct BSGrab {
    static func main() async {
        signal(SIGPIPE, SIG_IGN)
        _ = CGMainDisplayID()   // initializes CoreGraphics (SCContentFilter asserts otherwise)
        let args = Array(CommandLine.arguments.dropFirst())
        guard let cmd = args.first else { fail("usage: bsgrab info | stream --crop x,y,w,h --size W,H [--fps F] [--seconds S] [--frames N]", 2) }
        let win = await scBlueStacks()
        let filter = SCContentFilter(desktopIndependentWindow: win)
        if cmd == "info" {
            let b = win.frame, c = filter.contentRect
            print("{\"window_id\":\(win.windowID),\"pid\":\(win.owningApplication?.processID ?? 0),\"bounds\":[\(b.minX),\(b.minY),\(b.width),\(b.height)],"
                + "\"content_rect\":[\(c.minX),\(c.minY),\(c.width),\(c.height)],\"scale\":\(filter.pointPixelScale)}")
            exit(0)
        }
        guard cmd == "stream" else { fail("unknown command \(cmd)", 2) }
        guard let crop = arg(args, "--crop").flatMap(parseRect),
              let size = arg(args, "--size").flatMap({ parseRect("0,0," + $0) })
        else { fail("--crop x,y,w,h and --size W,H are required", 2) }
        guard crop.maxX <= win.frame.width + 0.5, crop.maxY <= win.frame.height + 0.5, crop.minX >= 0, crop.minY >= 0
        else { fail("crop \(crop) outside the window \(win.frame.size)", 2) }
        let fps = max(1, min(60, Int(arg(args, "--fps") ?? "10") ?? 10))
        let seconds = max(1, min(900, Double(arg(args, "--seconds") ?? "60") ?? 60))
        let frames = max(0, Int(arg(args, "--frames") ?? "0") ?? 0)

        let cfg = SCStreamConfiguration()
        cfg.sourceRect = crop
        cfg.width = Int(size.width)
        cfg.height = Int(size.height)
        cfg.pixelFormat = kCVPixelFormatType_32BGRA
        cfg.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(fps))
        cfg.queueDepth = 4
        cfg.showsCursor = false
        let sink = FrameSink(maxFrames: frames)
        let stream = SCStream(filter: filter, configuration: cfg, delegate: sink)
        do {
            try stream.addStreamOutput(sink, type: .screen, sampleHandlerQueue: DispatchQueue(label: "bsgrab.frames"))
            try await stream.startCapture()
        } catch { fail("startCapture: \(error)", 4) }
        FileHandle.standardError.write("bsgrab: window \(win.windowID) crop \(crop) -> \(cfg.width)x\(cfg.height) @\(fps) for \(seconds)s\n".data(using: .utf8)!)
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1e9))
        try? await stream.stopCapture()
        FileHandle.standardError.write("bsgrab: done, \(sink.seq) frames\n".data(using: .utf8)!)
        exit(0)
    }
}
