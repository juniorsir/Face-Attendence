# Use Ubuntu 22.04 which has guaranteed precompiled python3-dlib
FROM ubuntu:22.04

# Prevent timezone and region prompts from hanging the build
ENV DEBIAN_FRONTEND=noninteractive

# 1. Install software-properties-common to manage repositories
# 2. Enable the 'universe' repository where dlib lives
# 3. Install pre-compiled Python, dlib, OpenCV, and NumPy
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository universe && \
    apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dlib \
    python3-numpy \
    python3-opencv \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files into the container
COPY . /app

# Install the remaining pure-Python packages via pip
# (Ubuntu 22.04 does not require the --break-system-packages flag)
RUN pip3 install --no-cache-dir -r requirements.txt

# Start the FastAPI application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
