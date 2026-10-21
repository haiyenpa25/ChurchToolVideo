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


@pytest.mark.integration
def test_studio_pro_features_feathered_blur_logo_color_music_outro(sample_video, monkeypatch, tmp_path):
    from app.models.schemas import ClipStyle, CoverBand
    from app.services import music_service

    logo_id = "b" * 32
    music_id = "c" * 32
    outro_id = "d" * 32
    monkeypatch.setattr(renderer, "LOGOS_DIR", tmp_path)
    monkeypatch.setattr(music_service, "MUSIC_DIR", tmp_path)
    monkeypatch.setattr(music_service, "OUTROS_DIR", tmp_path)

    # Create sample logo PNG, sample music (.audio), and sample outro (.mp4)
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "color=c=gold:s=64x64",
                    "-frames:v", "1", str(tmp_path / f"{logo_id}.png")], capture_output=True, check=True)
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "sine=f=220:d=4",
                    "-f", "mp3", "-c:a", "libmp3lame", str(tmp_path / f"{music_id}.audio")], capture_output=True, check=True)
    subprocess.run([FFMPEG_BIN, "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=24:d=1",
                    "-f", "lavfi", "-i", "sine=f=520:d=1", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(tmp_path / f"{outro_id}.mp4")], capture_output=True, check=True)

    style = ClipStyle(
        template="sacred_dialog",
        caption_y=0.78,
        band=CoverBand(mode="blur", y=0.67, h=0.33, color="#0F172A", opacity=0.92, feather=0.38, blur_strength=16),
    )
    clip = ShortClip(id=1, title="Án điển Chúa", parts=[ClipPart(start_sec=0, end_sec=1.2)], style=style)
    opts = ShortsRenderOptions(
        encoder="x264",
        burn_subtitles=False,
        loudnorm=False,
        logo_id=logo_id,
        logo_scale=0.18,
        logo_x=0.06,
        logo_y=0.04,
        logo_opacity=0.85,
        brightness=0.05,
        contrast=1.08,
        saturation=1.12,
        music_id=music_id,
        music_start=0.5,
        music_end=2.5,
        music_fade_in=0.4,
        music_fade_out=0.4,
        music_volume=0.25,
        outro_id=outro_id,
    )
    output = renderer.render_short(sample_video, clip, opts)
    data = json.loads(subprocess.run(
        [FFPROBE_BIN, "-v", "error", "-show_format", "-of", "json", str(output)],
        capture_output=True, text=True, check=True,
    ).stdout)
    # 1.2s clip + 1.0s outro = ~2.2s
    assert float(data["format"]["duration"]) == pytest.approx(2.2, abs=0.35)


def test_poster_title_card_and_hide_subs(tmp_path):
    from app.models.schemas import CaptionWord, ClipStyle
    from app.services.captions_service import write_ass

    words = [
        CaptionWord(w="Lời", start=0.2, end=0.8, s=0, hook=False),
        CaptionWord(w="mở", start=0.8, end=1.4, s=0, hook=False),
        CaptionWord(w="đầu", start=1.4, end=2.0, s=0, hook=False),
        CaptionWord(w="Chúa", start=3.6, end=4.2, s=1, hook=False),
        CaptionWord(w="chăn", start=4.2, end=4.8, s=1, hook=False),
        CaptionWord(w="giữ", start=4.8, end=5.4, s=1, hook=False),
    ]
    part = ClipPart(start_sec=0.0, end_sec=6.0, words=words)
    style = ClipStyle(
        title_show=True,
        title_template="poster_left",
        title_font="bevietnam",
        title_size=1.0,
        title_y=0.62,
        title_seconds=3.0,
        title_speaker="HOÀNG NAM TIẾN",
        title_badge="HAVE A SIP",
        title_accent="#4ADE80",
        title_hide_subs=True,
    )
    ass_path = tmp_path / "poster.ass"
    ok = write_ass(
        ass_path,
        [part],
        transcript={"sentences": []},
        width=1080,
        height=1920,
        offsets=[0.0],
        words=[words],
        clip_style=style,
        title="*GIÓ* TẦNG NÀO | GẶP *MÂY* TẦNG ĐÓ",
        captions=True,
    )
    assert ok is True
    content = ass_path.read_text(encoding="utf-8")
    # Title style is left-aligned (alignment=7) and TitleBadge style is top-right (alignment=9)
    assert "Style: Title,Be Vietnam Pro," in content
    assert "Style: TitleBadge,Be Vietnam Pro," in content
    assert r"{\c&H80DE4A&}GIÓ{\c&HFFFFFF&} TẦNG NÀO\NGẶP {\c&H80DE4A&}MÂY{\c&HFFFFFF&} TẦNG ĐÓ" in content
    assert "HOÀNG NAM TIẾN" in content
    assert "HAVE A SIP" in content
    # Because title_hide_subs=True and title_seconds=3.0, words at 0.2..2.0s are suppressed, while words at 3.6..5.4s are kept
    assert "Lời" not in content
    assert "Chúa" in content

    for tpl in ("editorial_bar", "gold_frame", "modern_card", "banner_split", "classic"):
        style_tpl = style.model_copy(update={"title_template": tpl})
        tpl_path = tmp_path / f"title_{tpl}.ass"
        assert write_ass(
            tpl_path,
            [part],
            transcript={"sentences": []},
            width=1080,
            height=1920,
            offsets=[0.0],
            words=[words],
            clip_style=style_tpl,
            title="*CHỦ ĐỀ* TRỌNG TÂM | GẶP *Ý HAY*",
            captions=True,
        )
        tpl_text = tpl_path.read_text(encoding="utf-8")
        assert "HOÀNG NAM TIẾN" in tpl_text
        assert "HAVE A SIP" in tpl_text



