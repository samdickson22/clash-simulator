// bsbounds: the BlueStacks main window's bounds from CoreGraphics (CGWindowListCopyWindowInfo) - NO ScreenCaptureKit,
// so it cannot interrupt a running SCK capture stream (bsgrab info calls SCShareableContent: -3805 resets, s66b 10-17).
// Prints one JSON line like bsgrab info: {"window_id":N,"pid":P,"bounds":[x,y,w,h],"onscreen":true}; exit 1 if none.
// Picks the largest layer-0 window owned by "BlueStacks" (on-screen windows first). Read-only.
import CoreGraphics
import Foundation
let all = (CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]]) ?? []
var best: (Bool, Double, [String: Any])? = nil
for w in all {
  guard (w[kCGWindowOwnerName as String] as? String) == "BlueStacks",
        (w[kCGWindowLayer as String] as? Int) == 0,
        let b = w[kCGWindowBounds as String] as? [String: Double] else { continue }
  let area = (b["Width"] ?? 0) * (b["Height"] ?? 0)
  let on = (w[kCGWindowIsOnscreen as String] as? Bool) ?? false
  if area < 10000 { continue }
  if best == nil || (on && !best!.0) || (on == best!.0 && area > best!.1) { best = (on, area, w) }
}
guard let (on, _, w) = best, let b = w[kCGWindowBounds as String] as? [String: Double] else {
  FileHandle.standardError.write("error: no BlueStacks window\n".data(using: .utf8)!); exit(1)
}
let id = w[kCGWindowNumber as String] as? Int ?? 0, pid = w[kCGWindowOwnerPID as String] as? Int ?? 0
func f(_ v: Double?) -> String { String(format: "%.1f", v ?? 0) }
print("{\"window_id\":\(id),\"pid\":\(pid),\"bounds\":[\(f(b["X"])),\(f(b["Y"])),\(f(b["Width"])),\(f(b["Height"]))],\"onscreen\":\(on)}")
