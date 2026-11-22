#!/bin/bash
# Builds Kvm's small native tools into native-build/ (macOS only; Kvm.spec bundles them).
#   kvm-audiotap  what the Mac is playing, for "Hear this Mac" (ScreenCaptureKit, macOS 13+)
set -e
cd "$(dirname "$0")/.."
[ "$(uname)" = "Darwin" ] || { echo "native tools are for macOS"; exit 0; }
mkdir -p native-build
swiftc -O -target "$(uname -m)-apple-macos13.0" -framework ScreenCaptureKit -framework CoreMedia \
  -o native-build/kvm-audiotap native/kvm-audiotap.swift
echo "Built native-build/kvm-audiotap"
