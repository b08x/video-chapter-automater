Integration & Unification
Task 1.1: Integrate Video Pre-processing (Re-encoding & Audio Extraction)
Description: Migrate vlm_preprocessing.sh capabilities (video re-encoding to H.264/H.265 with GPU acceleration, audio extraction to MP3, or audio removal) into the VideoProcessor module as new methods.

1.1.1: Create preprocess_video method in VideoProcessor for re-encoding logic.
1.1.2: Implement GPU-accelerated FFmpeg commands (NVIDIA NVENC, Intel VAAPI, AMD AMF) using gpu_detection.py and subprocess.
1.1.3: Create extract_audio method in VideoProcessor for MP3 extraction.
1.1.4: Expose new pre-processing options via CLI arguments in cli.py.
1.1.5: Update setup_wizard.py and UserPreferences for configuring default re-encoding codecs, audio extraction, and output formats.
1.1.6: Ensure robust error handling for FFmpeg subprocess calls, including feedback for missing GPU support or incorrect FFmpeg builds.
Task 1.2: Integrate Advanced Scene Image Extraction
Description: Incorporate extract_scenes.py functionality (scene detection, representative image extraction, perceptual hashing for deduplication) into the VideoProcessor module.

1.2.1: Create extract_scene_images method in VideoProcessor using scenedetect and imagehash.
1.2.2: Share scene detection logic with existing chapter automation to avoid redundancy.
1.2.3: Implement image deduplication using perceptual hashing.
1.2.4: Expose as a new CLI command or option (e.g., --extract-scene-images).
1.2.5: Extend UserPreferences to configure image output paths, formats (JPEG, PNG), and deduplication thresholds.
1.2.6: Integrate progress reporting for image extraction into the Rich TUI.
Architectural Refinement & Best Practices
Task 2.1: Consolidate Core Video Processing Logic
Description: Review and refactor core.py, processor.py, and main.py to establish a single, canonical VideoProcessor implementation, removing redundancy and clarifying module responsibilities.

2.1.1: Analyze current usage of VideoChapterProcessor (core.py), EnhancedVideoProcessor (main.py), and VideoProcessor (processor.py).
2.1.2: Merge best practices and essential functionalities into processor.py's VideoProcessor.
2.1.3: Deprecate or remove redundant files/classes.
Task 2.2: Develop VLM/RAG Pipeline Orchestrator
Description: Create a higher-level Python module or extend cli.py to orchestrate a full VLM workflow, chaining video pre-processing, scene image/audio extraction, and transform_raw_video.py steps.

2.2.1: Design an orchestrate_vlm_pipeline function/class.
2.2.2: Define parameters for input video, desired outputs (re-encoded video, audio, scene images), and target VLM analysis JSON transformation.
2.2.3: Implement sequential calls to integrated VideoProcessor methods and transform_raw_video.py.
2.2.4: Provide TUI feedback for overall pipeline progress.
Usability & Robustness Enhancements
Task 3.1: Enhance External Dependency Management
Description: Improve setup_wizard and overall dependency handling for more robust and user-friendly installation of ffmpeg and scenedetect (and its OpenCV dependencies) across platforms.

3.1.1: Research platform-specific binary installers for FFmpeg.
3.1.2: Implement checks for FFmpeg's hardware acceleration capabilities (NVENC, VAAPI) and provide clear user guidance if unsupported.
3.1.3: Provide more explicit guidance for users on uv usage for Python dependencies.
Task 3.2: Improve GPU-Specific Error Reporting
Description: Refine error messages and logging for FFmpeg command failures due to GPU-related issues (e.g., missing drivers, incorrect FFmpeg build, incompatible hardware acceleration flags).

3.2.1: Parse FFmpeg stderr output more intelligently to identify common GPU acceleration errors.
3.2.2: Provide actionable advice to users based on detected errors.
