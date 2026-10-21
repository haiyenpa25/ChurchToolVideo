import json
from types import SimpleNamespace
import pytest
from app.services import ffmpeg_service, shorts_render_service as renderer
from app.models.schemas import ShortClip, ClipPart, ClipStyle, CoverBand, ShortsRenderOptions


@pytest.mark.parametrize("rotation", [90, -90, 270])
@pytest.mark.parametrize("side_data", [False, True])
def test_probe_reports_dimensions_after_rotation(monkeypatch, tmp_path, rotation, side_data):
    stream = {"codec_type": "video", "width": 1920, "height": 1080}
    stream.update({"side_data_list": [{"rotation": rotation}]} if side_data else {"tags": {"rotate": str(rotation)}})
    seen = []
    def run(cmd, **kwargs):
        seen.append(cmd)
        return SimpleNamespace(stdout=json.dumps({"streams": [stream], "format": {"duration": "1"}}))
    monkeypatch.setattr(ffmpeg_service.subprocess, "run", run)
    info = ffmpeg_service.get_media_info(tmp_path / "sample.mp4")
    assert (info["width"], info["height"]) == (1080, 1920)
    assert "rotation" in " ".join(seen[0])


def test_source_dimensions_are_even_for_captions_and_cover_band(tmp_path, monkeypatch):
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    monkeypatch.setattr(renderer, "get_media_info", lambda p: {"duration": 2, "width": 1081, "height": 1921, "has_audio": True})
    sizes, commands = [], []
    def ass(*args, **kwargs):
        sizes.append(args[3:5])
        return False
    def run(args, cwd, *extra):
        commands.append(args)
        (cwd / "final.mp4").write_bytes(b"video")
    monkeypatch.setattr(renderer, "write_ass", ass)
    monkeypatch.setattr(renderer, "run_ffmpeg", run)
    clip = ShortClip(id=1, title="Title", parts=[ClipPart(start_sec=0, end_sec=1)],
                     style=ClipStyle(band=CoverBand(mode="blur")))
    renderer.render_short(tmp_path / "source.mp4", clip, ShortsRenderOptions(aspect="source", encoder="x264", show_title=True))
    assert sizes == [(1080, 1920)]
    graph = commands[0][commands[0].index("-filter_complex") + 1]
    assert "crop=1080:" in graph


def test_get_media_info_caches_existing_file_until_modified(monkeypatch, tmp_path):
    video = tmp_path / "cached.mp4"
    video.write_bytes(b"video-v1")
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(stdout=json.dumps({"streams": [{"codec_type": "video", "width": 1280, "height": 720}], "format": {"duration": "5", "size": "8"}}))

    monkeypatch.setattr(ffmpeg_service.subprocess, "run", run)
    first = ffmpeg_service.get_media_info(video)
    second = ffmpeg_service.get_media_info(video)
    assert len(calls) == 1
    assert first == second
    video.write_bytes(b"video-v2-longer")
    ffmpeg_service.get_media_info(video)
    assert len(calls) == 2


def test_face_crop_positions_reuses_detection_across_aspects(monkeypatch, tmp_path):
    from app.services import reframe_service
    video = tmp_path / "speaker.mp4"
    video.write_bytes(b"video")
    scans = []

    def fake_detect(path_str, mtime_ns, start_sec, end_sec):
        scans.append((path_str, start_sec, end_sec))
        return ((0.0, 1920, 1080, 0.25), (1.0, 1920, 1080, 0.75))

    monkeypatch.setattr(reframe_service, "_detect_part_faces", reframe_service.lru_cache(maxsize=8)(fake_detect))
    part = ClipPart(start_sec=0, end_sec=2)
    pts_916, count_916 = reframe_service.face_crop_positions(video, part, aspect="9:16")
    pts_11, count_11 = reframe_service.face_crop_positions(video, part, aspect="1:1")
    assert len(scans) == 1
    assert count_916 == 2 and count_11 == 2
    assert pts_916 != pts_11


def test_refine_word_timestamps_clamps_long_leading_word():
    from app.services.whisper_service import refine_word_timestamps
    words = [{"w": "Chúa", "start": 0.0, "end": 3.2}, {"w": "yêu", "start": 3.2, "end": 3.5}]
    refined = refine_word_timestamps(words)
    assert refined[0]["start"] == 2.4
    assert refined[0]["end"] == 3.2
    assert refined[1] == words[1]


def test_summarize_project_strips_heavy_fields():
    from app.main import _summarize_project
    project = {
        "video_id": "sermon",
        "title": "Bài giảng",
        "raw_text": "A" * 5000,
        "clips": [{"id": 1, "title": "Clip 1", "parts": [{"start_sec": 0, "end_sec": 10, "words": [{"w": "Amen"}]}]}],
    }
    summary = _summarize_project(project, True)
    assert "raw_text" not in summary
    assert len(summary["clips"]) == 1
    assert "parts" not in summary["clips"][0]
    assert summary["video_available"] is True


def test_url_upload_validation_and_worker(monkeypatch, tmp_path):
    from pathlib import Path
    from app import main
    from app.models.schemas import UrlUploadRequest
    from app.services.project_service import ProjectStore
    from app.services.task_manager import TaskManager

    with pytest.raises(ValueError, match="http://"):
        UrlUploadRequest(url="file:///etc/passwd")
    with pytest.raises(ValueError, match="nội bộ"):
        UrlUploadRequest(url="http://127.0.0.1:8000/video.mp4")
    with pytest.raises(ValueError, match="nội bộ"):
        UrlUploadRequest(url="http://192.168.1.10/video.mp4")
    valid = UrlUploadRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert valid.url.startswith("https://")

    manager = TaskManager(tmp_path / "tasks.db")
    store = ProjectStore(tmp_path / "projects.db")
    monkeypatch.setattr(main, "task_manager", manager)
    monkeypatch.setattr(main, "project_store", store)
    monkeypatch.setattr(main, "TMP_DIR", tmp_path)
    monkeypatch.setattr(main, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(main, "_resolve_ytdlp_cmd", lambda: ["yt-dlp"])
    monkeypatch.setattr(
        main,
        "get_media_info",
        lambda p: {"duration": 60.0, "duration_formatted": "00:01:00", "width": 1920, "height": 1080, "has_audio": True},
    )

    def fake_run_media(cmd, err_msg):
        out_idx = cmd.index("-o") + 1
        staging_dir = Path(cmd[out_idx]).parent
        (staging_dir / "Bai_giang_Chua_Nhat.mp4").write_bytes(b"video-data")

    monkeypatch.setattr(ffmpeg_service, "run_media_command", fake_run_media)
    task_id = manager.create_task()
    main._url_upload_worker(task_id, valid.url)
    task = manager.get_task(task_id)
    assert task.status == "COMPLETED"
    assert task.result["original_name"] == "Bai_giang_Chua_Nhat.mp4"
    saved = store.get(task.result["video_id"])
    assert saved["title"] == "Bai giang Chua Nhat"


