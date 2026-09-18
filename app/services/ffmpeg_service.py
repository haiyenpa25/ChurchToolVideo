import json
import logging
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import FFMPEG_BIN, FFPROBE_BIN

logger = logging.getLogger("ffmpeg_service")

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

def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Inspects video/audio metadata using ffprobe"""
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-show_entries", "format=duration,size,format_name:stream=width,height,codec_name,codec_type",
        "-of", "json",
        str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
            elif stream.get("codec_type") == "audio":
                has_audio = True

        return {
            "duration": duration,
            "duration_formatted": format_seconds_to_display(duration),
            "size": size,
            "width": width,
            "height": height,
            "has_audio": has_audio
        }
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
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
    Placing -i first ensures precise seek timestamps without keyframe zero-snap.
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
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
    Uses libx264 ultrafast with high quality (crf 20) and audio copy.
    Guarantees zero freeze frames at segment starts and crisp audio sync.
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN,
        "-i", str(input_video_path),
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-c:a", "copy",
        "-avoid_negative_ts", "make_zero",
        str(output_video_path),
        "-y"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
