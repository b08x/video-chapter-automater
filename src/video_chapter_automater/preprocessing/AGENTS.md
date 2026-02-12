# PREPROCESSING KNOWLEDGE BASE

**Generated:** 2026-02-12

## OVERVIEW
Core modular operations for video encoding, audio extraction, and scene detection with pluggable strategies.

## STRUCTURE
```
preprocessing/
├── base.py            # Interfaces (PreprocessingOperation)
├── strategies/        # Logic plug-ins
│   ├── codec_strategies.py # FFmpeg encoding
│   └── hash_strategies.py  # Image deduplication
├── video_encoder.py   # GPU/CPU orchestration
├── audio_extractor.py # FFmpeg audio tools
└── scene_extractor.py # Scene detection pipeline
```

## WHERE TO LOOK
| Component | File | Role |
|-----------|------|------|
| Video Encoding | `video_encoder.py` | GPU detection + fallback logic |
| Scene Detection | `scene_extractor.py` | PySceneDetect + Perceptual Hash |
| Audio Extraction | `audio_extractor.py` | WAV/Mono speech optimization |
| Hash Strategies | `hash_strategies.py` | pHash/dHash/wHash algorithms |

## CONVENTIONS
- **Strategy Pattern**: Always implement new codecs or hash algorithms as strategies in `strategies/`.
- **GPU-First**: Attempt hardware acceleration (Nvenc, VAAPI, QSV) before falling back.
- **Interactive Fallback**: When GPU fails, `video_encoder` MUST prompt user before retrying on CPU.
- **Result Objects**: Every operation must return a `PreprocessingResult` defined in `base.py`.

## ANTI-PATTERNS
- **Silent Degradation**: Never fallback to CPU without user approval (prevents performance surprises).
- **Direct Subprocess**: Avoid raw `subprocess.run`. Use `Processor` helpers or ensure robust error capture.
- **Redundant Logic**: Do not hardcode FFmpeg flags. Extract to `CodecStrategy.get_ffmpeg_args()`.

## NOTES
- Deduplication threshold defaults to 5 (Hamming distance).
- Audio extraction defaults to 16kHz Mono (Whisper-optimized).
