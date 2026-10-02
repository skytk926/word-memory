import Foundation
import Vision
import AppKit

// Usage: ocr.swift <image_path>
// Prints recognized text lines with bounding boxes as TSV: x y w h \t text

guard CommandLine.arguments.count > 1 else {
    FileHandle.standardError.write("usage: ocr <image>\n".data(using: .utf8)!)
    exit(1)
}

let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot load image \(path)\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["ja", "zh-Hans", "en"]
request.customWords = ["ます", "です", "する", "こと", "もの", "ため"]

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    FileHandle.standardError.write("OCR failed: \(error)\n".data(using: .utf8)!)
    exit(1)
}

guard let results = request.results else { exit(0) }

for obs in results {
    guard let cand = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    // Vision coordinates: origin bottom-left, normalized
    let x = b.origin.x
    let y = b.origin.y
    let w = b.size.width
    let h = b.size.height
    let text = cand.string
    print("\(x)\t\(y)\t\(w)\t\(h)\t\(text)")
}
