// kvm-audiotap: writes what this Mac is playing to stdout, for Kvm to send to another computer.
//
// Output: 48 kHz, 2 channels, interleaved 32-bit float, little-endian, no header. Kvm's own
// sound is left out (so hearing each other doesn't echo). Exits when stdin closes or stdout
// breaks. Uses ScreenCaptureKit (macOS 13+), so it needs the "Screen & System Audio Recording"
// permission, which macOS grants to Kvm (the app this tool runs inside).
//
// Build: native/build.sh

import CoreMedia
import Foundation
import ScreenCaptureKit

setvbuf(stdout, nil, _IOFBF, 1 << 16)
signal(SIGPIPE, SIG_IGN)

func fail(_ text: String, _ code: Int32) -> Never {
    FileHandle.standardError.write((text + "\n").data(using: .utf8)!)
    exit(code)
}

@available(macOS 13.0, *)
final class Tap: NSObject, SCStreamOutput, SCStreamDelegate {
    private var stream: SCStream?
    private let queue = DispatchQueue(label: "kvm.audiotap")
    private var scratch = [Float](repeating: 0, count: 0)

    func start() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        guard let display = content.displays.first else { fail("no display", 4) }
        let cfg = SCStreamConfiguration()
        cfg.capturesAudio = true
        cfg.excludesCurrentProcessAudio = true
        cfg.sampleRate = 48000
        cfg.channelCount = 2
        // The picture isn't used: keep it as small and slow as allowed.
        cfg.width = 2
        cfg.height = 2
        cfg.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        cfg.queueDepth = 3
        // Leave out Kvm itself (our parent), so sound we play from the other computer isn't sent back.
        let parent = getppid()
        let kvm = content.applications.filter { $0.processID == parent }
        let filter = SCContentFilter(display: display, excludingApplications: kvm, exceptingWindows: [])
        let s = SCStream(filter: filter, configuration: cfg, delegate: self)
        try s.addStreamOutput(self, type: .audio, sampleHandlerQueue: queue)
        try s.addStreamOutput(self, type: .screen, sampleHandlerQueue: queue)
        try await s.startCapture()
        stream = s
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sb: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, sb.isValid else { return }
        do {
            try sb.withAudioBufferList { list, _ in
                let bufs = Array(list)
                guard let first = bufs.first, let p0 = first.mData else { return }
                if bufs.count >= 2, let p1 = bufs[1].mData {
                    // Planar (one buffer per channel): interleave.
                    let n = Int(first.mDataByteSize) / 4
                    let l = p0.assumingMemoryBound(to: Float.self)
                    let r = p1.assumingMemoryBound(to: Float.self)
                    if scratch.count < n * 2 { scratch = [Float](repeating: 0, count: n * 2) }
                    for i in 0..<n {
                        scratch[2 * i] = l[i]
                        scratch[2 * i + 1] = r[i]
                    }
                    scratch.withUnsafeBufferPointer { write($0.baseAddress!, n * 8) }
                } else if first.mNumberChannels == 1 {
                    let n = Int(first.mDataByteSize) / 4
                    let m = p0.assumingMemoryBound(to: Float.self)
                    if scratch.count < n * 2 { scratch = [Float](repeating: 0, count: n * 2) }
                    for i in 0..<n {
                        scratch[2 * i] = m[i]
                        scratch[2 * i + 1] = m[i]
                    }
                    scratch.withUnsafeBufferPointer { write($0.baseAddress!, n * 8) }
                } else {
                    write(p0, Int(first.mDataByteSize))  // already interleaved stereo
                }
            }
        } catch {
            // A malformed buffer: skip it.
        }
    }

    private func write(_ p: UnsafeRawPointer, _ count: Int) {
        if fwrite(p, 1, count, stdout) != count { exit(0) }  // Kvm went away
        fflush(stdout)
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fail("stopped: \(error.localizedDescription)", 2)
    }
}

if #available(macOS 13.0, *) {
    let tap = Tap()
    Task {
        do {
            try await tap.start()
        } catch {
            fail("permission or start error: \(error.localizedDescription)", 1)
        }
    }
    // Kvm closes our stdin to stop us.
    DispatchQueue.global().async {
        while readLine() != nil {}
        exit(0)
    }
    withExtendedLifetime(tap) { dispatchMain() }
} else {
    fail("needs macOS 13 or later", 3)
}
