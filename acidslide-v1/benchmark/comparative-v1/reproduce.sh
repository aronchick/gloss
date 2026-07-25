#!/bin/sh
set -eu

REPO_ROOT=$(cd -- "$(dirname -- "$0")/../../../.." && pwd)
COMPARATIVE_ROOT="$REPO_ROOT/acidslide-v1/benchmark/comparative-v1"
IMAGE_TAG="acidslide-v1:comparative-v1"

cd "$REPO_ROOT"
uv run "$COMPARATIVE_ROOT/generate_baselines.py"
docker build --platform linux/amd64 --provenance=false -t "$IMAGE_TAG" acidslide-v1
IMAGE_DIGEST=$(docker image inspect "$IMAGE_TAG" --format '{{.Id}}')
docker run --rm \
  --platform linux/amd64 \
  --entrypoint /opt/acidslide/venv/bin/python \
  --volume "$REPO_ROOT:/workspace" \
  --workdir /workspace \
  "$IMAGE_TAG" \
  /workspace/acidslide-v1/benchmark/comparative-v1/score_bundle.py \
  --image-digest "$IMAGE_DIGEST"
uv run "$COMPARATIVE_ROOT/verify_bundle.py"
