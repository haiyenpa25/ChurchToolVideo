import json
import subprocess
import pytest
from app.config import FFMPEG_BIN, FFPROBE_BIN
from app.models.schemas import ShortClip, ClipPart, ShortsRenderOptions
from app.services import shorts_render_service as renderer
from app.services.captions_service import write_ass, clip_srt
from app.services.pacing_service import speech_segments


def transcript(*spans):
    """Words as (start, end) pairs, one sentence."""
    words = [{"w": f"từ{i}", "start": s, "end": e} for i, (s, e) in enumerate(spans)]
    return {"sentences": [{"id": "S0001", "start": spans[0][0], "end": spans[-1][1],
                           "text": " ".join(w["w"] for w in words), "words": words}]}


def test_long_pauses_are_cut_short_ones_kept():
    t = transcript((0.2, 0.6), (0.7, 1.4), (3.0, 3.6), (3.7, 4.5), (4.8, 5.6))
    spans = [(p.start_sec, p.end_sec) for p in speech_segments(ClipPart(start_sec=0, end_sec=6), t, gap=0.6)]
    # 1.4→3.0 is a 1.6s pause: cut. 4.5→4.8 is a breath: kept. Edges under the gap stay.
    assert spans == [(0.0, 1.58), (2.92, 6.0)]


def test_tiny_islands_merge_and_parts_without_words_stay_whole():
    t = transcript((0.0, 2.0), (3.0, 3.2), (5.0, 7.0))
    spans = [(p.start_sec, p.end_sec) for p in speech_segments(ClipPart(start_sec=0, end_sec=7), t, gap=0.6)]
    assert spans == [(0.0, 3.38), (4.92, 7.0)]
    part = ClipPart(start_sec=10, end_sec=20)
    assert speech_segments(part, transcript((0.0, 1.0))) == [part]
    assert speech_segments(part, None) == [part]


def test_clip_srt_follows_output_timeline():
    t = transcript((0.0, 1.0), (5.0, 6.0))
    srt = clip_srt([ClipPart(start_sec=0, end_sec=1.2), ClipPart(start_sec=4.9, end_sec=6.2)], [0, 1.2], t)
    assert "00:00:00,000 --> 00:00:01,000\ntừ0" in srt
    assert "00:00:01,300 --> 00:00:02,300\ntừ1" in srt


@pytest.mark.parametrize("style,position,expect", [
    ("box", "bottom", ",3,20,0,2,60,60,672,1"), ("yellow", "top", "&H0000E5FF"), ("outline", "middle", ",5,60,60,0,1")])
def test_caption_styles_and_positions(tmp_path, style, position, expect):
    write_ass(tmp_path / "c.ass", ClipPart(start_sec=0, end_sec=2), transcript((0.0, 1.0)), 1080, 1920,
              style=style, position=position)
    assert expect in (tmp_path / "c.ass").read_text(encoding="utf-8")


