import sys
import os
import subprocess
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def test_config():
    print("--- [1] Testing app.config & Binaries ---")
    from app.config import FFMPEG_BIN, FFPROBE_BIN, WORKSPACE_DIR
    print(f"FFMPEG_BIN: {FFMPEG_BIN}")
    print(f"FFPROBE_BIN: {FFPROBE_BIN}")
    print(f"WORKSPACE_DIR: {WORKSPACE_DIR}")
    assert Path(FFMPEG_BIN).exists() or shutil.which(FFMPEG_BIN), "FFmpeg binary not found"
    print("✓ Config & Binaries: PASS")

def test_parser():
    print("\n--- [2] Testing app.services.parser_service ---")
    from app.services.parser_service import parse_timestamps_text

    sample_text = """
    Dưới đây là các đoạn được chọn:
    1. 00:00:05 - 00:00:15: Lời giới thiệu ban đầu
    Đoạn 2: [00:00:20,500] --> [00:00:35,200] - Phần thông báo giáo xứ
    3. 01:10 -> 01:45: Bài thánh ca mở màn
    02:00 to 02:30: Lời nguyện giáo dân
    Dòng ghi chú không có mốc thời gian
    """

    segments, ignored = parse_timestamps_text(sample_text)
    print(f"Parsed {len(segments)} segments:")
    for s in segments:
        print(f"  - #{s.id}: [{s.start_formatted} -> {s.end_formatted}] ({s.duration_sec}s) - {s.title}")
    print(f"Ignored lines: {ignored}")

    assert len(segments) == 4, f"Expected 4 segments, got {len(segments)}"
    assert segments[0].start_sec == 5.0 and segments[0].end_sec == 15.0
    assert "Lời giới thiệu ban đầu" in segments[0].title
    assert segments[1].start_sec == 20.5 and segments[1].end_sec == 35.2
    assert len(ignored) >= 1
    print("✓ Parser Service: PASS")

def test_ffmpeg_operations():
    print("\n--- [3] Testing FFmpeg Service (Synthetic Video, Audio Extract, Stream Copy, Zip) ---")
    from app.config import FFMPEG_BIN, UPLOADS_DIR, AUDIO_DIR, SEGMENTS_DIR, PACKAGES_DIR
    from app.services.ffmpeg_service import (
        get_media_info,
        extract_audio_16k,
        trim_video_stream_copy,
        create_zip_archive
    )

    # 1. Create a 5-second synthetic test video with audio using FFmpeg
    test_video = UPLOADS_DIR / "test_synth.mp4"
    print(f"Generating test video: {test_video} ...")
    cmd = [
        FFMPEG_BIN,
        "-f", "lavfi", "-i", "testsrc=duration=5:size=640x360:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
        "-c:v", "libx264", "-c:a", "aac",
        str(test_video),
        "-y"
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    assert test_video.exists() and test_video.stat().st_size > 0

    # 2. Test get_media_info
    info = get_media_info(test_video)
    print(f"Video Info: Duration={info['duration']}s, Size={info['size']} bytes, Dim={info['width']}x{info['height']}")
    assert info["duration"] > 4.5

    # 3. Test extract_audio_16k
    test_audio = AUDIO_DIR / "test_synth.wav"
    extract_audio_16k(test_video, test_audio)
    assert test_audio.exists() and test_audio.stat().st_size > 0
    print(f"Extracted Audio: {test_audio.stat().st_size} bytes (16kHz Mono)")

    # 4. Test trim_video_stream_copy (Instant cut: 1.0s -> 3.5s)
    test_segment = SEGMENTS_DIR / "test_segment_1.mp4"
    trim_video_stream_copy(test_video, 1.0, 3.5, test_segment)
    assert test_segment.exists() and test_segment.stat().st_size > 0
    print(f"Stream Copy Trimmed Segment: {test_segment.stat().st_size} bytes")

    # 4b. Test trim_video_frame_accurate
    from app.services.ffmpeg_service import trim_video_frame_accurate
    test_segment_acc = SEGMENTS_DIR / "test_segment_acc.mp4"
    trim_video_frame_accurate(test_video, 1.0, 3.5, test_segment_acc)
    assert test_segment_acc.exists() and test_segment_acc.stat().st_size > 0
    print(f"Frame-Accurate Trimmed Segment: {test_segment_acc.stat().st_size} bytes")

    # 5. Test create_zip_archive
    test_zip = PACKAGES_DIR / "test_package.zip"
    create_zip_archive([test_segment, test_segment_acc], test_zip)
    assert test_zip.exists() and test_zip.stat().st_size > 0
    print(f"Zip Archive: {test_zip.stat().st_size} bytes")

    print("✓ FFmpeg Operations: PASS")

def test_fastapi_app():
    print("\n--- [4] Testing FastAPI App Initialization ---")
    from app.main import app
    routes = [route.path for route in app.routes]
    print(f"Registered routes: {routes}")
    assert "/" in routes
    assert "/api/upload" in routes
    assert "/api/transcribe" in routes
    assert "/api/tasks/{task_id}" in routes
    assert "/api/trim/preview" in routes
def test_whisper_service():
    print("\n--- [5] Testing faster-whisper Service & GPU Acceleration ---")
    from app.services.whisper_service import get_whisper_device, load_model, transcribe_audio
    from app.config import AUDIO_DIR
    
    device, compute = get_whisper_device()
    print(f"Detected Whisper device: {device} ({compute})")
    
    model, actual_device = load_model("tiny")
    print(f"Loaded model on actual device: {actual_device}")
    
    test_audio = AUDIO_DIR / "test_synth.wav"
    assert test_audio.exists()
    
    res = transcribe_audio(
        audio_path=test_audio,
        video_id="test_synth",
        model_size="tiny",
        initial_prompt="Ba-na-ba, Giê-xu Christ, Phao-lô",
        progress_callback=lambda pct, msg: None
    )
    assert "srt_file" in res and "vtt_file" in res
    print(f"Transcribed successfully! Generated: {res['srt_file']}, {res['vtt_file']}")
    print("✓ Whisper Service & Acceleration: PASS")

if __name__ == "__main__":
    import shutil
    try:
        test_config()
        test_parser()
        test_ffmpeg_operations()
        test_fastapi_app()
        test_whisper_service()
        print("\n==========================================")
        print("🎉 ALL TESTS PASSED SUCCESSFULLY! (100%)")
        print("==========================================")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
