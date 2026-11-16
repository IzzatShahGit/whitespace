#!/usr/bin/env bash
# Build the SnapDeploy image (ARM64, web + API in one) and save it for upload.
#
#   make snapdeploy          (or: scripts/snapdeploy-build.sh)
#
# Output: dist/whitespace-snapdeploy.tar  -> SnapDeploy > Deploy > "Upload a Docker image"
# Nothing is pushed anywhere; the code never leaves this machine except in that upload.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE=whitespace-snapdeploy:latest
OUT=dist/whitespace-snapdeploy.tar

# This PC is x86; SnapDeploy runs ARM64. Register ARM emulation once per boot.
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
  echo "==> Enabling ARM64 emulation (once per boot)"
  docker run --privileged --rm tonistiigi/binfmt --install arm64
fi

echo "==> Building $IMAGE for linux/arm64"
start=$(date +%s)
docker buildx build \
  --builder default \
  --platform linux/arm64 \
  --provenance=false --sbom=false \
  -f deploy/snapdeploy/Dockerfile \
  -t "$IMAGE" \
  --load \
  .

arch=$(docker image inspect "$IMAGE" --format '{{.Os}}/{{.Architecture}}')
if [ "$arch" != "linux/arm64" ]; then
  echo "Built image is $arch, expected linux/arm64" >&2
  exit 1
fi

echo "==> Saving to $OUT"
mkdir -p dist
rm -f "$OUT"
docker save "$IMAGE" -o "$OUT"

echo
echo "Done in $(( $(date +%s) - start ))s: $OUT ($(du -h "$OUT" | cut -f1), $arch)"
echo "Upload it in SnapDeploy: Deploy > Upload a Docker image (port 8000)."
