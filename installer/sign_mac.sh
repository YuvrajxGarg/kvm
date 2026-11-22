#!/bin/sh
# Re-signs dist/<App>.app (ad hoc, no Apple certificate) with a designated requirement that names
# only the bundle identifier:
#   installer/sign_mac.sh Kvm com.yuvrajgarg.kvm
# An ad hoc signature's default requirement is the exact hash of this build, so macOS forgets
# Accessibility, Input Monitoring and Screen Recording after every update. With
# "identifier com.yuvrajgarg.kvm" each new build still matches what was allowed before.
set -eu
APP=$1
ID=$2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUNDLE=$ROOT/dist/$APP.app
[ -d "$BUNDLE" ] || { echo "dist/$APP.app not found: build the app first"; exit 1; }

# Nested helper tools first (inside out), each with a stable requirement of its own.
find "$BUNDLE/Contents" -type f -name 'kvm-*' -perm -u+x | while read -r tool; do
  tid="$ID.$(basename "$tool")"
  codesign --force --sign - --identifier "$tid" --requirements "=designated => identifier \"$tid\"" "$tool"
done
codesign --force --sign - --identifier "$ID" --requirements "=designated => identifier \"$ID\"" "$BUNDLE"

codesign --verify --strict --deep "$BUNDLE"
codesign --display --requirements - "$BUNDLE" 2>&1 | tee /dev/stderr | grep -q "designated => identifier \"$ID\"" \
  || { echo "designated requirement not set"; exit 1; }
echo "Signed $BUNDLE"
