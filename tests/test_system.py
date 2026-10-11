import json
import shutil
import subprocess
import time
import zipfile

import pytest

from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.services import ffmpeg_service as ffmpeg
from app.services.parser_service import parse_timestamps_text


def test_config():
    assert shutil.which(FFMPEG_BIN)
    assert shutil.which(FFPROBE_BIN)


def test_parser():
    segments, ignored = parse_timestamps_text("""
Ghi chú không có mốc thời gian
1. 00:00:05 - 00:00:15: Lời giới thiệu ban đầu
Đoạn 2: [00:00:20,500] --> [00:00:35,200] - Phần thông báo
3. 01:10 -> 01:45: Bài thánh ca
02:00 to 02:30: Lời nguyện
""")
    assert len(segments) == 4
    assert [(s.start_sec, s.end_sec) for s in segments] == [
        (5, 15), (20.5, 35.2), (70, 105), (120, 150)
    ]
    assert segments[0].title == "Lời giới thiệu ban đầu"
    assert len(ignored) == 1


def test_frame_accurate_command(monkeypatch, tmp_path):
    commands = []

    def run(cmd, **kwargs):
        commands.append(cmd)
        (tmp_path / "cut.mp4").write_bytes(b"video")
        return subprocess.CompletedProcess(cmd, 0, stderr="")

    monkeypatch.setattr(ffmpeg.subprocess, "run", run)
    ffmpeg.trim_video_frame_accurate(tmp_path / "input.mp4", 2400, 2402.5, tmp_path / "cut.mp4")
    cmd = commands[0]
    assert cmd.index("-ss") < cmd.index("-i")
    assert cmd[cmd.index("-t") + 1] == "2.5"
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "-to" not in cmd


@pytest.mark.parametrize("start,end", [(-1, 2), (2, 2), (3, 2)])
def test_invalid_cut(start, end, tmp_path):
    with pytest.raises(ValueError):
        ffmpeg.trim_video_frame_accurate(tmp_path / "input.mp4", start, end, tmp_path / "out.mp4")


def test_ffmpeg_failure(monkeypatch, tmp_path):
    def fail(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="encoder failed")

    monkeypatch.setattr(ffmpeg.subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="encoder failed"):
        ffmpeg.trim_video_frame_accurate(tmp_path / "input.mp4", 0, 1, tmp_path / "out.mp4")


@pytest.mark.integration
def test_ffmpeg_operations(tmp_path):
    video = tmp_path / "source.mp4"
    subprocess.run([
        FFMPEG_BIN, "-f", "lavfi", "-i", "testsrc2=duration=5:size=640x360:rate=24",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=5",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-y", str(video),
    ], capture_output=True, check=True)
    assert ffmpeg.get_media_info(video)["duration"] > 4.5
    audio = ffmpeg.extract_audio_16k(video, tmp_path / "audio.wav")
    assert audio.stat().st_size > 0
    copy = ffmpeg.trim_video_stream_copy(video, 1, 3.5, tmp_path / "copy.mp4")
    accurate = ffmpeg.trim_video_frame_accurate(video, 1, 3.5, tmp_path / "accurate.mp4")
    assert copy.stat().st_size > 0
    assert ffmpeg.get_media_info(accurate)["duration"] == pytest.approx(2.5, abs=0.1)
    probe = subprocess.run([
        FFPROBE_BIN, "-v", "error", "-show_streams", "-of", "json", str(accurate)
    ], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    assert {s["codec_name"] for s in streams} == {"h264", "aac"}
    archive = ffmpeg.create_zip_archive([copy, accurate], tmp_path / "package.zip")
    with zipfile.ZipFile(archive) as zipped:
        assert set(zipped.namelist()) == {"copy.mp4", "accurate.mp4"}

    # Repeat encoded packets to make a one-hour input without encoding an hour.
    long_video = tmp_path / "hour.mp4"
    subprocess.run([
        FFMPEG_BIN, "-stream_loop", "-1", "-i", str(video), "-t", "3600",
        "-c", "copy", "-y", str(long_video),
    ], capture_output=True, check=True)
    started = time.perf_counter()
    late_cut = ffmpeg.trim_video_frame_accurate(long_video, 2400, 2402.5, tmp_path / "late.mp4")
    elapsed = time.perf_counter() - started
    assert elapsed < 15, f"Late seek took {elapsed:.2f}s"
    print(f"40-minute seek on synthetic 640x360 input: {elapsed:.2f}s")
    assert ffmpeg.get_media_info(late_cut)["duration"] == pytest.approx(2.5, abs=0.1)


def test_fastapi_app():
    from app.main import app

    routes = {route.path for route in app.routes}
    assert {"/", "/api/upload", "/api/transcribe", "/api/tasks/{task_id}", "/api/trim/preview"} <= routes
