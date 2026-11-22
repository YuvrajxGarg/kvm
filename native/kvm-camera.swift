// kvm-camera: this Mac's camera, as JPEG pictures on stdout, for Kvm to send to another computer.
//
//   kvm-camera [width] [height] [fps]
// Each picture is a 4-byte big-endian length, then the JPEG. Exits when stdin closes or stdout
// breaks. macOS asks for Camera permission for Kvm (the app this tool runs inside) the first time.
//
// Build: native/build.sh

import AVFoundation
import CoreImage
import Foundation
import ImageIO

signal(SIGPIPE, SIG_IGN)

func fail(_ text: String, _ code: Int32) -> Never {
    FileHandle.standardError.write((text + "\n").data(using: .utf8)!)
    exit(code)
}

let args = CommandLine.arguments
let wantW = Int(args.count > 1 ? args[1] : "1280") ?? 1280
let fps = Double(args.count > 3 ? args[3] : "30") ?? 30

final class Camera: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()
    let ctx = CIContext(options: [.useSoftwareRenderer: false])
    let queue = DispatchQueue(label: "kvm.camera")
    var last = 0.0

    func start() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            break
        case .notDetermined:
            let sem = DispatchSemaphore(value: 0)
            var ok = false
            AVCaptureDevice.requestAccess(for: .video) { granted in ok = granted; sem.signal() }
            sem.wait()
            if !ok { fail("camera permission declined", 5) }
        default:
            fail("camera permission declined", 5)
        }
        guard let dev = AVCaptureDevice.default(for: .video) else { fail("no camera on this Mac", 4) }
        session.beginConfiguration()
        let preset: AVCaptureSession.Preset = wantW >= 1920 ? .hd1920x1080 : (wantW >= 1280 ? .hd1280x720 : .vga640x480)
        if session.canSetSessionPreset(preset) { session.sessionPreset = preset }
        do {
            let input = try AVCaptureDeviceInput(device: dev)
            guard session.canAddInput(input) else { fail("camera busy", 6) }
            session.addInput(input)
        } catch {
            fail("camera: \(error.localizedDescription)", 6)
        }
        let out = AVCaptureVideoDataOutput()
        out.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        out.alwaysDiscardsLateVideoFrames = true
        out.setSampleBufferDelegate(self, queue: queue)
        guard session.canAddOutput(out) else { fail("camera output", 6) }
        session.addOutput(out)
        session.commitConfiguration()
        session.startRunning()
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sb: CMSampleBuffer, from connection: AVCaptureConnection) {
        let now = ProcessInfo.processInfo.systemUptime
        if now - last < 1.0 / fps { return }
        last = now
        guard let pb = CMSampleBufferGetImageBuffer(sb), let cs = CGColorSpace(name: CGColorSpace.sRGB) else { return }
        let img = CIImage(cvPixelBuffer: pb)
        let q = CIImageRepresentationOption(rawValue: kCGImageDestinationLossyCompressionQuality as String)
        guard let data = ctx.jpegRepresentation(of: img, colorSpace: cs, options: [q: 0.72]) else { return }
        var len = UInt32(data.count).bigEndian
        let ok = withUnsafeBytes(of: &len) { fwrite($0.baseAddress!, 1, 4, stdout) == 4 } &&
            data.withUnsafeBytes { fwrite($0.baseAddress!, 1, data.count, stdout) == data.count }
        if !ok { exit(0) }  // Kvm went away
        fflush(stdout)
    }
}

let cam = Camera()
cam.start()
DispatchQueue.global().async {
    while readLine() != nil {}
    exit(0)
}
withExtendedLifetime(cam) { dispatchMain() }
