#!/bin/bash
# Builds Kvm's small native tools into native-build/ (macOS only; Kvm.spec bundles them).
#   kvm-audiotap  what the Mac is playing, for "Hear this Mac" (ScreenCaptureKit, macOS 13+)
#   kvm-vdisplay  an extra display, for "Extend this Mac onto ..." (CGVirtualDisplay)
#   kvm-camera    the Mac's camera as JPEG pictures, for "Use this Mac's camera" (AVFoundation)
set -e
cd "$(dirname "$0")/.."
[ "$(uname)" = "Darwin" ] || { echo "native tools are for macOS"; exit 0; }
mkdir -p native-build
swiftc -O -target "$(uname -m)-apple-macos13.0" -framework ScreenCaptureKit -framework CoreMedia \
  -o native-build/kvm-audiotap native/kvm-audiotap.swift
swiftc -O -target "$(uname -m)-apple-macos12.0" -import-objc-header native/CGVirtualDisplay.h \
  -o native-build/kvm-vdisplay native/kvm-vdisplay.swift
swiftc -O -target "$(uname -m)-apple-macos12.0" -o native-build/kvm-camera native/kvm-camera.swift
echo "Built native-build/kvm-audiotap, kvm-vdisplay, kvm-camera"
