# Use Debian Bookworm which has precompiled python3-dlib
FROM debian:bookworm-slim

# Prevent interactive prompts during apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies, precompiled dlib, numpy, and opencv
# This bypasses the 8GB RAM C++ compilation completely!
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dlib \
    python3-numpy \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install pure-Python packages via pip
# --break-system-packages is required in Debian 12 (safe inside a Docker container)
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Start the FastAPI application
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}