@pytest.mark.integration
def test_render_removes_silence_cleans_audio_and_writes_srt(tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=8", "-f", "lavfi", "-i", "sine=f=400:d=8",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(video)], capture_output=True, check=True)
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    t = transcript((0.0, 1.5), (5.0, 6.5))  # 3.5s pause in the middle
    clip = ShortClip(id=1, title="Nhịp nhanh", parts=[ClipPart(start_sec=0, end_sec=6.5)])
    output = renderer.render_short(video, clip, ShortsRenderOptions(encoder="x264", remove_silence=True, clean_audio=True,
                                   burn_subtitles=True, caption_style="box"), transcript=t)
    duration = float(json.loads(subprocess.run([FFPROBE_BIN, "-v", "error", "-show_format", "-of", "json", str(output)],
                                               capture_output=True, text=True, check=True).stdout)["format"]["duration"])
    assert duration == pytest.approx(3.26, abs=0.25)
    srt = output.with_suffix(".srt").read_text(encoding="utf-8")
    assert "00:00:01,747 --> 00:00:03,247\ntừ1" in srt


def test_pop_style_highlights_one_word_per_event(tmp_path):
    t = transcript((0.0, 0.4), (0.4, 0.8), (0.8, 1.2), (1.2, 1.6))
    write_ass(tmp_path / "p.ass", ClipPart(start_sec=0, end_sec=2), t, 1080, 1920, style="pop")
    text = (tmp_path / "p.ass").read_text(encoding="utf-8")
    events = [l for l in text.splitlines() if l.startswith("Dialogue")]
    # Four words become two balanced lines (2 + 2), one event per spoken word.
    assert len(events) == 4
    assert events[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.40") and r"{\fad(70,0)}" in events[0]
    assert r"\c&H00E5FF&" in events[1] and events[1].index("từ1") > events[1].index(r"\c&H00E5FF&")
    assert "Noto Sans,97," in text  # 9% of the frame width


def test_clip_crop_overrides_shared_crop(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(renderer, "video_filter", lambda options, crop_x=None, *a, **k: seen.append(options.crop_x) or "null")
    monkeypatch.setattr(renderer, "run_ffmpeg", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop")))
    monkeypatch.setattr(renderer, "get_media_info", lambda p: {"duration": 10, "width": 1920, "height": 1080, "has_audio": True})
    monkeypatch.setattr(renderer, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(renderer, "SHORTS_DIR", tmp_path / "shorts")
    video = tmp_path / "v.mp4"; video.write_bytes(b"")
    for crop, expected in ((0.0, 0.0), (None, 0.5)):
        with pytest.raises(RuntimeError):
            renderer.render_short(video, ShortClip(id=1, crop_x=crop, parts=[ClipPart(start_sec=0, end_sec=1)]),
                                  ShortsRenderOptions(encoder="x264", reframe="crop", crop_x=0.5))
        assert seen[-1] == expected


def test_every_caption_template_renders(tmp_path):
    from app.services.captions_service import CAPTION_TEMPLATES
    t = transcript((0.0, 0.4), (0.4, 0.8), (0.8, 1.2))
    for style in CAPTION_TEMPLATES:
        path = tmp_path / f"{style}.ass"
        assert write_ass(path, ClipPart(start_sec=0, end_sec=2), t, 1080, 1920, style=style), style
        text = path.read_text(encoding="utf-8")
        assert text.count("Style: Default,Noto Sans,") == 1
        if CAPTION_TEMPLATES[style].get("upper"):
            assert "TỪ0" in text
        if CAPTION_TEMPLATES[style]["highlight"] == "fill":
            assert r"{\kf" in text


def test_segments_are_laid_end_to_end_in_one_ass(tmp_path):
    t = transcript((0.0, 1.0), (10.0, 11.0))
    write_ass(tmp_path / "m.ass", [ClipPart(start_sec=0, end_sec=1.2), ClipPart(start_sec=9.9, end_sec=11.2)], t,
              offsets=[0, 1.2])
    events = [l for l in (tmp_path / "m.ass").read_text(encoding="utf-8").splitlines() if l.startswith("Dialogue")]
    assert events[0].startswith("Dialogue: 0,0:00:00.00,0:00:01.00") and events[1].startswith("Dialogue: 0,0:00:01.30,0:00:02.30")


def test_crop_window_is_cut_before_scaling_and_zooms():
    plain = renderer.video_filter(ShortsRenderOptions(reframe="crop"), source=(1920, 1080))
    assert plain.startswith("crop=606:1080:") and plain.index("crop=") < plain.index("scale=1080:1920")
    zoomed = renderer.video_filter(ShortsRenderOptions(reframe="crop", crop_zoom=2, crop_x=1, crop_y=0), source=(1920, 1080))
    assert zoomed.startswith("crop=302:540:x='(iw-ow)*(1.0)':y='(ih-oh)*(0.0)'")
    # Phone video into 16:9: the window spans the full width and slides vertically.
    assert renderer.video_filter(ShortsRenderOptions(aspect="16:9", reframe="crop"), source=(1080, 1920)).startswith("crop=1080:606:")


def test_caption_template_and_word_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import transcript_service
    monkeypatch.setattr(transcript_service, "SUBTITLES_DIR", tmp_path)
    data = {"video_id": "v1", "duration": 5, "sentences": [
        {"id": "S0001", "start": 0, "end": 1, "text": "Chúa Giê-xu", "words": [{"w": "Chúa", "start": 0, "end": 0.5}, {"w": "Giêsu", "start": 0.5, "end": 1}]},
        {"id": "S0002", "start": 1, "end": 3, "text": "yêu bạn", "words": []}]}
    (tmp_path / "v1.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    client = TestClient(app)
    templates = client.get("/api/shorts/caption-templates").json()
    assert {"pop", "neon", "box_white", "karaoke"} <= {t["id"] for t in templates}
    words = client.get("/api/shorts/caption-words/v1").json()
    assert [w["w"] for w in words[0]] == ["Chúa", "Giê-xu"]  # corrected spelling, Whisper timing
    assert words[1] == [{"w": "yêu", "start": 1.0, "end": 2.0}, {"w": "bạn", "start": 2.0, "end": 3.0}]
    assert client.get("/assets/fonts/NotoSans-Bold.ttf").status_code == 200
