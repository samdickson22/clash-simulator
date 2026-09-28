import Foundation
import ImageIO
import Vision

func recognize(path: String) -> [String: Any] {
    let url = URL(fileURLWithPath: path) as CFURL
    guard
        let source = CGImageSourceCreateWithURL(url, nil),
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        return ["path": path, "valid": false, "error": "decode_failed"]
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["en-US"]
    do {
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    } catch {
        return [
            "path": path,
            "valid": false,
            "error": "vision_request_failed",
            "detail": String(describing: error),
        ]
    }

    let candidates = (request.results ?? []).compactMap { observation -> [String: Any]? in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        return ["text": candidate.string, "confidence": Double(candidate.confidence)]
    }
    return ["path": path, "valid": !candidates.isEmpty, "candidates": candidates]
}

for path in CommandLine.arguments.dropFirst() {
    let payload = recognize(path: path)
    if let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
       let line = String(data: data, encoding: .utf8)
    {
        print(line)
    }
}
