# syntax=docker/dockerfile:1.4
# Multi-stage Dockerfile using uv for modern Python package management
# Supports both CPU-only and GPU-accelerated builds with optimal caching

###########################################
# Base Stage: Common system dependencies #
###########################################

# Use NVIDIA CUDA base image for GPU acceleration support
# Also works for CPU-only builds with runtime GPU detection
FROM nvidia/cuda:12.1.0-base-ubuntu22.04 AS base

# Build arguments for customization
ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.4.15
ARG BUILD_TYPE=production
ARG TARGETARCH=amd64

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PYTHON_DOWNLOADS=never

# Install system dependencies with optimized layer caching
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # Core Python and tools
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-venv \
    python3-pip \
    # Node.js and npm for chapconv
    nodejs \
    npm \
    # Media processing
    ffmpeg \
    # System utilities
    curl \
    wget \
    ca-certificates \
    # Build essentials for compiled packages
    build-essential \
    pkg-config \
    # GPU acceleration libraries
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # OpenCL support for Intel GPUs
    ocl-icd-opencl-dev \
    intel-opencl-icd \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python

# Install uv for fast Python package management
RUN --mount=type=cache,target=/tmp/uv-cache \
    pip install --no-cache-dir uv==${UV_VERSION}

# Create virtual environment with uv (much faster than python -m venv)
RUN uv venv /opt/venv --python=${PYTHON_VERSION}

# Install Node.js dependencies globally for chapconv
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --only=production && \
    npm install -g @mtillmann/chapconv@^0.0.3 && \
    which chapconv && chapconv --help

#################################
# Dependencies Stage: uv caching #
#################################

FROM base AS deps

# Copy dependency files for optimal Docker layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies with uv (significantly faster than pip)
# This layer will be cached unless dependencies change
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --frozen --no-install-project --extra docker

##################################
# Development Stage: Full tooling #
##################################

FROM deps AS development

# Install development dependencies
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --frozen --no-install-project --extra all

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 developer \
    && chown -R developer:developer /opt/venv

USER developer
WORKDIR /app

# Install project in development mode
COPY --chown=developer:developer . .
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000 \
    uv sync --frozen --extra all

# Development entrypoint supports hot reload and debugging
ENTRYPOINT ["python", "-m", "video_chapter_automater.cli"]
CMD ["--help"]

#####################################
# Production Stage: Minimal runtime  #
#####################################

FROM deps AS production

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && mkdir -p /app /data \
    && chown -R appuser:appuser /app /data /opt/venv

# Copy application source
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml /app/

# Switch to non-root user
USER appuser
WORKDIR /app

# Install the project (not in development mode)
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000 \
    uv pip install --no-deps -e .

# Health check to ensure the application starts correctly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -m video_chapter_automater.cli --version || exit 1

# Create volume mount points
VOLUME ["/data", "/output"]

# Production entrypoint
ENTRYPOINT ["python", "-m", "video_chapter_automater.cli"]
CMD ["--help"]

#################################
# GPU Test Stage: Hardware check #
#################################

FROM production AS gpu-test

# Copy GPU detection script
COPY --chown=appuser:appuser test_gpu.py .

# Test GPU capabilities on container start
RUN python test_gpu.py || echo "GPU test failed - CPU fallback available"

############################
# Final Stage Selection     #
############################

# Default to production, but can be overridden with --target
FROM production AS final
