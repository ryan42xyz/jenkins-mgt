#!/bin/bash

# Exit on any error
set -e

# Configuration
IMAGE_NAME="jenkins-mgt"
REGISTRY="${DOCKER_REGISTRY:-your-registry.example.com/your-org}"
if [ -n "$1" ]; then
  TAG="$1"
else
  TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
fi

# Build the Docker image
echo "Building Docker image..."
docker buildx build --platform linux/amd64 -t ${REGISTRY}/${IMAGE_NAME}:${TAG} . --push

# Push the image to registry
echo "Image already pushed by buildx."

echo "Build completed successfully!"
echo "Image: ${REGISTRY}/${IMAGE_NAME}:${TAG}" 