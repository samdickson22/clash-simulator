// bsclick: synthetic left-mouse taps/drags on the BlueStacks window via CGEvent (needs Accessibility).
//
//   bsclick [--vp x,y,w,h] <command>        one command from the arguments
//   bsclick [--vp x,y,w,h] serve            one command per stdin line, one reply line each (keeps latency low)
// Commands:
//   where u v              no event: print the screen point and the window under it
//   tap u v                move, 20 ms, down, 50 ms, up
//   drag u0 v0 u1 v1 ms    move, down, 10 equal dragged steps over ms (50..1000), up
// u,v are fractions (0..1) of the viewport --vp, given in window-relative points (default: the whole window).
// Every command re-reads the window position, and refuses unless the front-most visible window under EVERY
// point it would touch is owned by BlueStacks. Fixed timings (no randomization). Replies:
//   ok <cmd> <screen_x> <screen_y> <t_start_unix_ns> <t_end_unix_ns>   |   err <reason>
import ApplicationServices
import CoreGraphics
import Foundation

func screenPoint(_ bs: BSWindow, _ vp: CGRect?, _ u: Double, _ v: Double) throws -> CGPoint {
    guard (0...1).contains(u), (0...1).contains(v) else { throw E("u,v outside 0..1") }
    let r = vp ?? CGRect(origin: .zero, size: bs.bounds.size)
    guard r.minX >= 0, r.minY >= 0, r.maxX <= bs.bounds.width + 0.5, r.maxY <= bs.bounds.height + 0.5
    else { throw E("viewport \(r) outside the window \(bs.bounds.size)") }
    let p = CGPoint(x: bs.bounds.minX + r.minX + u * r.width, y: bs.bounds.minY + r.minY + v * r.height)
    guard bs.bounds.insetBy(dx: 1, dy: 1).contains(p) else { throw E("point outside the window") }
    guard let top = topWindow(at: p) else { throw E("no window under the point") }
    guard top.owner == bsOwner else { throw E("point is covered by \(top.owner) (layer \(top.layer))") }
    return p
}

struct E: Error { let msg: String; init(_ m: String) { msg = m } }

let src = CGEventSource(stateID: .hidSystemState)

func post(_ t: CGEventType, _ p: CGPoint) throws {
    guard let e = CGEvent(mouseEventSource: src, mouseType: t, mouseCursorPosition: p, mouseButton: .left)
    else { throw E("CGEvent create failed") }
    e.post(tap: .cghidEventTap)
}

func pause(_ ms: Double) { usleep(useconds_t(ms * 1000)) }

func run(_ words: [String], _ vp: CGRect?) -> String {
    guard let cmd = words.first else { return "err empty" }
    let n = words.dropFirst().compactMap { Double($0) }
    guard n.count == words.count - 1 else { return "err non-numeric argument" }
    guard let bs = findBlueStacks() else { return "err no on-screen BlueStacks window" }
    do {
        let t0 = nowUnixNs()
        switch (cmd, n.count) {
        case ("where", 2):
            let r = vp ?? CGRect(origin: .zero, size: bs.bounds.size)
            let p = CGPoint(x: bs.bounds.minX + r.minX + n[0] * r.width, y: bs.bounds.minY + r.minY + n[1] * r.height)
            let top = topWindow(at: p)
            return "ok where \(p.x) \(p.y) top=\(top?.owner ?? "-"):\(top?.layer ?? -1):\(top?.id ?? 0) bs=\(bs.id) bounds=\(bs.bounds)"
        case ("tap", 2):
            let p = try screenPoint(bs, vp, n[0], n[1])
            try post(.mouseMoved, p); pause(20)
            try post(.leftMouseDown, p); pause(50)
            try post(.leftMouseUp, p)
            return "ok tap \(p.x) \(p.y) \(t0) \(nowUnixNs())"
        case ("drag", 5):
            let a = try screenPoint(bs, vp, n[0], n[1]), b = try screenPoint(bs, vp, n[2], n[3])
            let ms = max(50, min(1000, n[4]))
            try post(.mouseMoved, a); pause(20)
            try post(.leftMouseDown, a)
            for i in 1...10 {
                pause(ms / 10)
                let f = Double(i) / 10
                try post(.leftMouseDragged, CGPoint(x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f))
            }
            try post(.leftMouseUp, b)
            return "ok drag \(b.x) \(b.y) \(t0) \(nowUnixNs())"
        default:
            return "err unknown command or wrong argument count: \(words.joined(separator: " "))"
        }
    } catch let e as E { return "err \(e.msg)" } catch { return "err \(error)" }
}

@main
struct BSClick {
    static func main() {
        var args = Array(CommandLine.arguments.dropFirst())
        var vp: CGRect? = nil
        if let i = args.firstIndex(of: "--vp") {
            guard i + 1 < args.count, let r = parseRect(args[i + 1]) else { fail("--vp x,y,w,h", 2) }
            vp = r; args.removeSubrange(i...(i + 1))
        }
        guard !args.isEmpty else { fail("usage: bsclick [--vp x,y,w,h] (where u v | tap u v | drag u0 v0 u1 v1 ms | serve)", 2) }
        guard args.first == "where" || AXIsProcessTrusted() else { fail("not trusted for Accessibility", 3) }
        if args == ["serve"] {
            setvbuf(stdout, nil, _IOLBF, 0)
            while let line = readLine() {
                let w = line.split(separator: " ").map(String.init)
                if w.isEmpty { continue }
                print(run(w, vp))
            }
            exit(0)
        }
        let out = run(args, vp)
        print(out)
        exit(out.hasPrefix("ok") ? 0 : 1)
    }
}
