#!/bin/bash

# Kiểm tra Docker đã được cài đặt
if ! command -v docker &> /dev/null; then
    echo "Docker không được tìm thấy. Vui lòng cài đặt Docker trước."
    exit 1
fi

# Tạo thư mục output nếu chưa tồn tại
mkdir -p output

echo "=== Bắt đầu quá trình build ==="

# Xóa builder cũ nếu tồn tại
echo "Removing old builder if exists..."
docker buildx rm windows-builder 2>/dev/null || true

# Tạo builder mới
echo "Creating new builder..."
docker buildx create --name windows-builder --driver docker-container --platform windows/amd64
docker buildx use windows-builder
docker buildx inspect --bootstrap

# Build Docker image cho Windows
echo "Building Docker image..."
docker buildx build \
    --platform windows/amd64 \
    --tag customs-fetcher-builder:latest \
    --load \
    -f Dockerfile.windows .

# Tạo container và copy files
echo "Copying build artifacts..."
container_id=$(docker create customs-fetcher-builder:latest)
docker cp $container_id:/app/dist/. ./output/
docker rm $container_id

# Dọn dẹp
echo "Cleaning up..."
docker buildx rm windows-builder

echo "=== Build hoàn tất ==="
echo "Kiểm tra thư mục output/ để lấy file exe"
