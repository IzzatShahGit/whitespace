#!/usr/bin/env bash
# Build the two production images for the EC2 server (ARM64):
#   whitespace-api:prod  from backend/Dockerfile
#   whitespace-web:prod  from frontend/Dockerfile
# Run by scripts/ec2-deploy.sh; can be run alone to check that the build works.
set -euo pipefail
cd "$(dirname "$0")/.."

# This PC is x86; the server is ARM64. Register ARM emulation once per boot (the API's
# Python packages are installed under it; the web app builds natively, see its Dockerfile).
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
  echo "==> Enabling ARM64 emulation (once per boot)"
  docker run --privileged --rm tonistiigi/binfmt --install arm64
fi

build() {
  docker buildx build --builder default --platform linux/arm64 \
    --provenance=false --sbom=false --load "$@"
}

start=$(date +%s)
echo "==> Building whitespace-api:prod"
build -f backend/Dockerfile -t whitespace-api:prod .
echo "==> Building whitespace-web:prod"
# Caddy sends /api/* straight to the API; this is only the web app's fallback route.
build --build-arg API_INTERNAL_URL=http://api:8000 -t whitespace-web:prod frontend

for image in whitespace-api:prod whitespace-web:prod; do
  arch=$(docker image inspect "$image" --format '{{.Os}}/{{.Architecture}}')
  if [ "$arch" != "linux/arm64" ]; then
    echo "$image is $arch, expected linux/arm64" >&2
    exit 1
  fi
done
echo "Built both images in $(( $(date +%s) - start ))s"
