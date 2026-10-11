import shutil
import math
import subprocess
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path

from app.config import FFMPEG_BIN, SHORTS_DIR, TMP_DIR
from app.models.schemas import ShortClip, ShortsRenderOptions
from app.services.ffmpeg_service import get_media_info, format_seconds_to_srt
from app.services.task_manager import serialized_gpu_job


def run_ffmpeg(args, cwd=None):
    try:
        return subprocess.run([FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y", *args],
                              cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Không thể render Short bằng FFmpeg: {(e.stderr or '')[-2000:]}") from e


@lru_cache(maxsize=1)
def nvenc_available():
    try:
        run_ffmpeg(["-f", "lavfi", "-i", "color=s=128x128:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"])
        return True
    except (RuntimeError, OSError):
        return False


def video_filter(options):
    if options.aspect == "source":
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1[v]"
    width, height = (1080, 1920) if options.aspect == "9:16" else (1920, 1080)
    if options.reframe == "crop":
        return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}:(iw-ow)*{options.crop_x}:0,setsar=1[v]")
    return (f"split[a][b];[a]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=20:5[bg];"
            f"[b]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]")


def write_part_subtitles(path, part, transcript):
    blocks = []
    for sentence in transcript.get("sentences", []):
        start = max(part.start_sec, sentence["start"])
        end = min(part.end_sec, sentence["end"])
        if end > start:
            blocks.append(f'{len(blocks)+1}\n{format_seconds_to_srt(start-part.start_sec)} --> '
                          f'{format_seconds_to_srt(end-part.start_sec)}\n{sentence["text"]}\n')
    path.write_text("\n".join(blocks), encoding="utf-8")
    return bool(blocks)


@serialized_gpu_job
def render_short(video_path, clip, options, progress_cb=None, transcript=None, task_id=None):
    clip = ShortClip.model_validate(clip)
    options = ShortsRenderOptions.model_validate(options)
    video_path = Path(video_path).resolve()
    meta = get_media_info(video_path)
    if not clip.parts or any(p.end_sec > meta["duration"] + 0.05 for p in clip.parts):
        raise ValueError("Clip trống hoặc mốc cắt vượt thời lượng video.")
    if options.burn_subtitles and transcript is None:
        raise ValueError("Cần transcript để chèn phụ đề.")
    # A fresh UUID isolates every clip/job; never use a title or user path here.
    root = TMP_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    output = SHORTS_DIR / f"{uuid.uuid4().hex}_clip{clip.id}.mp4"
    SHORTS_DIR.mkdir(parents=True, exist_ok=True)
    use_nvenc = options.encoder != "x264" and nvenc_available()
    if options.encoder == "nvenc" and not use_nvenc:
        raise ValueError("NVENC không khả dụng. Hãy chọn Tự động hoặc x264.")
    with tempfile.TemporaryDirectory(prefix=f"short-{task_id or 'local'}-", dir=root) as folder:
        work = Path(folder).resolve()
        if work.parent != root:
            raise ValueError("Thư mục tạm không hợp lệ.")

        def encode_parts(encoder):
            for i, part in enumerate(clip.parts):
                duration = part.end_sec - part.start_sec
                args = ["-ss", str(part.start_sec), "-i", str(video_path), "-t", str(duration)]
                if not meta["has_audio"]:
                    args = ["-ss", str(part.start_sec), "-i", str(video_path), "-f", "lavfi", "-i",
                            "anullsrc=r=48000:cl=stereo", "-t", str(duration)]
                filters = "[0:v]" + video_filter(options)
                if options.burn_subtitles and write_part_subtitles(work / "captions.srt", part, transcript):
                    filters += ";[v]subtitles=filename=captions.srt[out]"
                    label = "[out]"
                else:
                    label = "[v]"
                args += ["-filter_complex", filters, "-map", label, "-map", "0:a:0" if meta["has_audio"] else "1:a:0",
                         "-af", f"afade=t=in:d=0.04,afade=t=out:st={max(0, duration-0.04)}:d=0.04",
                         "-r", "30", "-c:v", encoder, "-pix_fmt", "yuv420p"]
                args += (["-preset", "p4", "-cq", "20"] if encoder == "h264_nvenc" else ["-preset", "veryfast", "-crf", "20"])
                args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                         "-video_track_timescale", "30000", f"part_{i}.mp4"]
                run_ffmpeg(args, work)
                if progress_cb:
                    progress_cb(int((i+1) / len(clip.parts) * 75), f"Đã render part {i+1}/{len(clip.parts)}")

        try:
            try:
                encode_parts("h264_nvenc" if use_nvenc else "libx264")
            except RuntimeError:
                if not use_nvenc or options.encoder != "auto":
                    raise
                if progress_cb:
                    progress_cb(0, "NVENC gặp lỗi, đang chuyển sang x264...")
                encode_parts("libx264")
            # AAC packet padding must not move the next video's first frame.
            (work / "list.txt").write_text("\n".join(
                f"file 'part_{i}.mp4'\nduration {math.ceil((p.end_sec-p.start_sec)*30)/30:.9f}"
                for i, p in enumerate(clip.parts)), encoding="utf-8")
            run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "merged.mp4"], work)
            if options.loudnorm:
                run_ffmpeg(["-i", "merged.mp4", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "final.mp4"], work)
            else:
                run_ffmpeg(["-i", "merged.mp4", "-c", "copy", "-movflags", "+faststart", "final.mp4"], work)
            shutil.copyfile(work / "final.mp4", output)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    if progress_cb:
        progress_cb(100, "Ghép Short hoàn tất")
    return output
