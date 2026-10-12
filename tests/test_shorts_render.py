import json
import subprocess
import pytest
from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.models.schemas import ShortClip, ClipPart, ShortsRenderOptions
from app.services import shorts_render_service as renderer


@pytest.fixture
def sample_video(tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=8",
                    "-f", "lavfi", "-i", "sine=f=400:d=8", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(video)], capture_output=True, check=True)
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    return video


@pytest.mark.integration
def test_three_part_vertical_render(sample_video):
    clip = ShortClip(id=1, title="Đức tin", parts=[ClipPart(start_sec=s, end_sec=s+0.8) for s in (0, 3, 6)])
    output = renderer.render_short(sample_video, clip, ShortsRenderOptions(encoder="x264", burn_subtitles=False))
    data = json.loads(subprocess.run([FFPROBE_BIN, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)],
                                   capture_output=True, text=True, check=True).stdout)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio = next(s for s in data["streams"] if s["codec_type"] == "audio")
    assert (video["width"], video["height"], video["codec_name"], video["r_frame_rate"]) == (1080, 1920, "h264", "30/1")
    assert (audio["codec_name"], audio["sample_rate"]) == ("aac", "48000")
    assert float(data["format"]["duration"]) == pytest.approx(2.4, abs=0.3)
    assert not list(renderer.TMP_DIR.iterdir())
    subprocess.run([FFMPEG_BIN, "-v", "error", "-i", str(output), "-f", "null", "-"], capture_output=True, check=True)


def test_render_failure_cleans_temp(sample_video, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("render error")
    monkeypatch.setattr(renderer, "run_ffmpeg", fail)
    clip = ShortClip(id=1, parts=[ClipPart(start_sec=0, end_sec=1)])
    with pytest.raises(RuntimeError, match="render error"):
        renderer.render_short(sample_video, clip, ShortsRenderOptions(encoder="x264", burn_subtitles=False))
    assert not list(renderer.TMP_DIR.iterdir())
    assert not list(renderer.SHORTS_DIR.iterdir())


@pytest.mark.integration
def test_vietnamese_captions_title_logo(sample_video, monkeypatch, tmp_path):
    logo_id = "a" * 32
    monkeypatch.setattr(renderer, "LOGOS_DIR", tmp_path)
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "color=c=blue:s=32x32",
                    "-frames:v", "1", str(tmp_path / f"{logo_id}.png")], capture_output=True, check=True)
    words = [{"w": word, "start": i*0.3, "end": (i+1)*0.3}
             for i, word in enumerate("Chúa yêu thương hỡi người ệ ữ ỡ".split())]
    clip = ShortClip(id=1, title="Đức Chúa Trời yêu thương", parts=[ClipPart(start_sec=0, end_sec=2.4)])
    output = renderer.render_short(sample_video, clip,
        ShortsRenderOptions(encoder="x264", burn_subtitles=True, karaoke=True, show_title=True, logo_id=logo_id),
        transcript={"sentences": [{"words": words}]})
    screenshot = tmp_path / "vietnamese.png"
    subprocess.run([FFMPEG_BIN, "-y", "-ss", "1.9", "-i", str(output), "-frames:v", "1", str(screenshot)],
                   capture_output=True, check=True)
    assert screenshot.stat().st_size > 0
    print(f"Vietnamese QA screenshot: {screenshot}")


def test_auto_face_crop_falls_back_on_no_faces(sample_video):
    from app.services.reframe_service import face_crop_positions
    part=ClipPart(start_sec=0,end_sec=1)
    points,count=face_crop_positions(sample_video,part,fallback=.3)
    assert count==0 and points[0][1]==.3
    output=renderer.render_short(sample_video,ShortClip(id=1,parts=[part]),
        ShortsRenderOptions(encoder="x264",reframe="crop",auto_reframe=True,burn_subtitles=False,loudnorm=False))
    assert output.stat().st_size>0


def test_dynamic_crop_expression_renders(sample_video, monkeypatch):
    from app.services import reframe_service
    monkeypatch.setattr(reframe_service,"face_crop_positions",lambda *args:[[(0,.1),(.4,.9)],2])
    output=renderer.render_short(sample_video,ShortClip(id=1,parts=[ClipPart(start_sec=0,end_sec=.8)]),
        ShortsRenderOptions(encoder="x264",reframe="crop",auto_reframe=True,burn_subtitles=False,loudnorm=False))
    assert output.stat().st_size>0


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["color", "blur"])
def test_cover_band_and_entrance_animations_render(sample_video, mode, tmp_path):
    from app.models.schemas import ClipStyle, CoverBand
    words = [{"w": w, "start": i*0.4, "end": (i+1)*0.4, "s": 0, "hook": i < 2}
             for i, w in enumerate("Muối của đất là bản tính".split())]
    style = ClipStyle(template="purple_box", hook_template="fire", font="anton", animation="slide", box="dark",
                      caption_y=0.86, band=CoverBand(mode=mode, y=0.8, h=0.12, color="#101010", opacity=0.9))
    clip = ShortClip(id=1, title="Muối của đất", parts=[ClipPart(start_sec=0, end_sec=2.4, words=words)], style=style)
    output = renderer.render_short(sample_video, clip, ShortsRenderOptions(encoder="x264", burn_subtitles=True,
                                   show_title=True), transcript={"sentences": []})
    frame = tmp_path / f"band-{mode}.png"
    subprocess.run([FFMPEG_BIN, "-y", "-ss", "1.0", "-i", str(output), "-frames:v", "1", str(frame)],
                   capture_output=True, check=True)
    assert frame.stat().st_size > 0
