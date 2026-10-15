// Shared: find the BlueStacks Air window and hit-test screen points (CoreGraphics window list, read-only).
// Coordinates are global display points, origin at the main display's top-left (the space CGEvent uses).
import CoreGraphics
import Foundation

struct BSWindow {
    let id: CGWindowID
    let pid: pid_t
    let bounds: CGRect
}

let bsOwner = "BlueStacks"

func onscreenWindows() -> [[String: Any]] {   // front to back
    (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]]) ?? []
}

func boundsOf(_ w: [String: Any]) -> CGRect? {
    guard let d = w[kCGWindowBounds as String] else { return nil }
    return CGRect(dictionaryRepresentation: d as! CFDictionary)
}

/// The largest on-screen, normal-layer, visible window owned by "BlueStacks". nil if none.
func findBlueStacks() -> BSWindow? {
    var best: BSWindow? = nil
    for w in onscreenWindows() {
        guard (w[kCGWindowOwnerName as String] as? String) == bsOwner,
              (w[kCGWindowLayer as String] as? Int) == 0,
              ((w[kCGWindowAlpha as String] as? Double) ?? 0) > 0,
              let r = boundsOf(w), r.width >= 200, r.height >= 200,
              let id = w[kCGWindowNumber as String] as? Int,
              let pid = w[kCGWindowOwnerPID as String] as? Int else { continue }
        if best == nil || r.width * r.height > best!.bounds.width * best!.bounds.height {
            best = BSWindow(id: CGWindowID(id), pid: pid_t(pid), bounds: r)
        }
    }
    return best
}

/// Owner, layer and id of the front-most visible window (any layer >= 0) that contains p.
func topWindow(at p: CGPoint) -> (owner: String, layer: Int, id: CGWindowID)? {
    for w in onscreenWindows() {
        let layer = (w[kCGWindowLayer as String] as? Int) ?? 0
        guard layer >= 0, ((w[kCGWindowAlpha as String] as? Double) ?? 0) > 0,
              let r = boundsOf(w), r.contains(p) else { continue }
        return ((w[kCGWindowOwnerName as String] as? String) ?? "?", layer,
                CGWindowID((w[kCGWindowNumber as String] as? Int) ?? 0))
    }
    return nil
}

func parseRect(_ s: String) -> CGRect? {
    let v = s.split(separator: ",").compactMap { Double($0) }
    guard v.count == 4, v[2] > 0, v[3] > 0 else { return nil }
    return CGRect(x: v[0], y: v[1], width: v[2], height: v[3])
}

func nowUnixNs() -> UInt64 {
    var ts = timespec(); clock_gettime(CLOCK_REALTIME, &ts)
    return UInt64(ts.tv_sec) * 1_000_000_000 + UInt64(ts.tv_nsec)
}

func fail(_ msg: String, _ code: Int32) -> Never {
    FileHandle.standardError.write(("error: " + msg + "\n").data(using: .utf8)!)
    exit(code)
}
