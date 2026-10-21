import json
import logging
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import FFMPEG_BIN, FFPROBE_BIN

logger = logging.getLogger("ffmpeg_service")


def run_media_command(cmd, output_path=None, timeout=3600):
    """Bound FFmpeg runtime and stop active worker processes on cancellation."""
    from app.services.task_manager import checkpoint, job_context
    process = None
    try:
        checkpoint()
        if not getattr(job_context, "manager", None):
            return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout,
                                  encoding="utf-8", errors="replace")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace")
        deadline = time.monotonic() + timeout
        while True:
            checkpoint()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, timeout)
            try:
                stdout, stderr = process.communicate(timeout=min(.2, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        checkpoint()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    except Exception:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        if output_path is not None:
            Path(output_path).unlink(missing_ok=True)
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stdout.close()
            process.stderr.close()

def format_seconds_to_srt(seconds: float) -> str:
    """Formats seconds into HH:MM:SS,mmm (SRT format)"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    remainder = total_ms % 3600000
    minutes = remainder // 60000
    remainder = remainder % 60000
    secs = remainder // 1000
    millis = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_seconds_to_display(seconds: float) -> str:
    """Formats seconds into HH:MM:SS or HH:MM:SS.mmm for friendly UI display"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    remainder = total_ms % 3600000
    minutes = remainder // 60000
    remainder = remainder % 60000
    secs = remainder // 1000
    millis = remainder % 1000
    if millis > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

_media_info_cache: Dict[tuple, Dict[str, Any]] = {}

def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Inspects video/audio metadata using ffprobe (cached by file path, mtime, and size)"""
    file_path = Path(file_path)
    cache_key = None
    if file_path.is_file():
        try:
            st = file_path.stat()
            cache_key = (str(file_path.resolve()), st.st_mtime_ns, st.st_size, id(subprocess.run))
            if cache_key in _media_info_cache:
                return dict(_media_info_cache[cache_key])
        except OSError:
            cache_key = None

    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-show_entries", "format=duration,size,format_name:stream=width,height,codec_name,codec_type:stream_tags=rotate:stream_side_data=rotation",
        "-of", "json",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(result.stdout)
        format_info = data.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        size = int(format_info.get("size", 0))

        width = None
        height = None
        has_audio = False
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = stream.get("width")
                height = stream.get("height")
                rotation = stream.get("tags", {}).get("rotate", 0)
                for side in stream.get("side_data_list", []):
                    if "rotation" in side:
                        rotation = side["rotation"]
                if abs(float(rotation)) % 180 == 90:
                    width, height = height, width
            elif stream.get("codec_type") == "audio":
                has_audio = True

        info = {
            "duration": duration,
            "duration_formatted": format_seconds_to_display(duration),
            "size": size,
            "width": width,
            "height": height,
            "has_audio": has_audio
        }
        if cache_key is not None:
            if len(_media_info_cache) >= 256:
                _media_info_cache.clear()
            _media_info_cache[cache_key] = dict(info)
        return info
    except Exception as e:
        logger.warning(f"Failed to probe media with ffprobe: {e}")
        return {
            "duration": 0.0,
            "duration_formatted": "00:00:00",
            "size": file_path.stat().st_size if file_path.exists() else 0,
            "width": None,
            "height": None,
            "has_audio": True
        }

def extract_audio_16k(video_path: Path, output_audio_path: Path) -> Path:
    """
    Extracts audio stream into 16kHz mono 16-bit PCM WAV.
    This is the exact recommended format for faster-whisper.
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-i", str(video_path),
        "-vn",
        "-af", "highpass=f=75,dynaudnorm=f=150:g=15",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path),
        "-y"
    ]
    try:
        proc = run_media_command(cmd, output_audio_path)
        if not output_audio_path.exists() or output_audio_path.stat().st_size == 0:
            raise RuntimeError("Tạo file audio thất bại, không có luồng âm thanh được ghi nhận.")
        return output_audio_path
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr or ""
        if "does not contain any stream" in err_msg or "Output file is empty" in err_msg:
            raise RuntimeError("Video này không có luồng âm thanh (hoặc âm thanh bị hỏng) nên không thể thực hiện bóc băng AI.")
        raise RuntimeError(f"FFmpeg extract audio error: {err_msg}")

def trim_video_stream_copy(
    input_video_path: Path,
    start_sec: float,
    end_sec: float,
    output_video_path: Path
) -> Path:
    """
    Trims a segment from input video using Stream Copy (-c copy).
    Instant processing (in milliseconds/seconds) without quality loss.
    Stream copy depends on keyframes; the beginning may freeze or appear black
    until a decodable keyframe. Use frame-accurate re-encoding for precise cuts.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-i", str(input_video_path),
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(output_video_path),
        "-y"
    ]
    try:
        proc = run_media_command(cmd, output_video_path)
        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            raise RuntimeError(f"Cắt video thất bại, file xuất ra rỗng: {proc.stderr}")
        return output_video_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg trim error: {e.stderr}")

def trim_video_frame_accurate(
    input_video_path: Path,
    start_sec: float,
    end_sec: float,
    output_video_path: Path
) -> Path:
    """
    Trims a segment from input video with frame-accurate re-encoding.
    Seeks before decoding, then re-encodes video (x264 CRF 20) and audio (AAC).
    FFmpeg's default accurate seek discards frames preceding the requested start.
    """
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError("Mốc cắt video không hợp lệ: cần 0 ≤ bắt đầu < kết thúc.")
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-ss", str(start_sec),
        "-i", str(input_video_path),
        "-t", str(end_sec - start_sec),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "160k",
        str(output_video_path),
        "-y"
    ]
    try:
        proc = run_media_command(cmd, output_video_path)
        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            raise RuntimeError(f"Cắt video frame-accurate thất bại, file rỗng: {proc.stderr}")
        return output_video_path
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg frame-accurate trim error: {e.stderr}")

def create_zip_archive(files: List[Path], output_zip_path: Path) -> Path:
    """Packs all video segments into a single .zip file"""
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in files:
            if file_path.exists():
                zip_file.write(file_path, arcname=file_path.name)
    return output_zip_path
