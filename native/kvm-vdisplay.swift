// kvm-vdisplay: adds an extra display to this Mac, for Kvm to show on another computer's screen
// ("Extend this Mac onto ..."). The display lives as long as this tool does.
//
//   kvm-vdisplay <width> <height> [hidpi 0|1]
// Prints "id <displayID>" once the display exists, then waits. Exits when stdin closes.
//
// Build: native/build.sh

import CoreGraphics
import Foundation

setvbuf(stdout, nil, _IOLBF, 0)

func fail(_ text: String, _ code: Int32) -> Never {
    FileHandle.standardError.write((text + "\n").data(using: .utf8)!)
    exit(code)
}

let args = CommandLine.arguments
let width = UInt32(args.count > 1 ? args[1] : "1920") ?? 1920
let height = UInt32(args.count > 2 ? args[2] : "1080") ?? 1080
let hidpi = args.count > 3 && args[3] == "1"
guard width >= 640, height >= 480, width <= 7680, height <= 4320 else { fail("bad size", 2) }

let desc = CGVirtualDisplayDescriptor()
desc.setDispatchQueue(DispatchQueue.main)
desc.name = "Kvm Display"
desc.maxPixelsWide = hidpi ? width * 2 : width
desc.maxPixelsHigh = hidpi ? height * 2 : height
// Pretend to be a 24-inch-ish panel, so macOS picks a sensible default scale.
let mmPerPixel = 0.2715
desc.sizeInMillimeters = CGSize(width: Double(width) * mmPerPixel, height: Double(height) * mmPerPixel)
desc.vendorID = 0x4B56   // "KV"
desc.productID = 0x0001
desc.serialNum = UInt32(getpid())
desc.terminationHandler = { _, _ in exit(0) }

guard let display = CGVirtualDisplay(descriptor: desc) else { fail("couldn't create the display", 3) }
let settings = CGVirtualDisplaySettings()
settings.hiDPI = hidpi ? 1 : 0
settings.modes = [CGVirtualDisplayMode(width: width, height: height, refreshRate: 60)]
guard display.apply(settings) else { fail("couldn't set the display mode", 4) }

print("id \(display.displayID)")

// Kvm closes our stdin to remove the display.
DispatchQueue.global().async {
    while readLine() != nil {}
    exit(0)
}
withExtendedLifetime(display) { dispatchMain() }
