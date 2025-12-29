
# Automatic Video Chapter Generator

This project provides a Python script and a Docker container to automate the process of adding chapter markers to a video file based on detected scene changes.

It uses a combination of three powerful tools:

- **PySceneDetect**: To analyze the video and find scene boundaries.

- **chapconv**: To convert the scene list into an FFmpeg-compatible chapter format.

- **FFmpeg**: To embed the chapter metadata into the video file without re-encoding.

The entire process is wrapped in a Python script and containerized with Docker for easy and repeatable execution. The Docker image is based on an NVIDIA CUDA image to enable GPU acceleration for FFmpeg and PySceneDetect where applicable.

## Prerequisites

- **Docker**: [Install Docker](https://docs.docker.com/get-docker/ "null")

- **NVIDIA GPU**: An NVIDIA graphics card with the latest drivers installed.

- **NVIDIA Container Toolkit**: Required to allow Docker containers to access the GPU. [Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html "null")

## Build the Docker Image

Navigate to the directory containing the `Dockerfile` and run the following command to build the image:

```shell
docker build -t video-chapter-generator .
```

## How to Run

1. Place your video file (e.g., `my_video.mp4`) in the same directory as the `Dockerfile`.

2. Run the Docker container using the command below. This command mounts the current directory into the `/app/` directory inside the container, allowing the script to access your video file.

```shell
docker run --rm -it --gpus all \
  -v "$(pwd)":/app \
  video-chapter-generator my_video.mp4
```

### Command Breakdown

- `docker run --rm -it`: Runs the container in interactive mode and automatically removes it when the process finishes.

- `--gpus all`: Grants the container access to all available NVIDIA GPUs.

- `-v "$(pwd)":/app`: Mounts the current host directory (`pwd`) to the `/app` directory inside the container. This is how the script reads your input file and writes the output file back to your machine.

- `video-chapter-generator`: The name of the image we built.

- `my_video.mp4`: The argument passed to the Python script, specifying the input video file.

### Output

The script will create a new video file in the same directory named `my_video_with_chapters.mp4`. This new file is a direct copy of the original video and audio streams but includes the new chapter markers.

## Configuration

VideoChapterAutomater stores user preferences in platform-specific, standards-compliant locations:

**Linux**: `~/.config/video-chapter-automater/config.json`
**macOS**: `~/Library/Application Support/video-chapter-automater/config.json`
**Windows**: `%APPDATA%\video-chapter-automater\config.json`

### XDG Base Directory Support

On all platforms, you can override the configuration directory by setting the `XDG_CONFIG_HOME` environment variable:

```bash
export XDG_CONFIG_HOME=/custom/path
vca --setup  # Config will be saved to /custom/path/video-chapter-automater/config.json
```

### Viewing Configuration

To view your current configuration:

```bash
vca --config
```

### First-Time Setup

Run the interactive setup wizard to configure your preferences:

```bash
vca --setup
```

**Note**: If you previously used an older version that stored configuration at `~/.video_chapter_automater/`, your old configuration will not be automatically migrated. You can either:
- Manually copy `config.json` to the new location
- Re-run the setup wizard with `vca --setup`
