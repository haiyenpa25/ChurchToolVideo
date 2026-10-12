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
